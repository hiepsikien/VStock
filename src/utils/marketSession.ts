/** VN equity session: HOSE/HNX, Mon–Fri, Asia/Ho_Chi_Minh */

const VN_TZ = 'Asia/Ho_Chi_Minh';

const WEEKDAY: Record<string, number> = {
  Sun: 0,
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
};

export const REFRESH = {
  /** Poll watchlist / quote while screen focused in session */
  quotePollMs: 30_000,
  /** Refresh 1D chart while viewing detail in session */
  chart1dPollMs: 5 * 60_000,
} as const;

function vnTimeParts(now: Date): { weekday: number; minutes: number } {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: VN_TZ,
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
      .formatToParts(now)
      .map((p) => [p.type, p.value]),
  );

  const weekday = WEEKDAY[parts.weekday] ?? 0;
  const hour = Number(parts.hour);
  const minute = Number(parts.minute);
  return { weekday, minutes: hour * 60 + minute };
}

export function isMarketOpen(now = new Date()): boolean {
  const { weekday, minutes } = vnTimeParts(now);
  if (weekday === 0 || weekday === 6) return false;

  const morning = minutes >= 9 * 60 && minutes < 11 * 60 + 30;
  const afternoon = minutes >= 13 * 60 && minutes < 14 * 60 + 45;
  return morning || afternoon;
}

export function marketSessionLabel(now = new Date()): string {
  return isMarketOpen(now) ? 'đang giao dịch' : 'ngoài giờ';
}
