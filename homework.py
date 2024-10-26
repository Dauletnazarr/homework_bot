from contextlib import suppress
from http import HTTPStatus
import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot
import telebot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DATE_FROM = 7 * 24 * 60 * 60
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
    required_tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_tokens = [
        token for token in required_tokens if not globals().get(token)]

    if missing_tokens:
        missing = ", ".join(missing_tokens)
        logging.critical(
            'Отсутствуют следующие переменные окружения: %s', missing
        )
        sys.exit('Отсутствуют необходимые переменные окружения.'
                 'Программа завершена.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    logging.debug('Начало отправки сообщения в Telegram')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.debug('Сообщение успешно отправлено!')


def get_api_answer(timestamp):
    """Проверка на получение ответа от API."""
    logging.debug('Начало отправки запроса к API.')
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS,
            params={'from_date': timestamp}, timeout=10
        )
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка запроса к API: {error}') from error

    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(f'API вернул ошибку: {response.status_code}')

    logging.debug('Ответ от API успешно получен.')
    return response.json()


def check_response(response):
    """
    Проверяет, является ли 'response' словарём.
    И есть ли в нём ключ 'homeworks'
    """
    logging.debug('Начало проверки ответа API на наличие необходимых ключей.')
    if not isinstance(response, dict):
        raise TypeError(
            'Ответ API должен быть словарем, но получен другой тип данных')
    if 'homeworks' not in response:
        raise KeyError('Ключ `homeworks` отсутствует в ответе API')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'В ответе API домашки под ключом "homeworks" данные приходят не'
            f' в виде списка, а в виде {type(response["homeworks"]).__name__}'
        )
    logging.debug('Проверка ответа API завершена.')


def parse_status(homework):
    """Извлекает из информации статус этой работы."""
    logging.debug('Начало проверки статуса домашки')
    if 'homework_name' not in homework:
        raise KeyError('В ответе API домашки нет ключа "homework_name"')
    if 'status' not in homework:
        raise KeyError('В ответе API домашки нет ключа "status"')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Такой "status" в "HOMEWORK_VERDICTS" не найден.')
    verdict = HOMEWORK_VERDICTS[status]
    logging.debug('Проверка статуса успешно завершена.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_time = int(time.time())
    timestamp = current_time - DATE_FROM
    old_status_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']

            if len(response) == 0:
                logging.debug('Новых обновлений нет.')
                continue

            homework = homeworks[0]
            message = parse_status(homework)

            if old_status_message != message:
                send_message(bot, message)
                old_status_message = message
                timestamp = response.get('current_date', timestamp)
            else:
                logging.debug('Новых обновлений нет.')

        except (telebot.apihelper.ApiException,
                requests.exceptions.RequestException) as error:
            logging.error(error)

        except Exception as error:
            logging.exception('Сбой в работе программы: %s', error)
            if old_status_message != message:
                with suppress(Exception):
                    send_message(bot, message)
                old_status_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s,'
        '%(message)s, %(lineno)d, %(funcName)s',
        encoding='utf-8',
        handlers=[logging.StreamHandler(stream=sys.stdout)]
    )

    main()
