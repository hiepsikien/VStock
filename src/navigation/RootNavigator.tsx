import React from 'react';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { MainTabParamList, RootStackParamList } from './types';
import { WatchlistScreen } from '../screens/WatchlistScreen';
import { NewsScreen } from '../screens/NewsScreen';
import { StockDetailScreen } from '../screens/StockDetailScreen';
import { colors } from '../theme';

const Tab = createBottomTabNavigator<MainTabParamList>();
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

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.separator,
          borderTopWidth: 0.5,
        },
        tabBarActiveTintColor: colors.positive,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tab.Screen
        name="Watchlist"
        component={WatchlistScreen}
        options={{ tabBarLabel: 'Theo dõi' }}
      />
      <Tab.Screen
        name="News"
        component={NewsScreen}
        options={{ tabBarLabel: 'Tin tức' }}
      />
    </Tab.Navigator>
  );
}

export function RootNavigator() {
  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="Tabs" component={MainTabs} />
        <Stack.Screen
          name="Detail"
          component={StockDetailScreen}
          options={{ animation: 'slide_from_right' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
