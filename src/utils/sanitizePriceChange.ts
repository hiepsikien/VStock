/** Repair abs change when it disagrees with % or looks like raw VND. */
export function sanitizePriceChange(
  price: number,
  change: number,
  changePercent: number,
): number {
  if (!Number.isFinite(price) || price <= 0) return change;

  const signMismatch =
    (change > 0 && changePercent < 0) ||
    (change < 0 && changePercent > 0) ||
    (Math.abs(change) < 1e-9 && Math.abs(changePercent) > 1e-9);

  // e.g. change=100 while price=14.45 — old SSI VND bug
  const absurdMagnitude = Math.abs(change) > Math.max(price * 0.35, 5);

  if (!signMismatch && !absurdMagnitude) {
    return Number(change.toFixed(2));
  }

  if (Number.isFinite(changePercent) && Math.abs(changePercent) > 1e-9) {
    const ref = price / (1 + changePercent / 100);
    if (ref > 0 && Number.isFinite(ref)) {
      return Number((price - ref).toFixed(2));
    }
  }

  return Number(((price * changePercent) / 100).toFixed(2));
}
