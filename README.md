# Expenditure Tracker Telegram Bot

A private Telegram bot that logs your spending to a Google Sheet and keeps you on budget.

- Log an expense by sending a message like `12.50 chicken rice` or `chicken rice 12.50`
- Tap buttons to pick the date, currency, category and payment method — the bot suggests a category for you
- Set monthly budgets per category; the bot warns you when you're close to or over a limit
- Send `/summary` any time to see this month's spending against your budgets
- Category suggestions get smarter every week as the bot learns from what you log
- Everything is saved to a Google Sheet you own

Setup takes about 30–45 minutes, and you don't need to know how to code. Follow the steps in order.

---

## What you'll need

- A **Telegram** account
- A **Google** account
- A place for the bot to run. Pick one:
  - **Railway** (recommended): runs in the cloud 24/7, and you set it up entirely in your web browser. Railway is a paid service with a free trial; check [railway.com/pricing](https://railway.com/pricing). You'll also need a free **GitHub** account.
  - **Your own computer**: free, but the bot only works while your computer is on. You'll need to install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

---

## Step 1: Create your Telegram bot

1. In Telegram, search for **@BotFather** and open a chat with it.
2. Send `/newbot`.
3. Choose a display name (anything, e.g. "My Spending"), then a username ending in `bot` (e.g. `alex_spending_bot`).
4. BotFather replies with a **token**, a long code like `7123456789:AAH...`. Copy it into a note; you'll need it in Step 5.

> Keep the token secret. Anyone who has it can control your bot.

## Step 2: Give the bot access to Google Sheets

Google needs a "service account", which is a robot Google account that the bot uses to write to your sheet.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in.
2. At the top, click the project picker → **New Project**. Name it anything (e.g. "Expense Bot") and click **Create**. Make sure the new project is selected.
3. Open the [Google Sheets API page](https://console.cloud.google.com/apis/library/sheets.googleapis.com) and click **Enable**.
4. Go to **APIs & Services → Credentials**, click **+ Create Credentials → Service account**.
5. Give it a name (e.g. "expense-bot") and click **Done**. You can skip the optional steps.
6. Click the service account you just created, open the **Keys** tab, then **Add Key → Create new key → JSON → Create**. A file downloads.
7. Rename the downloaded file to exactly `service_account.json`.
8. Open the file in Notepad (Windows) or TextEdit (Mac) and find the line starting with `"client_email"`. Copy the email address on that line; it looks like `expense-bot@your-project.iam.gserviceaccount.com`.

> Treat `service_account.json` like a password. **Never upload it to GitHub.**

## Step 3: Create your Google Sheet

1. Create a new, empty sheet at [sheets.new](https://sheets.new). Name it whatever you like.
2. Click **Share**, paste the `client_email` address from Step 2, set it to **Editor**, untick "Notify people", and click **Share**.
3. Look at the sheet's web address. The **Sheet ID** is the long code between `/d/` and `/edit`:

   ```
   https://docs.google.com/spreadsheets/d/1AbC...XyZ/edit#gid=0
                                          └─ Sheet ID ─┘
   ```

   Copy it into your note.

The bot adds the column headers itself the first time you log an expense.

## Step 4: Choose your categories, payment methods and budgets

All your personal settings are in the file **`config.py`**, under the heading `YOUR SETTINGS`. You'll edit it in Step 5 (Railway: on the GitHub website; your computer: in Notepad or TextEdit).

| Setting | What it means | Example |
|---|---|---|
| `DEFAULT_CURRENCY` | Your home currency | `"SGD"`, `"GBP"`, `"AUD"` |
| `TIMEZONE` | So "today" and "this month" match your clock ([list of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones), use the "TZ identifier" column) | `"Asia/Singapore"`, `"Europe/London"` |
| `OTHER_CURRENCIES` | Extra currency buttons for when you travel | `["MYR", "JPY", "USD"]` |
| `DEFAULT_CATEGORIES` | Your spending categories | see below |
| `PAYMENT_METHODS` | Your cards, wallets and cash | see below |
| `BUDGETS` | Monthly limit per category, in your home currency | see below |
| `BUDGET_WARNING_PERCENT` | Warn you when a category reaches this % of its budget | `80` |
| `DUPLICATE_CHECK_DAYS` | Ask "add again?" if you log the same item and amount within this many days. `0` turns it off | `1` |

**Rules when editing lists:** every name goes in `"double quotes"` and is followed by a comma. Keep the square brackets `[ ]` and curly brackets `{ }` as they are.

For example, to make your categories Groceries, Eating out and Bills:

```python
DEFAULT_CATEGORIES = [
    "Groceries",
    "Eating out",
    "Bills",
]
```

Payment methods work the same way:

```python
PAYMENT_METHODS = [
    "Visa",
    "Apple Pay",
    "Cash",
]
```

Budgets pair a category name (spelled **exactly** as in your category list) with a monthly amount. Amounts have no quotes. Leave out any category you don't want a budget for:

```python
BUDGETS = {
    "Groceries": 400,
    "Eating out": 250,
}
```

You can also add categories from inside the bot by tapping **Other (type it)**. They're remembered for next time.

## Step 5: Start the bot

Follow **either** Option A or Option B.

### Option A: Railway (runs 24/7)

1. **Copy this project to your GitHub.** Sign in to [GitHub](https://github.com), open this project's page, and click **Fork → Create fork**.
2. **Edit your settings.** In *your* fork, click `config.py`, then the pencil ✏️ icon. Make your changes from Step 4 and click **Commit changes**.
3. **Encode your Google key** so it fits in a single setting. Open a terminal:
   - **Windows:** press Start, type `PowerShell`, open it, and run (adjust the path if your file isn't in Downloads):
     ```powershell
     [Convert]::ToBase64String([IO.File]::ReadAllBytes("$HOME\Downloads\service_account.json")) | Set-Clipboard
     ```
   - **Mac:** open the Terminal app and run:
     ```bash
     base64 -i ~/Downloads/service_account.json | pbcopy
     ```

   Nothing appears on screen, but the encoded key is now copied. Paste it into your note.
4. **Create the Railway project.** Sign in to [Railway](https://railway.com) with GitHub, click **New Project → Deploy from GitHub repo**, and pick your fork.
5. **Add your secrets.** Click the new service → **Variables** tab, and add each of these with **+ New Variable**:

   | Name | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | the token from Step 1 |
   | `GOOGLE_SHEETS_ID` | the Sheet ID from Step 3 |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | the encoded key from step 3 above |
   | `ALLOWED_USER_IDS` | leave out for now; see Step 6 |

6. **Add storage** so the bot remembers your custom categories and what it has learned. In your project, add a **Volume** (right-click the project canvas or use **+ Create → Volume**), attach it to your bot service, and set the mount path to:
   ```
   /app/data
   ```
7. Click **Deploy** to apply the changes. The first build takes several minutes. When the service shows **Active**, go to Step 6.

### Option B: Your own computer

1. **Install and open [Docker Desktop](https://www.docker.com/products/docker-desktop/).** Leave it running.
2. **Download this project.** On its GitHub page click the green **Code** button → **Download ZIP**, then unzip it somewhere easy, such as your Documents folder.
3. **Add your Google key.** Move `service_account.json` from Step 2 into the unzipped project folder (the one containing `bot.py`).
4. **Create your settings file.**
   - Make a copy of `.env.example` in the same folder and name the copy `.env` (with the dot at the front and nothing after it).
   - Windows tip: in File Explorer, turn on **View → Show → File name extensions** first. Otherwise Windows may secretly name it `.env.txt`. If the file doesn't show up, use **View → Show → Hidden items**.
   - Mac tip: press **Cmd + Shift + .** in Finder to show files starting with a dot.
   - Open `.env` in Notepad or TextEdit and fill in `TELEGRAM_BOT_TOKEN` and `GOOGLE_SHEETS_ID`. Leave the other lines empty.
5. **Edit `config.py`** with your choices from Step 4 and save it.
6. **Open a terminal in the project folder.**
   - **Windows:** in File Explorer, open the project folder, right-click on an empty space → **Open in Terminal**.
   - **Mac:** right-click the project folder in Finder → **Services → New Terminal at Folder**.
7. **Start the bot:**
   ```
   docker compose up --build -d
   ```
   The first run downloads a lot and can take 5–10 minutes. When it finishes, go to Step 6.

Useful commands (run them from the same folder):

| To… | Run |
|---|---|
| See what the bot is doing / errors | `docker compose logs -f` (press Ctrl+C to stop watching) |
| Stop the bot | `docker compose down` |
| Start it again | `docker compose up -d` |

## Step 6: Make the bot yours only

Anyone can find a Telegram bot, so the bot only answers people you list.

1. In Telegram, search for your bot's username and send it any message, e.g. `hi`.
2. It replies *"Sorry, this bot is private. Your Telegram user ID is 123456789"*. Copy that number.
3. Add it as `ALLOWED_USER_IDS`:
   - **Railway:** add the variable `ALLOWED_USER_IDS` in the **Variables** tab, then click **Deploy**.
   - **Your computer:** put it after `ALLOWED_USER_IDS=` in `.env`, save, and run `docker compose up -d`.
4. Send `/start` to your bot. You should see the welcome message.

To let someone else share the bot (e.g. a partner logging to the same sheet), have them do steps 1–2 and add their ID with a comma: `123456789,987654321`.

---

## Using the bot

**Log an expense:** send the amount and what it was, in either order:

```
12.50 chicken rice
grab to work 18
```

Then tap through the buttons: date → currency → category (★ marks the suggestion, and you can pick more than one) → payment method → **Confirm**.

**Commands:**

| Command | What it does |
|---|---|
| `/summary` | This month's total, each budget with a progress bar, and other categories |
| `/summary 2026-09` | Same, for a past month (year-month) |
| `/train` | Re-learn category suggestions right now (also runs automatically every Sunday) |
| `/cancel` | Stop logging the current expense |
| `/help` | Show the list of commands |

**Budget warnings:** after you save an expense, the bot warns you if that category has reached your warning level (🟠) or gone over budget (🔴) this month.

**Good to know:**
- Budgets and totals count only expenses in your `DEFAULT_CURRENCY`. Foreign-currency spending is listed separately in `/summary`.
- An expense in several categories (e.g. a course that's both Education and Subscriptions) counts in full toward each category's budget, but only once in the monthly total.
- You can edit or delete rows directly in the Google Sheet. The bot reads the sheet fresh each time.

## Your Google Sheet

| Date | Amount | Currency | Item | Category | Payment Method |
|------|--------|----------|------|----------|----------------|
| 2026-08-09 | 12.50 | SGD | chicken rice | Hawker Centre/Coffee Shop | PayLah |

Keep these six columns in this order, and keep your expenses on the **first tab**. You're free to add charts or extra tabs after it.

## Changing your settings later

- **Railway:** edit `config.py` on GitHub (pencil icon → **Commit changes**). Railway redeploys automatically within a few minutes.
- **Your computer:** edit `config.py`, save, then run `docker compose up --build -d` in the project folder.

The bot doesn't notice changes to `config.py` until it's rebuilt as shown above.

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot doesn't reply at all | Check it's running: Railway → service **Deployments → View logs**, or `docker compose logs -f` on your computer. |
| Logs say `Missing setting: ...` | That variable is empty in `.env` / Railway Variables. Fill it in and restart. |
| Bot says "this bot is private" | Your user ID isn't in `ALLOWED_USER_IDS` yet; see Step 6. |
| "❌ Failed to save" | Usually the sheet isn't shared with the service account email (Step 3), or the Google Sheets API isn't enabled (Step 2.3). |
| Logs say `No Google credentials found` | Your computer: `service_account.json` isn't in the project folder, or is named differently. Railway: `GOOGLE_SERVICE_ACCOUNT_JSON` is missing. |
| The bot crashes after you edit `config.py` | Usually a missing quote, comma or bracket. Compare your edit with the examples in Step 4. |
| Custom categories disappear after a Railway update | The volume isn't attached at `/app/data` (Option A, step 6). |

## For developers

- `bot.py`: Telegram conversation flow and commands
- `budget.py`: monthly summary and budget warnings
- `sheets.py`: Google Sheets read/write
- `categoriser.py` / `train.py`: category suggestions using the `all-MiniLM-L6-v2` sentence-transformers model, averaged with your past items per category
- Runtime data (`custom_categories.json`, `trained_embeddings.npz`) is written to `DATA_DIR` (`/app/data` in Docker)
- Run training by hand: `docker compose exec bot python train.py`
