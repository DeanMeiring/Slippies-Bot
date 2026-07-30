import os
import sqlite3
import openpyxl
from datetime import datetime
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()  # loads variables from a local .env file if present (does nothing on Railway, which uses its own Variables tab)

# --- CONFIG (read from environment, never hardcoded) ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
ADMIN_SECRET = os.environ["ADMIN_SECRET"]  # required to add new license codes

DB_FILE = "licenses.db"
user_sessions = {}

# --- SETUP GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-flash')


# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS license_codes (
            code TEXT PRIMARY KEY,
            filename TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def seed_default_codes():
    # Only runs once - won't overwrite if codes already exist in the DB
    defaults = {
        "DEAN777": "Dean_Slips_Backlog.xlsx",
        "JOHAN888": "Johan_Slips_Backlog.xlsx"
    }
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    for code, filename in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO license_codes (code, filename) VALUES (?, ?)",
            (code, filename)
        )
    conn.commit()
    conn.close()


def get_filename_for_code(code):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT filename FROM license_codes WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def add_license_code(code, filename):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO license_codes (code, filename) VALUES (?, ?)",
        (code, filename)
    )
    conn.commit()
    conn.close()


def code_exists(code):
    return get_filename_for_code(code) is not None


def save_to_excel(filename, data_row):
    if not os.path.exists(filename):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Log Time", "Slip Date", "Vendor", "Total (ZAR)", "VAT", "Category"])
        wb.save(filename)
    wb = openpyxl.load_workbook(filename)
    ws = wb.active
    ws.append([datetime.now().strftime("%Y-%m-%d %H:%M")] + data_row)
    wb.save(filename)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 SlippiesBot is ONLINE.\n"
        "Use /login YOURCODE to start.\n"
        "Use /myfile to get your Excel backlog anytime."
    )


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("Usage: /login DEAN777")
        return
    code = context.args[0].upper()
    filename = get_filename_for_code(code)
    if filename:
        user_sessions[user_id] = filename
        await update.message.reply_text(f"✅ Access Granted! Saving to: {filename}")
    else:
        await update.message.reply_text("❌ License code not found.")


async def addcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /addcode NEWCODE123 admin_secret [optional_filename]
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /addcode NEWCODE123 your_admin_secret [optional_filename]"
        )
        return

    new_code = context.args[0].upper()
    provided_secret = context.args[1]

    if provided_secret != ADMIN_SECRET:
        await update.message.reply_text("❌ Invalid admin secret.")
        return

    if code_exists(new_code):
        await update.message.reply_text(f"⚠️ Code {new_code} already exists.")
        return

    if len(context.args) >= 3:
        filename = context.args[2]
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
    else:
        filename = f"{new_code}_Slips_Backlog.xlsx"

    add_license_code(new_code, filename)

    # Try to delete the message so the admin secret doesn't sit in chat history
    try:
        await update.message.delete()
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ New code created: {new_code}\nSaves to: {filename}"
    )


async def myfile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("🔒 Locked. Please /login first.")
        return

    target_file = user_sessions[user_id]

    if not os.path.exists(target_file):
        await update.message.reply_text("📭 No slips logged yet — nothing to send.")
        return

    await update.message.reply_document(
        document=open(target_file, "rb"),
        filename=target_file,
        caption=f"📊 Here's your backlog: {target_file}"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("🔒 Locked. Please /login first.")
        return

    status_msg = await update.message.reply_text("AI is reading your slip... 🧠")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        prompt = "Extract: Date (DD/MM/YYYY), Vendor, Total, VAT, Category. Return ONLY one comma-separated line."
        response = model.generate_content([
            prompt,
            {'mime_type': 'image/jpeg', 'data': bytes(photo_bytes)}
        ])

        data_parts = [item.strip() for item in response.text.split(',')]
        target_file = user_sessions[user_id]
        save_to_excel(target_file, data_parts)

        await status_msg.edit_text(f"✅ Success! Logged to {target_file}:\n`{response.text}`")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


if __name__ == '__main__':
    init_db()
    seed_default_codes()  # ensures DEAN777 / JOHAN888 exist on first run, harmless after

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("myfile", myfile))
    application.add_handler(CommandHandler("addcode", addcode))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("--- BOT IS LIVE ---")
    print("Waiting for Dean and Johan...")
    application.run_polling()
