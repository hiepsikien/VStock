import React from 'react';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { RootStackParamList } from './types';
import { WatchlistScreen } from '../screens/WatchlistScreen';
import { NewsScreen } from '../screens/NewsScreen';
import { StockDetailScreen } from '../screens/StockDetailScreen';
import { colors } from '../theme';

const Stack = createNativeStackNavigator<RootStackParamList>();

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.background,
    text: colors.text,
    border: colors.separator,
    primary: colors.accent,
  },
};

export function RootNavigator() {
  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="Watchlist" component={WatchlistScreen} />
        <Stack.Screen
          name="News"
          component={NewsScreen}
          options={{ animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="Detail"
          component={StockDetailScreen}
          options={{ animation: 'slide_from_right' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
