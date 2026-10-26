import asyncio
import logging
import re
from datetime import datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from budget import budget_warnings, monthly_summary
from categoriser import model, suggest_categories
from config import (
    ALLOWED_USER_IDS,
    DEFAULT_CURRENCY,
    DUPLICATE_CHECK_DAYS,
    OTHER_CURRENCIES,
    PAYMENT_METHODS,
    TELEGRAM_BOT_TOKEN,
    TIMEZONE,
    add_custom_category,
    load_categories,
)
from sheets import append_expense, find_recent_duplicate, get_expenses
from train import train

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DUPLICATE_CHECK, DATE, DATE_INPUT, CURRENCY, CURRENCY_INPUT, CATEGORY, CATEGORY_INPUT, PAYMENT, CONFIRM = range(9)

CANCEL_BUTTON = InlineKeyboardButton("❌ Cancel", callback_data="cancel")

AMOUNT_FIRST = re.compile(r"^\$?(\d+\.?\d*)\s+(.+)$")
ITEM_FIRST = re.compile(r"^(.+?)\s+\$?(\d+\.?\d*)$")

TZ = ZoneInfo(TIMEZONE)
TELEGRAM_CALLBACK_LIMIT = 64  # bytes allowed in a button's callback_data

HELP_TEXT = (
    "💰 <b>Expenditure Tracker</b>\n\n"
    "Send me your expense like:\n"
    "<code>12.50 chicken rice</code>\n\n"
    "I'll help you categorise and log it!\n\n"
    "/summary — this month's spending and budgets\n"
    "/summary 2026-09 — a past month\n"
    "/train — improve category suggestions now (also runs weekly)\n"
    "/cancel — stop logging the current expense"
)


def _now() -> datetime:
    return datetime.now(TZ)


def _date_keyboard() -> InlineKeyboardMarkup:
    today = _now()
    buttons = []
    for label, days_ago in (("Today", 0), ("Yesterday", 1), ("2 days ago", 2)):
        day = today - timedelta(days=days_ago)
        buttons.append([InlineKeyboardButton(
            f"{label} ({day.strftime('%d %b')})", callback_data=f"date:{day.strftime('%Y-%m-%d')}"
        )])
    buttons.append([InlineKeyboardButton("📅 Choose another date", callback_data="date:custom")])
    buttons.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(buttons)


def _currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Yes, {DEFAULT_CURRENCY}", callback_data=f"cur:{DEFAULT_CURRENCY}"),
            InlineKeyboardButton("No, other currency", callback_data="cur:other"),
        ],
        [CANCEL_BUTTON],
    ])


def _other_currency_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for cur in OTHER_CURRENCIES:
        row.append(InlineKeyboardButton(cur, callback_data=f"cur:{cur}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Other (type it)", callback_data="cur:type")])
    buttons.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(buttons)


def _category_keyboard(selected: set[str], suggested: str) -> InlineKeyboardMarkup:
    categories = load_categories()
    buttons = []
    for cat in categories:
        label = cat
        if cat in selected:
            label = f"✓ {cat}"
        elif cat == suggested and not selected:
            label = f"★ {cat}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"cat:{cat}")])
    buttons.append([InlineKeyboardButton("Other (type it)", callback_data="cat:other")])
    buttons.append([InlineKeyboardButton("✅ Done", callback_data="cat:done")])
    buttons.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(buttons)


def _payment_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(pm, callback_data=f"pay:{pm}")] for pm in PAYMENT_METHODS]
    buttons.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(buttons)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm:yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="confirm:no"),
        ]
    ])


def _expense_header(context: ContextTypes.DEFAULT_TYPE) -> str:
    return f"📝 <b>{escape(context.user_data['item'])}</b> — {context.user_data['amount']:.2f}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")


async def unauthorised(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.warning("Ignored message from unauthorised user %s", user.id if user else None)
    if update.message and user:
        await update.message.reply_text(
            f"Sorry, this bot is private.\n\nYour Telegram user ID is <code>{user.id}</code>. "
            "If this is your bot, add that number to ALLOWED_USER_IDS and restart it.",
            parse_mode="HTML",
        )


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = AMOUNT_FIRST.match(text)
    if match:
        amount = float(match.group(1))
        item = match.group(2).strip()
    else:
        match = ITEM_FIRST.match(text)
        if match:
            item = match.group(1).strip()
            amount = float(match.group(2))
        else:
            await update.message.reply_text("Format: <amount> <item> or <item> <amount>\nExample: 12.50 chicken rice")
            return ConversationHandler.END

    context.user_data["amount"] = amount
    context.user_data["item"] = item

    try:
        dup_date = find_recent_duplicate(item, amount, _now().date(), DUPLICATE_CHECK_DAYS)
    except Exception:
        logger.exception("Duplicate check failed")
        dup_date = None

    if dup_date:
        await update.message.reply_text(
            f"⚠️ <b>{escape(item)}</b> ({amount:.2f}) was already added on <b>{dup_date:%Y-%m-%d}</b>.\n\nAdd again?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Yes, add again", callback_data="dup:yes"),
                    InlineKeyboardButton("No, cancel", callback_data="dup:no"),
                ],
                [CANCEL_BUTTON],
            ]),
        )
        return DUPLICATE_CHECK

    await update.message.reply_text(
        f"{_expense_header(context)}\n\nWhen was this expense?",
        parse_mode="HTML",
        reply_markup=_date_keyboard(),
    )
    return DATE


