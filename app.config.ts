import type { ConfigContext, ExpoConfig } from 'expo/config';

const IS_DEV = process.env.APP_VARIANT === 'development';

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: IS_DEV ? 'VStock (Dev)' : 'VStock',
  slug: 'VStock',
  owner: 'hiepsikien',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'dark',
  scheme: IS_DEV ? 'vstock-dev' : 'vstock',
  ios: {
    supportsTablet: true,
    bundleIdentifier: IS_DEV
      ? 'com.nguyendinhanh.vstock.dev'
      : 'com.nguyendinhanh.vstock',
    buildNumber: '1',
    config: {
      usesNonExemptEncryption: false,
    },
    infoPlist: {
      NSAppTransportSecurity: {
        NSAllowsArbitraryLoads: true,
      },
      UIBackgroundModes: ['processing'],
    },
  },
  android: {
    package: IS_DEV
      ? 'com.nguyendinhanh.vstock.dev'
      : 'com.nguyendinhanh.vstock',
    adaptiveIcon: {
      backgroundColor: '#C8F000',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    predictiveBackGestureEnabled: false,
  },
  web: {
    favicon: './assets/favicon.png',
  },
  plugins: [
    'expo-dev-client',
    'expo-web-browser',
    'expo-background-task',
    [
      'expo-notifications',
      {
        icon: './assets/icon.png',
      },
    ],
    'expo-asset',
    [
      '@sentry/react-native/expo',
      {
        url: 'https://sentry.io/',
        organization: 'antun-ai',
        project: 'vstock-mobile',
      },
    ],
  ],
  extra: {
    appVariant: IS_DEV ? 'development' : 'production',
    eas: {
      projectId: 'f7e4ca56-9fa6-41b0-8b8b-362847caf13b',
    },
  },
});
