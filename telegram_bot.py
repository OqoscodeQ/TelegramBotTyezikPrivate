import logging
import os
import signal
import asyncio
import random
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError, Conflict
from flask import Flask

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота и твой username для уведомлений
TOKEN = os.getenv("TOKEN", "7996047867:AAG0diMuw5uhqGUVSYNcUPAst8hm2R_G47Q")
ADMIN_USERNAME = "@Tyezik"  # Твой username для уведомлений

# Список товаров
PRODUCTS = [
    {"name": "Буст макс ранга", "price": "200 руб", "image": "https://i.imgur.com/5KqL9vZ.jpg"},
    {"name": "Буст мифик лиги", "price": "200 руб", "image": "https://i.imgur.com/5KqL9vZ.jpg"},
    {"name": "Буст кубки от 0 до 500 и от 500 до 1000 кубков", "price": "от 100 рублей до 150 рублей (цена договорная)",
     "image": "https://i.imgur.com/9vJ1R2L.jpg"},
    {"name": "Буст квестов", "price": "150 руб", "image": "https://i.imgur.com/8n7mY4h.jpg"},
    {"name": "Предложить свою услугу", "price": "цену обговорим", "image": "https://i.imgur.com/x7p3Z0P.jpg"}
]

# Логи и лиги
LEAGUES = ["Бронза", "Серебро", "Золото", "Алмаз", "Мифик"]
COMMENTS = {
    "win": ["Отличная интуиция! 🎉 Ты угадал лигу!", "Ты мастер предсказаний! 💪", "Потрясающе! Ты попал в цель! 😎"],
    "lose": ["Увы, не угадал! 😂 К сожалению, у тебя была только одна попытка!", "Почти получилось! 😅 Но у тебя была только одна попытка!",
             "Не повезло на этот раз! У тебя была только одна попытка!"]
}

