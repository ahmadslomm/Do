import subprocess
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackContext

# Телеграм токен
TELEGRAM_TOKEN = '7196104221:AAEgvQfa2YEvB-WL1BBX3K_CM8Tev1bkoSs'
# URL вашего приложения
FLASK_APP_URL = 'https://click.cryptosymbiotic.com'

# Логирование
logging.basicConfig(level=logging.INFO)

# Функция запуска Flask-приложения через Gunicorn
def start_flask():
    logging.info("Запуск Flask-приложения с помощью Gunicorn...")
    # Запускаем Flask-приложение через Gunicorn
    flask_process = subprocess.Popen([
        'gunicorn',
        '-w', '2',  # Количество рабочих процессов
        '-b', '0.0.0.0:5000',  # Адрес и порт для прослушивания
        'app:app'  # Модуль и объект WSGI-приложения
    ])
    logging.info(f"Flask-приложение запущено с PID: {flask_process.pid}")
    return flask_process

def get_telegram_username(user_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat"
    params = {'chat_id': user_id}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        logging.info(f"Telegram API Response: {data}")
        if data['ok']:
            return data['result'].get('username', None)
    else:
        logging.error(f"Failed to fetch username: {response.text}")
    return None

def get_telegram_avatar(user_id):
    try:
        response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUserProfilePhotos", params={"user_id": user_id})
        data = response.json()

        if data['ok'] and data['result']['total_count'] > 0:
            file_id = data['result']['photos'][0][-1]['file_id']
            file_response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile", params={"file_id": file_id})
            file_data = file_response.json()

            if file_data['ok']:
                file_path = file_data['result']['file_path']
                avatar_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                return avatar_url
    except Exception as e:
        print(f"Error fetching avatar: {e}")
    return None

# Приветственное сообщение
welcome_text = "Welcome to the bot!"

# Функция для обработки новых пользователей через реферальную ссылку
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id  # Извлечение user_id из сообщения
    referral_arg = context.args[0] if context.args else None  # Извлечение referral_id из аргументов команды
    referral_id = referral_arg.replace('user_', '') if referral_arg else None

    # Получение и обновление имени пользователя Telegram
    telegram_username = get_telegram_username(user_id)
    if telegram_username:
        logging.info(f"Получено имя пользователя: {telegram_username}")
        # Отправляем запрос на сервер для обновления имени пользователя
        update_url = f"{FLASK_APP_URL}/update_username/{user_id}?username={telegram_username}"
        update_response = requests.get(update_url)
        logging.info(f"Ответ от сервера Flask: {update_response.text}")
    else:
        logging.warning(f"Не удалось получить имя пользователя для user_id: {user_id}")

    # Создание записи реферала, если referral_id определен
    if referral_id:
        referral_url = f"{FLASK_APP_URL}/create_referral"
        referral_data = {'user_id': user_id, 'referral_id': int(referral_id)}
        referral_response = requests.post(referral_url, json=referral_data)
        logging.info(f"Ответ от сервера Flask при создании реферала: {referral_response.text}")

    # Создание кнопок с WebAppInfo
    keyboard = [
        [InlineKeyboardButton(text="Launch Duck", web_app=WebAppInfo(url=f'{FLASK_APP_URL}/start?user_id={user_id}'))],
        [InlineKeyboardButton(text="Join community", web_app=WebAppInfo(url=f'{FLASK_APP_URL}/ссылка'))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем изображение и сообщение с кнопками
    try:
        with open('static/img/utv.png', 'rb') as photo_file:
            await update.message.reply_photo(photo=photo_file, caption=f'{welcome_text} User ID: {user_id}', reply_markup=reply_markup)
    except FileNotFoundError:
        logging.error("Файл изображения не найден")
    except Exception as e:
        logging.error(f"Ошибка при отправке изображения: {e}")

def main():
    logging.info("Запуск Telegram-бота...")
    flask_process = start_flask()

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    application.run_polling()
    logging.info("Telegram-бот запущен")

    # Завершаем Flask-приложение при завершении работы бота
    flask_process.terminate()

if __name__ == '__main__':
    main()

