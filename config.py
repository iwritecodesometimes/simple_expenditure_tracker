import json
import os
import sys

# ---------------------------------------------------------------------------
# Secrets — these come from your .env file (or Railway "Variables").
# You should not need to edit anything in this section.
# ---------------------------------------------------------------------------


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Missing setting: {name}. Add it to your .env file (or Railway Variables) — see README.")
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEETS_ID = _require("GOOGLE_SHEETS_ID")
# Optional: if empty, the bot reads service_account.json from the project folder instead.
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# Telegram user IDs allowed to use the bot, comma separated (e.g. "123456789,987654321").
# If you don't know yours, leave it empty, message the bot, and it will tell you.
ALLOWED_USER_IDS = [
    int(uid) for uid in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if uid
]

# Where the bot keeps files it creates (your custom categories, training results).
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# YOUR SETTINGS — edit these to suit you.
# After editing, restart the bot (see README, "Changing your settings").
# ---------------------------------------------------------------------------

# Your home currency. Used as the default and for budget totals.
DEFAULT_CURRENCY = "SGD"

# Your time zone, so "today" and "this month" match your clock.
# Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones (the "TZ identifier" column)
TIMEZONE = "Asia/Singapore"

# Other currencies offered as buttons when you say an expense isn't in DEFAULT_CURRENCY.
OTHER_CURRENCIES = ["MYR", "JPY", "KRW", "CNY", "USD", "EUR", "THB", "TWD"]

# Your spending categories. One per line, in quotes, followed by a comma.
DEFAULT_CATEGORIES = [
    "Restaurant",
    "Hawker Centre/Coffee Shop",
    "Entertainment",
    "Shopping",
    "Subscriptions",
    "Health",
    "Education",
    "Transport",
    "Table tennis/gym",
    "Food/water",
    "Investment",
]

# Your payment options. One per line, in quotes, followed by a comma.
PAYMENT_METHODS = [
    "PayLah",
    "Maybank Credit",
    "DBS Debit",
    "YouTrip",
    "Cash",
]

# Monthly budgets, in DEFAULT_CURRENCY. Leave out any category you don't want a budget for.
# The category name must match one of your categories exactly.
BUDGETS = {
    "Restaurant": 300,
    "Hawker Centre/Coffee Shop": 250,
    "Entertainment": 100,
    "Shopping": 200,
}

# Warn you after saving an expense once a category reaches this % of its budget.
BUDGET_WARNING_PERCENT = 80

# Ask "add again?" if you log the same item and amount within this many days (0 = never ask).
DUPLICATE_CHECK_DAYS = 1

# ---------------------------------------------------------------------------

CUSTOM_CATEGORIES_PATH = os.path.join(DATA_DIR, "custom_categories.json")


def load_categories() -> list[str]:
    cats = list(DEFAULT_CATEGORIES)
    if os.path.exists(CUSTOM_CATEGORIES_PATH):
        with open(CUSTOM_CATEGORIES_PATH) as f:
            custom = json.load(f)
        for c in custom:
            if c not in cats:
                cats.append(c)
    return cats


def add_custom_category(category: str):
    custom = []
    if os.path.exists(CUSTOM_CATEGORIES_PATH):
        with open(CUSTOM_CATEGORIES_PATH) as f:
            custom = json.load(f)
    if category not in custom and category not in DEFAULT_CATEGORIES:
        custom.append(category)
        with open(CUSTOM_CATEGORIES_PATH, "w") as f:
            json.dump(custom, f)
