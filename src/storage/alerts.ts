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

function roundAlertPrice(value: number): number {
  return Math.round(value * 100) / 100;
}

let mutationQueue: Promise<unknown> = Promise.resolve();

function enqueuePriceAlertMutation<T>(work: () => Promise<T>): Promise<T> {
  const run = mutationQueue.then(work, work);
  mutationQueue = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

function parseOptionalPrice(value: unknown): number | undefined {
  if (value == null) return undefined;
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return undefined;
  return roundAlertPrice(n);
}

function parseAlert(raw: unknown): PriceAlert | null {
  if (!raw || typeof raw !== 'object') return null;
  const a = raw as Partial<PriceAlert>;
  if (typeof a.symbol !== 'string' || !a.symbol.trim()) return null;
  const price = parseOptionalPrice(a.price);
  if (price == null) return null;
  if (a.condition !== 'above' && a.condition !== 'below') return null;
  return {
    id: typeof a.id === 'string' && a.id ? a.id : `alert_${Date.now()}`,
    symbol: a.symbol.trim().toUpperCase(),
    condition: a.condition,
    price,
    enabled: a.enabled !== false,
    triggeredAt: typeof a.triggeredAt === 'string' ? a.triggeredAt : undefined,
    lastSeenPrice: parseOptionalPrice(a.lastSeenPrice),
  };
}

async function loadPriceAlertsUnlocked(): Promise<PriceAlert[]> {
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

async function savePriceAlertsUnlocked(alerts: PriceAlert[]): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(alerts));
}

export async function loadPriceAlerts(): Promise<PriceAlert[]> {
  return loadPriceAlertsUnlocked();
}

export async function savePriceAlerts(alerts: PriceAlert[]): Promise<void> {
  return enqueuePriceAlertMutation(() => savePriceAlertsUnlocked(alerts));
}

/** Serialize load-modify-save so poll ticks cannot drop a concurrent upsert. */
export async function mutatePriceAlerts(
  updater: (alerts: PriceAlert[]) => PriceAlert[] | Promise<PriceAlert[]>,
): Promise<PriceAlert[]> {
  return enqueuePriceAlertMutation(async () => {
    const current = await loadPriceAlertsUnlocked();
    const next = await updater(current);
    if (next !== current) {
      await savePriceAlertsUnlocked(next);
    }
    return next;
  });
}

export async function upsertPriceAlert(
  alert: Omit<PriceAlert, 'id'> & { id?: string },
): Promise<PriceAlert[]> {
  return mutatePriceAlerts((alerts) => {
    const id = alert.id ?? `alert_${Date.now()}`;
    const next: PriceAlert = {
      id,
      symbol: alert.symbol.toUpperCase(),
      condition: alert.condition,
      price: roundAlertPrice(alert.price),
      enabled: alert.enabled,
      lastSeenPrice: parseOptionalPrice(alert.lastSeenPrice),
      triggeredAt: alert.enabled ? undefined : alert.triggeredAt,
    };
    const filtered = alerts.filter(
      (a) => a.id !== id && !(a.symbol === next.symbol && a.condition === next.condition),
    );
    return [...filtered, next];
  });
}

export async function removePriceAlert(id: string): Promise<PriceAlert[]> {
  return mutatePriceAlerts((alerts) => alerts.filter((a) => a.id !== id));
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
