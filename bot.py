import os
import json
import re
import random
from threading import Thread

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")


# =========================================================
# FILES
# =========================================================

ALLOWED_USERS_FILE = "allowed_users.json"
ALLOWED_GROUPS_FILE = "allowed_groups.json"

USERS_INFO_FILE = "users_info.json"
GROUPS_INFO_FILE = "groups_info.json"

USER_ERRORS_FILE = "user_errors.json"
CHAT_SETTINGS_FILE = "chat_settings.json"


# =========================================================
# FLASK - RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "FixMyEnglish is alive!"


def run_web():
    app.run(host="0.0.0.0", port=PORT)


# =========================================================
# JSON HELPERS
# =========================================================

def load_json(filename, default):
    try:
        if not os.path.exists(filename):
            return default

        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================================================
# DATA
# =========================================================

allowed_users = load_json(ALLOWED_USERS_FILE, [])
allowed_groups = load_json(ALLOWED_GROUPS_FILE, [])

users_info = load_json(USERS_INFO_FILE, {})
groups_info = load_json(GROUPS_INFO_FILE, {})

user_errors = load_json(USER_ERRORS_FILE, {})
chat_settings = load_json(CHAT_SETTINGS_FILE, {})


# =========================================================
# ACCESS
# =========================================================

def is_allowed(update: Update):
    user = update.effective_user
    chat = update.effective_chat

    if user and user.id == OWNER_ID:
        return True

    if chat.type == "private":
        return user and user.id in allowed_users

    return chat.id in allowed_groups


# =========================================================
# SAVE USER INFO
# =========================================================

def save_user_info(user):
    if not user:
        return

    users_info[str(user.id)] = {
        "id": user.id,
        "name": user.full_name or "Unknown",
        "username": user.username or "No username",
    }

    save_json(USERS_INFO_FILE, users_info)


# =========================================================
# SAVE GROUP INFO
# =========================================================

def save_group_info(chat):
    if not chat:
        return

    groups_info[str(chat.id)] = {
        "id": chat.id,
        "title": chat.title or "Unknown",
        "type": chat.type,
    }

    save_json(GROUPS_INFO_FILE, groups_info)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    chat = update.effective_chat

    save_user_info(user)

    if user.id == OWNER_ID:
        await update.message.reply_text(
            "👑 Welcome, Owner!\n\n"
            "FixMyEnglish is ready."
        )
        return

    if chat.type != "private":
        if chat.id in allowed_groups:
            await update.message.reply_text(
                "✅ FixMyEnglish is active in this group."
            )
        else:
            await update.message.reply_text(
                "⏳ This group is waiting for approval."
            )
        return

    if user.id in allowed_users:
        await update.message.reply_text(
            "🎉 Your access has already been approved!\n\n"
            "Welcome to FixMyEnglish 🤍\n\n"
            "✏️ Correct English mistakes\n"
            "📚 Learn from your mistakes\n"
            "🧠 Improve your English step by step"
        )
        return

    await update.message.reply_text(
        "⏳ Your request is waiting for approval.\n\n"
        "FixMyEnglish is an English-learning bot that will help you:\n"
        "✏️ Correct English mistakes\n"
        "📚 Learn from your mistakes\n"
        "🧠 Improve your English step by step\n\n"
        "Your request has been sent to the owner.\n"
        "Please wait until your access is approved."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Accept",
                callback_data=f"accept_user:{user.id}"
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"reject_user:{user.id}"
            ),
        ]
    ])

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=(
            "👤 New user request\n\n"
            f"Name: {user.full_name}\n"
            f"Username: @{user.username if user.username else 'None'}\n"
            f"ID: `{user.id}`"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_allowed(update):
        return

    text = (
        "📚 *FixMyEnglish*\n\n"
        "✏️ `/correct` — Correct a message\n"
        "🤖 `/autocorrect on` — Automatic correction\n"
        "🛑 `/autocorrect off` — Turn automatic correction off\n"
        "📊 `/mystats` — Your common mistakes\n\n"
        "The bot can also learn from repeated English mistakes."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# APPROVAL CALLBACKS
# =========================================================

async def approval_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        return

    data = query.data

    # -----------------------------------------------------
    # USER ACCEPT
    # -----------------------------------------------------

    if data.startswith("accept_user:"):

        user_id = int(data.split(":")[1])

        if user_id not in allowed_users:
            allowed_users.append(user_id)
            save_json(ALLOWED_USERS_FILE, allowed_users)

        await query.edit_message_text(
            "✅ User approved."
        )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 Your access has been approved!\n\n"
                    "Welcome to FixMyEnglish 🤍\n\n"
                    "FixMyEnglish is an English-learning bot that helps you:\n"
                    "✏️ Correct English mistakes\n"
                    "📚 Learn from your mistakes\n"
                    "🧠 Improve your English step by step\n\n"
                    "You can now use the bot."
                )
            )
        except Exception:
            pass

    # -----------------------------------------------------
    # USER REJECT
    # -----------------------------------------------------

    elif data.startswith("reject_user:"):

        user_id = int(data.split(":")[1])

        await query.edit_message_text(
            "❌ User rejected."
        )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ Your access request was not approved.\n\n"
                    "You cannot use FixMyEnglish at the moment."
                )
            )
        except Exception:
            pass

    # -----------------------------------------------------
    # GROUP ACCEPT
    # -----------------------------------------------------

    elif data.startswith("accept_group:"):

        group_id = int(data.split(":")[1])

        if group_id not in allowed_groups:
            allowed_groups.append(group_id)
            save_json(ALLOWED_GROUPS_FILE, allowed_groups)

        await query.edit_message_text(
            "✅ Group approved."
        )

        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=(
                    "🎉 This group has been approved!\n\n"
                    "Welcome to FixMyEnglish 🤍\n\n"
                    "The bot is now active in this group and "
                    "will help members improve their English."
                )
            )
        except Exception:
            pass

    # -----------------------------------------------------
    # GROUP REJECT
    # -----------------------------------------------------

    elif data.startswith("reject_group:"):

        group_id = int(data.split(":")[1])

        await query.edit_message_text(
            "❌ Group rejected."
        )


