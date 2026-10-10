from .base import Adapter


class Ozon(Adapter):
    key = 'ozon'
    hosts = ('www.ozon.kz', 'ozon.kz')
    reason = 'Публичный источник с разрешённым стабильным доступом не подтверждён; адаптер не реализован'
