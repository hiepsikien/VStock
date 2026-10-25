import React from 'react';
import { StyleSheet, Switch, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { colors, spacing } from '../theme';

type Props = {
  humanize: boolean;
  colorOn: boolean;
  onHumanize: (value: boolean) => void;
  onColor: (value: boolean) => void;
};

function LayerSwitch({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.item}>
      <Text style={styles.label}>{label}</Text>
      <Switch
        value={value}
        onValueChange={(next) => {
          void Haptics.selectionAsync();
          onChange(next);
        }}
        trackColor={{ false: 'rgba(255,255,255,0.22)', true: colors.accent }}
        thumbColor={colors.text}
        ios_backgroundColor="rgba(255,255,255,0.22)"
        accessibilityLabel={label}
      />
    </View>
  );
}

export function MixToggles({ humanize, colorOn, onHumanize, onColor }: Props) {
  return (
    <View style={styles.row}>
      <LayerSwitch label="Humanize" value={humanize} onChange={onHumanize} />
      <LayerSwitch label="Màu" value={colorOn} onChange={onColor} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  item: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingLeft: 10,
    paddingRight: 6,
    paddingVertical: 2,
    borderRadius: 9,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
});
