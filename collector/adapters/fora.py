from .base import Adapter


class Fora(Adapter):
    key = 'fora'
    hosts = ('www.fora.kz', 'fora.kz')
    reason = 'Разрешённый источник и парсер цен ещё не подтверждены'
