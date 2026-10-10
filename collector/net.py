"""HTTPS only, exact host allowlist, DNS/IP pinning, robots and bounded requests."""
import http.client
import ipaddress
import socket
import ssl
import time
import urllib.parse
from .robots import Robots


class SourceError(Exception):
    def __init__(self, status, message, retryable=False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


def validate_url(url, allowed_hosts):
    try:
        p = urllib.parse.urlsplit(url)
        if (p.scheme != 'https' or p.hostname not in allowed_hosts or
                p.username or p.password or p.port not in (None, 443) or p.fragment):
            raise ValueError()
        if any(ord(c) < 32 for c in url):
            raise ValueError()
        return p
    except (ValueError, TypeError):
        raise SourceError('error', 'URL отклонён: нужен HTTPS и разрешённый домен без учётных данных')


def safe_addresses(host):
    addresses = list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise SourceError('blocked', 'DNS адрес не является публичным')
    return addresses


class Client:
    agent = 'PriceHunter/1.0'

    def __init__(self, hosts, timeout=15, interval=2, max_requests=60):
        self.hosts = set(hosts)
        self.timeout = timeout
        self.interval = interval
        self.max_requests = max_requests
        self.requests = 0
        self.last_request = 0
        self.robots = {}

    def _raw(self, url):
        for redirect in range(5):
            p = validate_url(url, self.hosts)
            if self.requests >= self.max_requests:
                raise SourceError('partial', 'Лимит запросов за запуск достигнут')
            addresses = safe_addresses(p.hostname)
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.requests += 1
            self.last_request = time.monotonic()
            connection = http.client.HTTPSConnection(p.hostname, timeout=self.timeout, context=ssl.create_default_context())
            # TLS still verifies the original hostname; connect only to checked IP.
            connection._create_connection = lambda address, timeout=None, source_address=None: socket.create_connection((addresses[0], 443), timeout, source_address)
            try:
                path = urllib.parse.urlunsplit(('', '', p.path or '/', p.query, ''))
                connection.request('GET', path, headers={'User-Agent': self.agent, 'Accept': 'text/html,application/json;q=0.9,*/*;q=0.5', 'Accept-Encoding': 'identity'})
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    target = urllib.parse.urljoin(url, response.getheader('Location', ''))
                    validate_url(target, self.hosts)
                    # A redirected page must also pass destination robots rules.
                    if not target.endswith('/robots.txt'):
                        self._check_robots(target)
                    url = target
                    continue
                if response.status in (401,):
                    raise SourceError('auth_required', 'Источник требует авторизацию (HTTP 401)')
                if response.status in (403, 418, 429, 498):
                    raise SourceError('blocked', 'Источник ограничил доступ (HTTP %s)' % response.status)
                if response.status in (404, 410):
                    raise SourceError('unavailable', 'Страница больше недоступна (HTTP %s)' % response.status)
                if response.status >= 400:
                    raise SourceError('error', 'Ошибка источника HTTP %s' % response.status, retryable=response.status >= 500)
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise SourceError('error', 'Ответ превышает 5 MiB')
                content_type = response.getheader('Content-Type', '')
                text = raw.decode('utf-8', errors='replace')
                if 'captcha' in text[:10000].lower() and ('challenge' in text[:10000].lower() or 'verify you' in text[:10000].lower()):
                    raise SourceError('blocked', 'Проверка CAPTCHA: сбор остановлен')
                return text, url, content_type
            finally:
                connection.close()
        raise SourceError('error', 'Слишком много перенаправлений')

    def _check_robots(self, url):
        p = validate_url(url, self.hosts)
        if p.hostname not in self.robots:
            robots_url = 'https://' + p.hostname + '/robots.txt'
            # Sentinel prevents recursion for robots redirects. Deny until loaded.
            self.robots[p.hostname] = None
            try:
                text, _, _ = self._raw(robots_url)
                if '<html' in text.lower():
                    raise SourceError('blocked', 'Вместо robots.txt получена HTML-страница')
                parser = Robots(text, self.agent)
                self.robots[p.hostname] = parser
            except Exception:
                self.robots[p.hostname] = None
                raise SourceError('blocked', 'robots.txt недоступен: автоматический сбор не разрешён')
        parser = self.robots[p.hostname]
        if parser is None or not parser.can_fetch(self.agent, url):
            raise SourceError('robots_denied', 'URL запрещён robots.txt или правила недоступны')
        delay = parser.crawl_delay(self.agent)
        if delay:
            self.interval = max(self.interval, delay)

    def get(self, url):
        self._check_robots(url)
        for attempt in range(2):
            try:
                return self._raw(url)
            except (OSError, http.client.HTTPException):
                if attempt == 1:
                    raise SourceError('error', 'Сетевая ошибка или таймаут')
                time.sleep(2 ** attempt)
            except SourceError as e:
                if not e.retryable or attempt == 1:
                    raise
                time.sleep(2 ** attempt)
