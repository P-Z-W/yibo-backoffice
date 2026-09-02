"""Invoice OCR provider adapter with editable, structured output."""

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import settings

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_VAT_INVOICE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice"


class InvoiceOcrError(RuntimeError):
    """A user-facing invoice OCR error."""


class InvoiceOcrNotConfiguredError(InvoiceOcrError):
    """Raised when the selected provider has not been configured."""


@dataclass(slots=True)
class InvoiceRecognitionResult:
    entity_name: str
    tax_number: str
    amount: Decimal | None
    invoice_code: str
    invoice_number: str
    invoice_date: datetime | None
    status: str
    message: str
    provider: str
    request_id: str


_token_value = ""
_token_expires_at = 0.0


def _field_text(value: Any) -> str:
    if isinstance(value, dict):
        return _field_text(value.get("word", value.get("words", "")))
    if isinstance(value, list):
        values = [_field_text(item) for item in value]
        return "".join(item for item in values if item)
    return str(value or "").strip()


def _first_field(fields: dict[str, Any], *names: str) -> str:
    for name in names:
        text = _field_text(fields.get(name))
        if text:
            return text
    return ""


def _parse_amount(value: str) -> Decimal | None:
    normalized = value.replace(",", "").replace("，", "")
    match = re.search(r"-?\d+(?:\.\d{1,2})?", normalized)
    if not match:
        return None
    try:
        return Decimal(match.group()).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _parse_date(value: str) -> datetime | None:
    normalized = value.replace("年", "-").replace("月", "-").replace("日", "").strip()
    for pattern in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def parse_baidu_invoice(payload: dict[str, Any]) -> InvoiceRecognitionResult:
    """Normalize Baidu VAT invoice fields into the application's compact model."""
    if payload.get("error_code"):
        message = str(payload.get("error_msg") or "发票识别服务返回错误")
        raise InvoiceOcrError(f"发票识别失败：{message}")
    fields = payload.get("words_result")
    if not isinstance(fields, dict):
        raise InvoiceOcrError("未识别到有效的增值税发票内容")

    entity_name = _first_field(fields, "PurchaserName", "Purchaser", "BuyerName")
    tax_number = re.sub(
        r"\s+",
        "",
        _first_field(fields, "PurchaserRegisterNum", "PurchaserTaxNo", "BuyerTaxNo"),
    ).upper()
    amount_text = _first_field(
        fields,
        "AmountInFiguers",
        "AmountInFigures",
        "PriceTaxLow",
        "TotalTax",
    )
    amount = _parse_amount(amount_text)
    invoice_code = _first_field(fields, "InvoiceCode", "InvoiceCodeConfirm")
    invoice_number = _first_field(fields, "InvoiceNum", "InvoiceNumber", "InvoiceNumConfirm")
    invoice_date = _parse_date(_first_field(fields, "InvoiceDate", "Date"))

    missing = []
    if not entity_name:
        missing.append("主体")
    if not tax_number:
        missing.append("税号")
    if amount is None:
        missing.append("金额")
    status = "needs_review" if missing else "success"
    message = f"未识别到{'、'.join(missing)}，请手动补充" if missing else "识别成功，请核对后提交"
    return InvoiceRecognitionResult(
        entity_name=entity_name,
        tax_number=tax_number,
        amount=amount,
        invoice_code=invoice_code,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        status=status,
        message=message,
        provider="baidu",
        request_id=str(payload.get("log_id") or ""),
    )


def _get_baidu_token() -> str:
    global _token_expires_at, _token_value
    if _token_value and time.monotonic() < _token_expires_at:
        return _token_value
    if not settings.invoice_ocr_available:
        raise InvoiceOcrNotConfiguredError(
            "发票识别服务尚未配置，可先手动填写主体、税号和发票金额"
        )
    try:
        response = httpx.post(
            BAIDU_TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": settings.baidu_ocr_api_key,
                "client_secret": settings.baidu_ocr_secret_key,
            },
            timeout=settings.invoice_ocr_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise InvoiceOcrError("暂时无法连接发票识别服务") from exc
    token = str(payload.get("access_token") or "")
    if not token:
        raise InvoiceOcrError("发票识别服务鉴权失败，请检查配置")
    expires_in = max(60, int(payload.get("expires_in") or 3600) - 300)
    _token_value = token
    _token_expires_at = time.monotonic() + expires_in
    return token


def recognize_invoice(contents: bytes, suffix: str) -> InvoiceRecognitionResult:
    provider = settings.invoice_ocr_provider.strip().lower()
    if provider != "baidu":
        raise InvoiceOcrNotConfiguredError("当前发票识别服务未配置")
    if not settings.invoice_ocr_available:
        raise InvoiceOcrNotConfiguredError(
            "发票识别服务尚未配置，可先手动填写主体、税号和发票金额"
        )
    encoded = base64.b64encode(contents).decode("ascii")
    form_key = "pdf_file" if suffix == ".pdf" else "image"
    try:
        response = httpx.post(
            BAIDU_VAT_INVOICE_URL,
            params={"access_token": _get_baidu_token()},
            data={form_key: encoded, "type": "normal"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=settings.invoice_ocr_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise InvoiceOcrError("发票识别请求失败，请稍后重试或手动填写") from exc
    return parse_baidu_invoice(payload)