# =========================================================
# BOT ADDED TO GROUP
# =========================================================

async def bot_membership(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_member = update.my_chat_member

    if not chat_member:
        return

    chat = chat_member.chat

    old_status = chat_member.old_chat_member.status
    new_status = chat_member.new_chat_member.status

    if new_status in ("member", "administrator"):

        if old_status in ("left", "kicked"):

            save_group_info(chat)

            if chat.id in allowed_groups:
                return

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Accept",
                        callback_data=f"accept_group:{chat.id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject",
                        callback_data=f"reject_group:{chat.id}"
                    ),
                ]
            ])

            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    "👥 New group request\n\n"
                    f"Group: {chat.title}\n"
                    f"ID: `{chat.id}`"
                ),
                reply_markup=keyboard,
                parse_mode="Markdown"
            )


# =========================================================
# OWNER /LIST
# =========================================================

async def list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    text = "📋 *Approved Users*\n\n"

    if not allowed_users:
        text += "No approved users.\n"
    else:
        for user_id in allowed_users:

            info = users_info.get(
                str(user_id),
                {}
            )

            name = info.get("name", "Unknown")
            username = info.get("username", "No username")

            text += (
                f"👤 {name}\n"
                f"Username: @{username.replace('@', '')}\n"
                f"ID: `{user_id}`\n\n"
            )

    text += "\n📋 *Approved Groups*\n\n"

    if not allowed_groups:
        text += "No approved groups.\n"
    else:
        for group_id in allowed_groups:

            info = groups_info.get(
                str(group_id),
                {}
            )

            title = info.get("title", "Unknown")

            text += (
                f"👥 {title}\n"
                f"ID: `{group_id}`\n\n"
            )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# OWNER /DEL
# =========================================================

async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/del USER_ID or GROUP_ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid ID."
        )
        return

    changed = False

    if target_id in allowed_users:
        allowed_users.remove(target_id)
        save_json(ALLOWED_USERS_FILE, allowed_users)
        changed = True

    if target_id in allowed_groups:
        allowed_groups.remove(target_id)
        save_json(ALLOWED_GROUPS_FILE, allowed_groups)
        changed = True

    if changed:
        await update.message.reply_text(
            "✅ Removed successfully."
        )
    else:
        await update.message.reply_text(
            "❌ ID not found."
        )


