import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collector.money import money, discount
from collector.engine import evaluate, historical_baseline, identity
from collector.state import atomic_json, read_json, record, Lock
from collector.telegram import eligible, Telegram, TelegramError
from collector.net import validate_url, safe_addresses, SourceError
from collector.robots import Robots
from collector.adapters.technodom import Technodom
from collector.runner import empty_state, collect, notify
from collector.config import validate

NOW = dt.datetime(2026, 10, 11, 12, tzinfo=dt.timezone.utc)
CONFIG = json.loads(Path('config/monitor.json').read_text(encoding='utf-8'))


def offer(id='a', seller='a', price=4000, **changes):
    data = {'id': id, 'shop': seller, 'seller': seller, 'sku': id, 'name': 'Точный товар', 'url': 'https://www.technodom.kz/astana/p/' + id,
            'observed_at': NOW.isoformat(), 'price': price, 'struck_price': 400000, 'currency': 'KZT', 'category': 'computers',
            'delivery_cost': 0, 'mandatory_cost': 0, 'astana': 'Самовывоз подтверждён', 'full_payment': True, 'available': True,
            'identity_verified': True, 'brand': 'Acme', 'model': '123', 'variant': 'black', 'bundle': 'charger', 'volume': '512GB',
            'quantity': 1, 'condition': 'new', 'limitations': [], 'conditions': [], 'expiry': None}
    data.update(changes)
    return data


class MoneyTests(unittest.TestCase):
    def test_locale_and_currency(self):
        self.assertEqual(money('40\u202f000,50 ₸', 'KZT'), 40000.5)
        for value, currency in [('4,000', 'KZT'), ('4.000', 'KZT'), ('4000', 'RUB'), (None, 'KZT'), (0, 'KZT'), ('от 4000', 'KZT'), ('4 000 /мес', 'KZT'), (True, 'KZT'), ('NaN', 'KZT')]:
            self.assertIsNone(money(value, currency))
        self.assertEqual(discount(4000, 40000), 90)
        self.assertIsNone(discount(None, 40000))


class EvidenceTests(unittest.TestCase):
    def evaluate(self, current, refs=None, history=None):
        return evaluate(current, refs or [], history or [], NOW, CONFIG)

    def test_crossed_out_price_never_proves_discount(self):
        result = self.evaluate(offer())
        self.assertEqual(result['status'], 'insufficient')
        self.assertIsNone(result['baseline'])

    def test_exact_market_and_total_cost(self):
        refs = [offer(str(i), str(i), 40000) for i in range(3)]
        self.assertEqual(self.evaluate(offer(), refs)['status'], 'confirmed')
        result = self.evaluate(offer(delivery_cost=1000), refs)
        self.assertEqual(result['market_discount'], 87.5)
        self.assertEqual(result['status'], 'insufficient')
        self.assertEqual(self.evaluate(offer(delivery_cost=None), refs)['status'], 'possible')
        self.assertIsNone(self.evaluate(offer(delivery_cost=None), refs)['total'])

    def test_packs_and_variants_cannot_be_mixed(self):
        for field, value in [('quantity', 10), ('volume', '1TB'), ('variant', 'white'), ('bundle', 'none'), ('condition', 'used'), ('model', None)]:
            refs = [offer(str(i), str(i), 40000, **{field: value}) for i in range(3)]
            self.assertEqual(self.evaluate(offer(), refs)['status'], 'insufficient')

    def test_independence_availability_and_outliers(self):
        refs = [offer(str(i), 'same-seller', 40000) for i in range(3)]
        self.assertEqual(len(self.evaluate(offer(), refs)['comparisons']), 1)
        self.assertEqual(self.evaluate(offer(), refs)['status'], 'possible')
        refs = [offer(str(i), str(i), 40000, available=False) for i in range(3)]
        self.assertEqual(self.evaluate(offer(), refs)['status'], 'insufficient')
        refs = [offer('1', '1', 40000), offer('2', '2', 40000), offer('3', '3', 40000000)]
        self.assertEqual(self.evaluate(offer(), refs)['status'], 'possible')

    def test_history_excludes_current_anomaly_and_one_day(self):
        history = [{'at': (NOW - dt.timedelta(days=i)).isoformat(), 'price': 40000, 'total': 40000, 'available': True} for i in range(2, 9)]
        history.append({'at': NOW.isoformat(), 'price': 4000, 'total': 4000, 'available': True})
        self.assertEqual(historical_baseline(history, NOW, CONFIG), 40000)
        self.assertEqual(self.evaluate(offer(), history=history)['status'], 'confirmed')
        for h in history:
            h['at'] = (NOW - dt.timedelta(days=2)).isoformat()
        self.assertIsNone(historical_baseline(history, NOW, CONFIG))

    def test_exclusions_and_unknown_food_expiry(self):
        self.assertEqual(self.evaluate(offer(name='Вейп электронный'))['status'], 'excluded')
        self.assertEqual(self.evaluate(offer(expiry='2026-10-10', category='food'))['status'], 'excluded')
        self.assertIn('Срок годности не указан', self.evaluate(offer(category='food'))['limitations'])


