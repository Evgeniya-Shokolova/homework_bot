from http import HTTPStatus
import os
import time
import logging
import requests
from telebot import TeleBot
from dotenv import load_dotenv

# Загрузка переменных окружения
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

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical("Отсутствует обязательная переменная окружения.")
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logging.error('Ошибка API')
            raise requests.RequestException(
                f'Ошибка API: код{response.status_code}'
                )
        logging.debug('Запрос к API выполнен успешно.')
        return response.json()
    except requests.exceptions.RequestException:
        raise ('Ошибка запроса к API:')


def check_response(response):
    """Проверяет структуру ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем.')
    if 'homeworks' not in response:
        raise KeyError('Ответ API должен содержать ключ "homeworks".')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Данные под ключом "homeworks" должны быть списком.')
    return response['homeworks']


def parse_status(homework):
    """Извлекает и формирует статус работы для отправки в Telegram."""
    if 'homework_name' not in homework:
        raise ValueError('Отсутствует домашняя работа')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status is None:
        raise ValueError('Отсутствует статус домашней работы.')

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    if message != last_message:
                        send_message(bot, message)
                        last_message = message
            else:
                logging.debug('Нет новых статусов.')

            timestamp = int(time.time())  # Обновляем временную метку
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
