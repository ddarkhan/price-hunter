from .base import Adapter


class Sulpak(Adapter):
    key = 'sulpak'
    hosts = ('www.sulpak.kz', 'sulpak.kz')
    reason = 'robots.txt при живой проверке недоступен; автоматический сбор остановлен. Парсер не реализован'
