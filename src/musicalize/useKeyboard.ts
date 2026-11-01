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
// A focused control owns Space/Enter. Without this the page would also run
// the transport and the chip would fire twice.
const INTERACTIVE =
  'button, a[href], [role="button"], [role="slider"], [role="tab"], [role="link"], [role="menuitem"]';

function inTextEntry(target: ElementLike | null | undefined): boolean {
  if (!target) return false;
  const tag = target.tagName?.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (target.isContentEditable) return true;
  return Boolean(target.closest?.(TEXT_ENTRY));
}

function inInteractive(target: ElementLike | null | undefined): boolean {
  if (!target) return false;
  const tag = target.tagName?.toLowerCase();
  if (tag === 'button') return true;
  return Boolean(target.closest?.(INTERACTIVE));
}

/**
 * Web keyboard map for the listening surface.
 *
 * Normal keys are ignored while a text field or a control has focus: Space on
 * a focused chip activates that chip the normal way and never toggles the
 * transport a second time. `⌘K`/`Ctrl+K` and `Escape` still work everywhere,
 * because they open/close a layer rather than operate the transport. The room
 * keyboard is disabled entirely while a palette or popover owns the layer.
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

      if (inTextEntry(event.target) || inInteractive(event.target)) return;

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

    // Capture: a focused text input or control can stop the bubble, and Escape
    // must still reach the page. Normal keys are filtered by target above.
    doc.addEventListener('keydown', onKeyDown, true);
    return () => doc.removeEventListener?.('keydown', onKeyDown, true);
  }, [enabled]);
}
