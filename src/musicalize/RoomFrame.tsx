import React, { useEffect } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { installFocusRing } from './a11y';
import { COLUMN_WIDTH, DOCK_HEIGHT, palette } from './palette';

type Props = {
  wide: boolean;
  chooser: React.ReactNode;
  stage: React.ReactNode;
  controls: React.ReactNode;
  topBar?: React.ReactNode;
};

/** Two columns from 960px. Below that: stage, dock, then the chooser rail. */
export function RoomFrame({ wide, chooser, stage, controls, topBar }: Props) {
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();

  useEffect(() => {
    installFocusRing();
  }, []);

  if (wide) {
    return (
      <View
        style={[
          styles.root,
          { paddingTop: insets.top, paddingBottom: insets.bottom },
        ]}
      >
        {topBar}
        <View style={styles.wide}>
          <View style={styles.left}>{chooser}</View>
          <View style={styles.right}>
            <View style={styles.stage}>{stage}</View>
            <View style={styles.dock}>{controls}</View>
          </View>
        </View>
      </View>
    );
  }

  const stageHeight = Math.max(260, Math.min(460, height * 0.44));

  return (
    <View
      style={[styles.root, { paddingTop: insets.top, paddingBottom: insets.bottom }]}
    >
      {topBar}
      <View style={{ height: stageHeight }}>{stage}</View>
      <View style={[styles.dock, styles.dockNarrow]}>{controls}</View>
      <View style={styles.narrowChooser}>{chooser}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: palette.background,
  },
  wide: {
    flex: 1,
    flexDirection: 'row',
    minHeight: 0,
  },
  left: {
    width: COLUMN_WIDTH,
    backgroundColor: palette.panel,
    borderRightWidth: 1,
    borderRightColor: palette.hairline,
  },
  right: {
    flex: 1,
    minHeight: 0,
    backgroundColor: palette.background,
  },
  stage: {
    flex: 1,
    minHeight: 0,
    paddingTop: 8,
    overflow: 'hidden',
  },
  dock: {
    height: DOCK_HEIGHT,
    backgroundColor: palette.panel,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  dockNarrow: {
    height: 'auto',
  },
  narrowChooser: {
    flex: 1,
    minHeight: 0,
    backgroundColor: palette.panel,
  },
});
