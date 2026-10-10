from .base import Adapter


class Alser(Adapter):
    key = 'alser'
    hosts = ('alser.kz', 'www.alser.kz')
    reason = 'robots.txt при живой проверке недоступен; автоматический сбор остановлен. Парсер не реализован'