# =========================================================
# BASIC CORRECTION ENGINE
# =========================================================

SPELLING_FIXES = {
    "yestarday": "yesterday",
    "tomorow": "tomorrow",
    "becouse": "because",
    "beacuse": "because",
    "frend": "friend",
    "freind": "friend",
    "recieve": "receive",
    "adress": "address",
    "definately": "definitely",
    "seperate": "separate",
    "wierd": "weird",
    "littel": "little",
    "becasue": "because",
    "writting": "writing",
    "studing": "studying",
    "langauge": "language",
    "enviroment": "environment",
    " goverment": " government",
}


IRREGULAR_PAST = {
    "go": "went",
    "see": "saw",
    "come": "came",
    "eat": "ate",
    "take": "took",
    "make": "made",
    "have": "had",
    "get": "got",
}


def preserve_case(original, corrected):

    if original.isupper():
        return corrected.upper()

    if original[:1].isupper():
        return corrected.capitalize()

    return corrected


def basic_correction(text):

    corrected = text
    changes = []

    # -----------------------------------------------------
    # SPELLING
    # -----------------------------------------------------

    def spelling_replace(match):

        word = match.group(0)
        lower = word.lower()

        if lower in SPELLING_FIXES:

            new_word = preserve_case(
                word,
                SPELLING_FIXES[lower]
            )

            if new_word != word:
                changes.append((word, new_word))

            return new_word

        return word

    corrected = re.sub(
        r"[A-Za-z]+",
        spelling_replace,
        corrected
    )

    # -----------------------------------------------------
    # I + IS / ARE
    # -----------------------------------------------------

    patterns = [
        (r"\bI\s+is\b", "I am"),
        (r"\bI\s+are\b", "I am"),
        (r"\bI\s+has\b", "I have"),
        (r"\bhe\s+are\b", "he is"),
        (r"\bshe\s+are\b", "she is"),
        (r"\bit\s+are\b", "it is"),
        (r"\bthey\s+is\b", "they are"),
        (r"\bwe\s+is\b", "we are"),
        (r"\byou\s+is\b", "you are"),
    ]

    for pattern, replacement in patterns:

        new_text = re.sub(
            pattern,
            replacement,
            corrected,
            flags=re.IGNORECASE
        )

        if new_text != corrected:

            found = re.search(
                pattern,
                corrected,
                flags=re.IGNORECASE
            )

            if found:
                changes.append(
                    (
                        found.group(0),
                        replacement
                    )
                )

            corrected = new_text

    # -----------------------------------------------------
    # HE / SHE / IT
    # -----------------------------------------------------

    subject_verbs = {
        "go": "goes",
        "do": "does",
        "have": "has",
        "watch": "watches",
        "wash": "washes",
        "study": "studies",
    }

    for verb, new_verb in subject_verbs.items():

        pattern = rf"\b(he|she|it)\s+{verb}\b"

        match = re.search(
            pattern,
            corrected,
            flags=re.IGNORECASE
        )

        if match:

            subject = match.group(1)

            replacement = f"{subject} {new_verb}"

            corrected = re.sub(
                pattern,
                replacement,
                corrected,
                flags=re.IGNORECASE
            )

            changes.append(
                (
                    f"{subject} {verb}",
                    replacement
                )
            )

    # -----------------------------------------------------
    # SIMPLE PAST
    # -----------------------------------------------------

    for verb, past in IRREGULAR_PAST.items():

        pattern = rf"\b(I|he|she|we|they|you)\s+{verb}\s+(yesterday|last night|last week)\b"

        match = re.search(
            pattern,
            corrected,
            flags=re.IGNORECASE
        )

        if match:

            subject = match.group(1)
            time_word = match.group(2)

            replacement = f"{subject} {past} {time_word}"

            corrected = re.sub(
                pattern,
                replacement,
                corrected,
                flags=re.IGNORECASE
            )

            changes.append(
                (
                    f"{subject} {verb} {time_word}",
                    replacement
                )
            )

    return corrected, changes


# =========================================================
# SAVE ERROR
# =========================================================