async def duplicate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "dup:no":
        try:
            await query.edit_message_text("❌ Cancelled.")
        except BadRequest:
            pass
        return ConversationHandler.END

    try:
        await query.edit_message_text(
            f"{_expense_header(context)}\n\nWhen was this expense?",
            parse_mode="HTML",
            reply_markup=_date_keyboard(),
        )
    except BadRequest:
        pass
    return DATE


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    date_str = query.data.removeprefix("date:")

    if date_str == "custom":
        try:
            await query.edit_message_text(
                "Type the date (e.g. 2026-08-10 or 10/08/2026):"
            )
        except BadRequest:
            pass
        return DATE_INPUT

    context.user_data["date"] = date_str

    try:
        await query.edit_message_text(
            f"Date: {date_str}\n\nIs this in {DEFAULT_CURRENCY}?",
            reply_markup=_currency_keyboard(),
        )
    except BadRequest:
        pass
    return CURRENCY


async def date_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    date_str = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y"):
        try:
            date_str = datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    if date_str is None:
        await update.message.reply_text(
            "Couldn't understand that date. Try formats like 2026-08-10 or 10/08/2026:"
        )
        return DATE_INPUT

    context.user_data["date"] = date_str
    await update.message.reply_text(
        f"Date: {date_str}\n\nIs this in {DEFAULT_CURRENCY}?",
        reply_markup=_currency_keyboard(),
    )
    return CURRENCY


async def currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.removeprefix("cur:")

    if data == "other":
        try:
            await query.edit_message_text(
                "Select currency:",
                reply_markup=_other_currency_keyboard(),
            )
        except BadRequest:
            pass
        return CURRENCY

    if data == "type":
        try:
            await query.edit_message_text("Type the currency code (e.g. IDR, VND):")
        except BadRequest:
            pass
        return CURRENCY_INPUT

    context.user_data["currency"] = data
    try:
        return await _show_category_step(query, context)
    except BadRequest:
        return CATEGORY


