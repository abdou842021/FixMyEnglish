import os
import json
from threading import Thread

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

USERS_FILE = "allowed_users.json"
GROUPS_FILE = "allowed_groups.json"

# =========================================================
# LOAD / SAVE DATA
# =========================================================

def load_ids(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_ids(filename, ids):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(list(ids), file, indent=2)


allowed_users = load_ids(USERS_FILE)
allowed_groups = load_ids(GROUPS_FILE)

pending_users = set()
pending_groups = set()

# =========================================================
# FLASK SERVER FOR RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "FixMyEnglish is alive!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# ACCESS CHECK
# =========================================================

def is_owner(user_id):
    return user_id == OWNER_ID


# =========================================================
# START COMMAND
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # OWNER
    if is_owner(user.id):
        await update.message.reply_text(
            "👑 Welcome, Owner!\n\n"
            "FixMyEnglish is ready."
        )
        return

    # PRIVATE
    if chat.type == "private":

        if user.id in allowed_users:
            await update.message.reply_text(
                "✅ Your access is approved.\n\n"
                "FixMyEnglish is ready!"
            )
            return

        await update.message.reply_text(
            "⏳ Your access request has been sent to the owner.\n"
            "Please wait for approval."
        )

        await send_user_request(update, context)
        return

    # GROUP
    if chat.type in ["group", "supergroup"]:

        if chat.id in allowed_groups:
            await update.message.reply_text(
                "✅ This group is approved."
            )
        else:
            await update.message.reply_text(
                "⏳ This group is waiting for owner approval."
            )


# =========================================================
# PRIVATE USER APPROVAL REQUEST
# =========================================================

async def send_user_request(update, context):

    user = update.effective_user

    if user.id in pending_users:
        return

    pending_users.add(user.id)

    name = user.full_name
    username = f"@{user.username}" if user.username else "No username"

    keyboard = [
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
    ]

    text = (
        "👤 New private-user request\n\n"
        f"Name: {name}\n"
        f"Username: {username}\n"
        f"ID: {user.id}\n\n"
        "Do you want to approve this user?"
    )

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# GROUP APPROVAL REQUEST
# =========================================================

async def group_added(update: Update, context: ContextTypes.DEFAULT_TYPE):

    member_update = update.my_chat_member

    if not member_update:
        return

    chat = member_update.chat
    new_member = member_update.new_chat_member

    if (
        new_member.status in ["member", "administrator"]
        and chat.type in ["group", "supergroup"]
    ):

        if chat.id in allowed_groups:
            return

        if chat.id in pending_groups:
            return

        pending_groups.add(chat.id)

        keyboard = [
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
        ]

        text = (
            "👥 New group request\n\n"
            f"Group: {chat.title}\n"
            f"ID: {chat.id}\n\n"
            "Do you want to approve this group?"
        )

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# =========================================================
# APPROVAL BUTTONS
# =========================================================

async def approval_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    # ONLY OWNER
    if query.from_user.id != OWNER_ID:
        await query.answer(
            "You are not authorized.",
            show_alert=True
        )
        return

    await query.answer()

    data = query.data

    # -----------------------------------------------------
    # ACCEPT USER
    # -----------------------------------------------------

    if data.startswith("accept_user:"):

        user_id = int(data.split(":")[1])

        allowed_users.add(user_id)
        save_ids(USERS_FILE, allowed_users)

        pending_users.discard(user_id)

        await query.edit_message_text(
            f"✅ User approved.\n\n"
            f"ID: {user_id}"
        )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 Your access has been approved!\n\n"
                    "You can now use FixMyEnglish."
                )
            )
        except Exception:
            pass

        return

    # -----------------------------------------------------
    # REJECT USER
    # -----------------------------------------------------

    if data.startswith("reject_user:"):

        user_id = int(data.split(":")[1])

        pending_users.discard(user_id)

        await query.edit_message_text(
            f"❌ User rejected.\n\n"
            f"ID: {user_id}"
        )

        return

    # -----------------------------------------------------
    # ACCEPT GROUP
    # -----------------------------------------------------

    if data.startswith("accept_group:"):

        group_id = int(data.split(":")[1])

        allowed_groups.add(group_id)
        save_ids(GROUPS_FILE, allowed_groups)

        pending_groups.discard(group_id)

        await query.edit_message_text(
            f"✅ Group approved.\n\n"
            f"ID: {group_id}"
        )

        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=(
                    "🎉 This group has been approved!\n\n"
                    "FixMyEnglish is now active."
                )
            )
        except Exception:
            pass

        return

    # -----------------------------------------------------
    # REJECT GROUP
    # -----------------------------------------------------

    if data.startswith("reject_group:"):

        group_id = int(data.split(":")[1])

        pending_groups.discard(group_id)

        await query.edit_message_text(
            f"❌ Group rejected.\n\n"
            f"ID: {group_id}"
        )

        return


# =========================================================
# LIST COMMAND
# =========================================================

async def list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    users_text = "\n".join(
        str(user_id) for user_id in allowed_users
    )

    groups_text = "\n".join(
        str(group_id) for group_id in allowed_groups
    )

    if not users_text:
        users_text = "None"

    if not groups_text:
        groups_text = "None"

    text = (
        "📋 APPROVED USERS\n\n"
        f"{users_text}\n\n"
        "👥 APPROVED GROUPS\n\n"
        f"{groups_text}"
    )

    await update.message.reply_text(text)


# =========================================================
# DELETE COMMAND
# =========================================================

async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "Use:\n/del ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid ID."
        )
        return

    if target_id in allowed_users:

        allowed_users.remove(target_id)
        save_ids(USERS_FILE, allowed_users)

        await update.message.reply_text(
            f"✅ User removed.\n\nID: {target_id}"
        )
        return

    if target_id in allowed_groups:

        allowed_groups.remove(target_id)
        save_ids(GROUPS_FILE, allowed_groups)

        await update.message.reply_text(
            f"✅ Group removed.\n\nID: {target_id}"
        )
        return

    await update.message.reply_text(
        "❌ ID not found."
    )


# =========================================================
# UNAPPROVED PRIVATE USERS
# =========================================================

async def private_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    if is_owner(user.id):
        return

    if user.id not in allowed_users:

        await update.message.reply_text(
            "⏳ Your access has not been approved yet."
        )

        await send_user_request(update, context)


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing."
        )

    if OWNER_ID == 0:
        raise RuntimeError(
            "OWNER_ID is missing."
        )

    # Start web server for Render
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
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("list", list_command)
    )

    application.add_handler(
        CommandHandler("del", delete_command)
    )

    # Detect bot added to a group
    application.add_handler(
        ChatMemberHandler(
            group_added,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    # Approval buttons
    application.add_handler(
        CallbackQueryHandler(
            approval_callback
        )
    )

    # Private messages
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            private_messages
        )
    )

    print("FixMyEnglish is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
