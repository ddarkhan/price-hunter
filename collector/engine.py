"""Evidence rules: no title-only matches, no seller crossed-out baseline."""
import datetime as dt
import statistics
import re
from .money import discount

UTC = dt.timezone.utc


def timestamp(text):
    return dt.datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(UTC)


def now_iso():
    return dt.datetime.now(UTC).isoformat(timespec='seconds')


def identity(offer):
    fields = ('brand', 'model', 'quantity', 'volume', 'bundle', 'variant', 'condition')
    if not offer.get('identity_verified') or any(offer.get(k) is None for k in fields):
        return None
    return tuple(format(float(offer[k]), '.10g') if k == 'quantity' else str(offer[k]).strip().casefold() for k in fields)


def total(offer):
    costs = [offer.get('price'), offer.get('delivery_cost'), offer.get('mandatory_cost')]
    if any(v is None for v in costs):
        return None
    return round(sum(costs), 2)


def excluded(offer, now):
    title = offer['name'].casefold()
    terms = r'\b(алкоголь|водка|вино|пиво|табак|сигарет\w*|вейп\w*|vape\w*|оружи\w*|пистолет\w*|лекарств\w*|неисправ\w*|просроч\w*)\b'
    if re.search(terms, title) or offer.get('condition') in ('broken', 'expired'):
        return True
    if offer.get('expiry'):
        try:
            if dt.date.fromisoformat(offer['expiry']) < now.date():
                return True
        except ValueError:
            return True
    return False


def historical_baseline(history, now, config):
    cutoff = now - dt.timedelta(days=config['history_days'])
    anomaly_cutoff = now - dt.timedelta(hours=24)
    # At most one median per day; 15-minute samples cannot fake long history.
    days = {}
    for h in history:
        when = timestamp(h['at'])
        if cutoff <= when < anomaly_cutoff and h.get('price') is not None and h.get('available') is True:
            days.setdefault(when.date(), []).append(h['price'])
    if sum(len(v) for v in days.values()) < config['history_min_samples'] or len(days) < config['history_min_days']:
        return None
    daily = [statistics.median(v) for v in days.values()]
    base = statistics.median(daily)
    # Require reasonably stable preceding levels; broad variation isn't an ordinary price.
    if base <= 0 or statistics.median(abs(v - base) for v in daily) / base > .2:
        return None
    return round(base, 2)


def comparable(offer, other, now, stale_minutes):
    key = identity(offer)
    if key is None or identity(other) != key or offer['id'] == other['id']:
        return False
    return (other.get('available') is True and other.get('astana') and other.get('full_payment') is True
            and other.get('seller') and total(other) is not None
            and abs((now - timestamp(other['observed_at'])).total_seconds()) <= stale_minutes * 60)


def evaluate(offer, offers, history, now, config):
    offer = dict(offer)
    offer['total'] = total(offer)
    independent = {}
    for other in offers:
        if comparable(offer, other, now, config['stale_minutes']):
            # Same merchant across multiple domains isn't independent.
            seller = other['seller'].strip().casefold()
            if seller == offer['seller'].strip().casefold():
                continue
            if seller not in independent or total(other) < total(independent[seller]):
                independent[seller] = other
    refs = list(independent.values())
    values = [total(o) for o in refs]
    if len(values) >= 3:
        med = statistics.median(values)
        refs = [o for o in refs if .4 * med <= total(o) <= 2.5 * med]
    offer['comparisons'] = [
        dict({k: o[k] for k in ('id', 'name', 'shop', 'seller', 'url', 'observed_at', 'price', 'quantity', 'condition')}, total=total(o)) for o in refs]
    offer['market_base'] = round(statistics.median([total(o) for o in refs]), 2) if refs else None
    offer['history_base'] = historical_baseline(history, now, config)
    offer['history_basis'] = 'Цена самого товара за предыдущие дни; текущие 24 часа исключены'
    offer['market_discount'] = discount(offer['total'], offer['market_base'])
    offer['history_discount'] = discount(offer['total'], offer['history_base'])
    # Unknown delivery gives only a lower bound on total and an upper bound on discount.
    known_min = offer['price'] + (offer.get('delivery_cost') or 0) + (offer.get('mandatory_cost') or 0)
    market_hint = discount(known_min, offer['market_base'])
    history_hint = discount(known_min, offer['history_base'])
    bases = [(offer['market_base'], 'market', len(refs) >= 3), (offer['history_base'], 'history', offer['history_base'] is not None)]
    base, kind, sufficient = max(bases, key=lambda b: b[0] or 0)
    offer['baseline'], offer['baseline_kind'] = base, kind if base else None
    offer['discount'] = discount(offer['total'], base)
    offer['discount_upper_bound'] = max([d for d in (market_hint, history_hint) if d is not None], default=None)
    fresh = 0 <= (now - timestamp(offer['observed_at'])).total_seconds() <= config['stale_minutes'] * 60
    verified = (sufficient and identity(offer) is not None and offer['total'] is not None
                and offer.get('available') is True and bool(offer.get('astana'))
                and offer.get('full_payment') is True and offer.get('condition') == 'new' and fresh)
    if excluded(offer, now):
        offer['status'] = 'excluded'
    elif offer.get('available') is False:
        offer['status'] = 'unavailable'
    elif verified and offer.get('discount') is not None and offer['discount'] >= config['threshold']:
        offer['status'] = 'confirmed'
    elif offer.get('discount_upper_bound') is not None and offer['discount_upper_bound'] >= config['threshold']:
        offer['status'] = 'possible'
    else:
        offer['status'] = 'insufficient'
    offer['confidence'] = 'high' if verified else 'medium' if base else 'low'
    offer['history'] = history
    if offer['category'] == 'food' and not offer.get('expiry'):
        offer['limitations'] = offer['limitations'] + ['Срок годности не указан']
    return offer
