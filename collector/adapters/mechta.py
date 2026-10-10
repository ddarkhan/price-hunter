from .base import Adapter


class Mechta(Adapter):
    key = 'mechta'
    hosts = ('www.mechta.kz', 'mechta.kz')
    reason = 'Разрешённый источник и парсер цен ещё не подтверждены'
