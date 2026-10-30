import React from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { MusicalizeApp } from './src/musicalize/MusicalizeApp';

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <MusicalizeApp />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