class SourceTests(unittest.TestCase):
    def test_actual_technodom_fixture(self):
        adapter = Technodom({}, CONFIG['network'])
        o = adapter.parse(Path('tests/fixtures/technodom-product.html').read_text(encoding='utf-8'),
                          'https://www.technodom.kz/astana/p/naushniki-apple-earpods-usb-c-288036', 'gadgets', NOW.isoformat())
        self.assertEqual(o['price'], 14490)
        self.assertEqual(o['struck_price'], 14490)
        self.assertIsNone(o['model'])
        self.assertIsNone(identity(o))
        self.assertIsNone(o['delivery_cost'])
        self.assertIn('Abu Dhabi', o['astana'])
        self.assertTrue(o['full_payment'])
        self.assertTrue(o['image'].startswith('https://'))

    def test_real_discovery(self):
        adapter = Technodom({}, CONFIG['network'])
        text = Path('tests/fixtures/technodom-category.html').read_text(encoding='utf-8')
        with patch.object(adapter.client, 'get', return_value=(text, CONFIG['shops']['technodom']['categories'][0]['url'], 'text/html')):
            self.assertEqual(len(adapter.discover(CONFIG['shops']['technodom']['categories'][0])), 24)

    def test_robots_and_ssrf(self):
        robots = Robots('User-agent: *\nDisallow: /search\nDisallow: /*sorting=*\nAllow: /search/allowed$\n', 'PriceHunter/1.0')
        self.assertFalse(robots.can_fetch('', 'https://www.technodom.kz/search'))
        self.assertFalse(robots.can_fetch('', 'https://www.technodom.kz/astana/catalog?sorting=price'))
        self.assertTrue(robots.can_fetch('', 'https://www.technodom.kz/search/allowed'))
        self.assertFalse(robots.can_fetch('', 'https://www.technodom.kz/search/allowed/a'))
        for url in ['http://www.technodom.kz/a', 'https://127.0.0.1/a', 'https://www.technodom.kz.evil/a', 'https://user:pass@www.technodom.kz/a', 'https://www.technodom.kz:444/a']:
            with self.assertRaises(SourceError):
                validate_url(url, Technodom.hosts)
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('169.254.169.254', 443))]):
            with self.assertRaises(SourceError):
                safe_addresses('www.technodom.kz')


class StateTests(unittest.TestCase):
    def test_atomic_persistence_and_variant_change(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'state.json'
            s = empty_state()
            record(s, offer(), NOW, 30)
            self.assertTrue(atomic_json(p, s))
            restored = read_json(p, {})
            self.assertEqual(restored['items']['a']['history'][0]['price'], 4000)
            self.assertFalse(atomic_json(p, restored))
            record(restored, offer(variant='white'), NOW, 30)
            self.assertEqual(len(restored['items']['a']['history']), 1)
            with Lock(Path(temp) / 'lock'):
                with self.assertRaises(FileExistsError):
                    with Lock(Path(temp) / 'lock'):
                        pass

    def test_duplicate_suppression_and_restock(self):
        o = dict(offer(), status='confirmed', total=4000)
        self.assertTrue(eligible(o, None, CONFIG))
        previous = {'value': 4000, 'sent': True}
        self.assertFalse(eligible(o, previous, CONFIG))
        self.assertTrue(eligible(dict(o, price=3600, total=3600), previous, CONFIG))
        self.assertFalse(eligible(dict(o, price=3601, total=3601), previous, CONFIG))
        self.assertTrue(eligible(o, dict(previous, was_unavailable=True), CONFIG))
        self.assertFalse(eligible(o, dict(previous, pending=True), CONFIG))

    def test_send_only_marks_success_after_confirmation(self):
        data = {'offers': [dict(offer(), status='confirmed', total=4000, baseline=40000, baseline_kind='market', discount=90, comparisons=[])], 'sources': []}
        config = dict(CONFIG, stale_minutes=1440)
        current_time = dt.datetime.now(dt.timezone.utc).isoformat()
        data['offers'][0]['observed_at'] = current_time
        state = empty_state()
        saves = []
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'not-a-real-token', 'TELEGRAM_CHAT_ID': 'not-a-real-chat'}), patch.object(Telegram, 'send', side_effect=TelegramError('ambiguous')):
            notify(config, state, data, lambda: saves.append(copy.deepcopy(state)))
        self.assertTrue(state['notifications']['a']['pending'])
        self.assertFalse(state['notifications']['a']['sent'])
        self.assertTrue(saves[0]['notifications']['a']['pending'])
        state = empty_state()
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test', 'TELEGRAM_CHAT_ID': 'test'}), patch.object(Telegram, 'send', return_value=123):
            notify(config, state, data, lambda: None)
        self.assertTrue(state['notifications']['a']['sent'])
        self.assertFalse(state['notifications']['a']['pending'])
        state = empty_state()
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test', 'TELEGRAM_CHAT_ID': 'test'}), patch.object(Telegram, 'send', side_effect=TelegramError('rejected', ambiguous=False)):
            notify(config, state, data, lambda: None)
        self.assertNotIn('a', state['notifications'])

    def test_public_data_no_notification_ledger(self):
        with patch.object(Technodom, 'discover', return_value=[]):
            dataset = collect(CONFIG, empty_state())
        from scripts.check_public import check
        check(dataset)
        with self.assertRaises(ValueError):
            check({'chat_id': 'private'})
        with self.assertRaises(ValueError):
            validate(dict(CONFIG, threshold=80))

    def test_source_error_alert_never_marks_rejected_send_as_sent(self):
        state = empty_state()
        data = {'offers': [], 'sources': [{'shop': 'technodom', 'implemented': True, 'status': 'error', 'message': 'test failure'}]}
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test', 'TELEGRAM_CHAT_ID': 'test'}), patch.object(Telegram, 'send', side_effect=TelegramError('rejected', ambiguous=False)):
            for _ in range(3):
                notify(CONFIG, state, data, lambda: None)
        self.assertFalse(state['source_alerts']['technodom']['sent'])
        self.assertFalse(state['source_alerts']['technodom']['pending'])

    def test_variant_notification_keys_and_equivalent_quantity(self):
        from collector.schema import offer_key
        self.assertNotEqual(offer_key(offer()), offer_key(offer(variant='white')))
        self.assertEqual(identity(offer(quantity=1)), identity(offer(quantity=1.0)))


if __name__ == '__main__':
    unittest.main()
