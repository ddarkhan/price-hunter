import type { Dataset, Offer } from './types';
export const stores: Record<string, string> = { technodom: 'Technodom', ozon: 'Ozon', wildberries: 'Wildberries', sulpak: 'Sulpak', dns: 'DNS', kaspi: 'Kaspi', mechta: 'Mechta', alser: 'Alser', fora: 'Fora' };
export const categories: Record<string, string> = { computers: 'Компьютеры', gadgets: 'Гаджеты', accessories: 'Аксессуары', appliances: 'Бытовая техника', clothing: 'Одежда и обувь', food: 'Продукты', household: 'Химия и гигиена', tools: 'Дом и инструменты', sport: 'Спорт и хобби' };
export const statuses: Record<string, string> = { confirmed: 'Подтверждено', possible: 'Нужна проверка', insufficient: 'Недостаточно данных', unavailable: 'Нет в наличии', excluded: 'Исключено', ok: 'Доступен', partial: 'Частичный сбор', disabled: 'Отключён', blocked: 'Заблокирован', robots_denied: 'Запрет robots.txt', auth_required: 'Нужна авторизация', not_implemented: 'Не реализован', error: 'Ошибка', no_data: 'Нет данных' };
export function price(n: number | null | undefined): string { return n == null ? 'Неизвестно' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(n)} ₸`; }
export function date(s: string | null): string { return s ? new Date(s).toLocaleString('ru-RU', { timeZone: 'Asia/Almaty', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'Ещё не было'; }
export function stale(data: Dataset, now = Date.now()): boolean { return !data.last_success || !Number.isFinite(Date.parse(data.last_success)) || now - new Date(data.last_success).getTime() > data.stale_minutes * 60_000; }
export function offerStale(offer: Offer, minutes: number): boolean { return Date.now() - new Date(offer.observed_at).getTime() > minutes * 60_000; }
export function safeLink(url: string): string | undefined {
  try { const p = new URL(url); const domains = ['technodom.kz', 'ozon.kz', 'wildberries.kz', 'sulpak.kz', 'dns-shop.kz', 'kaspi.kz', 'mechta.kz', 'alser.kz', 'fora.kz'];
    if (p.protocol !== 'https:' || p.username || p.password || (p.port && p.port !== '443')) return;
    if (domains.some(h => p.hostname === h || p.hostname === `www.${h}`)) return url;
  } catch { /* Unknown is not a valid link. */ }
}
export function safeImage(url: string | null): string | undefined { try { if (!url) return; const p = new URL(url); return p.protocol === 'https:' && !p.username && !p.password && ['api.technodom.kz', 'www.technodom.kz', 'technodom.kz'].includes(p.hostname) ? url : undefined; } catch { return; } }
export function validateData(value: unknown): Dataset {
  if (!value || typeof value !== 'object') throw new Error('Некорректный формат данных');
  const d = value as Dataset;
  if (d.schema_version !== 1 || d.currency !== 'KZT' || !Array.isArray(d.offers) || !Array.isArray(d.sources) || !d.coverage || !Number.isFinite(d.stale_minutes)) throw new Error('Версия или структура JSON не поддерживается');
  for (const o of d.offers) if (!o.id || !o.name || !Number.isFinite(o.price) || o.price <= 0 || o.currency !== 'KZT' || !Array.isArray(o.history) || !Array.isArray(o.limitations) || !Array.isArray(o.conditions) || !Array.isArray(o.comparisons) || !Number.isFinite(Date.parse(o.observed_at)) || !['confirmed', 'possible', 'insufficient', 'unavailable'].includes(o.status)) throw new Error('Повреждённые товарные данные');
  for (const s of d.sources) if (!s.shop || !s.status || !Array.isArray(s.categories)) throw new Error('Повреждённые состояния источников');
  return d;
}