def save_error(user_id, wrong, right):

    user_key = str(user_id)

    if user_key not in user_errors:
        user_errors[user_key] = {
            "total": 0,
            "mistakes": {}
        }

    user_errors[user_key]["total"] += 1

    key = f"{wrong}|||{right}"

    mistakes = user_errors[user_key]["mistakes"]

    mistakes[key] = mistakes.get(key, 0) + 1

    save_json(
        USER_ERRORS_FILE,
        user_errors
    )


# =========================================================
# CORRECTION MESSAGE
# =========================================================

async def send_correction(
    update,
    corrected,
    changes
):

    if not changes:
        return

    lines = []

    for wrong, right in changes:
        lines.append(
            f"`{wrong}` → `{right}`"
        )

    text = (
        "✏️ *Correction*\n\n"
        f"{corrected}\n\n"
        "🔴 *Mistakes:*\n"
        + "\n".join(lines)
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# /CORRECT
# =========================================================

async def correct_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update):
        return

    message = update.message

    if not message.reply_to_message:
        await message.reply_text(
            "↩️ Reply to an English message with /correct"
        )
        return

    target = message.reply_to_message

    if not target.text:
        await message.reply_text(
            "❌ I can only correct text messages."
        )
        return

    text = target.text.strip()

    if len(text) > 1500:
        await message.reply_text(
            "⚠️ The message is too long."
        )
        return

    corrected, changes = basic_correction(text)

    if not changes:
        await message.reply_text(
            "✅ No obvious mistake found."
        )
        return

    for wrong, right in changes:
        save_error(
            update.effective_user.id,
            wrong,
            right
        )

    await send_correction(
        update,
        corrected,
        changes
    )


# =========================================================
# /AUTOCORRECT
# =========================================================

async def autocorrect_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update):
        return

    chat_id = str(update.effective_chat.id)

    if not context.args:

        enabled = chat_settings.get(
            chat_id,
            True
        )

        status = "ON 🟢" if enabled else "OFF 🔴"

        await update.message.reply_text(
            f"🤖 Auto-correction: {status}\n\n"
            "Use:\n"
            "/autocorrect on\n"
            "/autocorrect off"
        )

        return

    option = context.args[0].lower()

    if option == "on":

        chat_settings[chat_id] = True

        save_json(
            CHAT_SETTINGS_FILE,
            chat_settings
        )

        await update.message.reply_text(
            "🤖 Auto-correction is now ON 🟢"
        )

    elif option == "off":

        chat_settings[chat_id] = False

        save_json(
            CHAT_SETTINGS_FILE,
            chat_settings
        )

        await update.message.reply_text(
            "🤖 Auto-correction is now OFF 🔴"
        )

    else:

        await update.message.reply_text(
            "Use:\n"
            "/autocorrect on\n"
            "/autocorrect off"
        )


# =========================================================
# /MYSTATS
# =========================================================

async def mystats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update):
        return

    user_id = str(update.effective_user.id)

    data = user_errors.get(
        user_id,
        {
            "total": 0,
            "mistakes": {}
        }
    )

    total = data.get("total", 0)
    mistakes = data.get("mistakes", {})

    if not mistakes:

        await update.message.reply_text(
            "📊 You don't have any saved mistakes yet."
        )
        return

    sorted_mistakes = sorted(
        mistakes.items(),
        key=lambda x: x[1],
        reverse=True
    )

    lines = [
        "📊 *Your English Mistakes*",
        "",
        f"Total corrections: {total}",
        ""
    ]

    for key, count in sorted_mistakes[:10]:

        wrong, right = key.split(
            "|||",
            1
        )

        lines.append(
            f"• `{wrong}` → `{right}` ({count}x)"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown"
    )


# =========================================================
# NAME RECOGNITION + DUA
# =========================================================

NAME_PATTERNS = [
    # Arabic
    r"(?<!\w)عبد\s*الكريم(?!\w)",
    r"(?<!\w)عبد\s+الكريم(?!\w)",
    r"(?<!\w)كريم(?!\w)",

    # Latin / French
    r"(?i)(?<![a-z])abdelkarim(?![a-z])",
    r"(?i)(?<![a-z])abdel\s+karim(?![a-z])",
    r"(?i)(?<![a-z])abdelkrim(?![a-z])",
    r"(?i)(?<![a-z])abd\s+el\s+karim(?![a-z])",
    r"(?i)(?<![a-z])abd\s+elkrim(?![a-z])",
]


