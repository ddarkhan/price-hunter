import { describe, expect, it } from 'vitest';
import { price, safeLink, stale, validateData } from './lib';
import empty from '../public/data/catalog.json';
describe('public data safeguards', () => {
  it('preserves unknown amounts and rejects untrusted links', () => { expect(price(null)).toBe('Неизвестно'); expect(safeLink('javascript:alert(1)')).toBeUndefined(); expect(safeLink('https://kaspi.kz.evil.example/a')).toBeUndefined(); expect(safeLink('https://user:pass@kaspi.kz/a')).toBeUndefined(); expect(safeLink('https://www.technodom.kz/astana/p/a')).toBeTruthy(); });
  it('reports never-run and old snapshots as stale', () => { expect(stale(validateData({ ...empty, last_success: null }))).toBe(true); expect(stale(validateData({ ...empty, last_success: '2025-01-01T00:00:00Z' }))).toBe(true); });
  it('rejects corrupted data rather than silently showing a false empty result', () => { expect(() => validateData({ ...empty, offers: null })).toThrow(); expect(() => validateData({ ...empty, currency: 'RUB' })).toThrow(); });
});
