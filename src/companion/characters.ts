import type { ImageSourcePropType } from 'react-native';

export type CompanionCharacterId = 'vy';

export type CompanionProfile = {
  gender: string;
  age: number;
  birthplace: string;
  occupation: string;
  /** First-person intro — sounds like the character talking */
  bio: string;
};

export type CompanionCharacter = {
  id: CompanionCharacterId;
  /** Display name in chat header / bubbles */
  name: string;
  /** Short role line under the name */
  tagline: string;
  /** Opening bubble when chat opens (first time) */
  greeting: string;
  /** Soft line when returning after a long gap */
  welcomeBack: string;
  /** Composer placeholder */
  placeholder: string;
  /** Accent used on avatar ring / FAB */
  accent: string;
  avatar: ImageSourcePropType;
  profile: CompanionProfile;
};

// Top-level require so Metro registers the asset reliably.
const VY_AVATAR = require('../../assets/companions/vy.png');

/** First Companion character. Add more entries here later. */
export const COMPANION_CHARACTERS: Record<CompanionCharacterId, CompanionCharacter> = {
  vy: {
    id: 'vy',
    name: 'Vy',
    tagline: 'Bạn đồng hành trên sàn',
    greeting:
      'Chào bạn, mình là Vy đây — ngồi cạnh nhìn bảng thôi, không phải cố vấn gì đâu. Có gì đang làm bạn băn khoăn không?',
    welcomeBack: 'Lại gặp nhau rồi nhỉ. Dạo này bảng thế nào?',
    placeholder: 'Nhắn với Vy…',
    accent: '#2DD4BF',
    avatar: VY_AVATAR,
    profile: {
      gender: 'Nữ',
      age: 26,
      birthplace: 'Hà Nội',
      occupation: 'Nhân vật ảo trên VStock',
      bio:
        'Mình sinh ra ở Hà Nội, lớn lên với thói quen chiều nào cũng liếc bảng trước khi tan tầm. Trên VStock mình là nhân vật ảo — không phải môi giới hay cố vấn thật — chỉ ngồi cạnh bạn đọc tin, giải thích số liệu và giữ nhịp khi thị trường nhảy. Quyết định mua bán vẫn là của bạn.',
    },
  },
};

export const DEFAULT_COMPANION_ID: CompanionCharacterId = 'vy';

export function getCompanionCharacter(
  id: CompanionCharacterId = DEFAULT_COMPANION_ID,
): CompanionCharacter {
  return COMPANION_CHARACTERS[id] ?? COMPANION_CHARACTERS.vy;
}
