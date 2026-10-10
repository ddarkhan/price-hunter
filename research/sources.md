# Проверка публичных источников Price Hunter

Проверено 11 октября 2026 (Астана, UTC+5). Живые GET-запросы выполнены локальным Python 3.8 `urllib.request`, без cookies, авторизации, прокси, обхода CAPTCHA или подмены браузера. Статусы относятся к этой среде, а не ко всем компьютерам. GitHub Actions не проверен: подключённого репозитория и runner нет. Веб-инструмент отдельно получил 403/Cache miss на Technodom; это отличается от успешных прямых запросов Python.

## Technodom: подтверждённый автоматический поиск

`https://www.technodom.kz/robots.txt` — HTTP 200. В группе `User-agent: *` отсутствует Crawl-delay. Запрещены `/search`, `/compare`, `/cart*`, `/checkout*`, `*/my-account*`, `/gift-cards/*`, `/gift-cards-v1*`, `/cloudpayments`, `/*SID=*`, параметры рекомендаций и `*sorting=*`. Публичные `/astana/catalog/` и `/astana/p/` не запрещены. Адаптер обязан перепроверять robots при каждом запуске и применять собственную задержку запросов.

Фактическая цепочка обнаружения: robots -> `https://www.technodom.kz/server-sitemap.xml` -> `https://www.technodom.kz/astana/server-sitemap.xml` -> `https://www.technodom.kz/astana/categories-server-sitemap.xml`. Последний sitemap содержит 481 URL. Все этапы HTTP 200. Дальнейший охват проекта должен быть ограничен явно настроенными страницами; наличие sitemap не означает обход всего каталога.

| Публичная категория | HTTP | Уникальные ссылки товаров на первой странице |
| --- | --- | --- |
| https://www.technodom.kz/astana/catalog/smartfony-i-gadzhety/naushniki/vse-naushniki | 200 | 24 |
| https://www.technodom.kz/astana/catalog/noutbuki-i-komp-jutery/noutbuki-i-aksessuary/noutbuki | 200 | 24 |
| https://www.technodom.kz/astana/catalog/noutbuki-i-komp-jutery/komplektujuschie/ssd-diski | 200 | 20 |
| https://www.technodom.kz/astana/catalog/bytovaja-tehnika/uhod-za-odezhdoj/stiral-nye-mashiny | 200 | 25 |

Discovery: обычные HTML anchors с `href="/astana/p/..."`. Часть страниц может дополнительно содержать ссылки из SEO-текста; ограничение количества проверяемых товаров обязательно. Не использовались выдуманные CSS-селекторы или API. Пагинация не исследована; первая страница — фактический охват.

Проверенный товар: `https://www.technodom.kz/astana/p/naushniki-apple-earpods-usb-c-288036`, HTTP 200. JSON-LD `@type=Product` содержит:

- name: Наушники Apple EarPods (USB-C);
- sku: 288036;
- mpn: 288036 — совпадает с внутренним SKU магазина, не доказательство совпадения с товарами других магазинов;
- brand.name: Apple;
- offers.price: 14490, offers.priceCurrency: KZT;
- offers.availability: `https://schema.org/InStock`;
- image: вложенный массив URL, требуется безопасное распрямление;
- описание характеристик; GTIN, достоверный manufacturer model, condition и число единиц в упаковке отсутствуют.

Дополнительные публичные поля: `__NEXT_DATA__.props.pageProps.initialState.productInfoStore.productInfo` содержит `price=14490`, `oldPrice=14490`, `isAvailable=true`, `type=regular`, `color`, `attributes`, `variants`, `categoriesRu`. `oldPrice` — заявленная магазином старая цена; её нельзя использовать как независимую базу скидки. Рассрочка находится в отдельных полях `creditInfo`/`kaspiInstallmentInfo` и не заменяет полную цену `price`.

`__NEXT_DATA__.props.pageProps.initialState.core.currentCity.slug=astana` подтверждает контекст города. `props.pageProps.stockPoints` содержит публичные точки самовывоза: Астана, ТЦ «Abu Dhabi Plaza» — stock=12; Астана, ул. Республика, 34а — stock=5; fromWindow=false. Общий маршрут `/p/` без `/astana/` возвращает Алматы; нельзя переносить его наличие на Астану. Нулевая доставка на странице не доказана: стоимость доставки оставлять неизвестной. Поля stockPoints пригодны для подтверждения только при проверенном городе, положительном stock и подходящем состоянии. Эти наблюдения — обычные цены; аномалия 90% не обнаружена.

Санитизированные реальные fixtures: `tests/fixtures/technodom-product.html` и `tests/fixtures/technodom-category.html`. Содержат только необходимые товарные поля и публичные точки самовывоза. Отзывы, имена покупателей, ID заказов, пользовательские состояния и cookies не сохранены. Fixtures предназначены для тестов парсера; не должны попадать в рабочую выдачу как свежие наблюдения.

## Остальные магазины: честные ограничения

| Магазин | Проверенный URL | Результат прямого запроса |
| --- | --- | --- |
| Sulpak | https://www.sulpak.kz/robots.txt и https://www.sulpak.kz | 403 Forbidden |
| Alser | https://alser.kz/robots.txt и https://alser.kz | 403 Forbidden |
| DNS | https://www.dns-shop.kz/robots.txt | 403 Forbidden |
| Mechta | https://www.mechta.kz/robots.txt | 403 Forbidden |
| Wildberries | https://www.wildberries.kz/robots.txt | HTTP 498 |
| Ozon | https://www.ozon.kz/robots.txt | HTTP 307, цикл перенаправлений |
| Kaspi | https://kaspi.kz/robots.txt | Тайм-аут чтения 20 секунд |
| Fora | https://fora.kz/robots.txt | Подключение отклонено, WinError 10061 |
| shop.kz (дополнительный исследованный источник) | https://shop.kz/robots.txt и https://shop.kz | HTTP 411 Length Required |

Ни у одного из этих источников в данной проверке не подтверждён полноценный разрешённый путь category -> product -> price. Ставить статус «работает» нельзя; адаптеры должны сообщать «заблокирован»/«не реализован» либо конкретную сетевую ошибку. Для robots, который недоступен, использовать fail-closed: товарные страницы не обходить, разрешение не предполагать. Никакого обхода блокировок не выполнялось.
