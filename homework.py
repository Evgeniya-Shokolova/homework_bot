import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

load_dotenv()

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


def setup_logging():
    """Настраивает логирование."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s,%(levelname)s,%(message)s,%(funcName)s,%(lineno)d',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    missing_tokens = [token for token in [
        "PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
        if not globals()[token]]
    if missing_tokens:
        logging.critical(
            f'Отсутствуют обязательные переменные окружения:\
                {", ".join(missing_tokens)}')
        sys.exit(1)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    logging.debug(f'Начинаю отправку сообщения: {message}')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except (requests.RequestException, ApiException) as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')
        raise


def get_api_answer(timestamp):
    """Делает запрос к API."""
    params = {'from_date': timestamp}
    logging.debug(f'Начинаю запрос к API {ENDPOINT} с параметрами: {params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        raise ConnectionError(f'Ошибка API: {error}')

    if response.status_code != HTTPStatus.OK:
        logging.error(
            f'Ошибка API: код {response.status_code}\
                при запросе к {ENDPOINT} с параметрами: {params}')
        raise ConnectionError(f'Ошибка API: код {response.status_code}')
    logging.debug('Запрос к API выполнен успешно.')
    return response.json()


def check_response(response):
    """Проверяет структуру ответа API."""
    logging.debug('Начинаю проверку ответа сервера.')

    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарем. Получен тип: {type(response)}')
    if 'homeworks' not in response:
        raise KeyError('Ответ API должен содержать ключ "homeworks".')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Данные под ключом "homeworks" должны быть списком.\
                Получен тип: {type(response["homeworks"])}')

    logging.debug('Проверка ответа сервера выполнена успешно.')
    return response['homeworks']


def parse_status(homework):
    """Извлекает и формирует статус работы для отправки в Telegram."""
    if 'homework_name' not in homework:
        raise ValueError('Отсутствует домашняя работа.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status is None:
        raise ValueError('Отсутствует статус домашней работы.')

    if 'status' not in homework:
        raise ValueError('Отсутствует статус домашней работы.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    last_error_message = ''

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)

            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
            else:
                logging.debug('Нет новых статусов.')

            timestamp = api_answer.get('current_date', int(time.time()))

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    setup_logging()
    main()
