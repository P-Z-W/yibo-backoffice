"""Database-backed operating-analysis APIs."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission, user_has_role
from app.db.session import get_db
from app.models.analytics import (
    AnalyticsDetailRow,
    AnalyticsImportBatch,
    BusinessEvent,
    MetricDefinition,
    MonthlyMetric,
    MonthlyReview,
)
from app.models.operation_record import (
    CustomerChangeRecord,
    CustomerServiceRecord,
    ShortVideoRecord,
    ValueAddedRecord,
)
from app.models.supplier import SupplierChange
from app.models.user import User
from app.schemas.operations import (
    MonthlyAnalyticsInput,
    MonthlyAnalyticsStatusInput,
    ShippingExportInput,
    ShippingRemarkInput,
    StaffingAnalysisInput,
    StaffingInputsInput,
)
from app.services.analytics_import import (
    DATASET_DEFINITIONS,
    MAX_UPLOAD_BYTES,
    STAFFING_COLUMNS,
    STAFFING_INPUT_COLUMNS,
    build_detail_export,
    build_shipping_export,
    build_shipping_template,
    build_staffing_template,
    build_template,
    find_column,
    get_definition,
    number,
    parse_workbook,
    public_definitions,
    summarize_rows,
)
from app.services.analytics_sources import (
    RETURN_COLUMNS,
    SHIPPING_COLUMNS,
    fetch_return_items,
    fetch_shipping_orders,
)
from app.services.audit import add_audit_log

router = APIRouter(prefix="/analytics", tags=["经营分析"])

SHIPPING_SYSTEM_WINDOW_MONTHS = 3
BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
STAFFING_DEFAULT_TEAMS = ("发货组", "售后组")

SOURCE_LABELS = {
    "migration": "历史迁入",
    "manual": "系统手工录入",
    "excel": "Excel 上传",
    "system": "系统自动取数",
    "supplier_module": "供应商管理",
    "operation_module": "客户与运营管理",
}

SUPPLIER_DETAIL_COLUMNS = [
    "供应商名称",
    "供应商联系人",
    "联系电话",
    "联系地址",
    "合作时间",
    "常用产品类型",
    "备注",
]

OPERATION_DETAIL_CONFIGS = {
    "customer_changes": {
        "model": CustomerChangeRecord,
        "columns": ["变化类型", "发生时间", "客户名称", "来源渠道", "数量", "备注"],
        "fields": [
            "change_type",
            "occurred_at",
            "customer_name",
            "source_channel",
            "quantity",
            "note",
        ],
        "source_name": "客户管理模块",
    },
    "service_issues": {
        "model": CustomerServiceRecord,
        "columns": [
            "团队名",
            "投诉大类",
            "问题详细描述",
            "核实原因",
            "责任归属",
            "整改措施",
            "状态",
        ],
        "fields": [
            "team_name",
            "complaint_category",
            "issue_description",
            "verified_cause",
            "responsibility",
            "corrective_action",
            "status",
        ],
        "source_name": "客户服务管理模块",
    },
    "value_added": {
        "model": ValueAddedRecord,
        "columns": ["团队ID", "团队名称", "服务编码", "服务名称", "服务分组", "数量"],
        "fields": [
            "team_id",
            "team_name",
            "service_code",
            "service_name",
            "service_group",
            "quantity",
        ],
        "source_name": "增值服务模块",
    },
    "short_video": {
        "model": ShortVideoRecord,
        "columns": ["短视频数量", "短视频类型", "负责人", "备注"],
        "fields": ["video_count", "video_type", "owner", "note"],
        "source_name": "短视频管理模块",
    },
}


def month_date(month: str) -> date:
    try:
        return date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="月份格式必须为 YYYY-MM") from exc


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def operation_month_condition(dataset_type: str, model, selected: date):
    if dataset_type != "customer_changes":
        return model.month == selected
    start = datetime.combine(selected, datetime.min.time())
    end = datetime.combine(shift_month(selected, 1), datetime.min.time())
    return or_(
        and_(
            model.occurred_at.is_not(None),
            model.occurred_at >= start,
            model.occurred_at < end,
        ),
        and_(model.occurred_at.is_(None), model.month == selected),
    )


def current_business_month() -> date:
    today = datetime.now(BUSINESS_TIMEZONE).date()
    return date(today.year, today.month, 1)


def shipping_snapshot_state(selected: date) -> dict[str, object]:
    current = current_business_month()
    window_start = shift_month(current, -(SHIPPING_SYSTEM_WINDOW_MONTHS - 1))
    if selected > current:
        state = "future"
        label = "未来月份"
        hint = "未来月份暂不允许系统取数"
        can_system_sync = False
    elif selected < window_start:
        state = "historical"
        label = "历史快照"
        hint = "已超出滚动三个月窗口，系统取数不会再覆盖该月数据"
        can_system_sync = False
    elif selected == current:
        state = "current"
        label = "当月数据"
        hint = "当前月份允许按月重新系统取数"
        can_system_sync = True
    else:
        state = "review"
        label = "月度复核"
        hint = "处于滚动三个月窗口内，允许重新系统取数"
        can_system_sync = True
    return {
        "state": state,
        "label": label,
        "hint": hint,
        "can_system_sync": can_system_sync,
        "window_start": window_start.strftime("%Y-%m"),
        "window_end": current.strftime("%Y-%m"),
    }


def ensure_shipping_system_sync_allowed(selected: date) -> dict[str, object]:
    snapshot = shipping_snapshot_state(selected)
    if snapshot["can_system_sync"]:
        return snapshot
    if snapshot["state"] == "historical":
        raise HTTPException(
            status_code=409,
            detail="该月份已进入历史快照，不再允许系统取数覆盖",
        )
    raise HTTPException(status_code=409, detail="未来月份暂不允许系统取数")


def ensure_month_editable(db: Session, selected: date) -> None:
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is not None and review.status == "archived":
        raise HTTPException(status_code=409, detail="该月份已归档，请先重新开启后再修改")


def detail_definition(dataset_type: str):
    try:
        return get_definition(dataset_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def detail_row_values(
    dataset_type: str,
    payload: dict[str, object],
    dataset_total: Decimal | None = None,
) -> dict[str, object]:
    if dataset_type == "shipping_orders":
        values = {column: payload.get(column) for column in SHIPPING_COLUMNS}
        count = number(payload.get("发货单量")) or Decimal("0")
        values["数据发货占比"] = (
            float(round(count / dataset_total * 100, 2))
            if dataset_total and dataset_total > 0
            else 0
        )
        values["备注"] = str(payload.get("备注") or "")
        return values
    if dataset_type == "return_items":
        values = {column: payload.get(column) for column in RETURN_COLUMNS}
        component_columns = ("处理退货件数", "拦截件扣费件数", "异常件扣费件数")
        component_values = [number(payload.get(column)) for column in component_columns]
        has_components = any(value is not None for value in component_values)
        if has_components:
            total = sum(
                (value for value in component_values if value is not None), Decimal("0")
            )
        else:
            total = (
                number(payload.get("退货件数合计"))
                or number(payload.get("退货件数"))
                or number(payload.get("退件件数"))
                or Decimal("0")
            )
        for column, value in zip(component_columns, component_values, strict=True):
            values[column] = float(value) if value is not None else None
        values["退货件数合计"] = float(total)
        values["数据退货占比"] = (
            float(round(total / dataset_total * 100, 2))
            if dataset_total and dataset_total > 0
            else 0
        )
        return values
    return payload


def read_excel_upload(file: UploadFile) -> tuple[str, bytes]:
    original_name = Path(file.filename or "经营分析分表.xlsx").name
    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    return original_name, contents


def parse_excel_upload(dataset_type: str, file: UploadFile) -> tuple[str, dict[str, object]]:
    definition = detail_definition(dataset_type)
    original_name, contents = read_excel_upload(file)
    try:
        parsed = parse_workbook(original_name, contents, definition)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return original_name, parsed


def active_detail_payloads(
    db: Session, dataset_type: str, selected: date
) -> list[dict[str, object]]:
    return [
        row.payload
        for row in db.scalars(
            select(AnalyticsDetailRow)
            .join(AnalyticsImportBatch)
            .where(
                AnalyticsImportBatch.dataset_type == dataset_type,
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
            .order_by(AnalyticsImportBatch.created_at, AnalyticsDetailRow.row_number)
        )
    ]


def detail_payload_total(
    payload: dict[str, object], total_columns: tuple[str, ...]
) -> Decimal:
    for column in total_columns:
        parsed = number(payload.get(column))
        if parsed is not None:
            return parsed
    if "退货件数合计" in total_columns:
        components = [
            number(payload.get(column))
            for column in ("处理退货件数", "拦截件扣费件数", "异常件扣费件数")
        ]
        if any(value is not None for value in components):
            return sum(
                (value for value in components if value is not None), Decimal("0")
            )
    return Decimal("0")


def system_source_guard(
    db: Session,
    selected: date,
    source_data: dict[str, object],
    *,
    dataset_type: str,
    total_columns: tuple[str, ...],
    metric_label: str,
) -> dict[str, object]:
    current_rows = active_detail_payloads(db, dataset_type, selected)
    current_total = sum(
        (detail_payload_total(row, total_columns) for row in current_rows),
        Decimal("0"),
    )
    new_total = Decimal(str(source_data.get("total") or 0))
    current_team_count = len(current_rows)
    new_team_count = int(source_data.get("row_count") or 0)
    warnings: list[str] = []
    blocking = False

    if current_total > 0 and new_total == 0:
        warnings.append(f"本次系统取数为 0，但当前月已有{metric_label}，已阻止覆盖")
        blocking = True
    elif current_total > 0 and new_total < current_total * Decimal("0.70"):
        decrease = (current_total - new_total) / current_total * 100
        warnings.append(f"{metric_label}较当前版本下降 {decrease:.1f}%，请核对后确认")

    if (
        current_team_count > 0
        and new_team_count > 0
        and new_team_count < current_team_count * 0.70
    ):
        warnings.append(
            f"团队数量由 {current_team_count} 个降至 {new_team_count} 个，请核对后确认"
        )

    return {
        "warnings": warnings,
        "blocking": blocking,
        "requires_confirmation": bool(warnings) and not blocking,
        "current_total": float(current_total),
        "current_team_count": current_team_count,
    }


def shipping_source_guard(
    db: Session,
    selected: date,
    source_data: dict[str, object],
) -> dict[str, object]:
    return system_source_guard(
        db,
        selected,
        source_data,
        dataset_type="shipping_orders",
        total_columns=("发货单量",),
        metric_label="发货单量",
    )


def return_source_guard(
    db: Session,
    selected: date,
    source_data: dict[str, object],
) -> dict[str, object]:
    return system_source_guard(
        db,
        selected,
        source_data,
        dataset_type="return_items",
        total_columns=("退货件数合计", "退货件数", "退件件数"),
        metric_label="退货件数合计",
    )


def normalized_team_name(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).casefold()


STAFFING_INPUT_ALIASES: dict[str, tuple[str, ...]] = {
    "小组": ("小组", "团队名称", "团队名"),
    "正式工人数": ("正式工人数", "正式人数"),
    "最优配置": ("最优配置", "最佳配置"),
    "人均月产出": ("人均月产出",),
    "最优人均产出": ("最优人均产出", "最低人均产出"),
    "综合分析": ("综合分析", "分析"),
}


def staffing_number(
    value: object,
    *,
    team_name: str,
    label: str,
    required: bool = False,
    integer: bool = False,
) -> int | float | None:
    parsed = number(value)
    if parsed is None:
        if required:
            raise HTTPException(status_code=422, detail=f"小组“{team_name}”缺少“{label}”")
        return None
    if parsed < 0:
        raise HTTPException(status_code=422, detail=f"小组“{team_name}”的“{label}”不能为负数")
    if integer:
        if parsed != parsed.to_integral_value():
            raise HTTPException(status_code=422, detail=f"小组“{team_name}”的“{label}”必须是整数")
        return int(parsed)
    return float(parsed)


def staffing_ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) / float(denominator), 6)


def calculate_staffing_row(
    inputs: dict[str, object], previous_output: float | None
) -> dict[str, object]:
    regular = inputs.get("正式工人数")
    optimal = inputs.get("最优配置")
    output = inputs.get("人均月产出")
    target_output = inputs.get("最优人均产出")
    configuration_gap = (
        round(float(regular) - float(optimal), 2)
        if regular is not None and optimal is not None
        else None
    )
    efficiency_gap = (
        round(float(output) - float(target_output), 2)
        if output is not None and target_output is not None
        else None
    )
    output_change = (
        round(float(output) - previous_output, 2)
        if output is not None and previous_output is not None
        else None
    )
    return {
        **inputs,
        "配置偏差": configuration_gap,
        "偏差比例": staffing_ratio(configuration_gap, regular),
        "效率差额": efficiency_gap,
        "效率差额占比": staffing_ratio(efficiency_gap, target_output),
        "人均月产出净变化": output_change,
        "人均月产出环比": staffing_ratio(output_change, previous_output),
    }


def staffing_template_team_names(db: Session, selected: date) -> list[str]:
    latest_month = db.scalar(
        select(func.max(AnalyticsImportBatch.month)).where(
            AnalyticsImportBatch.dataset_type == "staffing",
            AnalyticsImportBatch.month < selected,
            AnalyticsImportBatch.active.is_(True),
        )
    )
    if latest_month is None:
        return list(STAFFING_DEFAULT_TEAMS)

    payloads = db.scalars(
        select(AnalyticsDetailRow.payload)
        .join(AnalyticsImportBatch)
        .where(
            AnalyticsImportBatch.dataset_type == "staffing",
            AnalyticsImportBatch.month == latest_month,
            AnalyticsImportBatch.active.is_(True),
        )
        .order_by(AnalyticsDetailRow.row_number)
    ).all()
    names: list[str] = []
    normalized_names: set[str] = set()
    for row in payloads:
        name = str(row.get("小组") or "").strip()
        key = normalized_team_name(name)
        if key and key not in normalized_names:
            normalized_names.add(key)
            names.append(name)
    return names or list(STAFFING_DEFAULT_TEAMS)


def prepare_staffing_rows(
    db: Session,
    selected: date,
    uploaded_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not uploaded_rows:
        raise HTTPException(status_code=422, detail="Excel 中没有人员调整数据")
    column_map = {
        column: find_column(uploaded_rows, aliases)
        for column, aliases in STAFFING_INPUT_ALIASES.items()
    }
    if column_map["小组"] is None:
        raise HTTPException(status_code=422, detail="模板中缺少“小组”列")
    if column_map["正式工人数"] is None:
        raise HTTPException(status_code=422, detail="模板中缺少“正式工人数”列")

    current_rows = active_detail_payloads(db, "staffing", selected)
    current_by_team = {
        normalized_team_name(row.get("小组")): row
        for row in current_rows
        if normalized_team_name(row.get("小组"))
    }
    updates: dict[str, dict[str, object]] = {}
    for excel_row, raw in enumerate(uploaded_rows, start=2):
        team_name = str(raw.get(column_map["小组"] or "") or "").strip()
        key = normalized_team_name(team_name)
        if not key:
            raise HTTPException(status_code=422, detail=f"Excel 第 {excel_row} 行小组为空")
        if key in updates:
            raise HTTPException(status_code=422, detail=f"Excel 中小组重复：{team_name}")
        current = current_by_team.get(key, {})
        inputs: dict[str, object] = {"小组": team_name}
        for label in STAFFING_INPUT_COLUMNS[1:]:
            source_column = column_map[label]
            raw_value = raw.get(source_column) if source_column else current.get(label)
            if label in {"正式工人数", "最优配置"}:
                inputs[label] = staffing_number(
                    raw_value,
                    team_name=team_name,
                    label=label,
                    required=label == "正式工人数",
                )
            elif label in {"人均月产出", "最优人均产出"}:
                inputs[label] = staffing_number(
                    raw_value,
                    team_name=team_name,
                    label=label,
                )
            else:
                analysis = str(raw_value or "").strip()
                if len(analysis) > 5000:
                    raise HTTPException(
                        status_code=422,
                        detail=f"小组“{team_name}”的“综合分析”不能超过 5000 字",
                    )
                inputs[label] = analysis
        updates[key] = inputs

    previous_rows = active_detail_payloads(db, "staffing", previous_month(selected))
    previous_output_by_team = {
        normalized_team_name(row.get("小组")): float(value)
        for row in previous_rows
        if (value := number(row.get("人均月产出"))) is not None
    }
    merged_inputs: list[dict[str, object]] = []
    matched_count = 0
    for key, current in current_by_team.items():
        if key in updates:
            merged_inputs.append(updates.pop(key))
            matched_count += 1
        else:
            merged_inputs.append(
                {column: current.get(column) for column in STAFFING_INPUT_COLUMNS}
            )
    added_count = len(updates)
    merged_inputs.extend(updates.values())
    calculated = [
        calculate_staffing_row(
            inputs,
            previous_output_by_team.get(normalized_team_name(inputs.get("小组"))),
        )
        for inputs in merged_inputs
    ]
    return calculated, {
        "matched_count": matched_count,
        "added_count": added_count,
        "preserved_count": max(0, len(current_by_team) - matched_count),
        "unmatched_count": 0,
        "unmatched_teams": [],
    }


def merge_shipping_upload(
    current_rows: list[dict[str, object]],
    uploaded_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    team_column = find_column(uploaded_rows, ("团队名称", "团队名"))
    count_column = find_column(uploaded_rows, ("发货单量", "单量"))
    remark_column = find_column(uploaded_rows, ("备注", "说明"))
    if team_column is None:
        raise HTTPException(status_code=422, detail="模板中缺少“团队名称”列")
    if count_column is None and remark_column is None:
        raise HTTPException(status_code=422, detail="模板中至少需要“发货单量”或“备注”列")

    updates: dict[str, tuple[str, dict[str, object]]] = {}
    for index, row in enumerate(uploaded_rows, start=2):
        team_name = str(row.get(team_column) or "").strip()
        key = normalized_team_name(team_name)
        if not key:
            raise HTTPException(status_code=422, detail=f"Excel 第 {index} 行团队名称为空")
        if key in updates:
            raise HTTPException(status_code=422, detail=f"Excel 中团队名称重复：{team_name}")
        updates[key] = (team_name, row)

    current_keys: set[str] = set()
    merged_rows: list[dict[str, object]] = []
    matched: list[str] = []
    for current in current_rows:
        team_name = str(current.get("团队名称") or "").strip()
        key = normalized_team_name(team_name)
        if not key:
            continue
        if key in current_keys:
            raise HTTPException(status_code=409, detail=f"当前明细存在重名团队：{team_name}")
        current_keys.add(key)
        merged = {
            "团队名称": team_name,
            "发货单量": current.get("发货单量"),
            "数据发货占比": current.get("数据发货占比"),
            "备注": str(current.get("备注") or ""),
        }
        upload = updates.get(key)
        if upload is not None:
            _, uploaded = upload
            if count_column is not None and uploaded.get(count_column) not in (None, ""):
                count = number(uploaded.get(count_column))
                if count is None or count < 0 or count != count.to_integral_value():
                    raise HTTPException(
                        status_code=422,
                        detail=f"团队“{team_name}”的发货单量必须是非负整数",
                    )
                merged["发货单量"] = int(count)
            if remark_column is not None:
                remark = str(uploaded.get(remark_column) or "").strip()
                if len(remark) > 500:
                    raise HTTPException(
                        status_code=422,
                        detail=f"团队“{team_name}”的备注不能超过 500 字",
                    )
                merged["备注"] = remark
            matched.append(team_name)
        merged_rows.append(merged)

    unmatched = [name for key, (name, _) in updates.items() if key not in current_keys]
    return merged_rows, matched, unmatched


def filtered_team_records(
    db: Session,
    selected: date,
    dataset_type: str,
    total_columns: tuple[str, ...],
    search: str = "",
    sort_order: str = "",
):
    records = db.execute(
        select(AnalyticsDetailRow, AnalyticsImportBatch)
        .join(AnalyticsImportBatch)
        .where(
            AnalyticsImportBatch.dataset_type == dataset_type,
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
        .order_by(AnalyticsImportBatch.created_at.desc(), AnalyticsDetailRow.row_number)
    ).all()
    keyword = search.strip().casefold()
    if keyword:
        records = [
            item
            for item in records
            if keyword in str(item[0].payload.get("团队名称") or "").casefold()
        ]
    if sort_order:
        records.sort(
            key=lambda item: detail_payload_total(item[0].payload, total_columns),
            reverse=sort_order == "desc",
        )
    return records


def filtered_shipping_records(
    db: Session,
    selected: date,
    search: str = "",
    sort_order: str = "",
):
    return filtered_team_records(
        db,
        selected,
        "shipping_orders",
        ("发货单量",),
        search,
        sort_order,
    )


def filtered_return_records(
    db: Session,
    selected: date,
    search: str = "",
    sort_order: str = "",
):
    return filtered_team_records(
        db,
        selected,
        "return_items",
        ("退货件数合计", "退货件数", "退件件数"),
        search,
        sort_order,
    )


def supplier_change_details(
    db: Session,
    selected: date,
    month: str,
    page: int,
    size: int,
) -> dict[str, object]:
    definition = detail_definition("supplier_changes")
    changes = db.scalars(
        select(SupplierChange)
        .where(SupplierChange.change_month == selected)
        .order_by(SupplierChange.created_at.desc(), SupplierChange.id.desc())
    ).all()
    latest_by_supplier: dict[int, SupplierChange] = {}
    for change in changes:
        latest_by_supplier.setdefault(change.supplier_id, change)
    rows = list(latest_by_supplier.values())
    total = len(rows)
    page_rows = rows[(page - 1) * size : page * size]

    def values(change: SupplierChange) -> dict[str, object]:
        snapshot = change.snapshot
        return {
            "供应商名称": str(snapshot.get("name") or ""),
            "供应商联系人": str(snapshot.get("contact_name") or ""),
            "联系电话": str(snapshot.get("contact_phone") or ""),
            "联系地址": str(snapshot.get("address") or ""),
            "合作时间": str(snapshot.get("cooperation_start_date") or ""),
            "常用产品类型": str(snapshot.get("product_types") or ""),
            "备注": str(snapshot.get("note") or change.change_note or ""),
        }

    latest_at = rows[0].created_at if rows else None
    return {
        "dataset": {
            "code": definition.code,
            "name": definition.name,
            "description": definition.description,
            "summary_hint": definition.summary_hint,
        },
        "month": month,
        "columns": SUPPLIER_DETAIL_COLUMNS,
        "rows": [
            {
                "id": change.id,
                "row_number": index + (page - 1) * size,
                "values": values(change),
                "source_name": "供应商管理模块",
                "imported_at": change.created_at.isoformat() if change.created_at else "",
            }
            for index, change in enumerate(page_rows, start=1)
        ],
        "total": total,
        "page": page,
        "size": size,
        "summary": {"supplier_change": total},
        "batches": (
            [
                {
                    "original_name": "供应商管理模块",
                    "sheet_name": "供应商变更记录",
                    "mode": "system",
                    "row_count": total,
                    "imported_at": latest_at.isoformat() if latest_at else "",
                    "imported_by_name": "系统内维护",
                }
            ]
            if rows
            else []
        ),
    }


def operation_record_details(
    db: Session,
    dataset_type: str,
    selected: date,
    month: str,
    page: int,
    size: int,
) -> dict[str, object]:
    definition = detail_definition(dataset_type)
    config = OPERATION_DETAIL_CONFIGS[dataset_type]
    model = config["model"]
    columns = config["columns"]
    fields = config["fields"]
    source_name = config["source_name"]
    month_condition = operation_month_condition(dataset_type, model, selected)
    total = db.scalar(select(func.count(model.id)).where(month_condition)) or 0
    rows = db.scalars(
        select(model)
        .where(month_condition)
        .order_by(model.updated_at.desc(), model.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    latest = db.scalar(
        select(model)
        .where(month_condition)
        .order_by(model.updated_at.desc(), model.id.desc())
        .limit(1)
    )
    summary: dict[str, int] = {}
    if dataset_type == "customer_changes":
        code_by_type = {
            "新进": "new_customers",
            "流失": "lost_customers",
            "意向": "prospective_customers",
        }
        for change_type, quantity in db.execute(
            select(model.change_type, func.coalesce(func.sum(model.quantity), 0))
            .where(month_condition)
            .group_by(model.change_type)
        ):
            if change_type in code_by_type:
                summary[code_by_type[change_type]] = int(quantity)
    return {
        "dataset": {
            "code": definition.code,
            "name": definition.name,
            "description": definition.description,
            "summary_hint": definition.summary_hint,
        },
        "month": month,
        "columns": columns,
        "rows": [
            {
                "id": row.id,
                "row_number": index + (page - 1) * size,
                "values": {
                    column: value if (value := getattr(row, field)) is not None else ""
                    for column, field in zip(columns, fields)
                },
                "source_name": source_name,
                "imported_at": row.updated_at.isoformat() if row.updated_at else "",
            }
            for index, row in enumerate(rows, start=1)
        ],
        "total": total,
        "page": page,
        "size": size,
        "summary": summary,
        "batches": (
            [
                {
                    "original_name": source_name,
                    "sheet_name": definition.name,
                    "mode": "system",
                    "row_count": total,
                    "imported_at": latest.updated_at.isoformat() if latest else "",
                    "imported_by_name": "系统内维护",
                }
            ]
            if latest
            else []
        ),
    }


@router.get("")
def analytics(
    month: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> dict[str, object]:
    selected = month_date(month)
    previous = previous_month(selected)
    definitions = db.scalars(
        select(MetricDefinition)
        .where(MetricDefinition.enabled.is_(True))
        .order_by(MetricDefinition.sort_order)
    ).all()
    current_values = {
        row.metric_id: row
        for row in db.scalars(select(MonthlyMetric).where(MonthlyMetric.month == selected))
    }
    previous_values = {
        row.metric_id: row
        for row in db.scalars(select(MonthlyMetric).where(MonthlyMetric.month == previous))
    }
    active_batches = db.scalars(
        select(AnalyticsImportBatch)
        .where(
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
        .order_by(AnalyticsImportBatch.created_at.desc(), AnalyticsImportBatch.id.desc())
    ).all()
    supplier_change_count = db.scalar(
        select(func.count(func.distinct(SupplierChange.supplier_id))).where(
            SupplierChange.change_month == selected
        )
    ) or 0
    latest_supplier_change = db.scalar(
        select(SupplierChange)
        .where(SupplierChange.change_month == selected)
        .order_by(SupplierChange.created_at.desc(), SupplierChange.id.desc())
        .limit(1)
    )
    operation_module_status: dict[str, dict[str, object]] = {}
    for code, config in OPERATION_DETAIL_CONFIGS.items():
        model = config["model"]
        month_condition = operation_month_condition(code, model, selected)
        operation_module_status[code] = {
            "count": db.scalar(
                select(func.count(model.id)).where(month_condition)
            )
            or 0,
            "latest": db.scalar(
                select(model)
                .where(month_condition)
                .order_by(model.updated_at.desc(), model.id.desc())
                .limit(1)
            ),
            "source_name": config["source_name"],
        }
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    user_ids = {
        value
        for value in [
            *(row.updated_by_id for row in current_values.values()),
            *(row.created_by_id for row in active_batches),
            latest_supplier_change.changed_by_id if latest_supplier_change else None,
            *(
                status["latest"].updated_by_id
                for status in operation_module_status.values()
                if status["latest"] is not None
            ),
            review.updated_by_id if review else None,
        ]
        if value is not None
    }
    user_names = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(user_ids)))
    } if user_ids else {}
    items = []
    for definition in definitions:
        current = current_values.get(definition.id)
        prior = previous_values.get(definition.id)
        current_number = float(current.value) if current else None
        prior_number = float(prior.value) if prior else None
        change = (
            current_number - prior_number
            if current_number is not None and prior_number is not None
            else None
        )
        ratio = change / prior_number * 100 if change is not None and prior_number else None
        items.append(
            {
                "id": definition.id,
                "code": definition.code,
                "name": definition.name,
                "category": definition.category,
                "unit": definition.unit,
                "precision": definition.precision,
                "value": current_number,
                "previous_value": prior_number,
                "change": round(change, 4) if change is not None else None,
                "change_ratio": round(ratio, 2) if ratio is not None else None,
                "note": current.note if current else "",
                "source_type": current.source_type if current else None,
                "source_label": SOURCE_LABELS.get(current.source_type, current.source_type)
                if current
                else "暂无数据",
                "source_name": current.source_name if current else None,
                "updated_at": current.updated_at.isoformat() if current else None,
                "updated_by_name": user_names.get(current.updated_by_id) if current else None,
            }
        )
    definitions_by_code = {row.code: row for row in definitions}
    batches_by_dataset: dict[str, list[AnalyticsImportBatch]] = {}
    for batch in active_batches:
        batches_by_dataset.setdefault(batch.dataset_type, []).append(batch)
    completion_items = []
    for definition in DATASET_DEFINITIONS:
        batches = batches_by_dataset.get(definition.code, [])
        metric_rows = [
            current_values[metric_definition.id]
            for code in definition.metric_codes
            if (metric_definition := definitions_by_code.get(code)) is not None
            and metric_definition.id in current_values
        ]
        if definition.code == "supplier_changes":
            if latest_supplier_change is not None:
                state = "system"
                label = "模块取数"
                source_name = "供应商管理模块"
                updated_at = latest_supplier_change.created_at
                updated_by_name = user_names.get(latest_supplier_change.changed_by_id)
                row_count = supplier_change_count
            else:
                state = "missing"
                label = "待补充"
                source_name = None
                updated_at = None
                updated_by_name = None
                row_count = 0
        elif definition.code in operation_module_status:
            module = operation_module_status[definition.code]
            latest_record = module["latest"]
            if latest_record is not None:
                state = "system"
                label = "模块取数"
                source_name = module["source_name"]
                updated_at = latest_record.updated_at
                updated_by_name = user_names.get(latest_record.updated_by_id)
                row_count = module["count"]
            else:
                state = "missing"
                label = "待补充"
                source_name = None
                updated_at = None
                updated_by_name = None
                row_count = 0
        elif batches:
            latest_batch = batches[0]
            state = "system" if latest_batch.mode == "system" else "uploaded"
            label = "系统取数" if latest_batch.mode == "system" else "已上传"
            source_name = latest_batch.original_name
            updated_at = latest_batch.created_at
            updated_by_name = user_names.get(latest_batch.created_by_id)
            row_count = sum(batch.row_count for batch in batches)
        elif metric_rows:
            latest_metric = max(metric_rows, key=lambda row: row.updated_at)
            state = "summary_only"
            label = "总表已录入"
            source_name = latest_metric.source_name or SOURCE_LABELS.get(
                latest_metric.source_type, latest_metric.source_type
            )
            updated_at = latest_metric.updated_at
            updated_by_name = user_names.get(latest_metric.updated_by_id)
            row_count = 0
        else:
            state = "missing"
            label = "待补充"
            source_name = None
            updated_at = None
            updated_by_name = None
            row_count = 0
        completion_items.append(
            {
                "code": definition.code,
                "name": definition.name,
                "state": state,
                "label": label,
                "source_name": source_name,
                "row_count": row_count,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "updated_by_name": updated_by_name,
            }
        )
    completed_count = sum(item["state"] != "missing" for item in completion_items)
    activity_candidates = [
        *(
            (row.updated_at, user_names.get(row.updated_by_id), SOURCE_LABELS.get(row.source_type))
            for row in current_values.values()
        ),
        *(
            (row.created_at, user_names.get(row.created_by_id), row.original_name)
            for row in active_batches
        ),
    ]
    if review:
        activity_candidates.append(
            (review.updated_at, user_names.get(review.updated_by_id), "月度复盘")
        )
    if latest_supplier_change is not None:
        activity_candidates.append(
            (
                latest_supplier_change.created_at,
                user_names.get(latest_supplier_change.changed_by_id),
                "供应商管理模块",
            )
        )
    for module in operation_module_status.values():
        latest_record = module["latest"]
        if latest_record is not None:
            activity_candidates.append(
                (
                    latest_record.updated_at,
                    user_names.get(latest_record.updated_by_id),
                    module["source_name"],
                )
            )
    latest_activity = (
        max(activity_candidates, key=lambda item: item[0])
        if activity_candidates
        else None
    )
    events = db.scalars(
        select(BusinessEvent)
        .where(BusinessEvent.month == selected)
        .order_by(BusinessEvent.category, BusinessEvent.id)
    ).all()
    trend_rows = db.scalars(select(MonthlyMetric).order_by(MonthlyMetric.month)).all()
    trend: dict[str, list[dict[str, object]]] = {}
    definitions_by_id = {row.id: row for row in definitions}
    for row in trend_rows:
        definition = definitions_by_id.get(row.metric_id)
        if definition is None:
            continue
        trend.setdefault(definition.code, []).append(
            {"month": row.month.strftime("%Y-%m"), "value": float(row.value)}
        )
    return {
        "month": month,
        "previous_month": previous.strftime("%Y-%m"),
        "metrics": items,
        "review": {
            "summary": review.summary or "" if review else "",
            "highlights": review.highlights or "" if review else "",
            "issues": review.issues or "" if review else "",
            "risks": review.risks or "" if review else "",
            "next_plan": review.next_plan or "" if review else "",
            "status": review.status if review else "draft",
            "completed_at": review.completed_at.isoformat()
            if review and review.completed_at
            else None,
            "archived_at": review.archived_at.isoformat()
            if review and review.archived_at
            else None,
            "updated_at": review.updated_at.isoformat() if review else None,
            "updated_by_name": user_names.get(review.updated_by_id) if review else None,
        },
        "completion": {
            "completed": completed_count,
            "total": len(completion_items),
            "percent": round(completed_count / len(completion_items) * 100)
            if completion_items
            else 0,
            "items": completion_items,
        },
        "latest_activity": {
            "updated_at": latest_activity[0].isoformat(),
            "updated_by_name": latest_activity[1],
            "source": latest_activity[2],
        }
        if latest_activity
        else None,
        "events": [
            {
                "id": row.id,
                "category": row.category,
                "title": row.title,
                "description": row.description or "",
                "event_date": row.event_date.isoformat() if row.event_date else None,
            }
            for row in events
        ],
        "trend": trend,
    }


@router.put("")
def save_analytics(
    payload: MonthlyAnalyticsInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    ensure_month_editable(db, selected)
    valid_ids = set(db.scalars(select(MetricDefinition.id)).all())
    for item in payload.metrics:
        if item.metric_id not in valid_ids:
            raise HTTPException(status_code=400, detail=f"指标 {item.metric_id} 不存在")
        target = db.scalar(
            select(MonthlyMetric).where(
                MonthlyMetric.month == selected,
                MonthlyMetric.metric_id == item.metric_id,
            )
        )
        new_value = Decimal(item.value)
        if target is None:
            target = MonthlyMetric(
                metric_id=item.metric_id,
                month=selected,
                value=new_value,
                source_type="manual",
                source_name="系统手工录入",
                updated_by_id=user.id,
            )
            db.add(target)
        elif target.value != new_value:
            target.value = new_value
            target.source_type = "manual"
            target.source_name = "系统手工录入"
            target.source_batch_id = None
            target.updated_by_id = user.id
        target.note = item.note.strip() or None
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is None:
        review = MonthlyReview(month=selected, status="draft")
        db.add(review)
    review.summary = payload.summary.strip() or None
    review.highlights = payload.highlights.strip() or None
    review.issues = payload.issues.strip() or None
    review.risks = payload.risks.strip() or None
    review.next_plan = payload.next_plan.strip() or None
    review.updated_by_id = user.id
    add_audit_log(
        db,
        action="analytics.save",
        resource=f"analytics:{payload.month}",
        request=request,
        user=user,
        detail={"metrics": len(payload.metrics), "review_status": review.status},
    )
    db.commit()
    return {"ok": True, "message": f"{payload.month} 经营数据已保存"}


@router.put("/status")
def update_analytics_status(
    payload: MonthlyAnalyticsStatusInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is None:
        review = MonthlyReview(month=selected, status="draft", updated_by_id=user.id)
        db.add(review)
    previous_status = review.status
    if previous_status == "archived" and payload.status != "archived":
        if not user_has_role(db, user, "admin"):
            raise HTTPException(status_code=403, detail="只有系统管理员可以重新开启已归档月份")
    now = datetime.now()
    review.status = payload.status
    review.updated_by_id = user.id
    if payload.status == "draft":
        review.completed_at = None
        review.archived_at = None
    elif payload.status == "completed":
        review.completed_at = now
        review.archived_at = None
    else:
        review.completed_at = review.completed_at or now
        review.archived_at = now
    add_audit_log(
        db,
        action="analytics.status",
        resource=f"analytics:{payload.month}",
        request=request,
        user=user,
        detail={"from": previous_status, "to": payload.status},
    )
    db.commit()
    return {"ok": True, "status": payload.status, "message": "月份状态已更新"}


@router.get("/detail-types")
def detail_types(
    _: User = Depends(require_permission("analytics.view")),
) -> list[dict[str, object]]:
    return public_definitions()


@router.get("/details/{dataset_type}/template")
def detail_template(
    dataset_type: str,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> StreamingResponse:
    definition = detail_definition(dataset_type)
    if dataset_type == "shipping_orders":
        rows = active_detail_payloads(db, dataset_type, month_date(month)) if month else []
        content = build_shipping_template(rows)
        filename = quote(f"{month + ' ' if month else ''}{definition.name}匹配模板.xlsx")
    elif dataset_type == "staffing":
        content = build_staffing_template()
        filename = quote(f"{definition.name}月度上传模板.xlsx")
    else:
        content = build_template(definition)
        filename = quote(f"{definition.name}导入模板.xlsx")
    return StreamingResponse(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/details/shipping_orders/export")
def export_shipping_orders(
    payload: ShippingExportInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> StreamingResponse:
    selected = month_date(payload.month)
    monthly_rows = active_detail_payloads(db, "shipping_orders", selected)
    if not monthly_rows:
        raise HTTPException(status_code=404, detail="当前月份没有可导出的发货数据")

    records = filtered_shipping_records(
        db,
        selected,
        payload.search if payload.scope == "filtered" else "",
        payload.sort_order,
    )
    if payload.scope == "selected":
        selected_ids = set(payload.row_ids)
        if not selected_ids:
            raise HTTPException(status_code=422, detail="请先勾选需要导出的团队")
        records = [item for item in records if item[0].id in selected_ids]
    if not records:
        raise HTTPException(status_code=404, detail="没有符合条件的发货数据")

    monthly_total = summarize_rows("shipping_orders", monthly_rows).get(
        "shipping_orders", Decimal("0")
    )
    rows = [
        detail_row_values("shipping_orders", row.payload, monthly_total)
        for row, _batch in records
    ]
    filename = quote(f"{payload.month} 发货单量导出.xlsx")
    return StreamingResponse(
        build_shipping_export(rows, payload.columns),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/details/return_items/export")
def export_return_items(
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    search: str = Query(default="", max_length=100),
    sort_order: str = Query(default="", pattern=r"^(|asc|desc)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> StreamingResponse:
    selected = month_date(month)
    monthly_rows = active_detail_payloads(db, "return_items", selected)
    if not monthly_rows:
        raise HTTPException(status_code=404, detail="当前月份没有可导出的退货数据")
    records = filtered_return_records(db, selected, search, sort_order)
    if not records:
        raise HTTPException(status_code=404, detail="没有符合条件的退货数据")
    monthly_total = summarize_rows("return_items", monthly_rows).get(
        "return_items", Decimal("0")
    )
    rows = [
        detail_row_values("return_items", row.payload, monthly_total)
        for row, _batch in records
    ]
    definition = detail_definition("return_items")
    filename = quote(f"{month} 退货件数导出.xlsx")
    return StreamingResponse(
        build_detail_export(definition, rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/details/staffing/export")
def export_staffing(
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> StreamingResponse:
    selected = month_date(month)
    definition = detail_definition("staffing")
    rows = active_detail_payloads(db, "staffing", selected)
    filename = quote(f"{month} {definition.name}导出.xlsx")
    return StreamingResponse(
        build_detail_export(definition, rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/details/{dataset_type}/preview")
def preview_detail_import(
    dataset_type: str,
    file: UploadFile = File(...),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    original_name, parsed = parse_excel_upload(dataset_type, file)
    rows = parsed["rows"]
    summary = summarize_rows(dataset_type, rows)
    warnings = list(parsed["warnings"])
    match_result = None
    if dataset_type == "shipping_orders" and month:
        current_rows = active_detail_payloads(db, dataset_type, month_date(month))
        if current_rows:
            merged_rows, matched, unmatched = merge_shipping_upload(current_rows, rows)
            summary = summarize_rows(dataset_type, merged_rows)
            match_result = {
                "matched_count": len(matched),
                "unmatched_count": len(unmatched),
                "unmatched_teams": unmatched,
            }
            if unmatched:
                warnings.append(
                    f"有 {len(unmatched)} 个团队未匹配，将跳过：{'、'.join(unmatched[:10])}"
                )
        else:
            warnings.append("当前月份尚无发货明细，首次上传将按 Excel 建立明细。")
    elif dataset_type == "staffing":
        if not month:
            raise HTTPException(status_code=422, detail="人员调整必须选择页面月份后再上传")
        rows, match_result = prepare_staffing_rows(db, month_date(month), rows)
        summary = summarize_rows(dataset_type, rows)
        parsed["columns"] = list(STAFFING_COLUMNS)
        parsed["preview_rows"] = rows[:20]
        parsed["row_count"] = len(rows)
        warnings = [
            warning
            for warning in warnings
            if not warning.startswith("未识别推荐字段")
        ]
        warnings.append(f"将按页面所选月份 {month} 保存；Excel 内的月份列不会覆盖页面月份。")
    return {
        "original_name": original_name,
        "sheet_name": parsed["sheet_name"],
        "columns": parsed["columns"],
        "rows": parsed["preview_rows"],
        "row_count": parsed["row_count"],
        "warnings": warnings,
        "summary": {code: float(value) for code, value in summary.items()},
        "match_result": match_result,
    }


@router.get("/details/shipping_orders/system-preview")
def preview_shipping_system_data(
    month: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(month)
    snapshot = ensure_shipping_system_sync_allowed(selected)
    try:
        source_data = fetch_shipping_orders(selected)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    guard = shipping_source_guard(db, selected, source_data)
    return {**source_data, "snapshot": snapshot, **guard}


@router.post("/details/shipping_orders/system-sync")
def sync_shipping_system_data(
    request: Request,
    month: str = Query(...),
    confirm_warning: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(month)
    snapshot = ensure_shipping_system_sync_allowed(selected)
    ensure_month_editable(db, selected)
    try:
        source_data = fetch_shipping_orders(selected)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    guard = shipping_source_guard(db, selected, source_data)
    if guard["blocking"]:
        raise HTTPException(status_code=409, detail=str(guard["warnings"][0]))
    if guard["requires_confirmation"] and not confirm_warning:
        raise HTTPException(
            status_code=409,
            detail="本次数据变化较大，请先预览并确认后再保存",
        )

    existing_batches = db.scalars(
        select(AnalyticsImportBatch).where(
            AnalyticsImportBatch.dataset_type == "shipping_orders",
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
    ).all()
    existing_remarks = {
        str(row.payload.get("团队名称") or ""): str(row.payload.get("备注") or "")
        for row in db.scalars(
            select(AnalyticsDetailRow)
            .join(AnalyticsImportBatch)
            .where(
                AnalyticsImportBatch.dataset_type == "shipping_orders",
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
            .order_by(AnalyticsImportBatch.created_at, AnalyticsDetailRow.row_number)
        )
        if row.payload.get("团队名称")
    }
    for existing in existing_batches:
        existing.active = False

    for row in source_data["rows"]:
        team_name = str(row.get("团队名称") or "")
        row["备注"] = existing_remarks.get(team_name, "")

    source_name = str(source_data["source_name"])
    batch = AnalyticsImportBatch(
        dataset_type="shipping_orders",
        month=selected,
        original_name=f"系统取数 · {source_name}",
        sheet_name=(
            f"{source_data['month_start']} 至 {source_data['month_end']}（不含结束日）"
        ),
        mode="system",
        columns=list(source_data["columns"]),
        row_count=int(source_data["row_count"]),
        active=True,
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()
    for row_number, row in enumerate(source_data["rows"], start=1):
        db.add(
            AnalyticsDetailRow(
                batch_id=batch.id,
                row_number=row_number,
                payload=dict(row),
            )
        )

    metric = db.scalar(
        select(MetricDefinition).where(MetricDefinition.code == "shipping_orders")
    )
    if metric is None:
        raise HTTPException(status_code=500, detail="发货单量指标未配置")
    target = db.scalar(
        select(MonthlyMetric).where(
            MonthlyMetric.month == selected,
            MonthlyMetric.metric_id == metric.id,
        )
    )
    total = Decimal(str(source_data["total"]))
    if target is None:
        target = MonthlyMetric(metric_id=metric.id, month=selected, value=total)
        db.add(target)
    else:
        target.value = total
    target.source_type = "system"
    target.source_name = source_name
    target.source_batch_id = batch.id
    target.updated_by_id = user.id
    target.note = "按确认口径从 pre_matched_order 自动汇总"

    add_audit_log(
        db,
        action="analytics.system_sync",
        resource=f"analytics:shipping_orders:{month}",
        request=request,
        user=user,
        detail={
            "source": source_name,
            "month_start": source_data["month_start"],
            "month_end": source_data["month_end"],
            "teams": source_data["row_count"],
            "shipping_orders": source_data["total"],
            "conditions": source_data["conditions"],
        },
    )
    db.commit()
    return {
        "ok": True,
        "message": f"已保存 {source_data['row_count']} 个团队的发货单量",
        "row_count": source_data["row_count"],
        "total": source_data["total"],
        "snapshot": snapshot,
        "warnings": guard["warnings"],
    }


@router.get("/details/return_items/system-preview")
def preview_return_system_data(
    month: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(month)
    snapshot = ensure_shipping_system_sync_allowed(selected)
    try:
        source_data = fetch_return_items(selected)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    guard = return_source_guard(db, selected, source_data)
    return {**source_data, "snapshot": snapshot, **guard}


@router.post("/details/return_items/system-sync")
def sync_return_system_data(
    request: Request,
    month: str = Query(...),
    confirm_warning: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(month)
    snapshot = ensure_shipping_system_sync_allowed(selected)
    ensure_month_editable(db, selected)
    try:
        source_data = fetch_return_items(selected)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    guard = return_source_guard(db, selected, source_data)
    if guard["blocking"]:
        raise HTTPException(status_code=409, detail=str(guard["warnings"][0]))
    if guard["requires_confirmation"] and not confirm_warning:
        raise HTTPException(
            status_code=409,
            detail="本次数据变化较大，请先预览并确认后再保存",
        )

    existing_batches = db.scalars(
        select(AnalyticsImportBatch).where(
            AnalyticsImportBatch.dataset_type == "return_items",
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
    ).all()
    for existing in existing_batches:
        existing.active = False

    source_name = str(source_data["source_name"])
    batch = AnalyticsImportBatch(
        dataset_type="return_items",
        month=selected,
        original_name=f"系统取数 · {source_name}",
        sheet_name=f"{source_data['month_start']} 至 {source_data['month_end']}（不含）",
        mode="system",
        columns=list(source_data["columns"]),
        row_count=int(source_data["row_count"]),
        active=True,
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()
    for row_number, row in enumerate(source_data["rows"], start=1):
        db.add(
            AnalyticsDetailRow(
                batch_id=batch.id,
                row_number=row_number,
                payload=dict(row),
            )
        )

    metric = db.scalar(select(MetricDefinition).where(MetricDefinition.code == "return_items"))
    if metric is None:
        raise HTTPException(status_code=500, detail="退货件数指标未配置")
    target = db.scalar(
        select(MonthlyMetric).where(
            MonthlyMetric.month == selected,
            MonthlyMetric.metric_id == metric.id,
        )
    )
    total = Decimal(str(source_data["total"]))
    if target is None:
        target = MonthlyMetric(metric_id=metric.id, month=selected, value=total)
        db.add(target)
    else:
        target.value = total
    target.source_type = "system"
    target.source_name = source_name
    target.source_batch_id = batch.id
    target.updated_by_id = user.id
    target.note = "处理退货、拦截件扣费与异常件扣费三项按团队汇总"

    add_audit_log(
        db,
        action="analytics.system_sync",
        resource=f"analytics:return_items:{month}",
        request=request,
        user=user,
        detail={
            "source": source_name,
            "month_start": source_data["month_start"],
            "month_end": source_data["month_end"],
            "teams": source_data["row_count"],
            "return_items": source_data["total"],
            "conditions": source_data["conditions"],
        },
    )
    db.commit()
    return {
        "ok": True,
        "message": f"已保存 {source_data['row_count']} 个团队的退货件数",
        "row_count": source_data["row_count"],
        "total": source_data["total"],
        "snapshot": snapshot,
        "warnings": guard["warnings"],
    }


@router.patch("/details/shipping_orders/rows/{row_id}/remark")
def update_shipping_remark(
    row_id: int,
    payload: ShippingRemarkInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    ensure_month_editable(db, selected)
    record = db.execute(
        select(AnalyticsDetailRow, AnalyticsImportBatch)
        .join(AnalyticsImportBatch)
        .where(
            AnalyticsDetailRow.id == row_id,
            AnalyticsImportBatch.dataset_type == "shipping_orders",
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="未找到当前月份的发货明细")

    row, batch = record
    remark = payload.remark.strip()
    row.payload = {**row.payload, "备注": remark}
    add_audit_log(
        db,
        action="analytics.shipping_remark.update",
        resource=f"analytics:shipping_orders:{payload.month}:{row_id}",
        request=request,
        user=user,
        detail={
            "batch_id": batch.id,
            "team_name": row.payload.get("团队名称"),
            "remark": remark,
        },
    )
    db.commit()
    return {"ok": True, "row_id": row_id, "remark": remark}


@router.patch("/details/staffing/rows/{row_id}/analysis")
def update_staffing_analysis(
    row_id: int,
    payload: StaffingAnalysisInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    ensure_month_editable(db, selected)
    record = db.execute(
        select(AnalyticsDetailRow, AnalyticsImportBatch)
        .join(AnalyticsImportBatch)
        .where(
            AnalyticsDetailRow.id == row_id,
            AnalyticsImportBatch.dataset_type == "staffing",
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="未找到当前月份的人员调整明细")

    row, batch = record
    analysis = payload.analysis.strip()
    row.payload = {**row.payload, "综合分析": analysis}
    add_audit_log(
        db,
        action="analytics.staffing_analysis.update",
        resource=f"analytics:staffing:{payload.month}:{row_id}",
        request=request,
        user=user,
        detail={
            "batch_id": batch.id,
            "team_name": row.payload.get("小组"),
            "analysis": analysis,
        },
    )
    db.commit()
    return {"ok": True, "row_id": row_id, "analysis": analysis}


@router.patch("/details/staffing/rows/{row_id}/inputs")
def update_staffing_inputs(
    row_id: int,
    payload: StaffingInputsInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    ensure_month_editable(db, selected)
    record = db.execute(
        select(AnalyticsDetailRow, AnalyticsImportBatch)
        .join(AnalyticsImportBatch)
        .where(
            AnalyticsDetailRow.id == row_id,
            AnalyticsImportBatch.dataset_type == "staffing",
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
    ).one_or_none()
    if record is None and row_id > 0:
        raise HTTPException(status_code=404, detail="未找到当前月份的人员调整明细")

    initialized_from_template = False
    if record is None:
        requested_team = str(payload.team_name or "").strip()
        if not requested_team:
            raise HTTPException(status_code=422, detail="人员调整模板行缺少小组名称")
        batch = db.scalar(
            select(AnalyticsImportBatch)
            .where(
                AnalyticsImportBatch.dataset_type == "staffing",
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
            .order_by(AnalyticsImportBatch.created_at.desc())
        )
        if batch is None:
            batch = AnalyticsImportBatch(
                dataset_type="staffing",
                month=selected,
                original_name=f"{payload.month} 人员调整页面模板",
                sheet_name="人员调整",
                mode="manual",
                columns=list(STAFFING_COLUMNS),
                row_count=0,
                active=True,
                created_by_id=user.id,
            )
            db.add(batch)
            db.flush()
            template_teams = staffing_template_team_names(db, selected)
            if normalized_team_name(requested_team) not in {
                normalized_team_name(name) for name in template_teams
            }:
                template_teams.append(requested_team)
            previous_output_by_team = {
                normalized_team_name(previous_row.get("小组")): float(value)
                for previous_row in active_detail_payloads(
                    db, "staffing", previous_month(selected)
                )
                if (value := number(previous_row.get("人均月产出"))) is not None
            }
            for row_number, name in enumerate(template_teams, start=1):
                empty_inputs = {
                    "小组": name,
                    "正式工人数": None,
                    "最优配置": None,
                    "人均月产出": None,
                    "最优人均产出": None,
                    "综合分析": "",
                }
                db.add(
                    AnalyticsDetailRow(
                        batch_id=batch.id,
                        row_number=row_number,
                        payload=calculate_staffing_row(
                            empty_inputs,
                            previous_output_by_team.get(normalized_team_name(name)),
                        ),
                    )
                )
            db.flush()
            initialized_from_template = True

        batch_rows = db.scalars(
            select(AnalyticsDetailRow)
            .where(AnalyticsDetailRow.batch_id == batch.id)
            .order_by(AnalyticsDetailRow.row_number)
        ).all()
        row = next(
            (
                item
                for item in batch_rows
                if normalized_team_name(item.payload.get("小组"))
                == normalized_team_name(requested_team)
            ),
            None,
        )
        if row is None:
            row = AnalyticsDetailRow(
                batch_id=batch.id,
                row_number=len(batch_rows) + 1,
                payload=calculate_staffing_row(
                    {
                        "小组": requested_team,
                        "正式工人数": None,
                        "最优配置": None,
                        "人均月产出": None,
                        "最优人均产出": None,
                        "综合分析": "",
                    },
                    None,
                ),
            )
            db.add(row)
            batch_rows.append(row)
            db.flush()
        batch.row_count = len(batch_rows)
    else:
        row, batch = record

    team_name = str(row.payload.get("小组") or "").strip()
    old_values = {
        column: row.payload.get(column) for column in STAFFING_INPUT_COLUMNS[1:5]
    }
    inputs = {
        "小组": team_name,
        "正式工人数": staffing_number(
            payload.regular_staff,
            team_name=team_name,
            label="正式工人数",
            required=True,
        ),
        "最优配置": staffing_number(
            payload.optimal_staff,
            team_name=team_name,
            label="最优配置",
        ),
        "人均月产出": staffing_number(
            payload.monthly_output,
            team_name=team_name,
            label="人均月产出",
        ),
        "最优人均产出": staffing_number(
            payload.optimal_monthly_output,
            team_name=team_name,
            label="最优人均产出",
        ),
        "综合分析": str(row.payload.get("综合分析") or ""),
    }
    previous_output = next(
        (
            float(value)
            for previous_row in active_detail_payloads(
                db, "staffing", previous_month(selected)
            )
            if normalized_team_name(previous_row.get("小组"))
            == normalized_team_name(team_name)
            and (value := number(previous_row.get("人均月产出"))) is not None
        ),
        None,
    )
    calculated = calculate_staffing_row(inputs, previous_output)
    row.payload = {**row.payload, **calculated}

    active_rows = db.scalars(
        select(AnalyticsDetailRow)
        .join(AnalyticsImportBatch)
        .where(
            AnalyticsImportBatch.dataset_type == "staffing",
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
    ).all()
    regular_total = sum(
        (
            value
            for item in active_rows
            if (value := number(item.payload.get("正式工人数"))) is not None
        ),
        Decimal("0"),
    )
    metric = db.scalar(
        select(MetricDefinition).where(MetricDefinition.code == "staff_adjustment")
    )
    if metric is None:
        raise HTTPException(status_code=500, detail="人员调整指标未配置")
    target = db.scalar(
        select(MonthlyMetric).where(
            MonthlyMetric.month == selected,
            MonthlyMetric.metric_id == metric.id,
        )
    )
    if target is None:
        target = MonthlyMetric(
            metric_id=metric.id,
            month=selected,
            value=regular_total,
        )
        db.add(target)
    else:
        target.value = regular_total
    target.source_type = "manual"
    target.source_name = "人员调整页面手工修改"
    target.source_batch_id = batch.id
    target.updated_by_id = user.id
    target.note = "由人员调整分表手工修改后自动汇总"

    add_audit_log(
        db,
        action="analytics.staffing_inputs.update",
        resource=f"analytics:staffing:{payload.month}:{row.id}",
        request=request,
        user=user,
        detail={
            "batch_id": batch.id,
            "team_name": team_name,
            "before": old_values,
            "after": {
                column: calculated.get(column)
                for column in STAFFING_INPUT_COLUMNS[1:5]
            },
            "regular_total": float(regular_total),
            "initialized_from_template": initialized_from_template,
        },
    )
    db.commit()
    return {
        "ok": True,
        "row_id": row.id,
        "values": calculated,
        "regular_total": float(regular_total),
    }


@router.post("/details/{dataset_type}/import")
def import_detail_rows(
    dataset_type: str,
    request: Request,
    month: str = Form(...),
    mode: str = Form(default="replace"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    definition = detail_definition(dataset_type)
    selected = month_date(month)
    ensure_month_editable(db, selected)
    if mode not in {"replace", "append"}:
        raise HTTPException(status_code=422, detail="导入方式必须为 replace 或 append")
    original_name, parsed = parse_excel_upload(dataset_type, file)

    current_rows = active_detail_payloads(db, dataset_type, selected)
    staffing_match_result: dict[str, object] | None = None
    if dataset_type == "staffing":
        staffing_rows, staffing_match_result = prepare_staffing_rows(
            db, selected, parsed["rows"]
        )
        parsed["rows"] = staffing_rows
        parsed["preview_rows"] = staffing_rows[:20]
        parsed["columns"] = list(STAFFING_COLUMNS)
        parsed["row_count"] = len(staffing_rows)
        parsed["warnings"] = [
            warning
            for warning in parsed["warnings"]
            if not warning.startswith("未识别推荐字段")
        ]
        parsed["warnings"].append(
            f"已按页面月份 {month} 保存，派生指标由系统重新计算。"
        )
        mode = "replace"

    if dataset_type == "shipping_orders" and current_rows:
        merged_rows, matched, unmatched = merge_shipping_upload(
            current_rows, parsed["rows"]
        )
        if not matched:
            raise HTTPException(status_code=422, detail="Excel 中没有匹配到现有团队")

        total = summarize_rows(dataset_type, merged_rows).get(
            "shipping_orders", Decimal("0")
        )
        snapshot_rows = [
            detail_row_values(dataset_type, row, total) for row in merged_rows
        ]
        existing_batches = db.scalars(
            select(AnalyticsImportBatch).where(
                AnalyticsImportBatch.dataset_type == dataset_type,
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
        ).all()
        for existing in existing_batches:
            existing.active = False

        batch = AnalyticsImportBatch(
            dataset_type=dataset_type,
            month=selected,
            original_name=f"Excel 匹配 · {original_name}",
            sheet_name=str(parsed["sheet_name"]),
            mode="match",
            columns=list(SHIPPING_COLUMNS),
            row_count=len(snapshot_rows),
            active=True,
            created_by_id=user.id,
        )
        db.add(batch)
        db.flush()
        for row_number, row in enumerate(snapshot_rows, start=1):
            db.add(
                AnalyticsDetailRow(
                    batch_id=batch.id,
                    row_number=row_number,
                    payload=row,
                )
            )

        metric = db.scalar(
            select(MetricDefinition).where(MetricDefinition.code == "shipping_orders")
        )
        if metric is None:
            raise HTTPException(status_code=500, detail="发货单量指标未配置")
        target = db.scalar(
            select(MonthlyMetric).where(
                MonthlyMetric.month == selected,
                MonthlyMetric.metric_id == metric.id,
            )
        )
        if target is None:
            target = MonthlyMetric(metric_id=metric.id, month=selected, value=total)
            db.add(target)
        else:
            target.value = total
        target.source_type = "excel"
        target.source_name = original_name
        target.source_batch_id = batch.id
        target.updated_by_id = user.id
        target.note = "Excel 按团队名称匹配更新"

        warnings = []
        if unmatched:
            warnings.append(
                f"有 {len(unmatched)} 个团队未匹配，已跳过：{'、'.join(unmatched[:10])}"
            )
        add_audit_log(
            db,
            action="analytics.shipping_excel_match",
            resource=f"analytics:shipping_orders:{month}",
            request=request,
            user=user,
            detail={
                "filename": original_name,
                "matched_teams": matched,
                "unmatched_teams": unmatched,
                "shipping_orders": float(total),
            },
        )
        db.commit()
        return {
            "ok": True,
            "message": f"已按团队名称匹配更新 {len(matched)} 个团队",
            "row_count": len(snapshot_rows),
            "matched_count": len(matched),
            "unmatched_teams": unmatched,
            "updated_metrics": [
                {"code": "shipping_orders", "name": metric.name, "value": float(total)}
            ],
            "warnings": warnings,
        }

    if mode == "replace":
        existing_batches = db.scalars(
            select(AnalyticsImportBatch).where(
                AnalyticsImportBatch.dataset_type == dataset_type,
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
        ).all()
        for existing in existing_batches:
            existing.active = False

    batch = AnalyticsImportBatch(
        dataset_type=dataset_type,
        month=selected,
        original_name=original_name,
        sheet_name=str(parsed["sheet_name"]),
        mode=mode,
        columns=list(parsed["columns"]),
        row_count=int(parsed["row_count"]),
        active=True,
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()
    for row_number, payload in enumerate(parsed["rows"], start=1):
        db.add(
            AnalyticsDetailRow(
                batch_id=batch.id,
                row_number=row_number,
                payload=payload,
            )
        )
    db.flush()

    summary = summarize_rows(dataset_type, active_detail_payloads(db, dataset_type, selected))
    definitions = {
        item.code: item
        for item in db.scalars(
            select(MetricDefinition).where(MetricDefinition.code.in_(summary))
        )
    }
    updated_metrics: list[dict[str, object]] = []
    for code, value in summary.items():
        metric = definitions.get(code)
        if metric is None:
            continue
        target = db.scalar(
            select(MonthlyMetric).where(
                MonthlyMetric.month == selected,
                MonthlyMetric.metric_id == metric.id,
            )
        )
        if target is None:
            target = MonthlyMetric(metric_id=metric.id, month=selected, value=value)
            db.add(target)
        else:
            target.value = value
        target.source_type = "excel"
        target.source_name = original_name
        target.source_batch_id = batch.id
        target.updated_by_id = user.id
        target.note = f"由{definition.name}分表自动汇总"
        updated_metrics.append({"code": code, "name": metric.name, "value": float(value)})

    add_audit_log(
        db,
        action="analytics.import",
        resource=f"analytics:{dataset_type}:{month}",
        request=request,
        user=user,
        detail={
            "dataset": definition.name,
            "filename": original_name,
            "sheet": parsed["sheet_name"],
            "mode": mode,
            "rows": parsed["row_count"],
        },
    )
    db.commit()
    return {
        "ok": True,
        "message": f"已导入 {parsed['row_count']} 行{definition.name}数据",
        "row_count": parsed["row_count"],
        "matched_count": (
            staffing_match_result.get("matched_count") if staffing_match_result else None
        ),
        "added_count": (
            staffing_match_result.get("added_count") if staffing_match_result else None
        ),
        "preserved_count": (
            staffing_match_result.get("preserved_count") if staffing_match_result else None
        ),
        "updated_metrics": updated_metrics,
        "warnings": parsed["warnings"],
    }


@router.get("/details/{dataset_type}")
def detail_rows(
    dataset_type: str,
    month: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    search: str = Query(default="", max_length=100),
    sort_order: str = Query(default="", pattern=r"^(|asc|desc)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> dict[str, object]:
    definition = detail_definition(dataset_type)
    selected = month_date(month)
    if dataset_type == "supplier_changes":
        return supplier_change_details(db, selected, month, page, size)
    if dataset_type in OPERATION_DETAIL_CONFIGS:
        return operation_record_details(db, dataset_type, selected, month, page, size)
    filters = (
        AnalyticsImportBatch.dataset_type == dataset_type,
        AnalyticsImportBatch.month == selected,
        AnalyticsImportBatch.active.is_(True),
    )
    batches = db.scalars(
        select(AnalyticsImportBatch)
        .where(*filters)
        .order_by(AnalyticsImportBatch.created_at.desc())
    ).all()
    batch_user_ids = {batch.created_by_id for batch in batches if batch.created_by_id is not None}
    batch_user_names = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(batch_user_ids)))
    } if batch_user_ids else {}
    columns: list[str] = []
    for batch in reversed(batches):
        for column in batch.columns:
            if column not in columns:
                columns.append(column)
    if dataset_type == "shipping_orders":
        columns = list(SHIPPING_COLUMNS)
    elif dataset_type == "return_items":
        columns = list(RETURN_COLUMNS)
    elif dataset_type == "staffing":
        columns = list(STAFFING_COLUMNS)

    staffing_is_template = False
    template_response_rows: list[dict[str, object]] | None = None
    detail_query = (
        select(AnalyticsDetailRow, AnalyticsImportBatch)
        .join(AnalyticsImportBatch)
        .where(*filters)
        .order_by(AnalyticsImportBatch.created_at.desc(), AnalyticsDetailRow.row_number)
    )
    if dataset_type == "shipping_orders":
        all_rows = filtered_shipping_records(db, selected, search, sort_order)
        total = len(all_rows)
        result = all_rows[(page - 1) * size : page * size]
    elif dataset_type == "return_items":
        all_rows = filtered_return_records(db, selected, search, sort_order)
        total = len(all_rows)
        result = all_rows[(page - 1) * size : page * size]
    elif dataset_type == "staffing":
        all_rows = db.execute(detail_query).all()
        keyword = search.strip().casefold()
        if not all_rows:
            staffing_is_template = True
            template_rows = [
                {
                    "id": -index,
                    "row_number": index,
                    "values": calculate_staffing_row(
                        {
                            "小组": team_name,
                            "正式工人数": None,
                            "最优配置": None,
                            "人均月产出": None,
                            "最优人均产出": None,
                            "综合分析": "",
                        },
                        None,
                    ),
                    "source_name": "待维护模板",
                    "imported_at": "",
                    "is_template": True,
                }
                for index, team_name in enumerate(
                    staffing_template_team_names(db, selected), start=1
                )
            ]
            if keyword:
                template_rows = [
                    item
                    for item in template_rows
                    if keyword
                    in str(item["values"].get("小组") or "").casefold()
                ]
            total = len(template_rows)
            template_response_rows = template_rows[(page - 1) * size : page * size]
            result = []
        else:
            if keyword:
                all_rows = [
                    item
                    for item in all_rows
                    if keyword in str(item[0].payload.get("小组") or "").casefold()
                ]
            total = len(all_rows)
            result = all_rows[(page - 1) * size : page * size]
    else:
        total = db.scalar(
            select(func.count(AnalyticsDetailRow.id))
            .join(AnalyticsImportBatch)
            .where(*filters)
        ) or 0
        result = db.execute(
            detail_query.offset((page - 1) * size).limit(size)
        ).all()
    active_payloads = active_detail_payloads(db, dataset_type, selected)
    summary = summarize_rows(dataset_type, active_payloads)
    if dataset_type == "staffing":
        regular_values = [number(row.get("正式工人数")) for row in active_payloads]
        optimal_values = [number(row.get("最优配置")) for row in active_payloads]
        gap_values = [number(row.get("配置偏差")) for row in active_payloads]
        summary.update(
            {
                "staff_regular_total": sum(
                    (value for value in regular_values if value is not None), Decimal("0")
                ),
                "staff_optimal_total": sum(
                    (value for value in optimal_values if value is not None), Decimal("0")
                ),
                "staff_configuration_gap": sum(
                    (value for value in gap_values if value is not None), Decimal("0")
                ),
                "staff_overstaffed_groups": Decimal(
                    sum(1 for value in gap_values if value is not None and value > 0)
                ),
                "staff_understaffed_groups": Decimal(
                    sum(1 for value in gap_values if value is not None and value < 0)
                ),
            }
        )
    dataset_total = summary.get(
        "shipping_orders" if dataset_type == "shipping_orders" else "return_items"
    )
    snapshot: dict[str, object] | None = None
    if dataset_type in {"shipping_orders", "return_items"}:
        snapshot = shipping_snapshot_state(selected)
        snapshot["version_count"] = db.scalar(
            select(func.count(AnalyticsImportBatch.id)).where(
                AnalyticsImportBatch.dataset_type == dataset_type,
                AnalyticsImportBatch.month == selected,
            )
        ) or 0
        snapshot["captured_at"] = batches[0].created_at.isoformat() if batches else None
        snapshot["source_name"] = batches[0].original_name if batches else None
    return {
        "dataset": {
            "code": definition.code,
            "name": definition.name,
            "description": definition.description,
            "summary_hint": definition.summary_hint,
        },
        "month": month,
        "columns": columns,
        "rows": template_response_rows
        if template_response_rows is not None
        else [
            {
                "id": row.id,
                "row_number": row.row_number,
                "values": detail_row_values(dataset_type, row.payload, dataset_total),
                "source_name": batch.original_name,
                "imported_at": batch.created_at.isoformat(),
                "is_template": False,
            }
            for row, batch in result
        ],
        "total": total,
        "page": page,
        "size": size,
        "summary": {code: float(value) for code, value in summary.items()},
        "snapshot": snapshot,
        "is_template": staffing_is_template,
        "batches": [
            {
                "original_name": batch.original_name,
                "sheet_name": batch.sheet_name,
                "mode": batch.mode,
                "row_count": batch.row_count,
                "imported_at": batch.created_at.isoformat(),
                "imported_by_name": batch_user_names.get(batch.created_by_id),
            }
            for batch in batches
        ],
    }
