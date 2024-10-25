import time
import requests
import re
import html
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from datetime import datetime
from keep_alive import keep_alive
from dotenv import load_dotenv
import os
from pymongo import MongoClient
load_dotenv()
# تنظیمات و متغیرهای مورد نیاز
TOKEN = os.getenv('TOKEN')
API_URL = f'http://tiamo.freehost.io/wl-ai-bot/ai.php?&msg='
ADMIN_USER_ID = 2117882551

keep_alive()

# اتصال به MongoDB
client = MongoClient("mongodb+srv://pooriyayt:AulJRCPpIyTW5S70@cluster0.ukehq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["mydatabase"]

# مجموعه‌ها
user_data_collection = db["user_data"]
vip_added_dates_collection = db["vip_added_dates"]

# تابع برای بارگذاری داده‌ها از MongoDB
def load_data():
    global bot_data
    bot_data = {
        "user_limits": {},
        "user_daily_limit": {},
        "user_last_reset": {},
        "user_language": {},
        "total_questions_asked": {},
        "premium_users": [],
        "vip_added_dates": {},
        "user_last_daily_reset": {},
        "banned_users": {}
    }

    try:
        # بارگذاری اطلاعات کاربران
        for row in user_data_collection.find():
            user_id = str(row['user_id'])
            bot_data["user_limits"][user_id] = row.get('minute_limit', 1)
            bot_data["user_daily_limit"][user_id] = row.get('daily_limit', 20)
            bot_data["user_last_reset"][user_id] = row.get('last_reset', datetime.now()).timestamp()
            bot_data["user_language"][user_id] = row.get('language_code', 'en')
            bot_data["total_questions_asked"][user_id] = row.get('questions_asked', 0)
            bot_data["user_last_daily_reset"][user_id] = row.get('last_daily_reset', datetime.now()).timestamp()
            if row.get('is_premium', False):
                bot_data["premium_users"].append(user_id)
            if row.get('ban_reason'):
                bot_data["banned_users"][user_id] = row['ban_reason']

        # بارگذاری تاریخ عضویت VIP کاربران
        for row in vip_added_dates_collection.find():
            bot_data["vip_added_dates"][str(row['user_id'])] = row['added_date'].strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        print(f"Error loading data from MongoDB: {e}")

# تابع برای ذخیره داده‌ها در MongoDB
def save_data():
    try:
        # ذخیره یا بروزرسانی اطلاعات کاربران
        for user_id, minute_limit in bot_data["user_limits"].items():
            daily_limit = bot_data["user_daily_limit"].get(user_id, 20)
            last_daily_reset = datetime.fromtimestamp(bot_data["user_last_daily_reset"].get(user_id, datetime.now().timestamp()))
            last_reset = datetime.fromtimestamp(bot_data["user_last_reset"].get(user_id, datetime.now().timestamp()))
            language_code = bot_data["user_language"].get(user_id, 'en')
            questions_asked = bot_data["total_questions_asked"].get(user_id, 0)
            is_premium = user_id in bot_data["premium_users"]
            ban_reason = bot_data["banned_users"].get(user_id, None)

            user_data_collection.update_one(
                {"user_id": int(user_id)},
                {"$set": {
                    "daily_limit": daily_limit,
                    "minute_limit": minute_limit,
                    "last_daily_reset": last_daily_reset,
                    "last_reset": last_reset,
                    "questions_asked": questions_asked,
                    "language_code": language_code,
                    "is_premium": is_premium,
                    "ban_reason": ban_reason
                }},
                upsert=True
            )

        # ذخیره یا بروزرسانی تاریخ عضویت VIP کاربران
        for user_id, added_date in bot_data["vip_added_dates"].items():
            vip_added_dates_collection.update_one(
                {"user_id": int(user_id)},
                {"$set": {
                    "added_date": datetime.strptime(added_date, '%Y-%m-%d %H:%M:%S')
                }},
                upsert=True
            )

    except Exception as e:
        print(f"Error saving data to MongoDB: {e}")


def load_messages(language_code):
    try:
        with open(f"messages_{language_code}.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# تابع برای دریافت پیام‌ها بر اساس زبان کاربر
def get_message(user_id, key, **kwargs):
    language_code = bot_data["user_language"].get(str(user_id), 'en')
    messages = load_messages(language_code)
    return messages.get(key, key).format(**kwargs)

# در بخش اصلی برنامه، ابتدا داده‌ها را بارگذاری می‌کنیم
load_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data='fa')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='en')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_message(update.message.from_user.id, 'welcome'), reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(get_message(update.message.from_user.id, 'help'))

