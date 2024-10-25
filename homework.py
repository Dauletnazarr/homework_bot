import logging
import os
import sys
import time
import requests

from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    encoding='utf-8',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """
    Проверяет доступность переменных окружения.
    Которые необходимы для работы программы.
    """
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Один или несколько токенов отсутствуют.')
        sys.exit('Отсутствуют необходимые переменные окружения.'
                 'Программа завершена.')


def log_and_notify(bot, message, critical=False):
    """Отправляет лог-сообщение админу в чат Telegram."""
    if critical:
        logger.critical(message)
    else:
        logger.error(message)
    send_message(bot, message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено!')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram {error}')


def get_api_answer(timestamp):
    """Проверка на получение ответа от API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS,
            params={'from_date': timestamp}, timeout=10)
        if response.status_code != 200:
            log_and_notify(f'API вернул ошибку: {response.status_code}')
            raise Exception(f'API вернул ошибку: {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        log_and_notify(f'API вернул ошибку: {error}')


def check_response(response):
    """Проверяет сам словарь на наличие ключей."""
    if 'homeworks' not in response:
        log_and_notify('В ответе API домашки нет ключа `homeworks`')
    if not isinstance(response['homeworks'], list):
        raise TypeError('в ответе API домашки под ключом "homeworks" '
                        'данные приходят не в виде списка')
    homework = response['homeworks'][0]
    if 'homework_name' and 'status' in homework:
        return homework


def parse_status(homework):
    """Извлекает из информации статус этой работы."""
    if 'homework_name' not in homework:
        raise Exception('В ответе API домашки нет ключа "homework_name"')
    homework_name = homework['homework_name']
    status = homework['status']
    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        log_and_notify('Неожиданный статус домашней работы в ответе API')


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_time = int(time.time())
    timestamp = current_time - (7 * 24 * 60 * 60)
    old_status_message = None

    while True:

        try:
            check_tokens()
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if old_status_message != message:
                send_message(bot, message)
                old_status_message = message
            else:
                logger.debug('Статус ревью не изменился')
        except Exception as error:
            log_and_notify(bot, f'Сбой в работе программы: {error}')

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