def _prepare_category_step(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    suggested = suggest_categories(context.user_data["item"])[0]
    context.user_data["suggested"] = suggested
    context.user_data["selected_categories"] = set()
    text = (
        f"Currency: {escape(context.user_data['currency'])}\n\n"
        f"Suggested category: <b>{escape(suggested)}</b>\n"
        "Select one or more categories, then press Done:"
    )
    return text, _category_keyboard(set(), suggested)


async def currency_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        await update.message.reply_text("Please type a 3-letter currency code, e.g. IDR or VND:")
        return CURRENCY_INPUT
    context.user_data["currency"] = currency

    text, keyboard = _prepare_category_step(context)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    return CATEGORY


async def _show_category_step(query, context: ContextTypes.DEFAULT_TYPE):
    text, keyboard = _prepare_category_step(context)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    return CATEGORY


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.removeprefix("cat:")

    if data == "done":
        selected = context.user_data.get("selected_categories", set())
        if not selected:
            selected = {context.user_data["suggested"]}
            context.user_data["selected_categories"] = selected

        await query.edit_message_text(
            f"Categories: {', '.join(sorted(selected))}\n\nSelect payment method:",
            reply_markup=_payment_keyboard(),
        )
        return PAYMENT

    if data == "other":
        await query.edit_message_text("Type your custom category:")
        return CATEGORY_INPUT

    selected = context.user_data.get("selected_categories", set())
    if data in selected:
        selected.discard(data)
    else:
        selected.add(data)
    context.user_data["selected_categories"] = selected

    await query.edit_message_reply_markup(
        reply_markup=_category_keyboard(selected, context.user_data["suggested"])
    )
    return CATEGORY


async def category_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_cat = " ".join(update.message.text.split())
    if "," in custom_cat:
        await update.message.reply_text("Category names can't contain commas. Type it again:")
        return CATEGORY_INPUT
    if len(f"cat:{custom_cat}".encode()) > TELEGRAM_CALLBACK_LIMIT:
        await update.message.reply_text("That name is too long. Type a shorter one:")
        return CATEGORY_INPUT

    add_custom_category(custom_cat)
    selected = context.user_data.get("selected_categories", set())
    selected.add(custom_cat)
    context.user_data["selected_categories"] = selected

    await update.message.reply_text(
        f"Added: {custom_cat}\n\n"
        "Select more categories or press Done:",
        reply_markup=_category_keyboard(selected, context.user_data["suggested"]),
    )
    return CATEGORY


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    payment = query.data.removeprefix("pay:")
    context.user_data["payment"] = payment

    amount = context.user_data["amount"]
    item = context.user_data["item"]
    date = context.user_data["date"]
    cats = ", ".join(sorted(context.user_data["selected_categories"]))

    await query.edit_message_text(
        f"📋 <b>Summary</b>\n\n"
        f"Date: {date}\n"
        f"Item: {escape(item)}\n"
        f"Amount: {escape(context.user_data['currency'])} {amount:.2f}\n"
        f"Category: {escape(cats)}\n"
        f"Payment: {escape(payment)}\n\n"
        "Confirm?",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard(),
    )
    return CONFIRM


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data != "confirm:yes":
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END

    categories = sorted(context.user_data["selected_categories"])
    try:
        append_expense(
            context.user_data["date"],
            context.user_data["amount"],
            context.user_data["currency"],
            context.user_data["item"],
            categories,
            context.user_data["payment"],
        )
    except Exception:
        logger.exception("Failed to save expense")
        await query.edit_message_text("❌ Failed to save. Try again later.")
        return ConversationHandler.END

    message = "✅ Saved to Google Sheets!"
    if context.user_data["currency"] == DEFAULT_CURRENCY:
        try:
            expense_date = datetime.strptime(context.user_data["date"], "%Y-%m-%d")
            warnings = budget_warnings(get_expenses(), expense_date.year, expense_date.month, categories)
            if warnings:
                message += "\n\n<b>Budget check</b>\n" + "\n".join(warnings)
        except Exception:
            logger.exception("Budget check failed")
    await query.edit_message_text(message, parse_mode="HTML")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("❌ Cancelled.")
    except BadRequest:
        pass
    return ConversationHandler.END


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = _now()
    year, month = today.year, today.month
    if context.args:
        try:
            parsed = datetime.strptime(context.args[0], "%Y-%m")
            year, month = parsed.year, parsed.month
        except ValueError:
            await update.message.reply_text("Usage: /summary or /summary 2026-09")
            return
    try:
        text = monthly_summary(get_expenses(), year, month)
    except Exception:
        logger.exception("Summary failed")
        text = "❌ Couldn't read your Google Sheet. Try again later."
    await update.message.reply_text(text, parse_mode="HTML")


async def train_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Learning from your expenses… this can take a minute.")
    try:
        report = await asyncio.to_thread(train, model)
    except Exception:
        logger.exception("Training failed")
        report = "❌ Training failed. Check the logs."
    await update.message.reply_text(report)


async def weekly_train(context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("Weekly training: %s", await asyncio.to_thread(train, model))
    except Exception:
        logger.exception("Weekly training failed")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    allowed = filters.User(user_id=ALLOWED_USER_IDS)
    if not ALLOWED_USER_IDS:
        logger.warning("ALLOWED_USER_IDS is empty — the bot will only reply with each sender's user ID.")

    conv = ConversationHandler(
        entry_points=[MessageHandler(allowed & filters.TEXT & ~filters.COMMAND, handle_expense)],
        states={
            DUPLICATE_CHECK: [CallbackQueryHandler(duplicate_callback, pattern=r"^dup:")],
            DATE: [CallbackQueryHandler(date_callback, pattern=r"^date:")],
            DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_input_handler)],
            CURRENCY: [CallbackQueryHandler(currency_callback, pattern=r"^cur:")],
            CURRENCY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, currency_input_handler)],
            CATEGORY: [CallbackQueryHandler(category_callback, pattern=r"^cat:")],
            CATEGORY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_input_handler)],
            PAYMENT: [CallbackQueryHandler(payment_callback, pattern=r"^pay:")],
            CONFIRM: [CallbackQueryHandler(confirm_callback, pattern=r"^confirm:")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_callback, pattern=r"^cancel$"),
        ],
    )

    app.add_handler(MessageHandler(~allowed, unauthorised))
    app.add_handler(CommandHandler(["start", "help"], start, filters=allowed))
    app.add_handler(CommandHandler("summary", summary, filters=allowed))
    app.add_handler(CommandHandler("train", train_command, filters=allowed))
    app.add_handler(conv)

    # Retrain category suggestions every Sunday at 3am local time.
    app.job_queue.run_daily(weekly_train, time=time(3, 0, tzinfo=ZoneInfo(TIMEZONE)), days=(0,))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
