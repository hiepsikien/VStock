import AsyncStorage from '@react-native-async-storage/async-storage';

export type AlertCondition = 'above' | 'below';

export type PriceAlert = {
  id: string;
  symbol: string;
  condition: AlertCondition;
  price: number;
  enabled: boolean;
  triggeredAt?: string;
};

const KEY = 'vstock.price.alerts';

export async function loadPriceAlerts(): Promise<PriceAlert[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((a) => a as PriceAlert)
      .filter((a) => a.symbol && a.price > 0);
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
  };
  const filtered = alerts.filter((a) => a.id !== id && !(a.symbol === next.symbol && a.condition === next.condition));
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
  return `${alert.symbol} ${op} ${alert.price}`;
}
