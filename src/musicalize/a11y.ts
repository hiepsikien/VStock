import { Platform } from 'react-native';

let installed = false;

/**
 * Web focus ring for the listening surface: 2px `hairlineStrong`, offset 2,
 * always on `:focus-visible` so a mouse press stays quiet. React Native Web
 * renders `Pressable` as a focusable div, so one stylesheet is enough and no
 * component needs to track focus itself.
 */
export function installFocusRing(): void {
  if (installed || Platform.OS !== 'web') return;
  installed = true;
  const doc = (globalThis as { document?: Document }).document;
  if (!doc?.head) return;
  const sheet = doc.createElement('style');
  sheet.setAttribute('data-musicalize', 'focus-ring');
  sheet.textContent = `
    :focus-visible {
      outline: 2px solid rgba(244, 241, 234, 0.16);
      outline-offset: 2px;
    }
    input:focus-visible {
      outline-offset: 1px;
    }
    [role='slider']:focus-visible,
    [role='adjustable']:focus-visible {
      outline-offset: 4px;
    }
  `;
  doc.head.appendChild(sheet);
}
