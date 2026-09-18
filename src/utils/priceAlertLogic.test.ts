import assert from 'node:assert/strict';
import type { PriceAlert } from '../storage/alerts';
import {
  evaluatePriceAlerts,
  isPriceAlreadyThroughAlert,
  isUsableQuotePrice,
  shouldTriggerPriceAlert,
} from './priceAlertLogic';

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

assert.equal(shouldTriggerPriceAlert(above, 81), false, 'no lastSeen → do not fire');
assert.equal(shouldTriggerPriceAlert(above, 81, 79), true, 'cross from below to above');
assert.equal(shouldTriggerPriceAlert(above, 80, 79), true, 'touch target from below');
assert.equal(shouldTriggerPriceAlert(above, 80.1, 80), true, 'armed at target, next uptick');
assert.equal(shouldTriggerPriceAlert(above, 80, 80), false, 'armed at target, unchanged');
assert.equal(shouldTriggerPriceAlert(above, 82, 81), false, 'already through, no re-cross');
assert.equal(shouldTriggerPriceAlert(above, 0, 79), false, 'invalid live price');

assert.equal(shouldTriggerPriceAlert(below, 69, 71), true, 'cross from above to below');
assert.equal(shouldTriggerPriceAlert(below, 70, 71), true, 'touch target from above');
assert.equal(shouldTriggerPriceAlert(below, 69.9, 70), true, 'armed at target, next downtick');
assert.equal(shouldTriggerPriceAlert(below, 70, 70), false, 'armed at target, unchanged');
assert.equal(shouldTriggerPriceAlert(below, 68, 69), false, 'already through, no re-cross');

assert.equal(isUsableQuotePrice(quote('VNM', 64.5)), true);
assert.equal(isUsableQuotePrice(quote('NAV', 0, { unavailable: true })), false);
assert.equal(isUsableQuotePrice(quote('NAV', 0)), false);

assert.equal(isPriceAlreadyThroughAlert('above', 80, 80), true);
assert.equal(isPriceAlreadyThroughAlert('above', 90, 80), false);
assert.equal(isPriceAlreadyThroughAlert('below', 70, 70), true);
assert.equal(isPriceAlreadyThroughAlert('below', 70, 80), false);

const firstTick = evaluatePriceAlerts(
  [above],
  [quote('VNM', 81)],
  '2026-09-18T00:00:00.000Z',
);
assert.equal(firstTick.deliveries.length, 0, 'first live tick only arms');
assert.equal(firstTick.alerts[0]?.lastSeenPrice, 81);
assert.equal(firstTick.alerts[0]?.enabled, true);
assert.equal(firstTick.changed, true);

const crossed = evaluatePriceAlerts(
  [{ ...above, lastSeenPrice: 79 }],
  [quote('VNM', 80.5)],
  '2026-09-18T00:01:00.000Z',
);
assert.equal(crossed.deliveries.length, 1);
assert.equal(crossed.alerts[0]?.enabled, false);
assert.equal(crossed.alerts[0]?.triggeredAt, '2026-09-18T00:01:00.000Z');
assert.equal(crossed.alerts[0]?.lastSeenPrice, 80.5);

const skippedZero = evaluatePriceAlerts(
  [{ ...below, lastSeenPrice: 71 }],
  [quote('VNM', 0, { unavailable: true })],
  '2026-09-18T00:02:00.000Z',
);
assert.equal(skippedZero.deliveries.length, 0, 'placeholder / unavailable quote must not fire');
assert.equal(skippedZero.alerts[0]?.enabled, true);
assert.equal(skippedZero.changed, false);

const original = [{ ...above, lastSeenPrice: 79 }];
const frozen = JSON.parse(JSON.stringify(original)) as PriceAlert[];
evaluatePriceAlerts(original, [quote('VNM', 81)], '2026-09-18T00:03:00.000Z');
assert.deepEqual(original, frozen, 'evaluate must not mutate input alerts');

const missingQuote = evaluatePriceAlerts(
  [{ ...above, lastSeenPrice: 79 }],
  [quote('FPT', 128)],
  '2026-09-18T00:04:00.000Z',
);
assert.equal(missingQuote.deliveries.length, 0);
assert.equal(missingQuote.alerts[0]?.enabled, true);

console.log('priceAlertLogic tests passed');
