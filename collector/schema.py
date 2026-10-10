import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from .money import money


class StructuredPage(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links, self.scripts, self.next_data = [], [], None
        self.capture, self.parts = False, []
        self.script_kind = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.capture, self.parts = True, []
            self.script_kind = 'schema'
        elif tag == 'script' and attrs.get('id') == '__NEXT_DATA__':
            self.capture, self.parts = True, []
            self.script_kind = 'next'

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            try:
                parsed = json.loads(''.join(self.parts))
                if self.script_kind == 'next':
                    self.next_data = parsed
                else:
                    self.scripts.append(parsed)
            except (ValueError, TypeError):
                pass
            self.capture = False


def nodes(value):
    if isinstance(value, list):
        for child in value:
            yield from nodes(child)
    elif isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (list, dict)):
                yield from nodes(child)


def clean_url(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, '', ''))


def offer_key(offer):
    key = '|'.join(str(offer.get(k) or 'unknown') for k in ('shop', 'seller', 'sku', 'variant')) + '|' + clean_url(offer['url'])
    return hashlib.sha256(key.encode()).hexdigest()[:20]


def first_image(value):
    if isinstance(value, list):
        return next((first_image(v) for v in value if first_image(v)), None)
    if isinstance(value, dict):
        value = value.get('url') or value.get('contentUrl')
    return value if isinstance(value, str) and value.startswith('https://') else None


def product(text, url, shop, category, observed_at):
    candidates = [n for s in StructuredPage(text).scripts for n in nodes(s)
                  if 'Product' in ([n.get('@type')] if isinstance(n.get('@type'), str) else (n.get('@type') or []))]
    if len(candidates) != 1:
        return None  # No guess among variants or product collections.
    p = candidates[0]
    offers = p.get('offers', {})
    if isinstance(offers, list):
        if len(offers) != 1:
            return None
        offers = offers[0]
    if not isinstance(offers, dict) or offers.get('@type') == 'AggregateOffer':
        return None  # lowPrice is not a purchasable variant.
    price = money(offers.get('price'), offers.get('priceCurrency'))
    if price is None or not p.get('name'):
        return None
    availability = str(offers.get('availability', '')).split('/')[-1]
    available = True if availability == 'InStock' else False if availability in ('OutOfStock', 'Discontinued', 'SoldOut') else None
    condition = str(offers.get('itemCondition', p.get('itemCondition', ''))).split('/')[-1]
    seller = offers.get('seller', {})
    if isinstance(seller, dict):
        seller = seller.get('name')
    brand = p.get('brand', {})
    if isinstance(brand, dict):
        brand = brand.get('name')
    sku = str(p.get('sku') or '')
    gtin = next((str(p[k]) for k in ('gtin13', 'gtin14', 'gtin12', 'gtin8', 'gtin') if p.get(k)), None)
    identifier = hashlib.sha256((shop + '|' + clean_url(url) + '|' + sku).encode()).hexdigest()[:20]
    return {
        'id': identifier, 'shop': shop, 'seller': seller or shop, 'sku': sku,
        'name': str(p['name'])[:500], 'url': clean_url(url), 'image': first_image(p.get('image')),
        'category': category, 'price': price, 'currency': 'KZT', 'struck_price': None,
        'gtin': gtin, 'brand': brand or None, 'model': None,
        'condition': 'new' if condition == 'NewCondition' else 'used' if condition == 'UsedCondition' else None,
        'quantity': None, 'volume': None, 'bundle': None, 'variant': None,
        'available': available, 'delivery_cost': None, 'mandatory_cost': None,
        'astana': None, 'full_payment': None, 'conditions': [], 'expiry': None,
        'identity_verified': False, 'observed_at': observed_at,
        'limitations': ['Комплектация, вариант и получение в Астане требуют проверки', 'Совместимость не подтверждена'],
        'evidence_url': clean_url(url),
    }
