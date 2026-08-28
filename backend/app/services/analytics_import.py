"""Excel parsing and summary helpers for operating-analysis detail tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 5000
MAX_IMPORT_COLUMNS = 80
PREVIEW_ROWS = 20


@dataclass(frozen=True)
class DatasetDefinition:
    code: str
    name: str
    description: str
    sheet_aliases: tuple[str, ...]
    columns: tuple[str, ...]
    required_columns: tuple[str, ...]
    summary_hint: str
    metric_codes: tuple[str, ...]


DATASET_DEFINITIONS: tuple[DatasetDefinition, ...] = (
    DatasetDefinition(
        "shipping_orders",
        "发货单量",
        "按团队登记当月发货单量，可由分表自动汇总到总表。",
        ("1-发货单量", "发货单量"),
        ("月份", "团队名称", "发货单量", "总发货订单", "数据发货占比", "备注"),
        ("团队名称", "发货单量"),
        "识别“发货单量”后自动求和。",
        ("shipping_orders",),
    ),
    DatasetDefinition(
        "return_items",
        "退货件数",
        "按团队登记当月退货件数，可由分表自动汇总到总表。",
        ("2-退货件数", "退货件数"),
        ("月份", "团队名称", "退货件数", "备注"),
        ("团队名称", "退货件数"),
        "识别“退货件数”后自动求和。",
        ("return_items",),
    ),
    DatasetDefinition(
        "customer_changes",
        "客户变化",
        "登记新进、流失和意向客户，可记录名称、来源渠道和说明。",
        ("3-客户变化", "客户变化"),
        ("月份", "变化类型", "客户名称", "来源渠道", "数量", "备注"),
        ("变化类型",),
        "按变化类型汇总新进、流失和意向客户；数量为空时按 1 计。",
        ("new_customers", "lost_customers", "prospective_customers"),
    ),
    DatasetDefinition(
        "supplier_changes",
        "供应商变化",
        "维护供应商档案及当月变化，联系方式仅对经营分析权限用户展示。",
        ("4-供应商变化", "供应商变化"),
        (
            "供应商名称",
            "供应商联系人",
            "联系电话",
            "联系地址",
            "合作时间",
            "常用产品类型",
            "备注",
        ),
        ("供应商名称",),
        "按供应商名称去重后汇总供应商数量。",
        ("supplier_change",),
    ),
    DatasetDefinition(
        "staffing",
        "人员调整",
        "按小组登记人员配置、产出和效率损失。",
        ("5-人员调整", "人员调整"),
        (
            "月份",
            "小组",
            "正式工人数",
            "最优配置",
            "配置偏差",
            "偏差比例",
            "人均月产出",
            "最低人均产出",
            "效率损失",
            "效率损失占比",
            "人均月产出变化",
            "人均月产出环比",
            "分析",
        ),
        ("小组", "正式工人数"),
        "识别“正式工人数”后自动求和。",
        ("staff_adjustment",),
    ),
    DatasetDefinition(
        "value_added",
        "增值服务细项",
        "按团队和服务类型登记增值服务数量。",
        ("6-增值服务细项", "增值服务细项"),
        ("月份", "团队ID", "团队名称", "服务编码", "服务名称", "服务分组", "数量"),
        ("团队名称", "服务名称", "数量"),
        "当前只进入分表；金额与次数口径确认后再自动汇总。",
        (),
    ),
    DatasetDefinition(
        "service_issues",
        "客户服务情况",
        "登记客户投诉、异常原因、责任归属和整改状态。",
        ("8-客户服务情况", "客户服务情况"),
        (
            "月份",
            "团队名",
            "投诉大类",
            "问题详细描述",
            "核实原因",
            "责任归属",
            "整改措施",
            "状态",
        ),
        ("月份", "投诉大类", "问题详细描述"),
        "作为服务问题台账展示，不直接改变总表数值。",
        (),
    ),
    DatasetDefinition(
        "short_video",
        "短视频情况",
        "登记短视频数量、类型、负责人和运营备注。",
        ("9-短视频情况", "短视频情况"),
        ("月份", "短视频数量", "短视频类型", "负责人", "备注"),
        ("月份", "短视频数量"),
        "作为运营台账展示，不直接改变现有总表数值。",
        (),
    ),
)

DEFINITIONS_BY_CODE = {item.code: item for item in DATASET_DEFINITIONS}


def public_definitions() -> list[dict[str, object]]:
    return [
        {
            "code": item.code,
            "name": item.name,
            "description": item.description,
            "columns": list(item.columns),
            "summary_hint": item.summary_hint,
            "metric_codes": list(item.metric_codes),
        }
        for item in DATASET_DEFINITIONS
    ]


def get_definition(code: str) -> DatasetDefinition:
    try:
        return DEFINITIONS_BY_CODE[code]
    except KeyError as exc:
        raise ValueError("不支持的经营分析分表") from exc


def normalized_header(value: object) -> str:
    return re.sub(r"[\s_\-—（）()%％/]+", "", str(value or "").strip()).lower()


def json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        return value.strip()
    return value


def unique_headers(values: list[object]) -> tuple[list[str], list[bool]]:
    headers: list[str] = []
    generated: list[bool] = []
    counts: dict[str, int] = {}
    for index, value in enumerate(values, start=1):
        base = str(value or "").strip()
        is_generated = not base
        if not base:
            base = f"未命名列{index}"
        counts[base] = counts.get(base, 0) + 1
        headers.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
        generated.append(is_generated)
    return headers, generated


def choose_sheet(workbook: object, definition: DatasetDefinition):
    worksheets = workbook.worksheets
    names = {normalized_header(sheet.title): sheet for sheet in worksheets}
    for alias in definition.sheet_aliases:
        match = names.get(normalized_header(alias))
        if match is not None:
            return match
    return workbook.active


def parse_workbook(
    filename: str,
    contents: bytes,
    definition: DatasetDefinition,
) -> dict[str, object]:
    if Path(filename).suffix.lower() != ".xlsx":
        raise ValueError("请上传 .xlsx 格式的文件")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ValueError("导入文件不能超过 10MB")
    try:
        workbook = load_workbook(BytesIO(contents), data_only=True, read_only=True)
        sheet = choose_sheet(workbook, definition)
        raw_rows = list(sheet.iter_rows(values_only=True, max_row=MAX_IMPORT_ROWS + 21))
    except Exception as exc:
        raise ValueError("无法读取该 Excel 文件") from exc
    if not raw_rows:
        raise ValueError("Excel 中没有可导入的数据")

    header_index: int | None = None
    expected = {normalized_header(value) for value in definition.columns}
    fallback: int | None = None
    best_score = -1
    for index, row in enumerate(raw_rows[:20]):
        values = [value for value in row if value not in (None, "")]
        if len(values) < 2:
            continue
        if fallback is None:
            fallback = index
        score = sum(normalized_header(value) in expected for value in values)
        if score > best_score:
            header_index = index
            best_score = score
    if best_score <= 0:
        header_index = fallback
    if header_index is None:
        raise ValueError("没有找到有效的表头行")

    raw_headers = list(raw_rows[header_index])
    last_header = max(
        (index for index, value in enumerate(raw_headers) if value not in (None, "")),
        default=-1,
    )
    if last_header < 0:
        raise ValueError("表头不能为空")
    if last_header + 1 > MAX_IMPORT_COLUMNS:
        raise ValueError(f"分表最多支持 {MAX_IMPORT_COLUMNS} 列")
    headers, generated = unique_headers(raw_headers[: last_header + 1])

    matrix: list[list[object]] = []
    for raw in raw_rows[header_index + 1 :]:
        values = [json_value(value) for value in list(raw)[: len(headers)]]
        values.extend([None] * (len(headers) - len(values)))
        if not any(value not in (None, "") for value in values):
            continue
        matrix.append(values)
        if len(matrix) > MAX_IMPORT_ROWS:
            raise ValueError(f"单次最多导入 {MAX_IMPORT_ROWS} 行")
    if not matrix:
        raise ValueError("表头下方没有可导入的数据")

    keep_indexes = [
        index
        for index in range(len(headers))
        if not generated[index]
        or any(row[index] not in (None, "") for row in matrix)
    ]
    columns = [headers[index] for index in keep_indexes]
    rows = [
        {columns[position]: row[index] for position, index in enumerate(keep_indexes)}
        for row in matrix
    ]
    present = {normalized_header(column) for column in columns}
    missing = [
        column for column in definition.required_columns if normalized_header(column) not in present
    ]
    warnings = []
    if missing:
        warnings.append(f"未识别推荐字段：{'、'.join(missing)}；数据仍可导入，但可能无法自动汇总。")
    return {
        "sheet_name": sheet.title,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "preview_rows": rows[:PREVIEW_ROWS],
        "warnings": warnings,
    }


def find_column(rows: list[dict[str, object]], aliases: tuple[str, ...]) -> str | None:
    if not rows:
        return None
    columns = list(rows[0])
    normalized = {normalized_header(column): column for column in columns}
    for alias in aliases:
        match = normalized.get(normalized_header(alias))
        if match:
            return match
    return None


def number(value: object) -> Decimal | None:
    if value in (None, "", "-", "--"):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip().replace(",", "").replace("，", "")
    if text.endswith(("%", "％")):
        text = text[:-1]
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def sum_column(rows: list[dict[str, object]], aliases: tuple[str, ...]) -> Decimal | None:
    column = find_column(rows, aliases)
    if column is None:
        return None
    values = [number(row.get(column)) for row in rows]
    usable = [value for value in values if value is not None]
    return sum(usable, Decimal("0")) if usable else None


def summarize_rows(dataset_type: str, rows: list[dict[str, object]]) -> dict[str, Decimal]:
    if dataset_type == "shipping_orders":
        value = sum_column(rows, ("发货单量", "单量"))
        return {"shipping_orders": value} if value is not None else {}
    if dataset_type == "return_items":
        value = sum_column(rows, ("退货件数", "退件件数"))
        return {"return_items": value} if value is not None else {}
    if dataset_type == "staffing":
        value = sum_column(rows, ("正式工人数",))
        return {"staff_adjustment": value} if value is not None else {}
    if dataset_type == "supplier_changes":
        column = find_column(rows, ("供应商名称",))
        if column is None:
            return {}
        names = {str(row.get(column) or "").strip() for row in rows}
        names.discard("")
        return {"supplier_change": Decimal(len(names))} if names else {}
    if dataset_type != "customer_changes":
        return {}

    type_column = find_column(rows, ("变化类型", "客户类型"))
    quantity_column = find_column(rows, ("数量", "客户数量"))
    if type_column is None:
        return {}
    totals = {
        "new_customers": Decimal("0"),
        "lost_customers": Decimal("0"),
        "prospective_customers": Decimal("0"),
    }
    matched = False
    for row in rows:
        change_type = str(row.get(type_column) or "").strip()
        code = None
        if "新" in change_type:
            code = "new_customers"
        elif "流失" in change_type:
            code = "lost_customers"
        elif "意向" in change_type:
            code = "prospective_customers"
        if code is None:
            continue
        quantity = number(row.get(quantity_column)) if quantity_column else Decimal("1")
        totals[code] += quantity if quantity is not None else Decimal("1")
        matched = True
    return totals if matched else {}


def build_template(definition: DatasetDefinition) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = definition.name[:31]
    sheet.append(list(definition.columns))
    sheet.freeze_panes = "A2"
    fill = PatternFill("solid", fgColor="DCEAFF")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="24436C")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for index, column in enumerate(definition.columns, start=1):
        sheet.column_dimensions[chr(64 + index) if index <= 26 else "A"].width = max(
            14, min(28, len(column) * 2 + 4)
        )
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
