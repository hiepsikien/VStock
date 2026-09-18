import type { PriceAlert } from '../storage/alerts';
import {
  evaluatePriceAlerts,
  isPriceAlreadyThroughAlert,
  isUsableQuotePrice,
  mergeEvaluatedAlerts,
  roundAlertPrice,
  shouldTriggerPriceAlert,
} from './priceAlertLogic';

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`);
  }
}

function assertDeepEqual<T>(actual: T, expected: T, message: string) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    throw new Error(`${message}: expected ${b}, got ${a}`);
  }
}

function alert(partial: Partial<PriceAlert> & Pick<PriceAlert, 'id' | 'symbol' | 'condition' | 'price'>): PriceAlert {
  return {
    enabled: true,
    ...partial,
  };
}

function quote(symbol: string, price: number, extra?: { unavailable?: boolean; name?: string }) {
  return { symbol, name: extra?.name ?? symbol, price, unavailable: extra?.unavailable };
}

const above = alert({ id: 'a1', symbol: 'VNM', condition: 'above', price: 80 });
const below = alert({ id: 'b1', symbol: 'VNM', condition: 'below', price: 70 });

assertEqual(roundAlertPrice(80.1), 80.1, 'round 80.1');
assertEqual(roundAlertPrice(80.104), 80.1, 'round 80.104');
assertEqual(roundAlertPrice(80.105), 80.11, 'round 80.105');
assertEqual(roundAlertPrice(80.0999999999), 80.1, 'float 80.1');
assertEqual(
  shouldTriggerPriceAlert({ ...above, price: 80.1 }, 80.11, 80.0999999999),
  true,
  'armed at rounded 80.10, next uptick',
);

assertEqual(shouldTriggerPriceAlert(above, 81), false, 'no lastSeen → do not fire');
assertEqual(shouldTriggerPriceAlert(above, 81, 79), true, 'cross from below to above');
assertEqual(shouldTriggerPriceAlert(above, 80, 79), true, 'touch target from below');
assertEqual(shouldTriggerPriceAlert(above, 80.1, 80), true, 'armed at target, next uptick');
assertEqual(shouldTriggerPriceAlert(above, 80, 80), false, 'armed at target, unchanged');
assertEqual(shouldTriggerPriceAlert(above, 82, 81), false, 'already through, no re-cross');
assertEqual(shouldTriggerPriceAlert(above, 0, 79), false, 'invalid live price');

assertEqual(shouldTriggerPriceAlert(below, 69, 71), true, 'cross from above to below');
assertEqual(shouldTriggerPriceAlert(below, 70, 71), true, 'touch target from above');
assertEqual(shouldTriggerPriceAlert(below, 69.9, 70), true, 'armed at target, next downtick');
assertEqual(shouldTriggerPriceAlert(below, 70, 70), false, 'armed at target, unchanged');
assertEqual(shouldTriggerPriceAlert(below, 68, 69), false, 'already through, no re-cross');

assertEqual(isUsableQuotePrice(quote('VNM', 64.5)), true, 'usable quote');
assertEqual(isUsableQuotePrice(quote('NAV', 0, { unavailable: true })), false, 'unavailable');
assertEqual(isUsableQuotePrice(quote('NAV', 0)), false, 'zero price');

assertEqual(isPriceAlreadyThroughAlert('above', 80, 80), true, 'above at target is through');
assertEqual(isPriceAlreadyThroughAlert('above', 90, 80), false, 'above not yet');
assertEqual(isPriceAlreadyThroughAlert('below', 70, 70), true, 'below at target is through');
assertEqual(isPriceAlreadyThroughAlert('below', 70, 80), false, 'below not yet');

const firstTick = evaluatePriceAlerts(
  [above],
  [quote('VNM', 81)],
  '2026-09-18T00:00:00.000Z',
);
assertEqual(firstTick.deliveries.length, 0, 'first live tick only arms');
assertEqual(firstTick.alerts[0]?.lastSeenPrice, 81, 'arm lastSeen');
assertEqual(firstTick.alerts[0]?.enabled, true, 'still enabled after arm');
assertEqual(firstTick.changed, true, 'arm persists lastSeen');

const crossed = evaluatePriceAlerts(
  [{ ...above, lastSeenPrice: 79 }],
  [quote('VNM', 80.5)],
  '2026-09-18T00:01:00.000Z',
);
assertEqual(crossed.deliveries.length, 1, 'cross delivers');
assertEqual(crossed.alerts[0]?.enabled, false, 'disabled after fire');
assertEqual(crossed.alerts[0]?.triggeredAt, '2026-09-18T00:01:00.000Z', 'triggeredAt set');
assertEqual(crossed.alerts[0]?.lastSeenPrice, 80.5, 'lastSeen at fire');

const skippedZero = evaluatePriceAlerts(
  [{ ...below, lastSeenPrice: 71 }],
  [quote('VNM', 0, { unavailable: true })],
  '2026-09-18T00:02:00.000Z',
);
assertEqual(skippedZero.deliveries.length, 0, 'placeholder / unavailable quote must not fire');
assertEqual(skippedZero.alerts[0]?.enabled, true, 'still enabled');
assertEqual(skippedZero.changed, false, 'no persist without usable quote');

const original = [{ ...above, lastSeenPrice: 79 }];
const frozen = JSON.parse(JSON.stringify(original)) as PriceAlert[];
evaluatePriceAlerts(original, [quote('VNM', 81)], '2026-09-18T00:03:00.000Z');
assertDeepEqual(original, frozen, 'evaluate must not mutate input alerts');

const missingQuote = evaluatePriceAlerts(
  [{ ...above, lastSeenPrice: 79 }],
  [quote('FPT', 128)],
  '2026-09-18T00:04:00.000Z',
);
assertEqual(missingQuote.deliveries.length, 0, 'missing symbol does not fire');
assertEqual(missingQuote.alerts[0]?.enabled, true, 'missing symbol stays enabled');

const snapshot = [{ ...above, lastSeenPrice: 79 }];
const evaluated = evaluatePriceAlerts(snapshot, [quote('VNM', 80.5)], '2026-09-18T00:05:00.000Z').alerts;
const createdDuringTick: PriceAlert = {
  id: 'a2',
  symbol: 'FPT',
  condition: 'above',
  price: 130,
  enabled: true,
  lastSeenPrice: 128,
};
const mergedKeepCreate = mergeEvaluatedAlerts(
  [...snapshot, createdDuringTick],
  evaluated,
  snapshot,
);
assertEqual(mergedKeepCreate.some((a) => a.id === 'a2'), true, 'merge keeps alert created during tick');
assertEqual(mergedKeepCreate.find((a) => a.id === 'a1')?.enabled, false, 'merge still applies fire');

const userEdited: PriceAlert = { ...above, price: 90, lastSeenPrice: 79, enabled: true };
const mergedKeepEdit = mergeEvaluatedAlerts([userEdited], evaluated, snapshot);
assertEqual(mergedKeepEdit[0]?.price, 90, 'merge keeps user price edit');
assertEqual(mergedKeepEdit[0]?.enabled, true, 'merge does not disable after user changed target');

console.log('priceAlertLogic tests passed');
