import os
import time
import logging, sys
import requests

from http import HTTPStatus

import telegram

from dotenv import load_dotenv

import exceptions

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
    """Проверка доступности необходимых токенов"""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
        ]
    for check_tokens in tokens:
        if check_tokens is None:
            message = 'Отсутствует перменная окружения!'
            logger.critical(message)
            raise SystemExit(message)


def send_message(bot, message):
    """Отправка сообщения в телеграмм"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except Exception as error:
        logger.error('Сообщение не отправлено!')
        raise SystemError(f'Сообщение не отправлено: {error}')


def get_api_answer(timestamp):
    """Получение ответа API"""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        message = f'''Нет ответа при запросе к эндпоинту:
            код ответа - {response.status_code}!'''
        logger.error(message)
        raise exceptions.NoResponseFromAPI(message)
    return response.json()


def check_response(response):
    """Проверка соответствия ответа API"""
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        message = f'Ошибка ключа homeworks: {error}'
        logger.error(message)
        raise exceptions.ResponseException(message)
    if homeworks is None:
        message = 'В ответе нет словаря homeworks'
        logger.error(message)
        raise exceptions.ResponseException(message)
    if not homeworks:
        message = 'Нет новых домашек'
        logger.error(message)
        raise exceptions.ResponseException(message)
    if type(homeworks) != list:
        message = 'Данные под ключом `homeworks` приходят не в виде списка'
        logger.error(message)
        raise TypeError(message)
    return homeworks


def parse_status(homework):
    """Получение статуса домашки из ответа API"""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    
    if homework_name is None:
        logger.error('Отустствует ключ homework_name')
        raise KeyError()

    if homework_status is None:
        logger.error('Отустствует ключ homework_status')
        raise KeyError()

    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неизвестный статус домашки'
        logger.error(message)
        raise exceptions.UnknownStatus(message)

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота"""
    check_tokens()

    week = 630117
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time() - week)
    old_error = None
    old_status = None

    while True:
        try:
            response = get_api_answer(timestamp)
        except exceptions.NoResponseFromAPI as response_error:
            if str(response_error) != old_error:
                old_error = str(response_error)
                send_message(bot, response_error)
            logger.error(response_error)
        try:
            homeworks = check_response(response)
            hw_status = homeworks[0].get('status')
            if hw_status == old_status:
                logger.debug('Обновления статуса нет')
            else:
                old_status = hw_status
                message = parse_status(homeworks[0])
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if old_error != str(error):
                old_error = str(error)
                send_message(bot, message)
            logger.error(message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
