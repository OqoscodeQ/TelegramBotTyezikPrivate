import logging
import os
import signal
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError, Conflict
from flask import Flask

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = os.getenv("TOKEN", "7784851665:AAH-AkFYh1tgcYxG9ti4DZJvogAseC5hVAM")

# Список товаров с прямыми ссылками на изображения
PRODUCTS = [
    {"name": "Буст макс ранга", "price": "200 руб", "image": "https://imgur.com/aX1QifJ"},
    {"name": "Буст мифик лиги", "price": "200 руб",
     "image": "https://imgur.com/r6xHSuB"},
    {"name": "Буст кубки от 0 до 500 и от 500 до 1000 кубков", "price": "от 100 рублей до 150 рублей (цена договорная)",
     "image": "https://imgur.com/x9YixzM"},
    {"name": "Буст квестов", "price": "150 руб", "image": "https://imgur.com/qIwBeF5"},
    {"name": "Предложить свою услугу", "price": "цену обговорим",
     "image": "https://via.placeholder.com/150?text=Custom+Service"}
]

# Список возможных лиг и комментариев
LEAGUES = ["Бронза", "Серебро", "Золото", "Алмаз", "Мифик"]
COMMENTS = {
    "win": [
        "Отличная интуиция! 🎉 Ты угадал лигу!",
        "Ты мастер предсказаний! 💪",
        "Потрясающе! Ты попал в цель! 😎"
    ],
    "lose": [
        "Увы, не угадал! 😂 К сожалению, у тебя была только одна попытка!",
        "Почти получилось! 😅 Но у тебя была только одна попытка!",
        "Не повезло на этот раз! У тебя была только одна попытка!"
    ]
}

# Настройка Flask
app = Flask(__name__)


@app.route('/')
def health_check():
    return "Bot is running", 200


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("Список товаров", callback_data='catalog')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "Привет! Ты попал в моего бота! 😎\n"
        "В этом боте ты можешь ознакомиться с моими услугами.\n"
        "Все проходит строго лично через меня.\n"
        "Напиши мне, пожалуйста, если тебе что-то приглянется!"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info("Команда /start выполнена")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
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
                    await query.message.reply_photo(
                        photo=product['image'],
                        caption=message,
                        reply_markup=reply_markup
                    )
                except TelegramError as e:
                    logger.error(f"Ошибка при отправке фото для {product['name']}: {e}")
                    await query.message.reply_text(message, reply_markup=reply_markup)

        elif query.data.startswith('product_'):
            try:
                product_index = int(query.data.split('_')[1]) - 1
                if 0 <= product_index < len(PRODUCTS):
                    product = PRODUCTS[product_index]
                    requisites_message = (
                        f"Вы выбрали: {product['name']} - {product['price']}\n\n"
                        "Реквизиты:\n"
                        "@Tyezik (пишите только по делу, прошу не спамить, могу не отвечать)\n"
                        "Ссылка на https://www.donationalerts.com/r/makarovbyshop\n"
                        "(прошу отправляйте точную сумму и в комментарий поясните за что платите, "
                        "также не оплачивайте сразу, только после консультации со мной)\n"
                        "Также гарантированно верну деньги, если не смогу выполнить заказ\n\n"
                        "Хочешь выиграть скидку? Введи /start_rang и сыграй в 'Угадай лигу'!"
                    )
                    await query.message.reply_text(requisites_message)
                    logger.info(f"Отправлены реквизиты для продукта {product['name']}")
                else:
                    await query.message.reply_text("Ошибка: выбран некорректный товар.")
                    logger.error(f"Некорректный индекс продукта: {product_index}")
            except ValueError as e:
                logger.error(f"Ошибка обработки callback_data {query.data}: {e}")
                await query.message.reply_text("Ошибка при выборе товара.")

    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
        await query.message.reply_text("Произошла ошибка, попробуйте позже.")


async def start_rang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start_rang для запуска игры"""
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else str(user_id)

    # Проверка, играл ли пользователь
    if context.user_data.get(f'played_{username}'):
        await update.message.reply_text("Извините, но вы уже пытали удачу! У вас была только одна попытка.")
        return

    context.user_data['correct_league'] = random.choice(LEAGUES)  # Случайная лига
    await update.message.reply_text(
        "Привет давай сыграем в игру угадай лигу, ты должен угадать лигу которую я загадаю и получишь скидку, "
        "напиши свою догадку и получи скидку! (Варианты: Бронза, Серебро, Золото, Алмаз, Мифик) "
        "У тебя только одна попытка!"
    )
    context.user_data['game_active'] = True
    logger.info(f"Игра 'Угадай лигу' начата для {username}. Загадана лига: {context.user_data['correct_league']}")


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текста для игры 'Угадай лигу'"""
    if context.user_data.get('game_active'):
        user_id = update.effective_user.id
        username = update.effective_user.username if update.effective_user.username else str(user_id)
        user_guess = update.message.text.strip().capitalize()
        correct_league = context.user_data['correct_league']
        result = user_guess == correct_league

        # Генерация токена скидки только при правильном ответе
        discount_message = ""
        if result:
            token_number = random.randint(1000, 9999)
            discount_token = f"Token-{token_number} 5%"
            discount_message = f"\n🎁 Поздравляю! Ты угадал и получил 5% скидку! Используй токен: {discount_token} при заказе!"

        response = (
            f"Твой ответ: {user_guess}\n"
            f"Загаданная лига: {correct_league}\n"
            f"{random.choice(COMMENTS['win']) if result else random.choice(COMMENTS['lose'])}"
            f"{discount_message}"
        )
        await update.message.reply_text(response)

        # Отмечаем, что пользователь сыграл
        context.user_data['game_active'] = False
        context.user_data[f'played_{username}'] = True
        logger.info(f"Игра 'Угадай лигу' завершена для {username}. Угадал: {result}, Токен: {discount_message}")
    else:
        await update.message.reply_text("Извините, но вы уже пытали удачу! У вас была только одна попытка.")


async def main() -> None:
    """Запуск бота"""
    try:
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("start_rang", start_rang))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Бот запущен")

        # Запуск Flask-сервера для Render
        port = int(os.getenv("PORT", 10000))  # Render предоставляет порт через переменную PORT
        asyncio.create_task(asyncio.to_thread(lambda: app.run(host='0.0.0.0', port=port)))

        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения, останавливаем бот...")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
    except Conflict as e:
        logger.error(f"Конфликт с другим экземпляром бота: {e}. Убедись, что запущен только один экземпляр.")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())