async def limits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    current_time = time.time()
    user_limits = bot_data["user_limits"]
    user_daily_limit = bot_data["user_daily_limit"]
    user_last_reset = bot_data["user_last_daily_reset"]
    total_questions_asked = bot_data["total_questions_asked"].get(str(user_id), 0)
    remaining_daily = user_daily_limit.get(str(user_id), 60 if str(user_id) in bot_data["premium_users"] else 20)
    remaining_minute = max(0, user_limits.get(str(user_id), 3 if str(user_id) in bot_data["premium_users"] else 1))
    daily_reset_timestamp = user_last_reset.get(str(user_id), current_time) + 86400
    reset_time = datetime.fromtimestamp(daily_reset_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    time_until_reset = daily_reset_timestamp - current_time
    hours, remainder = divmod(time_until_reset, 3600)
    minutes, _ = divmod(remainder, 60)
    
    await update.message.reply_text(get_message(
        user_id,
        'limits',
        remaining_minute=remaining_minute,
        remaining_daily=remaining_daily,
        hours=int(hours),
        minutes=int(minutes),
        total_questions_asked=total_questions_asked
    ))


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data='fa')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='en')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_message(update.message.from_user.id, 'choose_language'), reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    language_code = query.data

    # ذخیره زبان کاربر در دیتابیس
    bot_data["user_language"][str(user_id)] = language_code
    save_data()


    # ارسال پیام جدید به جای ویرایش پیام قبلی
    await context.bot.send_message(chat_id=query.message.chat_id, text=get_message(user_id, 'language_changed', language=language_code))


async def add_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /addvip <user_id>")
        return

    vip_user_id = context.args[0]
    if vip_user_id in bot_data["premium_users"]:
        await update.message.reply_text(f"User {vip_user_id} is already a VIP.")
        return

    bot_data["premium_users"].append(vip_user_id)
    
    # ذخیره تاریخ اضافه شدن کاربر به عنوان VIP
    bot_data["vip_added_dates"][vip_user_id] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    save_data()

    # ارسال پیام تبریک به کاربر
    await send_congratulations_message(context, vip_user_id)

    await update.message.reply_text(f"User {vip_user_id} has been granted VIP status.")

async def send_congratulations_message(context: ContextTypes.DEFAULT_TYPE, user_id):
    english_message = "Congratulations🌟 Your premium subscription has been activated."
    persian_message = "تبریک🌟 اشتراک پرمیوم شما فعال شد."
    
    user_language = bot_data["user_language"].get(user_id, "en")
    
    if user_language == "en":
        message = english_message
    else:
        message = persian_message

    await context.bot.send_message(chat_id=user_id, text=message)

async def remove_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_user_id = update.message.from_user.id
    if admin_user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removevip <user_id>")
        return

    vip_user_id = context.args[0]
    if vip_user_id in bot_data["premium_users"]:
        bot_data["premium_users"].remove(vip_user_id)
        if str(vip_user_id) in bot_data["vip_added_dates"]:
            del bot_data["vip_added_dates"][str(vip_user_id)]
        save_data()
        await update.message.reply_text(f"User {vip_user_id} has been removed from VIP list.")
    else:
        await update.message.reply_text(f"User {vip_user_id} is not in VIP list.")

async def vip_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_user_id = update.message.from_user.id
    if admin_user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    vip_list_text = "VIP Users:\n"
    for vip_user_id in bot_data["premium_users"]:
        remaining_days = calculate_remaining_days(vip_user_id)
        vip_list_text += f"- User ID: <code>{vip_user_id}</code>, Remaining Days: {remaining_days}\n"

    await update.message.reply_text(vip_list_text, parse_mode='HTML')

def calculate_remaining_days(user_id):
    current_time = datetime.now()
    start_time_str = bot_data["vip_added_dates"].get(str(user_id))

    if start_time_str is None:
        return 0

    start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
    premium_duration = current_time - start_time
    remaining_days = 30 - premium_duration.days

    return remaining_days if remaining_days >= 0 else 0

