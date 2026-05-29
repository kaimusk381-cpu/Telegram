# bot.py

import os
import sqlite3
import smtplib
import mimetypes
import requests

from email.message import EmailMessage

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# ==================================================
# CONFIG
# ==================================================

BOT_TOKEN = " "

GROQ_API_KEY = " "

EMAIL_ADDRESS = "mannluvy@gmail.com"

# Gmail App Password
EMAIL_PASSWORD = ". "

BOT_PASSWORD = "luvysecure"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ==================================================
# DATABASE
# =====k=============================================

db = sqlite3.connect(
    "bot.db",
    check_same_thread=False
)

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS auth(
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender INTEGER,
    recipient TEXT,
    subject TEXT,
    message TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS custom_names(
    user_id INTEGER PRIMARY KEY,
    name TEXT
)
""")

db.commit()

# ==================================================
# STATES
# ==================================================

EMAIL, SUBJECT, MESSAGE = range(3)

# ==================================================
# HELPERS
# ==================================================

def is_authenticated(user_id):

    cursor.execute(
        "SELECT * FROM auth WHERE user_id=?",
        (user_id,)
    )

    return cursor.fetchone() is not None

def get_custom_name(user_id):

    cursor.execute(
        "SELECT name FROM custom_names WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return "Support Team"

# ==================================================
# SENDMAIL FLOW
# ==================================================

async def sendmail(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # LOGIN CHECK

    if not is_authenticated(user_id):

        await update.message.reply_text(
            "Login first."
        )

        return ConversationHandler.END

    await update.message.reply_text(
        "Enter recipient email:"
    )

    return EMAIL


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["email"] = update.message.text

    await update.message.reply_text(
        "Enter subject:"
    )

    return SUBJECT


async def get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["subject"] = update.message.text

    await update.message.reply_text(
        "Send message/photo/document:"
    )

    return MESSAGE


async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    recipient = context.user_data["email"]

    subject = context.user_data["subject"]

    body = ""

    file_path = None

    links = []

    try:

        # TEXT

        if update.message.text:

            body = update.message.text

        # PHOTO

        elif update.message.photo:

            body = update.message.caption or ""

            photo = update.message.photo[-1]

            file = await photo.get_file()

            if not os.path.exists("downloads"):

                os.mkdir("downloads")

            file_path = "downloads/photo.jpg"

            await file.download_to_drive(file_path)

        # DOCUMENT

        elif update.message.document:

            body = update.message.caption or ""

            document = update.message.document

            file = await document.get_file()

            if not os.path.exists("downloads"):

                os.mkdir("downloads")

            file_path = (
                f"downloads/{document.file_name}"
            )

            await file.download_to_drive(file_path)

        # DETECT LINKS

        for word in body.split():

            if (
                word.startswith("http://")
                or
                word.startswith("https://")
            ):

                links.append(word)

        send_email(
            update.effective_user.id,
            recipient,
            subject,
            body,
            file_path,
            links
        )

        await update.message.reply_text(
            "Email sent successfully ✅"
        )

    except Exception as e:

        await update.message.reply_text(
            f"Error:\n{e}"
        )

    return ConversationHandler.END

# ==================================================
# LOGIN
# ==================================================

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    
    # CHECK PASSWORD ARGUMENT

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/login password"
        )

        return

    password = context.args[0].strip()

    # DEBUG CHECK

    print("Entered Password:", password)
    print("Real Password:", BOT_PASSWORD)

    # PASSWORD VERIFY

    if password == BOT_PASSWORD:

        cursor.execute(
            "INSERT OR IGNORE INTO auth(user_id) VALUES(?)",
            (user_id,)
        )

        db.commit()

        await update.message.reply_text(
            """
Authentication successful ✅

Admin Bot Active ✅

Commands:

/sendmail
/customname NAME
/rewrite your text
"""
        )

    else:

        await update.message.reply_text(
            "Wrong password ❌"
        )


# ==================================================
# START
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # PASSWORD CHECK

    if not is_authenticated(user_id):

        await update.message.reply_text(
            "✅ Authentication verification successful.\n\n"
            "Now login using:\n"
            "/login password"
        )

        return

    # SHOW COMMANDS AFTER LOGIN

    text = """
Admin Bot Active ✅

Commands:

/sendmail
/customname NAME
/rewrite your text
"""

    await update.message.reply_text(text)

# ==================================================
# CUSTOM NAME
# ==================================================

async def customname(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not is_authenticated(user_id):

        await update.message.reply_text(
            "Login first."
        )

        return

    name = " ".join(context.args)

    if not name:

        await update.message.reply_text(
            "Usage:\n/customname Your Name"
        )

        return

    cursor.execute("""
    INSERT OR REPLACE INTO custom_names(
        user_id,
        name
    )
    VALUES(?,?)
    """, (
        user_id,
        name
    ))

    db.commit()

    await update.message.reply_text(
        f"Custom name updated to:\n{name} ✅"
    )

# ==================================================
# SENDMAIL
# ==================================================

def send_email(
    user_id,
    to_email,
    subject,
    body,
    file_path=None,
    links=None
):

    custom_name = get_custom_name(user_id)

    msg = EmailMessage()

    msg["From"] = f"{custom_name} <{EMAIL_ADDRESS}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = EMAIL_ADDRESS

    # TEXT
    msg.set_content(body)

    # HTML
    html = f"""
    <html>
    <body style="font-family:Arial; padding:20px;">
        <h2>{custom_name}</h2>
        <div style="white-space:pre-wrap;">{body}</div>
    """

    # LINKS
    if links:
        html += "<hr><h4>Links</h4>"
        for link in links:
            html += f'<p><a href="{link}">{link}</a></p>'

    html += "</body></html>"

    msg.add_alternative(html, subtype="html")

    # ATTACH FILE
    if file_path:

        mime_type, _ = mimetypes.guess_type(file_path)

        if mime_type:
            main, sub = mime_type.split("/")
        else:
            main, sub = "application", "octet-stream"

        with open(file_path, "rb") as f:
            file_data = f.read()

        if main == "image":
            msg.add_attachment(
                file_data,
                maintype="image",
                subtype=sub,
                filename=os.path.basename(file_path)
            )
        else:
            msg.add_attachment(
                file_data,
                maintype=main,
                subtype=sub,
                filename=os.path.basename(file_path)
            )

    # ==================================================
    # FIXED SMTP CONNECTION (THIS WAS YOUR BUG)
    # ==================================================
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:

        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        smtp.login(
            EMAIL_ADDRESS,
            EMAIL_PASSWORD
        )

        smtp.send_message(msg)

# ==================================================
# STATS
# ==================================================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute(
        "SELECT COUNT(*) FROM logs"
    )

    total = cursor.fetchone()[0]

    await update.message.reply_text(
        f"Total Emails Sent: {total}"
    )

# ==================================================
# REWRITE AI
# ==================================================

async def rewrite(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = " ".join(context.args)

    if not text:

        await update.message.reply_text(
            "Usage:\n/rewrite your text"
        )

        return

    headers = {
        "Authorization":
        f"Bearer {GROQ_API_KEY}",

        "Content-Type":
        "application/json"
    }

    payload = {

        "model":
        "meta-llama/llama-4-scout-17b-16e-instruct",

        "messages": [

            {
                "role": "system",

                "content": (
                    "Rewrite the user's message "
                    "professionally, naturally "
                    "and clearly."
                )
            },

            {
                "role": "user",
                "content": text
            }
        ]
    }

    try:

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )

        data = response.json()

        if "choices" not in data:

            error_message = (
                data.get("error", {})
                .get("message", "Unknown error")
            )

            await update.message.reply_text(
                f"Groq Error:\n{error_message}"
            )

            return

        rewritten = (
            data["choices"][0]
            ["message"]["content"]
        )

        await update.message.reply_text(
            f"✨ Rewritten Message:\n\n{rewritten}"
        )

    except Exception as e:

        await update.message.reply_text(
            f"Error:\n{e}"
        )

# ==================================================
# MAIN
# ==================================================

def main():

    app = Application.builder().token(
        BOT_TOKEN
    ).build()

    conversation = ConversationHandler(

        entry_points=[
            CommandHandler(
                "sendmail",
                sendmail
            )
        ],

        states={

            EMAIL: [
                MessageHandler(
                    filters.TEXT &
                    ~filters.COMMAND,

                    get_email
                )
            ],

            SUBJECT: [
                MessageHandler(
                    filters.TEXT &
                    ~filters.COMMAND,

                    get_subject
                )
            ],

            MESSAGE: [
                MessageHandler(
                    filters.ALL &
                    ~filters.COMMAND,

                    get_message
                )
            ],
        },

        fallbacks=[]
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("login", login)
    )

    app.add_handler(
        CommandHandler("customname", customname)
    )

    app.add_handler(
        CommandHandler("rewrite", rewrite)
    )

    app.add_handler(conversation)

    print("Bot Running ✅")

    app.run_polling()

if __name__ == "__main__":
    main()
