import React from 'react';
import { Image, StyleSheet, View } from 'react-native';
import type { CompanionCharacter } from '../companion/characters';

type Props = {
  character: CompanionCharacter;
  size?: number;
};

export function CompanionAvatar({ character, size = 36 }: Props) {
  const ring = Math.max(2, Math.round(size * 0.06));
  return (
    <View
      style={[
        styles.ring,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          borderWidth: ring,
          borderColor: character.accent,
        },
      ]}
    >
      <Image
        source={character.avatar}
        style={{
          width: size - ring * 2,
          height: size - ring * 2,
          borderRadius: (size - ring * 2) / 2,
        }}
        accessibilityLabel={`Avatar ${character.name}`}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  ring: {
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
  },
});
