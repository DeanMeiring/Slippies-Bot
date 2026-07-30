import os
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

# The Licenses
VALID_CODES = {
    "DEAN777": "Dean_Slips_Backlog.xlsx",
    "JOHAN888": "Johan_Slips_Backlog.xlsx"
}

user_sessions = {}

# --- SETUP GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-flash')


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
    if code in VALID_CODES:
        user_sessions[user_id] = VALID_CODES[code]
        await update.message.reply_text(f"✅ Access Granted! Saving to: {VALID_CODES[code]}")
    else:
        await update.message.reply_text("❌ License code not found.")


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
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("myfile", myfile))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("--- BOT IS LIVE ---")
    print("Waiting for Dean and Johan...")
    application.run_polling()
