"""Fail CI on secrets/personal state in JSON served to the browser."""
import json
import re
import os
from pathlib import Path

FORBIDDEN_KEYS = re.compile(r'^(telegram_chat_id|chat_id|token|telegram_bot_token|cookie|cookies|authorization|email|phone|password|user_id|order_id|notifications|source_alerts)$', re.I)
SECRET_VALUES = re.compile(r'\b(?:\d{7,12}:[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b')


def check(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if FORBIDDEN_KEYS.match(key):
                raise ValueError('Запрещённое поле в публичных данных: ' + key)
            check(item)
    elif isinstance(value, list):
        for item in value:
            check(item)
    elif isinstance(value, str):
        if SECRET_VALUES.search(value):
            raise ValueError('Секрет обнаружен в публичной строке; значение скрыто')


if __name__ == '__main__':
    paths = list(Path('public').rglob('*.json')) + [Path('config/monitor.json')]
    for p in paths:
        check(json.loads(p.read_text(encoding='utf-8-sig')))
    for p in Path('dist').rglob('*'):
        if p.is_file() and p.suffix in ('.js', '.html', '.json', '.css'):
            content = p.read_text(encoding='utf-8')
            if SECRET_VALUES.search(content):
                raise ValueError('Секрет обнаружен в frontend-сборке; значение скрыто')
            for key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'):
                secret = os.environ.get(key)
                if secret and len(secret) >= 6 and secret in content:
                    raise ValueError('Переменная Telegram попала в frontend; значение скрыто')
    print('Публичные JSON проверены: %s файлов; секретных полей нет.' % len(paths))