async def add_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addban <user_id> <reason>")
        return

    ban_user_id = context.args[0]
    reason = " ".join(context.args[1:])
    
    if ban_user_id in bot_data["banned_users"]:
        await update.message.reply_text(f"User {ban_user_id} is already banned.")
        return

    bot_data["banned_users"][ban_user_id] = reason
    save_data()

    await update.message.reply_text(f"User {ban_user_id} has been banned for {reason}.")
    

async def remove_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeban <user_id>")
        return

    ban_user_id = context.args[0]
    if ban_user_id in bot_data["banned_users"]:
        del bot_data["banned_users"][ban_user_id]
        save_data()
        await update.message.reply_text(f"Ban has been removed for user {ban_user_id}.")
    else:
        await update.message.reply_text(f"User {ban_user_id} is not currently banned.")

async def ban_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_user_id = update.message.from_user.id
    if admin_user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    banned_list_text = "Banned Users:\n"
    for user_id, reason in bot_data["banned_users"].items():
        banned_list_text += f"- User ID: <code>{user_id}</code>, Reason: {reason}\n"

    await update.message.reply_text(banned_list_text, parse_mode='HTML')

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    await update.message.reply_text(f"Your user ID is: ```{user_id}```", parse_mode='HTML')


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if str(user_id) in bot_data["premium_users"]:
        await update.message.reply_text(get_message(user_id, 'premium_true'))
    else:
        await update.message.reply_text(get_message(user_id, 'premium_false'))

def reset_limits():
    while True:
        time.sleep(60)
        current_time = time.time()
        for user_id in list(bot_data["user_limits"].keys()):
            if current_time - bot_data["user_last_daily_reset"].get(str(user_id), current_time) >= 86400:
                bot_data["user_daily_limit"][str(user_id)] = 60 if str(user_id) in bot_data["premium_users"] else 20
                bot_data["user_limits"][str(user_id)] = 3 if str(user_id) in bot_data["premium_users"] else 1
                bot_data["user_last_daily_reset"][str(user_id)] = current_time
            elif current_time - bot_data["user_last_reset"][str(user_id)] >= 60:
                bot_data["user_limits"][str(user_id)] = 3 if str(user_id) in bot_data["premium_users"] else 1
                bot_data["user_last_reset"][str(user_id)] = current_time

        save_data()



def get_user_id_from_update(update: Update) -> str:
    return str(update.message.from_user.id)

import html

