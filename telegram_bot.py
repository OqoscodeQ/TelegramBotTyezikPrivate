import logging
import os
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError
from flask import Flask, request

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота и данные админа
TOKEN = os.getenv("TOKEN", "7833966397:AAEwA91PbqzuYberVdNwF2bATaWsZD_055U")
ADMIN_USERNAME = "@oqoscode"
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "1254694557")

# Список товаров, лиги, цвета, шрифты
PRODUCTS = [
    {"name": "Буст макс ранга", "price": "200 руб", "image": "https://imgur.com/aX1QifJ"},
    {"name": "Буст мифик лиги", "price": "200 руб", "image": "https://imgur.com/r6xHSuB"},
    {"name": "Буст кубки от 0 до 500 и от 500 до 1000 кубков", "price": "от 100 рублей до 150 рублей (цена договорная)",
     "image": "https://imgur.com/x9YixzM"},
    {"name": "Буст квестов", "price": "150 руб", "image": "https://imgur.com/qIwBeF5"},
    {"name": "Предложить свою услугу", "price": "цену обговорим", "image": "https://via.placeholder.com/150"}
]

LEAGUES = ["Бронза", "Серебро", "Золото", "Алмаз", "Мифик"]
COMMENTS = {
    "win": ["Отличная интуиция! 🎉 Ты угадал лигу!", "Ты мастер предсказаний! 💪", "Потрясающе! Ты попал в цель! 😎"],
    "lose": ["Увы, не угадал! 😂 К сожалению, у тебя была только одна попытка!",
             "Почти получилось! 😅 Но у тебя была только одна попытка!",
             "Не повезло на этот раз! У тебя была только одна попытка!"]
}

COLORS = {
    "red": "🔴",
    "blue": "🔵",
    "green": "🟢",
    "yellow": "🟡",
    "purple": "🟣",
    "orange": "🟠"
}

FONTS = {
    "normal": lambda x: x,
    "bold": lambda x: f"<b>{x}</b>",
    "italic": lambda x: f"<i>{x}</i>",
    "monospace": lambda x: f"<code>{x}</code>",
    "emoji": lambda x: f"{x} ✨",
    "fancy": lambda x: "".join(chr(ord(c) + 0x1D400) if c.isalpha() else c for c in x)
}


# Уведомление администратору
async def notify_admin(context, message):
    try:
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=message)
        elif ADMIN_USERNAME:
            await context.bot.send_message(chat_id=ADMIN_USERNAME, text=message)
        logger.info(f"Уведомление админу отправлено: {message}")
    except TelegramError as e:
        logger.error(f"Ошибка при отправке уведомления админу: {e}")


# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Получена команда /start от {update.effective_user.id}")
    keyboard = [
        [InlineKeyboardButton("Список товаров", callback_data='catalog')],
        [InlineKeyboardButton("Игра: Угадай лигу", callback_data='start_rang')],
        [InlineKeyboardButton("Настройки", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = apply_style(
        "Привет! Ты попал в моего бота! 😎\nВ этом боте ты можешь ознакомиться с моими услугами.\nВсе проходит строго лично через меня.\nНапиши мне, если тебе что-то приглянется!",
        context.user_data, update.effective_user.id
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')
    logger.info("Команда /start выполнена")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    logger.info(f"Получен callback: {query.data} от {query.from_user.id}")
    await query.answer()
    try:
        if query.data == 'catalog':
            await query.message.reply_text("📋 Мои услуги:", parse_mode='HTML')
            for i, product in enumerate(PRODUCTS, 1):
                message = apply_style(f"{i}. {product['name']} - {product['price']}", context.user_data,
                                      query.from_user.id)
                keyboard = [[InlineKeyboardButton("Выбрать", callback_data=f"product_{i}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.message.reply_photo(photo=product['image'], caption=message, reply_markup=reply_markup,
                                                    parse_mode='HTML')
                except TelegramError as e:
                    logger.error(f"Ошибка при отправке фото для {product['name']}: {e}")
                    await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')

        elif query.data.startswith('product_'):
            product_index = int(query.data.split('_')[1]) - 1
            if 0 <= product_index < len(PRODUCTS):
                product = PRODUCTS[product_index]
                user = query.from_user
                username = user.id
                requisites_message = apply_style(
                    f"Вы выбрали: {product['name']} - {product['price']}\n\nРеквизиты:\n"
                    f"@oqoscode (пишите только по делу, прошу не спамить, могу не отвечать)\n"
                    "Ссылка на FunPay: https://funpay.com/users/15119175\n"
                    "Ссылка на https://www.donationalerts.com/r/makarovbyshop\n"
                    "(прошу отправляйте точную сумму и в комментарий поясните за что платите, "
                    "также не оплачивайте сразу, только после консультации со мной)\n"
                    "Также гарантированно верну деньги, если не смогу выполнить заказ",
                    context.user_data, user.id
                )
                await query.message.reply_text(requisites_message, parse_mode='HTML')
                await notify_admin(context,
                                   f"🔔 Новый заказ! Пользователь {username} выбрал: {product['name']} - {product['price']}. Проверь!")
                logger.info(f"Уведомление отправлено админу о выборе {product['name']} пользователем {username}")
            else:
                await query.message.reply_text("Ошибка: выбран некорректный товар.", parse_mode='HTML')
                logger.error(f"Некорректный индекс продукта: {product_index}")

        elif query.data == 'start_rang':
            await start_rang(query, context)

        elif query.data == 'settings':
            await settings(query, context)

        elif query.data.startswith('color_'):
            color = query.data.split('_')[1]
            user_id = query.from_user.id
            context.user_data[f'color_{user_id}'] = color
            logger.info(f"Сохранён цвет {color} для user_id {user_id}")
            await query.message.reply_text(apply_style("Цвет интерфейса изменён!", context.user_data, user_id),
                                           parse_mode='HTML')

        elif query.data.startswith('font_'):
            font = query.data.split('_')[1]
            user_id = query.from_user.id
            context.user_data[f'font_{user_id}'] = font
            logger.info(f"Сохранён шрифт {font} для user_id {user_id}")
            await query.message.reply_text(apply_style("Шрифт интерфейса изменён!", context.user_data, user_id),
                                           parse_mode='HTML')

    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
        await query.message.reply_text("Произошла ошибка, попробуйте позже.", parse_mode='HTML')
        await notify_admin(context, f"Telegram API Error: {e}")


async def start_rang(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Получена команда /start_rang от {query.from_user.id}")
    user_id = query.from_user.id
    username = query.from_user.username if query.from_user.username else str(user_id)
    chat_id = query.message.chat.id
    if context.user_data.get(f'played_{user_id}'):
        await context.bot.send_message(chat_id=chat_id, text=apply_style(
            "Извините, но вы уже пытали удачу! У вас была только одна попытка.", context.user_data, user_id),
                                       parse_mode='HTML')
        return
    context.user_data['correct_league'] = random.choice(LEAGUES)
    await context.bot.send_message(
        chat_id=chat_id,
        text=apply_style(
            "Привет давай сыграем в игру угадай лигу, ты должен угадать лигу которую я загадаю и получишь скидку, "
            "напиши свою догадку и получи скидку! (Варианты: Бронза, Серебро, Золото, Алмаз, Мифик) "
            "У тебя только одна попытка!",
            context.user_data, user_id
        ),
        parse_mode='HTML'
    )
    context.user_data['game_active'] = True
    logger.info(f"Игра 'Угадай лигу' начата для {username}. Загадана лига: {context.user_data['correct_league']}")


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Получен ответ на игру от {update.effective_user.id}: {update.message.text}")
    if context.user_data.get('game_active'):
        user_id = update.effective_user.id
        username = update.effective_user.username if update.effective_user.username else str(user_id)
        user_guess = update.message.text.strip().capitalize()
        correct_league = context.user_data.get('correct_league')
        if correct_league is None:
            logger.error(f"correct_league не определён для {username}")
            await update.message.reply_text(
                apply_style("Игра не была начата корректно. Попробуй снова с /start_rang.", context.user_data, user_id),
                parse_mode='HTML')
            return
        result = user_guess == correct_league
        discount_message = ""
        if result:
            token_number = random.randint(1000, 9999)
            discount_token = f"Token-{token_number} 5%"
            discount_message = f"\n🎁 Поздравляю! Ты угадал и получил 5% скидку! Используй токен: {discount_token} при заказе!"
        response = apply_style(
            f"Твой ответ: {user_guess}\nЗагаданная лига: {correct_league}\n"
            f"{random.choice(COMMENTS['win']) if result else random.choice(COMMENTS['lose'])}"
            f"{discount_message}",
            context.user_data, user_id
        )
        await update.message.reply_text(response, parse_mode='HTML')
        context.user_data['game_active'] = False
        context.user_data[f'played_{user_id}'] = True
        logger.info(f"Игра 'Угадай лигу' завершена для {username}. Угадал: {result}, Токен: {discount_message}")
    else:
        await update.message.reply_text(
            apply_style("Извините, но вы уже пытали удачу! У вас была только одна попытка.", context.user_data,
                        user_id), parse_mode='HTML')


async def settings(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Получена команда /settings от {query.from_user.id}")
    color_buttons = []
    for color_key in COLORS.keys():
        color_buttons.append(
            InlineKeyboardButton(f"{COLORS[color_key]} {color_key}", callback_data=f"color_{color_key}"))
    color_rows = [color_buttons[i:i + 2] for i in range(0, len(color_buttons), 2)]

    font_buttons = []
    for font_key in FONTS.keys():
        font_buttons.append(InlineKeyboardButton(f"Шрифт: {font_key}", callback_data=f"font_{font_key}"))
    font_rows = [font_buttons[i:i + 2] for i in range(0, len(font_buttons), 2)]

    settings_keyboard = color_rows + font_rows
    reply_markup = InlineKeyboardMarkup(settings_keyboard)
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=apply_style("Выбери цвет или шрифт интерфейса:", context.user_data, query.from_user.id),
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    logger.info("Меню настроек показано")


def apply_style(text, user_data, user_id):
    color = user_data.get(f'color_{user_id}', 'red')
    font_key = user_data.get(f'font_{user_id}', 'normal')
    logger.info(f"Применён цвет: {color}, шрифт: {font_key} для user_id {user_id}")
    color_emoji = COLORS.get(color, COLORS['red'])
    font_func = FONTS.get(font_key, FONTS['normal'])
    styled_text = f"{color_emoji} {font_func(text)}"
    return styled_text


# Настройка Flask
app = Flask(__name__)

# Инициализация бота
application = Application.builder().token(TOKEN).build()
application.initialize()  # Добавляем инициализацию приложения

# Регистрация обработчиков
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))


# Обработчик вебхука
@app.route('/webhook', methods=['POST'])
async def webhook():
    logger.info("Получен POST-запрос на /webhook")
    data = request.get_json()
    logger.info(f"Данные от Telegram: {data}")
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    logger.info("Обработка обновления завершена")
    return 'OK', 200


# Запуск бота
if __name__ == "__main__":
    # Установка вебхука с URL из переменной окружения
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL не задан в переменных окружения!")
        raise ValueError("Необходимо задать WEBHOOK_URL в переменных окружения.")
    logger.info(f"Установка вебхука: {WEBHOOK_URL}")
    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))

    # Запуск Flask с динамическим портом
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)