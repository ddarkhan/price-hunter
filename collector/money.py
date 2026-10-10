import re
from decimal import Decimal, InvalidOperation


def money(value, currency):
    """Strict decimal parsing. Unknown or foreign currency is never zero/KZT."""
    if currency not in ('KZT', '₸', 'тг', 'тенге') or isinstance(value, bool):
        return None
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r'\s*(?:₸|тг|тенге|KZT)\s*$', '', text, flags=re.I)
    text = re.sub(r'[\s\u00a0\u202f]', '', text)
    if not re.fullmatch(r'\d+(?:[.,]\d{1,2})?', text):
        return None
    try:
        parsed = Decimal(text.replace(',', '.'))
        if parsed <= 0 or parsed > 1000000000:
            return None
        return float(parsed)
    except InvalidOperation:
        return None


def discount(total, baseline):
    if total is None or baseline is None or total <= 0 or baseline <= 0:
        return None
    return round((1 - total / baseline) * 100, 2)
