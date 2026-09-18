import Constants from 'expo-constants';
import { Alert, AppState, Platform } from 'react-native';
import type { Stock } from '../types';
import type { PriceAlert } from '../storage/alerts';

export const PRICE_ALERT_CHANNEL_ID = 'price-alerts';

/** Local/push notifications are not available in Expo Go (SDK 53+). */
export function notificationsSupported(): boolean {
  return Constants.appOwnership !== 'expo';
}

export function alertDeliveryHint(): string {
  if (notificationsSupported()) {
    return 'Thông báo khi giá cắt mức đã đặt. App nền vẫn kiểm tra (development / production build).';
  }
  return 'Expo Go: cảnh báo hiện trong app khi mở VStock (không có push). Build riêng để có thông báo nền.';
}

function formatAlertBody(alert: PriceAlert, stock: Pick<Stock, 'name' | 'price'>): string {
  const op = alert.condition === 'above' ? 'vượt' : 'xuống dưới';
  return `${stock.name}\nGiá ${stock.price.toFixed(2)} đã ${op} ${alert.price.toFixed(2)}`;
}

export function showInAppPriceAlert(alert: PriceAlert, stock: Stock) {
  Alert.alert(`Cảnh báo ${alert.symbol}`, formatAlertBody(alert, stock), [{ text: 'OK' }]);
}

let handlerReady = false;

export async function ensureNotificationHandler(): Promise<void> {
  if (handlerReady || !notificationsSupported()) return;
  try {
    const Notifications = await import('expo-notifications');
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
        shouldShowBanner: true,
        shouldShowList: true,
      }),
    });
    handlerReady = true;
  } catch {
    /* Expo Go / missing native module */
  }
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!notificationsSupported()) return false;

  try {
    await ensureNotificationHandler();
    const Notifications = await import('expo-notifications');

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    if (existing !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== 'granted') return false;

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(PRICE_ALERT_CHANNEL_ID, {
        name: 'Cảnh báo giá',
        importance: Notifications.AndroidImportance.HIGH,
      });
    }
    return true;
  } catch {
    return false;
  }
}

function isAppActive(): boolean {
  return AppState.currentState === 'active';
}

export async function deliverPriceAlert(alert: PriceAlert, stock: Stock): Promise<void> {
  if (!notificationsSupported()) {
    if (isAppActive()) {
      showInAppPriceAlert(alert, stock);
    }
    return;
  }

  try {
    await ensureNotificationHandler();
    const Notifications = await import('expo-notifications');
    const op = alert.condition === 'above' ? 'vượt' : 'xuống dưới';
    await Notifications.scheduleNotificationAsync({
      content: {
        title: `Cảnh báo ${alert.symbol}`,
        body: `${stock.name} · ${stock.price.toFixed(2)} (${op} ${alert.price.toFixed(2)})`,
        data: { symbol: alert.symbol },
        sound: true,
      },
      trigger: Platform.OS === 'android' ? { channelId: PRICE_ALERT_CHANNEL_ID } : null,
    });
  } catch {
    if (isAppActive()) {
      showInAppPriceAlert(alert, stock);
    }
  }
}
