from .base import Adapter
from ..schema import StructuredPage
from ..money import money
from ..net import SourceError, validate_url
from ..schema import product


class Technodom(Adapter):
    key = 'technodom'
    hosts = ('www.technodom.kz', 'technodom.kz')
    implemented = True
    product_prefix = '/astana/p/'

    def fetch(self, url, category, observed_at):
        validate_url(url, self.hosts)
        text, final_url, _ = self.client.get(url)
        return self.parse(text, final_url, category, observed_at)

    def parse(self, text, url, category, observed_at):
        offer = product(text, url, self.key, category, observed_at)
        if offer is None:
            raise SourceError('no_data', 'Нет однозначной цены Product/Offer в KZT')
        try:
            pp = StructuredPage(text).next_data['props']['pageProps']
            state = pp['initialState']
            info = state['productInfoStore']['productInfo']
            if str(info.get('sku')) != offer['sku'] or money(info.get('price'), 'KZT') != offer['price']:
                raise SourceError('no_data', 'SKU/цена JSON-LD и товарного состояния расходятся')
            offer['struck_price'] = money(info.get('oldPrice'), 'KZT')
            offer['full_payment'] = True  # verified price field; installment fields ignored
            offer['variant'] = (info.get('color') or {}).get('code')
            for group in info.get('attributes', []):
                for attribute in group.get('items', []):
                    if attribute.get('title') == 'Комплектация':
                        offer['bundle'] = str(attribute.get('value', '')) or None
            if info.get('isAvailable') is False:
                offer['available'] = False
            if state['core']['currentCity'].get('slug') == 'astana':
                points = [p for p in pp.get('stockPoints', [])
                          if isinstance(p.get('stock'), (int, float)) and p['stock'] > 0 and p.get('fromWindow') is False]
                if points:
                    offer['astana'] = 'Самовывоз: ' + '; '.join(str(p.get('title', '')) for p in points[:3])
                    # Pickup cost is NOT assumed zero; pricing cost remains unknown.
            if info.get('type') != 'regular':
                offer['limitations'].append('Тип товара: ' + str(info.get('type')) + '; состояние и гарантия требуют проверки')
        except (KeyError, TypeError):
            offer['limitations'].append('Не удалось проверить публичное состояние города/SKU')
        return offer
