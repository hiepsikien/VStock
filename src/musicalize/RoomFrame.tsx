import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { COLUMN_WIDTH, palette } from './palette';

type Props = {
  wide: boolean;
  chooser: React.ReactNode;
  stage: React.ReactNode;
  controls: React.ReactNode;
};

/** Two columns from 960px. Below that: chooser, stage, controls. */
export function RoomFrame({ wide, chooser, stage, controls }: Props) {
  const insets = useSafeAreaInsets();
  if (wide) {
    return (
      <View style={[styles.wide, { paddingTop: insets.top, paddingBottom: insets.bottom }]}>
        <View style={styles.left}>{chooser}</View>
        <View style={styles.right}>
          <View style={styles.stage}>{stage}</View>
          <ScrollView style={styles.controls} contentContainerStyle={styles.controlsContent}>
            {controls}
          </ScrollView>
        </View>
      </View>
    );
  }
  return (
    <ScrollView
      style={styles.narrow}
      contentContainerStyle={{ paddingTop: insets.top, paddingBottom: insets.bottom + 24 }}
    >
      <View style={styles.narrowChooser}>{chooser}</View>
      <View style={styles.narrowStage}>{stage}</View>
      {controls}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wide: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: palette.background,
  },
  left: {
    width: COLUMN_WIDTH,
    backgroundColor: palette.surface,
  },
  right: {
    flex: 1,
    backgroundColor: palette.background,
  },
  stage: {
    flex: 1,
    minHeight: 280,
    paddingTop: 8,
  },
  controls: {
    maxHeight: '46%',
  },
  controlsContent: {
    flexGrow: 1,
  },
  narrow: {
    flex: 1,
    backgroundColor: palette.background,
  },
  narrowChooser: {
    height: 460,
    backgroundColor: palette.surface,
  },
  narrowStage: {
    height: 280,
  },
});
