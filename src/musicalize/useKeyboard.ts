import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';

type Handlers = {
  onToggle?: () => void;
  onReplay?: () => void;
  onSeekBy?: (deltaSec: number) => void;
  onChapter?: (delta: number) => void;
  onGenre?: (index: number) => void;
  onFocusSearch?: () => void;
  onEscape?: () => void;
  onCommandPalette?: () => void;
  onMute?: () => void;
};

type KeyEvent = {
  key: string;
  shiftKey?: boolean;
  metaKey?: boolean;
  ctrlKey?: boolean;
  altKey?: boolean;
  target?: ElementLike | null;
  preventDefault?: () => void;
};

type ElementLike = {
  tagName?: string;
  isContentEditable?: boolean;
  closest?: (selector: string) => unknown;
};

type Doc = {
  addEventListener?: (name: string, fn: (event: KeyEvent) => void, capture?: boolean) => void;
  removeEventListener?: (name: string, fn: (event: KeyEvent) => void, capture?: boolean) => void;
};

const TEXT_ENTRY = 'input, textarea, select, [contenteditable="true"]';

function inTextEntry(target: ElementLike | null | undefined): boolean {
  if (!target) return false;
  const tag = target.tagName?.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (target.isContentEditable) return true;
  return Boolean(target.closest?.(TEXT_ENTRY));
}

/**
 * Web keyboard map for the listening surface.
 *
 * Space always means transport, even when a chip or a button has focus: the
 * event is prevented so the focused control does not fire a second time. Enter
 * still activates a focused control the normal way. `⌘K`/`Ctrl+K` opens the
 * palette even from the filter box; `M` is ordinary text there.
 */
export function useKeyboard(handlers: Handlers, enabled = true) {
  const latest = useRef(handlers);
  latest.current = handlers;

  useEffect(() => {
    if (!enabled || Platform.OS !== 'web') return;
    const doc = (globalThis as { document?: Doc }).document;
    if (!doc?.addEventListener) return;

    const onKeyDown = (event: KeyEvent) => {
      const current = latest.current;

      // ⌘K / Ctrl+K works even while the filter box has focus.
      if (
        (event.metaKey || event.ctrlKey) &&
        !event.altKey &&
        (event.key === 'k' || event.key === 'K')
      ) {
        if (current.onCommandPalette) {
          current.onCommandPalette();
          event.preventDefault?.();
        }
        return;
      }

      if (event.metaKey || event.ctrlKey || event.altKey) return;

      // Escape must reach the handler even from the filter box: blurring that
      // box is exactly what the key is for.
      if (event.key === 'Escape') {
        if (current.onEscape) {
          current.onEscape();
          event.preventDefault?.();
        }
        return;
      }

      if (inTextEntry(event.target)) return;

      const key = event.key;
      const shift = Boolean(event.shiftKey);
      let handled = true;

      switch (key) {
        case ' ':
        case 'Spacebar':
        case 'k':
        case 'K':
          current.onToggle?.();
          break;
        case 'ArrowLeft':
        case 'j':
        case 'J':
          if (shift) current.onChapter?.(-1);
          else current.onSeekBy?.(-5);
          break;
        case 'ArrowRight':
        case 'l':
        case 'L':
          if (shift) current.onChapter?.(1);
          else current.onSeekBy?.(5);
          break;
        case 'r':
        case 'R':
          current.onReplay?.();
          break;
        case '1':
        case '2':
        case '3':
        case '4':
        case '5': {
          const index = Number(key) - 1;
          if (current.onGenre) current.onGenre(index);
          else handled = false;
          break;
        }
        case '/':
          if (current.onFocusSearch) current.onFocusSearch();
          else handled = false;
          break;
        case 'm':
        case 'M':
          if (current.onMute) current.onMute();
          else handled = false;
          break;
        default:
          handled = false;
      }

      if (handled) event.preventDefault?.();
    };

    // Capture: a focused text input can stop the bubble, and Escape must still
    // reach the page. Space and the other transport keys are filtered below.
    doc.addEventListener('keydown', onKeyDown, true);
    return () => doc.removeEventListener?.('keydown', onKeyDown, true);
  }, [enabled]);
}
