import Constants from 'expo-constants';
import { Alert, Platform } from 'react-native';
import type { Stock } from '../types';
import type { PriceAlert } from '../storage/alerts';

/** Local/push notifications are not available in Expo Go (SDK 53+). */
export function notificationsSupported(): boolean {
  return Constants.appOwnership !== 'expo';
}

export function alertDeliveryHint(): string {
  if (notificationsSupported()) {
    return 'Bạn sẽ nhận thông báo khi giá chạm mức đã đặt, kể cả khi app ở nền (development build).';
  }
  return 'Expo Go: cảnh báo hiện trong app khi mở VStock (không có push). Build riêng để có thông báo nền.';
}

export function showInAppPriceAlert(alert: PriceAlert, stock: Stock) {
  const op = alert.condition === 'above' ? 'vượt' : 'xuống dưới';
  Alert.alert(
    `Cảnh báo ${alert.symbol}`,
    `${stock.name}\nGiá ${stock.price.toFixed(2)} đã ${op} ${alert.price.toFixed(2)}`,
    [{ text: 'OK' }],
  );
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!notificationsSupported()) return false;

  try {
    const Notifications = await import('expo-notifications');
    const Device = await import('expo-device');

    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
        shouldShowBanner: true,
        shouldShowList: true,
      }),
    });

    if (!Device.isDevice) return false;

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    if (existing !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== 'granted') return false;

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('price-alerts', {
        name: 'Cảnh báo giá',
        importance: Notifications.AndroidImportance.HIGH,
      });
    }
    return true;
  } catch {
    return false;
  }
}

export async function deliverPriceAlert(alert: PriceAlert, stock: Stock): Promise<void> {
  if (!notificationsSupported()) {
    showInAppPriceAlert(alert, stock);
    return;
  }

  try {
    const Notifications = await import('expo-notifications');
    const op = alert.condition === 'above' ? 'vượt' : 'xuống dưới';
    await Notifications.scheduleNotificationAsync({
      content: {
        title: `Cảnh báo ${alert.symbol}`,
        body: `${stock.name} · ${stock.price.toFixed(2)} (${op} ${alert.price})`,
        data: { symbol: alert.symbol },
      },
      trigger: null,
    });
  } catch {
    showInAppPriceAlert(alert, stock);
  }
}
