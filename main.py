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
# تنظیمات و متغیرهای مورد نیاز
TOKEN = '7401177865:AAGnSRLsqOkaZdReuFsV0mN1tMDv-i4R6b8'
API_KEY = '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'
API_URL = f'https://api.wl-std.com/panel/assets/script/hallo.php?key={API_KEY}&msg='
DATA_FILE = 'bot_data.json'
ADMIN_USER_ID = 5694969786

keep_alive()
# تابع برای بارگذاری داده‌ها از فایل JSON
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {
    "user_limits": {},
    "user_daily_limit": {},  # لیمیت روزانه
    "user_language": {},  # زبان کاربران
    "total_questions_asked": {},  # تعداد کل سوالات پرسیده شده توسط هر کاربر
    "premium_users": [],  # لیست کاربران پرمیوم
    "vip_added_dates": {},  # تاریخ افزودن کاربران به لیست VIP
    "banned_users": {},  # لیست کاربران بن شده به همراه دلیل بن
    "user_minute_limit": {},  # لیمیت پیام دقیقه‌ای
    "user_last_minute_reset": {},  # زمان آخرین ریست لیمیت پیام دقیقه‌ای
    "user_last_daily_reset": {}  # زمان آخرین ریست لیمیت روزانه
}


    if "banned_users" not in data:
        data["banned_users"] = {}

    return data

# تابع برای ذخیره داده‌ها در فایل JSON
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(bot_data, f)

# تابع برای بارگیری پیام‌ها از فایل JSON مربوطه
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
bot_data = load_data()

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
    user_daily_limit = bot_data["user_daily_limit"].get(str(user_id), 100 if str(user_id) in bot_data["premium_users"] else 50)
    user_minute_limit = bot_data["user_minute_limit"].get(str(user_id), 6 if str(user_id) in bot_data["premium_users"] else 3)
    daily_reset_timestamp = bot_data["user_last_daily_reset"].get(str(user_id), current_time) + 86400
    reset_time = datetime.fromtimestamp(daily_reset_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    time_until_reset = daily_reset_timestamp - current_time
    hours, remainder = divmod(time_until_reset, 3600)
    minutes, _ = divmod(remainder, 60)
    
    await update.message.reply_text(get_message(
        user_id,
        'limits',
        remaining_minute=user_minute_limit,
        remaining_daily=user_daily_limit,
        hours=int(hours),
        minutes=int(minutes),
        total_questions_asked=bot_data["total_questions_asked"].get(str(user_id), 0)
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

    bot_data["user_language"][str(user_id)] = language_code
    save_data()

    await query.answer()
    await query.edit_message_text(text=get_message(user_id, 'language_changed', language=language_code))

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
    await update.message.reply_text(f"Your user ID is: <code>{user_id}</code>", parse_mode='HTML')


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
        
        for user_id in list(bot_data["user_last_minute_reset"].keys()):
            if current_time - bot_data["user_last_minute_reset"].get(user_id, current_time) >= 60:
                bot_data["user_minute_limit"][user_id] = 6 if user_id in bot_data["premium_users"] else 3
                bot_data["user_last_minute_reset"][user_id] = current_time
        
        for user_id in list(bot_data["user_last_daily_reset"].keys()):
            if current_time - bot_data["user_last_daily_reset"].get(user_id, current_time) >= 86400:
                bot_data["user_daily_limit"][user_id] = 100 if user_id in bot_data["premium_users"] else 50
                bot_data["user_last_daily_reset"][user_id] = current_time
        
        # ذخیره سازی داده‌ها بعد از هر بار ریست لیمیت
        save_data(bot_data)


def get_user_id_from_update(update: Update) -> str:
    return str(update.message.from_user.id)

import html

# در تابع process_message:
async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = get_user_id_from_update(update)
        
        # چک کردن برای وجود کاربر در لیست بن شده‌ها
        if str(user_id) in bot_data["banned_users"]:
            reason = bot_data["banned_users"][str(user_id)]
            await update.message.reply_text(f"متاسفانه به دلیل {reason} امکان استفاده از ربات برای شما وجود ندارد.⛔")
            return
        
        current_time = time.time()
        
        # بررسی و به‌روزرسانی لیمیت‌ها برای کاربر
        if str(user_id) not in bot_data["user_limits"]:
            bot_data["user_limits"][str(user_id)] = 6 if str(user_id) in bot_data["premium_users"] else 3
            bot_data["user_daily_limit"][str(user_id)] = 100 if str(user_id) in bot_data["premium_users"] else 50
            bot_data["user_last_minute_reset"][str(user_id)] = current_time
            bot_data["user_last_daily_reset"][str(user_id)] = current_time
            bot_data["total_questions_asked"][str(user_id)] = 0
        
        # بررسی و به‌روزرسانی لیمیت پیام دقیقه‌ای
        if current_time - bot_data["user_last_minute_reset"][str(user_id)] >= 60:
            bot_data["user_limits"][str(user_id)] = 6 if str(user_id) in bot_data["premium_users"] else 3
            bot_data["user_last_minute_reset"][str(user_id)] = current_time
        
        # بررسی و به‌روزرسانی لیمیت روزانه
        if current_time - bot_data["user_last_daily_reset"][str(user_id)] >= 86400:
            bot_data["user_daily_limit"][str(user_id)] = 100 if str(user_id) in bot_data["premium_users"] else 50
            bot_data["user_limits"][str(user_id)] = 6 if str(user_id) in bot_data["premium_users"] else 3
            bot_data["user_last_daily_reset"][str(user_id)] = current_time
        
        # اگر لیمیت روزانه تمام شده باشد
        if bot_data["user_daily_limit"][str(user_id)] <= 0:
            await update.message.reply_text(get_message(user_id, 'daily_limit'))
            return
        
        # اگر لیمیت پیام دقیقه‌ای تمام شده باشد
        if bot_data["user_limits"][str(user_id)] <= 0:
            remaining_time = int((60 - (current_time - bot_data["user_last_minute_reset"][str(user_id)])))
            await update.message.reply_text(get_message(user_id, 'minute_limit', remaining_time=remaining_time))
        else:
            # کاهش لیمیت‌ها و افزایش تعداد سوالات پرسیده شده
            bot_data["user_limits"][str(user_id)] -= 1
            bot_data["user_daily_limit"][str(user_id)] -= 1
            bot_data["total_questions_asked"][str(user_id)] += 1
            
            msg = update.message.text
            await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
            processing_message = await update.message.reply_text(get_message(str(user_id), 'processing'))
    
            try:
                user_id_param = str(user_id)
                api_url_with_user_id = f'https://api.wl-std.com/panel/assets/script/hallo.php?key={API_KEY}&userid={user_id_param}&msg='
                response = requests.get(f"{api_url_with_user_id}{msg}")
                response.raise_for_status()
                answer = response.text
                
                # Escape special characters using html.escape
                answer = re.sub(r'([_[\]()~>#&<*+-=|({}.!])', r'\\\1', answer)
            except requests.RequestException as e:
                answer = get_message(str(user_id), 'error', error=str(e))
    
            await context.bot.send_chat_action(chat_id=update.message.chat_id, action="cancel")
            await context.bot.edit_message_text(
                chat_id=processing_message.chat_id,
                message_id=processing_message.message_id,
                text=answer,
                parse_mode='MarkdownV2'
            )
            
    except Exception as e:
        print(f"An error occurred: {e}")



def main() -> None:
    print("Bot started!")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
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

    reset_limits_thread = Thread(target=reset_limits)
    reset_limits_thread.start()

    application.run_polling()

if __name__ == '__main__':
    main()
