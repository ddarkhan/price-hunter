from urllib.parse import urljoin, urlsplit
from ..net import Client, SourceError, validate_url
from ..schema import StructuredPage, clean_url, product


class Adapter:
    implemented = False
    hosts = ()
    reason = 'Разбор цен и поиск новых товаров ещё не реализованы'
    product_prefix = None

    def __init__(self, config, network):
        self.config = config
        self.client = Client(self.hosts, **network)

    def discover(self, category):
        if not self.implemented:
            raise SourceError('not_implemented', self.reason)
        text, url, _ = self.client.get(category['url'])
        links = []
        for href in StructuredPage(text).links:
            candidate = clean_url(urljoin(url, href))
            p = urlsplit(candidate)
            if p.hostname in self.hosts and p.path.startswith(self.product_prefix):
                if candidate not in links:
                    links.append(candidate)
        return links

    def fetch(self, url, category, observed_at):
        if not self.implemented:
            raise SourceError('not_implemented', self.reason)
        validate_url(url, self.hosts)
        text, final_url, _ = self.client.get(url)
        offer = product(text, final_url, self.key, category, observed_at)
        if offer is None:
            raise SourceError('no_data', 'Нет однозначного Product/Offer с ценой KZT в структурированных данных')
        return offer

    def probe(self):
        self.client.get('https://' + self.hosts[0] + '/')