# Настройка Flask
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running", 200

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, played INTEGER, wins INTEGER, invites INTEGER, subscribed INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leaderboard 
                 (username TEXT PRIMARY KEY, score INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS achievements 
                 (username TEXT, achievement TEXT, PRIMARY KEY (username, achievement))''')
    conn.commit()
    conn.close()

# Обновление данных пользователя
def update_user(context, user_id, username, played=False, win=False, invite=False, subscribe=False):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (username, played, wins, invites, subscribed) VALUES (?, 0, 0, 0, 0)",
              (username,))
    if played:
        c.execute("UPDATE users SET played = 1 WHERE username = ?", (username,))
    if win:
        c.execute("UPDATE users SET wins = wins + 1 WHERE username = ?", (username,))
    if invite:
        c.execute("UPDATE users SET invites = invites + 1 WHERE username = ?", (username,))
    if subscribe:
        c.execute("UPDATE users SET subscribed = 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()

# Обновление лидерборда
def update_leaderboard(context, username, score):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO leaderboard (username, score) VALUES (?, ?)", (username, score))
    conn.commit()
    conn.close()

# Добавление ачивки
def add_achievement(context, username, achievement):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO achievements (username, achievement) VALUES (?, ?)", (username, achievement))
    conn.commit()
    conn.close()

# Уведомление администратору
async def notify_admin(context, message):
    try:
        await context.bot.send_message(chat_id=ADMIN_USERNAME, text=message)
    except TelegramError as e:
        logger.error(f"Ошибка при отправке уведомления админу: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Список товаров", callback_data='catalog')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "Привет! Ты попал в моего бота! 😎\n"
        "В этом боте ты можешь ознакомиться с моими услугами.\n"
        "Все проходит строго лично через меня.\n"
        "Напиши мне, если тебе что-то приглянется!"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info("Команда /start выполнена")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    logger.info(f"Получен callback: {query.data}")

    try:
        if query.data == 'catalog':
            await query.message.reply_text("📋 Мои услуги:")
            for i, product in enumerate(PRODUCTS, 1):
                message = f"{i}. {product['name']} - {product['price']}"
                keyboard = [[InlineKeyboardButton("Выбрать", callback_data=f"product_{i}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.message.reply_photo(photo=product['image'], caption=message, reply_markup=reply_markup)
                except TelegramError as e:
                    logger.error(f"Ошибка при отправке фото для {product['name']}: {e}")
                    await query.message.reply_text(message, reply_markup=reply_markup)

        elif query.data.startswith('product_'):
            product_index = int(query.data.split('_')[1]) - 1
            if 0 <= product_index < len(PRODUCTS):
                product = PRODUCTS[product_index]
                user = query.from_user
                username = user.username if user.username else str(user.id)
                requisites_message = (
                    f"Вы выбрали: {product['name']} - {product['price']}\n\n"
                    "Реквизиты:\n"
                    f"{ADMIN_USERNAME} (пишите только по делу, прошу не спамить, могу не отвечать)\n"
                    "Ссылка на FunPay: https://funpay.com/users/15119175\n"
                    "Ссылка на https://www.donationalerts.com/r/makarovbyshop\n"
                    "(прошу отправляйте точную сумму и в комментарий поясните за что платите, "
                    "также не оплачивайте сразу, только после консультации со мной)\n"
                    "Также гарантированно верну деньги, если не смогу выполнить заказ\n\n"
                    "Хочешь выиграть скидку? Введи /start_rang и сыграй в 'Угадай лигу'!"
                )
                await query.message.reply_text(requisites_message)
                # Уведомление админу о намерении покупки
                await notify_admin(context, f"🔔 Новый заказ! Пользователь {username} выбрал: {product['name']} - {product['price']}. Проверь!")
                logger.info(f"Уведомление отправлено админу о выборе {product['name']} пользователем {username}")
            else:
                await query.message.reply_text("Ошибка: выбран некорректный товар.")
                logger.error(f"Некорректный индекс продукта: {product_index}")

    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
        await query.message.reply_text("Произошла ошибка, попробуйте позже.")
        await notify_admin(context, f"Telegram API Error: {e}")

async def start_rang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else str(user_id)
    if context.user_data.get(f'played_{username}'):
        await update.message.reply_text("Извините, но вы уже пытали удачу! У вас была только одна попытка.")
        return
    context.user_data['correct_league'] = random.choice(LEAGUES)
    await update.message.reply_text(
        "Привет давай сыграем в игру угадай лигу, ты должен угадать лигу которую я загадаю и получишь скидку, "
        "напиши свою догадку и получи скидку! (Варианты: Бронза, Серебро, Золото, Алмаз, Мифик) "
        "У тебя только одна попытка!"
    )
    context.user_data['game_active'] = True
    logger.info(f"Игра 'Угадай лигу' начата для {username}. Загадана лига: {context.user_data['correct_league']}")

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('game_active'):
        user_id = update.effective_user.id
        username = update.effective_user.username if update.effective_user.username else str(user_id)
        user_guess = update.message.text.strip().capitalize()
        correct_league = context.user_data['correct_league']
        result = user_guess == correct_league
        discount_message = ""
        if result:
            token_number = random.randint(1000, 9999)
            discount_token = f"Token-{token_number} 5%"
            discount_message = f"\n🎁 Поздравляю! Ты угадал и получил 5% скидку! Используй токен: {discount_token} при заказе!"
            update_user(context, user_id, username, played=True, win=True)
            update_leaderboard(context, username, 1)
            add_achievement(context, username, "First Win")
        else:
            update_user(context, user_id, username, played=True)
        response = (
            f"Твой ответ: {user_guess}\n"
            f"Загаданная лига: {correct_league}\n"
            f"{random.choice(COMMENTS['win']) if result else random.choice(COMMENTS['lose'])}"
            f"{discount_message}"
        )
        await update.message.reply_text(response)
        context.user_data['game_active'] = False
        context.user_data[f'played_{username}'] = True
        logger.info(f"Игра 'Угадай лигу' завершена для {username}. Угадал: {result}, Токен: {discount_message}")
    else:
        await update.message.reply_text("Извините, но вы уже пытали удачу! У вас была только одна попытка.")

# Новая команда для уведомления о платеже
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else str(user_id)
    if context.args:
        product = " ".join(context.args)
        await notify_admin(context, f"💰 Платёж! Пользователь {username} сообщает об оплате за: {product}. Проверь на FunPay или DonationAlerts!")
        await update.message.reply_text("Спасибо! Уведомление отправлено продавцу. Ожидай подтверждения.")
    else:
        await update.message.reply_text("Укажи товар после /paid (например, /paid Буст макс ранга).")
    logger.info(f"Команда /paid выполнена для {username}")

# Интерактивные функции
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT username, score FROM leaderboard ORDER BY score DESC LIMIT 5")
    leaders = c.fetchall()
    conn.close()
    if leaders:
        msg = "🏆 Топ-5 лидеров:\n" + "\n".join([f"{i}. {u[0]}: {u[1]} очков" for i, u in enumerate(leaders, 1)])
    else:
        msg = "Лидерборд пока пуст!"
    await update.message.reply_text(msg)
    logger.info("Команда /leaderboard выполнена")

async def hint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('game_active'):
        user_id = update.effective_user.id
        username = update.effective_user.username if update.effective_user.username else str(user_id)
        correct_league = context.user_data['correct_league']
        hint = f"Подсказка: лига начинается на '{correct_league[0]}'. Стоимость подсказки: 50 руб (оплати через https://funpay.com/users/15119175)!"
        await update.message.reply_text(hint)
        logger.info(f"Подсказка выдана для {username}")
    else:
        await update.message.reply_text("Сначала начни игру с /start_rang!")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Весёлый стиль", callback_data='style_fun'),
                 InlineKeyboardButton("Формальный стиль", callback_data='style_formal')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери стиль сообщений:", reply_markup=reply_markup)
    logger.info("Команда /settings выполнена")

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    style = query.data.split('_')[1]
    user_id = query.effective_user.id
    username = query.effective_user.username if query.effective_user.username else str(user_id)
    context.user_data[f'style_{username}'] = style
    await query.message.reply_text(f"Стиль установлен: {style}!")
    logger.info(f"Стиль {style} установлен для {username}")

# Монетизация
async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chance = random.random()
    if chance < 0.1:
        discount = "15%"
        token = f"Token-{random.randint(1000, 9999)} {discount}"
    elif chance < 0.3:
        discount = "10%"
        token = f"Token-{random.randint(1000, 9999)} {discount}"
    else:
        discount = "5%"
        token = f"Token-{random.randint(1000, 9999)} {discount}"
    msg = f"🎉 Акция! Буст макс ранга со скидкой {discount} до 10 июня 2025! Используй токен: {token}!"
    await update.message.reply_text(msg)
    logger.info("Команда /promo выполнена")

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else str(user_id)
    referral_link = f"https://t.me/{context.bot.username}?start={username}"
    await update.message.reply_text(f"Пригласи друга по ссылке: {referral_link}\nЗа каждого друга получи 5% скидку!")
    update_user(context, user_id, username)
    logger.info(f"Команда /invite выполнена для {username}")

# Интеграции
async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        feedback_text = " ".join(context.args)
        await context.bot.send_message(chat_id=ADMIN_USERNAME, text=f"Отзыв от {update.effective_user.username}: {feedback_text}")
        await update.message.reply_text("Спасибо за отзыв! Он отправлен администратору.")
    else:
        await update.message.reply_text("Пожалуйста, введи отзыв после /feedback (например, /feedback Отличный бот!).")
    logger.info("Команда /feedback выполнена")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else str(user_id)
    update_user(context, user_id, username, subscribe=True)
    await update.message.reply_text("Вы подписаны на уведомления!")
    logger.info(f"Подписка активирована для {username}")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else str(user_id)
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET subscribed = 0 WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    await update.message.reply_text("Вы отписаны от уведомлений!")
    logger.info(f"Отписка выполнена для {username}")

# Игровые улучшения
async def guess_cups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get(f'played_cups_{update.effective_user.username or update.effective_user.id}'):
        await update.message.reply_text("Извините, вы уже пытали удачу в этой игре!")
        return
    correct_cups = random.randint(0, 1000)
    context.user_data['correct_cups'] = correct_cups
    await update.message.reply_text("Угадай количество кубков (0-1000)! Напиши число.")
    context.user_data['game_cups_active'] = True
    logger.info(f"Игра 'Угадай кубки' начата. Загаданы кубки: {correct_cups}")

async def handle_cups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('game_cups_active'):
        try:
            user_guess = int(update.message.text)
            correct_cups = context.user_data['correct_cups']
            result = abs(user_guess - correct_cups) < 50
            if result:
                token_number = random.randint(1000, 9999)
                discount_token = f"Token-{token_number} 5%"
                discount_message = f"\n🎁 Поздравляю! Ты угадал и получил 5% скидку! Используй токен: {discount_token}"
                update_user(context, update.effective_user.id, update.effective_user.username or str(update.effective_user.id), played=True, win=True)
                add_achievement(context, update.effective_user.username or str(update.effective_user.id), "Cups Master")
            else:
                discount_message = ""
            response = (
                f"Твой ответ: {user_guess}\n"
                f"Загаданные кубки: {correct_cups}\n"
                f"{'Отлично! Ты близко!' if result else 'Не угадал, попробуй в другой игре!'}{discount_message}"
            )
            await update.message.reply_text(response)
            context.user_data['game_cups_active'] = False
            context.user_data[f'played_cups_{update.effective_user.username or update.effective_user.id}'] = True
        except ValueError:
            await update.message.reply_text("Пожалуйста, введи число!")
    else:
        await update.message.reply_text("Сначала начни игру с /guess_cups!")

async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username if update.effective_user.username else str(update.effective_user.id)
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT achievement FROM achievements WHERE username = ?", (username,))
    achievements_list = c.fetchall()
    conn.close()
    if achievements_list:
        msg = f"🏅 Твои достижения, {username}:\n" + "\n".join([a[0] for a in achievements_list])
    else:
        msg = f"У тебя пока нет достижений, {username}!"
    await update.message.reply_text(msg)
    logger.info(f"Команда /achievements выполнена для {username}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username if update.effective_user.username else str(update.effective_user.id)
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT played, wins, invites FROM users WHERE username = ?", (username,))
    data = c.fetchone()
    conn.close()
    if data:
        played, wins, invites = data
        msg = f"📊 Статистика {username}:\nИгры: {played}\nПобеды: {wins}\nПриглашения: {invites}"
    else:
        msg = f"Статистика для {username} не найдена!"
    await update.message.reply_text(msg)
    logger.info(f"Команда /stats выполнена для {username}")

# Технические улучшения
async def send_error_to_admin(context, error_message):
    try:
        await context.bot.send_message(chat_id=ADMIN_USERNAME, text=f"Ошибка: {error_message}")
    except TelegramError as e:
        logger.error(f"Ошибка при отправке уведомления об ошибке: {e}")

async def check_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subscribed_users = []
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE subscribed = 1")
    subscribed_users = [row[0] for row in c.fetchall()]
    conn.close()
    if subscribed_users:
        msg = "🔧 Проверка услуг: все в порядке! Новые услуги скоро на https://funpay.com/users/15119175"
        for user in subscribed_users:
            await context.bot.send_message(chat_id=user, text=msg)
    await asyncio.sleep(86400)  # Проверка раз в день

# Запуск
async def main() -> None:
    try:
        init_db()
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("start_rang", start_rang))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        application.add_handler(CommandHandler("hint", hint))
        application.add_handler(CommandHandler("settings", settings))
        application.add_handler(CommandHandler("promo", promo))
        application.add_handler(CommandHandler("invite", invite))
        application.add_handler(CommandHandler("feedback", feedback))
        application.add_handler(CommandHandler("subscribe", subscribe))
        application.add_handler(CommandHandler("unsubscribe", unsubscribe))
        application.add_handler(CommandHandler("guess_cups", guess_cups))
        application.add_handler(CommandHandler("achievements", achievements))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("paid", paid))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(CallbackQueryHandler(settings_callback, pattern='^style_'))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'), handle_cups))
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Бот запущен")

        port = int(os.getenv("PORT", 10000))
        asyncio.create_task(asyncio.to_thread(lambda: app.run(host='0.0.0.0', port=port)))
        asyncio.create_task(check_services(None, application))

        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения, останавливаем бот...")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        await send_error_to_admin(application, f"Startup Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())