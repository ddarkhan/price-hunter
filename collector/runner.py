import argparse
import datetime as dt
import os
import time
from pathlib import Path
from .adapters import ADAPTERS
from .config import validate, apply_facts
from .engine import now_iso, timestamp, evaluate, excluded
from .state import read_json, atomic_json, Lock, record
from .net import SourceError
from .telegram import Telegram, TelegramError, eligible, message
from .schema import offer_key


def empty_state():
    return {'schema_version': 1, 'items': {}, 'notifications': {}, 'cursors': {}, 'sources': {}}


def collect(config, state, probe=False):
    now = dt.datetime.now(dt.timezone.utc)
    observed = now.isoformat(timespec='seconds')
    states, queue, seen, successes = [], [], set(), 0
    category_results = []
    for key, cls in ADAPTERS.items():
        settings = config['shops'].get(key, {'enabled': False})
        old = state['sources'].get(key, {})
        source = {'shop': key, 'implemented': cls.implemented, 'status': 'disabled', 'checked_at': observed,
                  'last_success': old.get('last_success'), 'products_checked': 0, 'products_failed': 0,
                  'discovered': 0, 'categories': [], 'message': 'Отключён в конфигурации', 'actions_verified': False}
        states.append(source)
        if not settings.get('enabled'):
            continue
        adapter = cls(settings, config['network'])
        if not cls.implemented:
            source.update(status='not_implemented', message=cls.reason)
            if probe:
                try:
                    adapter.probe()
                    source['message'] = 'Страница доступна; парсер и discovery не реализованы'
                except SourceError as e:
                    source.update(status=e.status, message=str(e) + '; парсер не реализован')
                except Exception:
                    source.update(status='error', message='Ошибка диагностики источника; парсер не реализован')
            state['sources'][key] = source
            continue
        source.update(status='no_data', message='Проверка категорий и карточек')
        discovered = []
        for cat in settings.get('categories', []):
            if cat['key'] not in config['enabled_categories']:
                continue
            result = {'label': cat['label'], 'key': cat['key'], 'url': cat['url'], 'status': 'ok', 'discovered': 0}
            source['categories'].append(result)
            category_results.append(result)
            try:
                urls = adapter.discover(cat)
                result['discovered'] = len(urls)
                source['discovered'] += len(urls)
                if not urls:
                    result['status'] = 'no_data'
                cursor_key = key + ':' + cat['url']
                cursor = state['cursors'].get(cursor_key, 0)
                rotated = urls[cursor % max(1, len(urls)):] + urls[:cursor % max(1, len(urls))]
                discovered.append([(u, cat['key']) for u in rotated])
            except SourceError as e:
                result.update(status=e.status, message=str(e))
                source.update(status=e.status, message=str(e))
            except Exception:
                result.update(status='error', message='Ошибка обработки категории')
        # Round robin across categories, rather than letting first category consume all capacity.
        discovery_queue = []
        for index in range(max([len(a) for a in discovered], default=0)):
            for group in discovered:
                if index < len(group):
                    discovery_queue.append(group[index])
        tracked = [(v['offer']['url'], v['offer']['category']) for v in state['items'].values()
                   if v['offer']['shop'] == key and v['offer']['category'] in config['enabled_categories']]
        tc = state['cursors'].get(key + ':tracked', 0) % max(1, len(tracked))
        tracked = tracked[tc:] + tracked[:tc]
        watches = [(v['url'], v['category']) for v in settings.get('watch_urls', []) if v['category'] in config['enabled_categories']]
        wc = state['cursors'].get(key + ':watch', 0) % max(1, len(watches))
        watches = watches[wc:] + watches[:wc]
        watch_budget = max(1, config['max_products'] // 4)
        candidates = watches[:watch_budget]
        state['cursors'][key + ':watch'] = wc + min(watch_budget, len(watches))
        for index in range(max(len(discovery_queue), len(tracked))):
            if index < len(discovery_queue):
                candidates.append(discovery_queue[index])
            if index < len(tracked):
                candidates.append(tracked[index])
        queue.append((adapter, source, candidates))
    # A request failure in one shop never terminates the others.
    remaining = config['max_products']
    for adapter, source, candidates in queue:
        for url, cat in candidates:
            if remaining <= 0:
                break
            if url in seen:
                continue
            seen.add(url)
            remaining -= 1
            try:
                raw_offer = adapter.fetch(url, cat, observed)
                checked_now = dt.datetime.now(dt.timezone.utc)
                raw_offer['observed_at'] = checked_now.isoformat(timespec='seconds')
                offer = apply_facts(raw_offer, config, checked_now)
                offer['id'] = offer_key(offer)
                source['products_checked'] += 1
                if excluded(offer, now):
                    continue
                record(state, offer, checked_now, config['history_days'])
                successes += 1
                source.update(last_success=offer['observed_at'])
            except SourceError as e:
                source['products_failed'] += 1
                source.update(status=e.status, message=str(e))
                if e.status == 'unavailable':
                    for item in state['items'].values():
                        if item['offer']['url'] == url:
                            item['offer'].update(available=False, observed_at=observed)
                if e.status in ('blocked', 'robots_denied', 'auth_required', 'partial'):
                    break
            except Exception:
                source['products_failed'] += 1
                source.update(status='error', message='Ошибка разбора карточки; значения не подставлены')
        if source['products_checked']:
            failed_categories = any(c['status'] != 'ok' for c in source['categories'])
            source.update(status='partial' if source['products_failed'] or failed_categories else 'ok',
                          message='Проверены только указанные страницы категорий и часть карточек; доставка неизвестна')
        source['requests'] = adapter.client.requests
        source['checked_at'] = now_iso()
        source['actions_verified'] = os.environ.get('GITHUB_ACTIONS') == 'true' and source['products_checked'] > 0
        state['sources'][adapter.key] = source
        for cat in adapter.config.get('categories', []):
            cursor_key = adapter.key + ':' + cat['url']
            state['cursors'][cursor_key] = state['cursors'].get(cursor_key, 0) + max(1, source['products_checked'] // max(1, len(source['categories'])))
        state['cursors'][adapter.key + ':tracked'] = state['cursors'].get(adapter.key + ':tracked', 0) + max(1, source['products_checked'] // 2)
    # Bound active state and stale records. Git commit history remains subject to repo maintenance.
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=config['history_days'])
    current = sorted(state['items'].items(), key=lambda i: i[1]['offer']['observed_at'], reverse=True)
    state['items'] = dict((k, v) for k, v in current[:config['max_tracked']] if timestamp(v['offer']['observed_at']) >= cutoff)
    state['notifications'] = {k: v for k, v in state['notifications'].items() if k in state['items']}
    offers = [item['offer'] for item in state['items'].values()]
    public = [evaluate(item['offer'], offers, item['history'], now, config) for item in state['items'].values()]
    public = [o for o in public if o['status'] != 'excluded']
    for offer in public:
        previous = state['notifications'].get(offer['id'])
        if previous and offer.get('available') is False:
            previous['was_unavailable'] = True
    prior_success = state.get('last_success')
    finished = now.isoformat(timespec='seconds')
    state['last_success'] = finished if successes else prior_success
    return {'schema_version': 1, 'generated_at': finished, 'last_success': state.get('last_success'),
            'city': 'Астана', 'currency': 'KZT', 'stale_minutes': config['stale_minutes'],
            'coverage': {'checked': sum(s['products_checked'] for s in states), 'tracked': len(public),
                         'discovered': sum(s['discovered'] for s in states), 'categories': category_results},
            'sources': states, 'offers': public, 'demo': False}


def notify(config, state, dataset, save):
    telegram = Telegram()
    if not telegram.ready:
        print('Telegram отключён: Secrets не заданы. Товары сохранены.')
        return
    now = dt.datetime.now(dt.timezone.utc)
    for offer in dataset['offers']:
        if (now - timestamp(offer['observed_at'])).total_seconds() > config['stale_minutes'] * 60:
            continue
        previous = state['notifications'].get(offer['id'])
        if previous and previous.get('sent') and previous.get('preliminary') and not previous.get('corrected') and offer['status'] in ('insufficient', 'unavailable'):
            try:
                telegram.send('Исправление предварительной находки: %s\nПроверка не подтверждает выгоду/наличие.\n%s' % (offer['name'], offer['url']))
                previous['corrected'] = True
                save()
            except TelegramError as e:
                print(str(e))
            continue
        if not eligible(offer, previous, config):
            continue
        ledger = {'value': offer['total'] if offer['total'] is not None else offer['price'], 'pending': True,
                  'sent': False, 'preliminary': offer['status'] != 'confirmed', 'was_unavailable': False, 'at': now_iso()}
        state['notifications'][offer['id']] = ledger
        save()  # In Actions this is committed before the external send.
        try:
            telegram.send(message(offer))
            ledger.update(pending=False, sent=True)
            save()
        except TelegramError as e:
            # Leave pending: do not blindly duplicate an ambiguous delivery.
            if not e.ambiguous:
                if previous:
                    state['notifications'][offer['id']] = previous
                else:
                    state['notifications'].pop(offer['id'], None)
                save()
            print(str(e))
    for source in dataset['sources']:
        # Three consecutive failures, one notification until recovery.
        entry = state.setdefault('source_alerts', {}).setdefault(source['shop'], {'failures': 0, 'sent': False})
        if not source['implemented'] or source['status'] == 'disabled':
            continue
        if source['status'] == 'ok':
            entry.update(failures=0, sent=False, pending=False)
        else:
            entry['failures'] += 1
            if entry['failures'] >= 3 and not entry['sent'] and not entry.get('pending'):
                # Reserve before sending, same ambiguity policy as offer messages.
                entry['pending'] = True
                save()
                try:
                    telegram.send('Price Hunter: у источника %s сбои проверки несколько запусков. %s' % (source['shop'], source['message']))
                    entry.update(pending=False, sent=True)
                except TelegramError as e:
                    if not e.ambiguous:
                        entry['pending'] = False
                    print(str(e))
        save()


def main():
    from .env import load_env
    load_env()
    parser = argparse.ArgumentParser(description='Price Hunter: сбор публичных товарных данных')
    parser.add_argument('command', choices=['collect', 'probe', 'notify', 'test-telegram', 'watch'])
    parser.add_argument('--config', default='config/monitor.json')
    parser.add_argument('--state-dir', default='runtime')
    parser.add_argument('--output', default='public/data/catalog.json')
    parser.add_argument('--persist-git', action='store_true', help='Commit data branch before/after each send')
    parser.add_argument('--interval', type=int, default=900)
    parser.add_argument('--resolve-pending', help='Product ID: explicitly mark ambiguous alert as delivered')
    args = parser.parse_args()
    config = validate(read_json(args.config, {}))
    root = Path(args.state_dir)
    root.mkdir(parents=True, exist_ok=True)
    if args.command == 'test-telegram':
        try:
            Telegram().send('Price Hunter: тестовое уведомление. Это проверка связи, а не товарная находка.')
            print('Telegram подтвердил тестовое сообщение.')
        except TelegramError as e:
            parser.exit(1, str(e) + '\n')
        return
    with Lock(root / 'collector.lock'):
        state = read_json(root / 'state.json', empty_state())
        if state.get('schema_version') != 1:
            parser.error('Версия сохранённого состояния не поддерживается')
        def save():
            atomic_json(root / 'state.json', state)
            if args.persist_git:
                from .gitdata import commit
                commit(root)
        if args.resolve_pending:
            ledger = state['notifications'].get(args.resolve_pending)
            if not ledger or not ledger.get('pending'):
                parser.error('Нет pending-уведомления с этим ID')
            ledger.update(pending=False, sent=True)
            save()
            print('Неопределённая отправка отмечена доставленной по явному указанию.')
            return
        if args.command == 'notify':
            notify(config, state, read_json(args.output, {'offers': [], 'sources': []}), save)
            return
        while True:
            dataset = collect(config, state, probe=args.command == 'probe')
            from scripts.check_public import check
            check(dataset)
            atomic_json(args.output, dataset)
            atomic_json(root / 'catalog.json', dataset)
            save()
            if args.command != 'probe':
                notify(config, state, dataset, save)
            print('Проверено: %s; отслеживается: %s; аномалий: %s' % (dataset['coverage']['checked'], dataset['coverage']['tracked'], sum(o['status'] == 'confirmed' for o in dataset['offers'])))
            if args.command != 'watch':
                break
            time.sleep(max(300, args.interval))


if __name__ == '__main__':
    main()
