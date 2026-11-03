import AsyncStorage from '@react-native-async-storage/async-storage';
import { parseProfileStore, serializeProfileStore, type ProfileStore } from './params';

const KEY = 'vstock.musicalize.profiles.v1';

export async function loadProfileStore(): Promise<ProfileStore | null> {
  try {
    return parseProfileStore(await AsyncStorage.getItem(KEY));
  } catch {
    return null;
  }
}

export async function saveProfileStore(store: ProfileStore): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, serializeProfileStore(store));
  } catch {
    // A full or unavailable store must not break the listening room.
  }
}
