from collections import defaultdict
from datetime import date
from html import escape

from config import BUDGET_WARNING_PERCENT, BUDGETS, DEFAULT_CURRENCY
from sheets import Expense


def _in_month(expenses: list[Expense], year: int, month: int) -> list[Expense]:
    return [e for e in expenses if e.date.year == year and e.date.month == month]


def category_totals(expenses: list[Expense]) -> dict[str, float]:
    """Spend per category in DEFAULT_CURRENCY. An expense with several categories counts toward each."""
    totals: dict[str, float] = defaultdict(float)
    for e in expenses:
        if e.currency == DEFAULT_CURRENCY:
            for cat in e.categories:
                totals[cat] += e.amount
    return totals


def _bar(fraction: float, width: int = 10) -> str:
    filled = min(width, round(fraction * width))
    return "█" * filled + "░" * (width - filled)


def monthly_summary(expenses: list[Expense], year: int, month: int) -> str:
    month_expenses = _in_month(expenses, year, month)
    title = date(year, month, 1).strftime("%B %Y")
    if not month_expenses:
        return f"📊 <b>{title}</b>\n\nNo expenses logged."

    cur = DEFAULT_CURRENCY
    total = sum(e.amount for e in month_expenses if e.currency == cur)
    totals = category_totals(month_expenses)
    lines = [f"📊 <b>{title}</b>", "", f"Total: <b>{cur} {total:.2f}</b>"]

    if BUDGETS:
        lines += ["", "<b>Budgets</b>"]
        for cat, limit in BUDGETS.items():
            spent = totals.get(cat, 0.0)
            fraction = spent / limit if limit else 0
            icon = "🔴" if fraction >= 1 else "🟠" if fraction * 100 >= BUDGET_WARNING_PERCENT else "🟢"
            lines.append(
                f"{icon} {escape(cat)}\n"
                f"   {_bar(fraction)} {spent:.2f} / {limit:.2f} ({fraction:.0%})"
            )

    unbudgeted = {c: v for c, v in totals.items() if c not in BUDGETS}
    if unbudgeted:
        lines += ["", "<b>Other categories</b>"]
        for cat, spent in sorted(unbudgeted.items(), key=lambda kv: -kv[1]):
            lines.append(f"• {escape(cat)}: {spent:.2f}")

    foreign: dict[str, float] = defaultdict(float)
    for e in month_expenses:
        if e.currency != cur:
            foreign[e.currency] += e.amount
    if foreign:
        lines += ["", f"<b>Not in {cur}</b> (not counted above)"]
        for c, amt in sorted(foreign.items()):
            lines.append(f"• {escape(c)} {amt:.2f}")

    if any(len(e.categories) > 1 for e in month_expenses):
        lines += ["", "<i>Expenses in several categories count toward each one.</i>"]

    return "\n".join(lines)


def budget_warnings(expenses: list[Expense], year: int, month: int, categories: list[str]) -> list[str]:
    """Warnings for the given categories that have reached BUDGET_WARNING_PERCENT this month."""
    totals = category_totals(_in_month(expenses, year, month))
    warnings = []
    for cat in categories:
        limit = BUDGETS.get(cat)
        if not limit:
            continue
        spent = totals.get(cat, 0.0)
        percent = spent / limit * 100
        if percent >= 100:
            warnings.append(f"🔴 {escape(cat)}: over budget — {DEFAULT_CURRENCY} {spent:.2f} of {limit:.2f} ({percent:.0f}%)")
        elif percent >= BUDGET_WARNING_PERCENT:
            warnings.append(f"🟠 {escape(cat)}: {DEFAULT_CURRENCY} {spent:.2f} of {limit:.2f} used ({percent:.0f}%)")
    return warnings
