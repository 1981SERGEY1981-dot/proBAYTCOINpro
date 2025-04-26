import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler


# Замените 'YOUR_TOKEN' на токен вашего бота, полученный от BotFather
TELEGRAM_TOKEN = '7327131134:AAE-NuNaSqypTpnfXWfQt2Y72pspj-JmDLw'

# Глобальные переменные для подписки
subscribed_chats = set()
last_block_index = None  # Для отслеживания последнего известного блока

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я BAYTCOIN Bot. Введите /help для получения списка команд.')

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - начать общение\n"
        "/help - помощь\n"
        "/latest - получить информацию о последнем блоке\n"
        "/stats - получить статистику блокчейна"
        "/subscribe - подписаться на уведомления о новых блоках\n"
        "/unsubscribe - отписаться от уведомлений о новых блоках"
    )

# Команда /latest
async def latest_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import requests
    try:
        response = requests.get('http://localhost:5000/chain')
        data = response.json()
        chain = data.get('chain', [])
        if not chain:
            await update.message.reply_text("Цепочка пуста.")
        else:
            last_block = chain[-1]
            text = (
                f"Последний блок:\n"
                f"Индекс: {last_block['index']}\n"
                f"Время: {last_block['timestamp']}\n"
                f"Proof: {last_block['proof']}\n"
                f"Difficulty: {last_block['difficulty']}\n"
                f"Prev Hash: {last_block['previous_hash']}\n"
                f"Merkle Root: {last_block.get('merkle_root', 'N/A')}\n"
                f"Количество транзакций: {len(last_block['transactions'])}"
            )
            await update.message.reply_text(text)
    except Exception as e:
        logger.error("Ошибка при получении последнего блока: %s", e)
        await update.message.reply_text("Ошибка при получении данных о блоке.")

# Команда /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import requests
    try:
        response = requests.get('http://localhost:5000/stats')
        data = response.json()
        text = (
            f"Статистика блокчейна:\n"
            f"Общее число блоков: {data.get('total_blocks')}\n"
            f"Общее число транзакций: {data.get('total_transactions')}\n"
            f"Ожидающих транзакций: {data.get('pending_transactions')}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        logger.error("Ошибка при получении статистики: %s", e)
        await update.message.reply_text("Ошибка при получении статистики.")

# Команда /subscribe - подписка на уведомления о новых блоках
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribed_chats.add(chat_id)
    await update.message.reply_text("Вы подписались на уведомления о новых блоках.")

# Команда /unsubscribe - отписка от уведомлений о новых блоках
async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribed_chats.discard(chat_id)
    await update.message.reply_text("Вы отписались от уведомлений о новых блоках.")

# Функция для проверки нового блока и отправки уведомлений подписанным пользователям
async def notify_new_block(context: ContextTypes.DEFAULT_TYPE):
    global last_block_index
    try:
        response = requests.get('http://localhost:5000/chain')
        data = response.json()
        chain = data.get('chain', [])
        if chain:
            latest = chain[-1]
            # Если последний блок новый, обновляем и рассылаем уведомления
            if last_block_index is None or latest['index'] > last_block_index:
                last_block_index = latest['index']
                message = (
                    f"Новый блок добыт!\n"
                    f"Индекс: {latest['index']}\n"
                    f"Proof: {latest['proof']}\n"
                    f"Difficulty: {latest['difficulty']}"
                )
                for chat_id in subscribed_chats:
                    await context.bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error("Ошибка при уведомлении о новом блоке: %s", e)

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("latest", latest_block))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Добавляем задачу для периодической проверки новых блоков.
    # Например, проверять каждые 30 секунд.
    application.job_queue.run_repeating(notify_new_block, interval=30, first=10)

    # Запускаем бота (метод run_polling запускает опрос Telegram API)
    application.run_polling()
    logger.info("BAYTCOIN Telegram Bot запущен и работает в режиме опроса.")

if __name__ == '__main__':
    main()

