import * as Sentry from '@sentry/react-native';

const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN?.trim();

/**
 * Crash reporting for TestFlight / production builds.
 * Set EXPO_PUBLIC_SENTRY_DSN (and SENTRY_AUTH_TOKEN for source maps on EAS).
 * Local Metro: disabled unless EXPO_PUBLIC_SENTRY_DEV=1.
 */
export function initSentry(): void {
  if (!dsn) return;

  const enableInDev = process.env.EXPO_PUBLIC_SENTRY_DEV === '1';

  Sentry.init({
    dsn,
    enabled: !__DEV__ || enableInDev,
    environment: __DEV__ ? 'development' : 'production',
    // Keep volume low while validating TestFlight; raise later if needed.
    tracesSampleRate: __DEV__ ? 1.0 : 0.1,
    sendDefaultPii: false,
    enableAutoSessionTracking: true,
  });
}

export { Sentry };
