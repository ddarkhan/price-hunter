"""Run locally AFTER creating your own bot; no tokens/chat IDs printed."""
import getpass
import http.client
import json
import re
import ssl
from pathlib import Path


def main():
    token = getpass.getpass('Токен нового бота (ввод скрыт): ').strip()
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
        raise SystemExit('Формат токена не распознан. Значение скрыто.')
    conn = http.client.HTTPSConnection('api.telegram.org', context=ssl.create_default_context(), timeout=20)
    try:
        conn.request('GET', '/bot' + token + '/getUpdates?allowed_updates=%5B%22message%22%5D')
        response = conn.getresponse()
        result = json.loads(response.read(1024 * 1024))
        if response.status != 200 or result.get('ok') is not True:
            raise SystemExit('Telegram не подтвердил запрос. Ответ с личными данными не выводится.')
        ids = list(dict.fromkeys(u['message']['chat']['id'] for u in result.get('result', []) if u.get('message', {}).get('chat', {}).get('type') == 'private'))
        if len(ids) != 1:
            raise SystemExit('Нужен ровно один личный чат с новым ботом. Отправьте ему /start и повторите. Ответ API не выводится.')
        path = Path('.env')
        lines = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
        lines = [line for line in lines if not line.startswith(('TELEGRAM_BOT_TOKEN=', 'TELEGRAM_CHAT_ID='))]
        lines += ['TELEGRAM_BOT_TOKEN=' + token, 'TELEGRAM_CHAT_ID=' + str(ids[0])]
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print('Токен и chat ID сохранены в локальный .env. Перенесите их в GitHub Actions Secrets; файл не публикуйте.')
    except (OSError, ValueError, http.client.HTTPException):
        raise SystemExit('Ошибка соединения с Telegram; секреты и ответ API не выводятся.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
