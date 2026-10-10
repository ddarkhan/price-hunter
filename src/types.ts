export type Status = 'confirmed' | 'possible' | 'insufficient' | 'unavailable';
export interface History { at: string; price: number; total: number | null; struck_price: number | null; available: boolean | null; url: string }
export interface Offer {
  id: string; name: string; shop: string; seller: string; sku: string; url: string; image: string | null; category: string;
  price: number; struck_price: number | null; total: number | null; currency: string; baseline: number | null;
  baseline_kind: 'history' | 'market' | null; market_base: number | null; history_base: number | null;
  discount: number | null; discount_upper_bound: number | null; market_discount: number | null; history_discount: number | null;
  confidence: string; status: Status; observed_at: string; astana: string | null; condition: string | null; quantity: number | null;
  volume: string | null; bundle: string | null; variant: string | null; model: string | null; brand: string | null;
  delivery_cost: number | null; mandatory_cost: number | null; full_payment: boolean | null; available: boolean | null;
  limitations: string[]; conditions: string[]; history: History[];
  comparisons: { id: string; name: string; shop: string; seller: string; url: string; observed_at: string; total: number; quantity: number; condition: string }[];
}
export interface Source { shop: string; status: string; implemented: boolean; checked_at: string; last_success: string | null;
  message: string; products_checked: number; products_failed: number; discovered: number; actions_verified: boolean;
  categories: { label: string; key: string; url: string; status: string; discovered: number; message?: string }[] }
export interface Dataset { schema_version: number; generated_at: string | null; last_success: string | null; city: string;
  currency: string; stale_minutes: number; demo: boolean; offers: Offer[]; sources: Source[];
  coverage: { checked: number; tracked: number; discovered: number; categories: Source['categories'] } }
