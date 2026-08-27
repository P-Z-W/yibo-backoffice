"""Compatibility settings for the proven reconciliation calculation engine."""

from datetime import datetime, timedelta

from app.core.config import settings as app_settings

_today = datetime.now()
_first_of_month = _today.replace(day=1)
_last_month_day = _first_of_month - timedelta(days=1)
_process_first_day = _last_month_day.replace(day=1)

PROCESS_MONTH = _last_month_day.strftime("%Y-%m")
CONFIG_FOLDER = str(app_settings.storage_path / "config")
DATA_FOLDER = str(app_settings.storage_path / "data" / PROCESS_MONTH)
OUTPUT_FOLDER = str(app_settings.storage_path / "output" / PROCESS_MONTH)

EXPRESS_INPUT_ST = "申通账单.xlsx"
EXPRESS_INPUT_ZT = "中通账单.xlsx"
EXPRESS_OUTPUT_FILE = "清洗合并总账单.xlsx"
RESULT_FILE = "最终对账结果.xlsx"
ORDER_FILE_PREFIX = "毅播快递数据_"
SQL_FILE_PATH = str(app_settings.storage_path / "private" / "SQL-config.txt")

DB_CONFIG = app_settings.remote_database_config
LOCAL_DB_CONFIG = app_settings.local_database_config

SQL_EXTEND_DAYS_BEFORE = 15
SQL_EXTEND_DAYS_AFTER = 5
SQL_START_DATE = (_process_first_day - timedelta(days=SQL_EXTEND_DAYS_BEFORE)).strftime(
    "%Y-%m-%d 00:00:00"
)
SQL_END_DATE = (_last_month_day + timedelta(days=SQL_EXTEND_DAYS_AFTER)).strftime(
    "%Y-%m-%d 23:59:59"
)
