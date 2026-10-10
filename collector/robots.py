"""Robots parser with wildcard/end-marker and longest-match Allow semantics."""
import re
from urllib.parse import urlsplit, unquote


class Robots:
    def __init__(self, text, agent):
        groups, agents, rules, delay = [], [], [], None
        has_rules = False
        for line in text.splitlines() + ['User-agent: __end__']:
            line = line.split('#', 1)[0].strip()
            if ':' not in line:
                continue
            key, value = (part.strip() for part in line.split(':', 1))
            key = key.casefold()
            if key == 'user-agent':
                if has_rules:
                    groups.append((agents, rules, delay))
                    agents, rules, delay, has_rules = [], [], None, False
                agents.append(value.casefold())
            elif key in ('allow', 'disallow') and agents:
                has_rules = True
                if value:
                    rules.append((key == 'allow', value))
            elif key == 'crawl-delay' and agents:
                has_rules = True
                try:
                    delay = float(value)
                except ValueError:
                    pass
        matching = [(max([len(a) if a != '*' else 0 for a in aa if a == '*' or a in agent.casefold()], default=-1), rr, dd) for aa, rr, dd in groups]
        level = max([m[0] for m in matching], default=-1)
        selected = [m for m in matching if m[0] == level and level >= 0]
        self.rules = [r for _, rr, _ in selected for r in rr]
        self.delay = max([d for _, _, d in selected if d is not None], default=None)

    def can_fetch(self, agent, url):
        p = urlsplit(url)
        target = unquote(p.path or '/') + ('?' + unquote(p.query) if p.query else '')
        matches = []
        for allow, pattern in self.rules:
            end = pattern.endswith('$')
            source = pattern[:-1] if end else pattern
            regex = '^' + re.escape(unquote(source)).replace(r'\*', '.*') + ('$' if end else '')
            if re.search(regex, target):
                matches.append((len(source.replace('*', '')), allow))
        return max(matches, default=(0, True))[1]

    def crawl_delay(self, agent):
        return self.delay
