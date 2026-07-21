/**
 * Reveal a reply in chunks so it feels like someone typing —
 * slower, word-ish bursts with natural pauses (not a fast machine dump).
 */
export async function revealText(
  full: string,
  onUpdate: (partial: string) => void,
  opts?: { minChunk?: number; maxChunk?: number; delayMs?: number },
): Promise<void> {
  const text = full.trim();
  if (!text) {
    onUpdate('');
    return;
  }

  const minChunk = opts?.minChunk ?? 3;
  const maxChunk = opts?.maxChunk ?? 9;
  const delayMs = opts?.delayMs ?? 68;

  let i = 0;
  while (i < text.length) {
    const chunk = Math.min(
      text.length - i,
      minChunk + Math.floor(Math.random() * (maxChunk - minChunk + 1)),
    );
    let end = i + chunk;
    if (end < text.length) {
      const slice = text.slice(i, Math.min(text.length, i + maxChunk + 10));
      const space = slice.search(/[\s,.!?;:]/);
      if (space > 0 && space <= maxChunk + 6) {
        end = i + space + 1;
      }
    }
    i = end;
    onUpdate(text.slice(0, i));

    const justTyped = text[i - 1] ?? '';
    let pause = delayMs + Math.floor(Math.random() * 36);
    // Human-like hesitations after punctuation / line breaks.
    if (/[.!?…]/.test(justTyped)) {
      pause += 220 + Math.floor(Math.random() * 280);
    } else if (/[,;:]/.test(justTyped)) {
      pause += 90 + Math.floor(Math.random() * 120);
    } else if (justTyped === '\n') {
      pause += 160 + Math.floor(Math.random() * 180);
    } else if (Math.random() < 0.12) {
      // Occasional micro-stall mid-thought.
      pause += 80 + Math.floor(Math.random() * 140);
    }
    await sleep(pause);
  }
  onUpdate(text);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Pause after the user sends — “reading” before fetching/typing. */
export function thinkingPauseMs(): number {
  return 520 + Math.floor(Math.random() * 480);
}

/** Gap before the next bubble in a multi-bubble reply. */
export function betweenBubblesPauseMs(): number {
  return 720 + Math.floor(Math.random() * 520);
}
