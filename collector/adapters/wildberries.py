from .base import Adapter


class Wildberries(Adapter):
    key = 'wildberries'
    hosts = ('www.wildberries.kz', 'wildberries.kz')
    reason = 'Источник KZT, точных вариантов и наличия в Астане не подтверждён; адаптер не реализован'
