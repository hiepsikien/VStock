import React, { useEffect, useState } from 'react';
import { Platform, useWindowDimensions, View } from 'react-native';
import { LiveRoom } from './LiveRoom';
import { palette, WIDE_BREAKPOINT } from './palette';
import { ReplayRoom } from './ReplayRoom';

type Mode = 'replay' | 'live';

export function MusicalizeApp() {
  const { width } = useWindowDimensions();
  const wide = width >= WIDE_BREAKPOINT;
  const [mode, setMode] = useState<Mode>('replay');

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const body = (globalThis as { document?: { body?: { style: { backgroundColor: string; margin: string } } } })
      .document?.body;
    if (!body) return;
    const previous = body.style.backgroundColor;
    body.style.backgroundColor = palette.background;
    body.style.margin = '0';
    return () => {
      body.style.backgroundColor = previous;
    };
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: palette.background }}>
      {mode === 'live' ? (
        <LiveRoom wide={wide} onMode={setMode} />
      ) : (
        <ReplayRoom wide={wide} onMode={setMode} />
      )}
    </View>
  );
}
