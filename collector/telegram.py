import http.client
import json
import os
import re
import ssl
import time
from .engine import total, timestamp


class TelegramError(Exception):
    def __init__(self, message, ambiguous=True):
        super().__init__(message)
        self.ambiguous = ambiguous


class Telegram:
    def __init__(self, token=None, chat=None):
        self.token = str(token or os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()
        self.chat = str(chat or os.environ.get('TELEGRAM_CHAT_ID') or '').strip()
        self.ready = bool(self.token and self.chat)

    def send(self, text):
        if not self.ready:
            raise TelegramError('Telegram Secrets не настроены', ambiguous=False)
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', self.token):
            raise TelegramError('Неверный формат TELEGRAM_BOT_TOKEN: вставьте только токен, без кавычек и TELEGRAM_BOT_TOKEN=.', ambiguous=False)
        if not re.fullmatch(r'-?\d+', self.chat):
            raise TelegramError('Неверный формат TELEGRAM_CHAT_ID: вставьте только число, без кавычек и TELEGRAM_CHAT_ID=.', ambiguous=False)
        ambiguous = True
        detail = 'нет подтверждённого ответа'
        for attempt in range(3):
            connection = http.client.HTTPSConnection('api.telegram.org', timeout=20, context=ssl.create_default_context())
            try:
                body = json.dumps({'chat_id': self.chat, 'text': text[:4000], 'link_preview_options': {'is_disabled': True}})
                connection.request('POST', '/bot' + self.token + '/sendMessage', body=body.encode(), headers={'Content-Type': 'application/json'})
                response = connection.getresponse()
                detail = 'HTTP ' + str(response.status)
                result = json.loads(response.read(100000))
                if not isinstance(result, dict):
                    raise ValueError('Unexpected response structure')
                hints = {
                    'Bad Request: chat not found': 'чат не найден: проверьте chat ID и отправьте боту /start',
                    'Forbidden: bot was blocked by the user': 'бот заблокирован пользователем',
                    'Forbidden: bot was deactivated': 'бот деактивирован',
                    'Unauthorized': 'токен отклонён Telegram',
                    'Not Found': 'проверьте токен бота',
                }
                hint = hints.get(result.get('description'))
                if hint:
                    detail += '; ' + hint
                if response.status == 429:
                    ambiguous = False
                    if attempt == 2:
                        break
                    time.sleep(min(60, max(1, int(result.get('parameters', {}).get('retry_after', 5)))))
                    continue
                if response.status == 200 and result.get('ok') is True and result.get('result', {}).get('message_id'):
                    time.sleep(1.1)
                    return result['result']['message_id']
                if 400 <= response.status < 500 and result.get('ok') is False:
                    ambiguous = False
                # Retrying an ambiguous server/network error could deliver duplicates.
                break
            except (OSError, ValueError, http.client.HTTPException) as error:
                # Exception text and arbitrary API descriptions can contain secrets.
                detail += '; ' + type(error).__name__
                break
            finally:
                connection.close()
        raise TelegramError('Telegram не подтвердил отправку: ' + detail + ('; возможна неопределённая доставка' if ambiguous else '; API отклонил запрос'), ambiguous=ambiguous)


def eligible(offer, previous, config):
    if offer['status'] != 'confirmed' and not (config['preliminary_alerts'] and offer['status'] == 'possible'):
        return False
    if offer.get('available') is False:
        return False
    value = total(offer)
    if value is None:
        value = offer['price']
    if not previous:
        return True
    if previous.get('pending'):
        return False  # ambiguous send; manual reconciliation required
    if previous.get('was_unavailable'):
        return offer.get('available') is True
    return value <= previous['value'] * .9


def message(offer):
    def price(value):
        return ('%s ₸' % format(value, ',.0f').replace(',', ' ')) if value is not None else 'неизвестно'
    when = timestamp(offer['observed_at']).astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=5)))
    label = '✅ Подтверждено' if offer['status'] == 'confirmed' else '⚡ НЕ ПОЛНОСТЬЮ ПРОВЕРЕНО'
    basis = 'история наблюдений' if offer['baseline_kind'] == 'history' else 'независимые предложения (%s)' % len(offer['comparisons'])
    percent = str(offer['discount']) + '%' if offer.get('discount') is not None else 'не подтверждена; верхняя оценка %s%%' % offer.get('discount_upper_bound')
    refs = '\n'.join(o['url'] for o in offer['comparisons'][:3])
    return ('🔥 %s\n%s\n💰 Цена: %s\n🚚 Получение: %s\n💳 Итого: %s\n'
            '🏷 База: %s (%s)\n📉 Скидка: %s\n📦 %s; SKU %s; комплект: %s; количество: %s; состояние: %s\n'
            '🎟 Условия: %s\n⚠️ %s\n🕒 %s, Астана\n🔎 %s\n🔗 %s') % (
                offer['name'], label, price(offer['price']), offer.get('astana') or 'Астана не подтверждена', price(offer['total']),
                price(offer['baseline']), basis, percent, offer['shop'], offer['sku'], offer.get('bundle') or 'неизвестен',
                offer.get('quantity') or 'неизвестно', offer.get('condition') or 'неизвестно',
                '; '.join(offer.get('conditions', [])) or 'Публичная цена; доставка и обязательные расходы: %s / %s' % (price(offer.get('delivery_cost')), price(offer.get('mandatory_cost'))),
                '; '.join(offer.get('limitations', [])), when.strftime('%d.%m.%Y %H:%M'), refs or offer['url'], offer['url'])
