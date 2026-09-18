import AsyncStorage from '@react-native-async-storage/async-storage';

export type AlertCondition = 'above' | 'below';

export type PriceAlert = {
  id: string;
  symbol: string;
  condition: AlertCondition;
  price: number;
  enabled: boolean;
  triggeredAt?: string;
  /** Last live quote observed while the alert was armed. Used for cross detection. */
  lastSeenPrice?: number;
};

const KEY = 'vstock.price.alerts';

function parseAlert(raw: unknown): PriceAlert | null {
  if (!raw || typeof raw !== 'object') return null;
  const a = raw as Partial<PriceAlert>;
  if (typeof a.symbol !== 'string' || !a.symbol.trim()) return null;
  const price = Number(a.price);
  if (!Number.isFinite(price) || price <= 0) return null;
  if (a.condition !== 'above' && a.condition !== 'below') return null;
  const lastSeenPrice =
    a.lastSeenPrice != null && Number.isFinite(Number(a.lastSeenPrice)) && Number(a.lastSeenPrice) > 0
      ? Number(a.lastSeenPrice)
      : undefined;
  return {
    id: typeof a.id === 'string' && a.id ? a.id : `alert_${Date.now()}`,
    symbol: a.symbol.trim().toUpperCase(),
    condition: a.condition,
    price,
    enabled: a.enabled !== false,
    triggeredAt: typeof a.triggeredAt === 'string' ? a.triggeredAt : undefined,
    lastSeenPrice,
  };
}

export async function loadPriceAlerts(): Promise<PriceAlert[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.map(parseAlert).filter((a): a is PriceAlert => a != null);
  } catch {
    return [];
  }
}

export async function savePriceAlerts(alerts: PriceAlert[]): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(alerts));
}

export async function upsertPriceAlert(
  alert: Omit<PriceAlert, 'id'> & { id?: string },
): Promise<PriceAlert[]> {
  const alerts = await loadPriceAlerts();
  const id = alert.id ?? `alert_${Date.now()}`;
  const next: PriceAlert = {
    id,
    symbol: alert.symbol.toUpperCase(),
    condition: alert.condition,
    price: alert.price,
    enabled: alert.enabled,
    lastSeenPrice:
      alert.lastSeenPrice != null && Number.isFinite(alert.lastSeenPrice) && alert.lastSeenPrice > 0
        ? alert.lastSeenPrice
        : undefined,
    triggeredAt: alert.enabled ? undefined : alert.triggeredAt,
  };
  const filtered = alerts.filter(
    (a) => a.id !== id && !(a.symbol === next.symbol && a.condition === next.condition),
  );
  const merged = [...filtered, next];
  await savePriceAlerts(merged);
  return merged;
}

export async function removePriceAlert(id: string): Promise<PriceAlert[]> {
  const alerts = await loadPriceAlerts();
  const next = alerts.filter((a) => a.id !== id);
  await savePriceAlerts(next);
  return next;
}

export async function getAlertsForSymbol(symbol: string): Promise<PriceAlert[]> {
  const sym = symbol.toUpperCase();
  const alerts = await loadPriceAlerts();
  return alerts.filter((a) => a.symbol === sym && a.enabled);
}

export function alertLabel(alert: PriceAlert): string {
  const op = alert.condition === 'above' ? '≥' : '≤';
  return `${alert.symbol} ${op} ${alert.price.toFixed(2)}`;
}
