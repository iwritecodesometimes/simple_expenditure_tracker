import base64
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import DateTimeOption, ValueRenderOption

from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEETS_ID

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json")

HEADERS = ["Date", "Amount", "Currency", "Item", "Category", "Payment Method"]


@dataclass
class Expense:
    date: date
    amount: float
    currency: str
    item: str
    categories: list[str]
    payment_method: str


def _service_account_info() -> dict:
    raw = GOOGLE_SERVICE_ACCOUNT_JSON
    if raw:
        # Accept either the raw JSON or a base64-encoded copy of it.
        return json.loads(raw if raw.startswith("{") else base64.b64decode(raw))
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        with open(SERVICE_ACCOUNT_FILE) as f:
            return json.load(f)
    raise RuntimeError(
        "No Google credentials found. Put service_account.json in the project folder "
        "or set GOOGLE_SERVICE_ACCOUNT_JSON — see README."
    )


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(_service_account_info(), scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet() -> gspread.Worksheet:
    return _get_client().open_by_key(GOOGLE_SHEETS_ID).sheet1


def _ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if not first_row:
        sheet.append_row(HEADERS, value_input_option="USER_ENTERED")


def _parse_date(value) -> date | None:
    # Google Sheets stores dates as days since 1899-12-30 when it recognises them as dates.
    if isinstance(value, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(value))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def get_expenses() -> list[Expense]:
    rows = _get_sheet().get_all_values(
        value_render_option=ValueRenderOption.unformatted,
        date_time_render_option=DateTimeOption.serial_number,
    )
    expenses = []
    for row in rows[1:]:
        if len(row) < 6:
            continue
        expense_date = _parse_date(row[0])
        try:
            amount = float(row[1])
        except (TypeError, ValueError):
            continue
        if expense_date is None:
            continue
        expenses.append(Expense(
            date=expense_date,
            amount=amount,
            currency=str(row[2]).strip().upper(),
            item=str(row[3]).strip(),
            categories=[c.strip() for c in str(row[4]).split(",") if c.strip()],
            payment_method=str(row[5]).strip(),
        ))
    return expenses


def find_recent_duplicate(item: str, amount: float, today: date, days: int) -> date | None:
    if days <= 0:
        return None
    cutoff = today - timedelta(days=days)
    for expense in reversed(get_expenses()):
        if (
            expense.date >= cutoff
            and expense.item.lower() == item.lower()
            and abs(expense.amount - amount) < 0.005
        ):
            return expense.date
    return None


def append_expense(date: str, amount: float, currency: str, item: str, categories: list[str], payment_method: str):
    sheet = _get_sheet()
    _ensure_headers(sheet)
    row = [
        date,
        f"{amount:.2f}",
        currency,
        item,
        ", ".join(categories),
        payment_method,
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")
