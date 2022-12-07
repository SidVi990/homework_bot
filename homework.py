import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности необходимых токенов."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправка сообщения в телеграмм."""
    try:
        logger.debug('Отправка сообщения...')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except Exception as error:
        logger.error('Сообщение не отправлено!')
        raise SystemError(f'Сообщение не отправлено: {error}')


def get_api_answer(timestamp):
    """Получение ответа API."""
    params = {'from_date': timestamp}
    try:
        logger.debug('Запрос к API...')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise SystemError(f'Ошибка запроса к API: {error}')
    if response.status_code != HTTPStatus.OK:
        message = f'Нет ответа API: {response.status_code}!'
        raise SystemError(message)
    return response.json()


def check_response(response):
    """Проверка соответствия ответа API."""
    if type(response) == dict:
        homeworks = response.get('homeworks')
    else:
        raise TypeError('Данные получены не в виде словаря!')
    if 'homeworks' and 'current_date' not in response:
        raise KeyError('Ошибка ключей в ответе API!')
    if not isinstance(homeworks, list):
        raise TypeError('Данные `homeworks` приходят не в виде списка!')
    
    return homeworks


def parse_status(homework):
    """Получение статуса домашки из ответа API."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ `homework_name`!')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ `status`!')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неизвестный статус домашки')

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'    


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствует перменная окружения!'
        logger.critical(message)
        sys.exit(message)

    week = 630117
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time() - week)
    old_error = None
    old_message = None
    message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                logger.info('Новых домашек нет')
            if message == old_message:
                logger.info('Нет обновлений статуса')
            else:
                old_message = message
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if old_error != str(error):
                old_error = str(error)
                send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