# در تابع process_message:

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = get_user_id_from_update(update)
        username = update.message.from_user.username or "null"
        msg = update.message.text

       
        # چک کردن دستورات و پردازش آن‌ها
        if msg.startswith('/'):
            command = msg.split()[0][1:]  # حذف کاراکتر / و دریافت کامند

            # دستورات مدیریتی
            if command == 'datadb':
                await send_data(update, context)
            elif command == 'viplist':
                await vip_list(update, context)
            elif command == 'banlist':
                await ban_list(update, context)
            else:
                # سایر دستورات
                if command == 'start':
                    await start(update, context)
                elif command == 'help':
                    await help_command(update, context)
                elif command == 'limits':
                    await limits_command(update, context)
                elif command == 'lang':
                    await language_command(update, context)
                elif command == 'premium':
                    await premium_command(update, context)
                elif command == 'id':
                    await get_user_id(update, context)

            return  # از ارسال پیام به API جلوگیری می‌شود

        # بررسی بن بودن کاربر
        if str(user_id) in bot_data["banned_users"]:
            reason = bot_data["banned_users"][str(user_id)]
            await update.message.reply_text(f"Sorry, you are banned due to {reason} and cannot use the bot.⛔️")
            return

        current_time = time.time()

        # تنظیم محدودیت‌ها و محدودیت‌های روزانه
        if str(user_id) not in bot_data["user_limits"]:
            bot_data["user_limits"][str(user_id)] = 3 if str(user_id) in bot_data["premium_users"] else 1
            bot_data["user_daily_limit"][str(user_id)] = 60 if str(user_id) in bot_data["premium_users"] else 20
            bot_data["user_last_reset"][str(user_id)] = current_time
            bot_data["user_last_daily_reset"][str(user_id)] = current_time
            bot_data["total_questions_asked"][str(user_id)] = 0

        # بررسی محدودیت‌های روزانه و دقیقه‌ای
        if current_time - bot_data["user_last_daily_reset"][str(user_id)] >= 86400:
            bot_data["user_daily_limit"][str(user_id)] = 60 if str(user_id) in bot_data["premium_users"] else 20
            bot_data["user_limits"][str(user_id)] = 3 if str(user_id) in bot_data["premium_users"] else 1
            bot_data["user_last_daily_reset"][str(user_id)] = current_time
        elif current_time - bot_data["user_last_reset"][str(user_id)] >= 60:
            bot_data["user_limits"][str(user_id)] = 3 if str(user_id) in bot_data["premium_users"] else 1
            bot_data["user_last_reset"][str(user_id)] = current_time

        # بررسی اینکه کاربر به محدودیت روزانه یا دقیقه‌ای نرسیده باشد
        if bot_data["user_daily_limit"][str(user_id)] <= 0:
            await update.message.reply_text(get_message(user_id, 'daily_limit'))
            return

        if bot_data["user_limits"][str(user_id)] <= 0:
            remaining_time = int((60 - (current_time - bot_data["user_last_reset"][str(user_id)])))
            await update.message.reply_text(get_message(user_id, 'minute_limit', remaining_time=remaining_time))
        else:
            bot_data["user_limits"][str(user_id)] -= 1
            bot_data["user_daily_limit"][str(user_id)] -= 1
            bot_data["total_questions_asked"][str(user_id)] += 1

            # ارسال پیام "در حال پردازش" و ذخیره کردن آیدی پیام
            await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
            processing_message = await update.message.reply_text(get_message(str(user_id), 'processing'))
            processing_message_id = processing_message.message_id

            try:
                api_url_with_user_id = f'http://tiamo.freehost.io/wl-ai-bot/ai.php?userid={user_id}&username={username}&pass=ljkfkwevjfdhdwevjdhwvnhjgdshfghjsdvfwgtfvcuwyrvcsiuyrfwesvfsvfjhsvufv2wvfeywufecvduwqtucfuqewfc&msg='
                response = requests.get(f"{api_url_with_user_id}{msg}")
                response.raise_for_status()
                answer = response.text

                # Escape special characters using html.escape
                answer = re.sub(r'([~])', r'\\\1', answer)

                # حذف پیام "در حال پردازش"
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_message_id)

                # ارسال پاسخ API به عنوان پیام جدید
                await update.message.reply_text(answer, parse_mode='MarkdownV2')
            except requests.RequestException as e:
                # در صورت بروز خطا، پیام "در حال پردازش" حذف شده و پیام خطا ارسال می‌شود
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_message_id)
                answer = get_message(str(user_id), 'error', error=str(e))
                await update.message.reply_text(answer)

    except Exception as e:
        print(f"An error occurred: {e}")




async def send_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_user_id = update.message.from_user.id
    if admin_user_id != ADMIN_USER_ID:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    try:
        with open(DATA_FILE, 'rb') as file:
            await context.bot.send_document(chat_id=admin_user_id, document=file)
        await update.message.reply_text("Bot data file has been sent successfully.")
    except FileNotFoundError:
        await update.message.reply_text("Data file not found.")



def main() -> None:
    print("Bot started!")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("datadb", send_data))
    application.add_handler(CommandHandler("limits", limits_command))
    application.add_handler(CommandHandler("lang", language_command))
    application.add_handler(CommandHandler("addvip", add_vip))
    application.add_handler(CommandHandler("id", get_user_id))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("removevip", remove_vip))
    application.add_handler(CommandHandler("viplist", vip_list))
    application.add_handler(CommandHandler("addban", add_ban))
    application.add_handler(CommandHandler("removeban", remove_ban))
    application.add_handler(CommandHandler("banlist", ban_list))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    application.add_handler(CallbackQueryHandler(button))

    reset_thread = Thread(target=reset_limits)
    reset_thread.daemon = True
    reset_thread.start()

    application.run_polling()

if __name__ == '__main__':
    main()