DUAS = [
    "May Allah bless you with happiness, peace, and success. 🤲",
    "May Allah grant you goodness in this life and the Hereafter. 🤲",
    "May Allah protect you, guide you, and bless your path. 🤲",
    "May Allah fill your heart with peace and your life with blessings. 🤲",
    "May Allah make your affairs easy and bless you with what is good. 🤲",
    "May Allah reward you with goodness and grant you lasting happiness. 🤲",
    "May Allah open good doors for you and bless your efforts. 🤲",
    "May Allah grant you beneficial knowledge and righteous deeds. 🤲",
    "May Allah keep you safe, guide you to what is best, and bless your days. 🤲",
    "May Allah grant you peace of heart, strength, and success. 🤲",
    "May Allah bless your family and grant you goodness and tranquility. 🤲",
    "May Allah forgive your shortcomings and increase you in goodness. 🤲",
    "May Allah make your future better than your past and bless your journey. 🤲",
    "May Allah grant you what is good for you and keep harmful things away from you. 🤲",
    "May Allah increase you in faith, wisdom, and beneficial knowledge. 🤲",
    "May Allah bless your time, your efforts, and your goals. 🤲",
    "May Allah grant you ease after every difficulty and happiness after every hardship. 🤲",
    "May Allah guide your heart, protect you from harm, and bless your life. 🤲",
    "May Allah grant you a peaceful heart and a blessed life. 🤲",
    "May Allah accept your good deeds and bless you with goodness in abundance. 🤲",
]


def name_is_mentioned(text):

    if not text:
        return False

    for pattern in NAME_PATTERNS:

        if re.search(pattern, text):
            return True

    return False


async def name_mention_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message:
        return

    if not message.text:
        return

    chat = update.effective_chat

    # Only groups
    if chat.type not in ("group", "supergroup"):
        return

    # Only approved groups
    if chat.id not in allowed_groups and update.effective_user.id != OWNER_ID:
        return

    text = message.text

    if name_is_mentioned(text):

        dua = random.choice(DUAS)

        await message.reply_text(
            dua,
            reply_to_message_id=message.message_id
        )


# =========================================================
# AUTOMATIC CORRECTION
# =========================================================

async def automatic_correction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message or not message.text:
        return

    text = message.text.strip()

    # Ignore commands
    if text.startswith("/"):
        return

    if not is_allowed(update):
        return

    # Ignore Arabic-only messages
    english_letters = re.findall(
        r"[A-Za-z]",
        text
    )

    if len(english_letters) < 3:
        return

    # Ignore very long messages
    if len(text) > 1500:
        return

    chat_id = str(
        update.effective_chat.id
    )

    enabled = chat_settings.get(
        chat_id,
        True
    )

    if not enabled:
        return

    corrected, changes = basic_correction(text)

    if not changes:
        return

    for wrong, right in changes:

        save_error(
            update.effective_user.id,
            wrong,
            right
        )

    await send_correction(
        update,
        corrected,
        changes
    )


# =========================================================
# MAIN MESSAGE HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    # Name recognition first
    await name_mention_handler(
        update,
        context
    )

    # Then automatic correction
    await automatic_correction(
        update,
        context
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # Render web server
    Thread(
        target=run_web,
        daemon=True
    ).start()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "correct",
            correct_command
        )
    )

    application.add_handler(
        CommandHandler(
            "autocorrect",
            autocorrect_command
        )
    )

    application.add_handler(
        CommandHandler(
            "mystats",
            mystats_command
        )
    )

    application.add_handler(
        CommandHandler(
            "list",
            list_command
        )
    )

    application.add_handler(
        CommandHandler(
            "del",
            delete_command
        )
    )

    # Approval buttons
    application.add_handler(
        CallbackQueryHandler(
            approval_callback
        )
    )

    # Bot added / removed from groups
    application.add_handler(
        ChatMemberHandler(
            bot_membership,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    # Text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    print("FixMyEnglish is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
