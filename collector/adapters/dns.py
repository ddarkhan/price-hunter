from .base import Adapter


class DNS(Adapter):
    key = 'dns'
    hosts = ('www.dns-shop.kz', 'dns-shop.kz')
    reason = 'HTML/API разбор и автоматическое обнаружение ещё не реализованы'
