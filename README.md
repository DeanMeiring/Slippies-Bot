# SlippiesBot

A Telegram bot that turns a photo of a receipt ("slip") into a logged expense — snap it, send it, and it lands as a new row in an Excel spreadsheet. No app, no manual data entry.

This is a personal project Dean built to track his (and a friend's) expenses without a dedicated app.

## What it does

- 📸 **Photo-based slip logging** — send the bot a photo of a receipt and it's parsed and logged automatically
- 🤖 **Gemini Vision extraction** — Google's Gemini API reads the photo and pulls out date, vendor, total, VAT, and category
- 📊 **Per-user Excel backlog** — each logged slip is appended as a new row to that user's own `.xlsx` file (via `/myfile` you can download it anytime)
- 🔑 **License-code access control** — users `/login` with a code that maps to their personal spreadsheet; an admin-secret-gated `/addcode` command lets the owner issue new codes without redeploying
- 🗄️ **SQLite-backed license codes** — codes and their target filenames are stored in a local SQLite database, seeded with defaults on first run

## Commands

| Command | What it does |
|---|---|
| `/start` | Greets the user and shows basic usage |
| `/login <code>` | Authenticates the chat session against a license code |
| `/myfile` | Sends back the user's Excel backlog as a document |
| `/addcode <code> <admin_secret> [filename]` | Admin-only: creates a new license code |
| *(send a photo)* | Extracts the slip's details via Gemini and appends them to the user's spreadsheet |

## Tech stack

- Python
- [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram bot framework (polling)
- Google Gemini API (`google-generativeai`, `gemini-2.5-flash`) — vision/text extraction from receipt photos
- `openpyxl` — writes/appends expense rows to per-user Excel workbooks
- `sqlite3` (standard library) — stores license codes
- `python-dotenv` — loads local environment variables during development
- Deployed as a Railway worker process (see `Procfile`)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project root (this file is gitignored — never commit it) with:
   ```
   TELEGRAM_TOKEN=
   GEMINI_API_KEY=
   ADMIN_SECRET=
   ```
   - `TELEGRAM_TOKEN` — your bot's token from [@BotFather](https://t.me/BotFather)
   - `GEMINI_API_KEY` — a Google Gemini API key
   - `ADMIN_SECRET` — a secret you choose; required to run `/addcode` and issue new license codes
3. Run the bot:
   ```
   python slippiesbot.py
   ```

On Railway (or any host that supplies environment variables directly), skip the `.env` file and set the same three variables in the platform's Variables/Environment settings — the `Procfile` runs the bot as a `worker` process.

## Status

Working prototype, in active personal use. A V2 with expanded features is in development.

<img width="1916" height="973" alt="image" src="https://github.com/user-attachments/assets/b6427615-3589-4d4e-871a-f9482222295d" />
