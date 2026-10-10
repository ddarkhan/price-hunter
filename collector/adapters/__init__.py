from .technodom import Technodom
from .sulpak import Sulpak
from .alser import Alser
from .ozon import Ozon
from .wildberries import Wildberries
from .dns import DNS
from .kaspi import Kaspi
from .mechta import Mechta
from .fora import Fora

ADAPTERS = {a.key: a for a in (Technodom, Sulpak, Alser, Ozon, Wildberries, DNS, Kaspi, Mechta, Fora)}
