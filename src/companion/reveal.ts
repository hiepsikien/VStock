/**
 * Reveal a reply in chunks so it feels like someone typing,
 * without relying on flaky RN SSE streams.
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

  const minChunk = opts?.minChunk ?? 2;
  const maxChunk = opts?.maxChunk ?? 5;
  const delayMs = opts?.delayMs ?? 18;

  let i = 0;
  while (i < text.length) {
    const chunk = Math.min(
      text.length - i,
      minChunk + Math.floor(Math.random() * (maxChunk - minChunk + 1)),
    );
    // Prefer breaking near whitespace so mid-word jumps feel less robotic.
    let end = i + chunk;
    if (end < text.length) {
      const slice = text.slice(i, Math.min(text.length, i + maxChunk + 8));
      const space = slice.search(/[\s,.!?;:]/);
      if (space > 0 && space <= maxChunk + 4) {
        end = i + space + 1;
      }
    }
    i = end;
    onUpdate(text.slice(0, i));
    await sleep(delayMs + Math.floor(Math.random() * 12));
  }
  onUpdate(text);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Short “saw your message” pause before typing indicator. */
export function thinkingPauseMs(): number {
  return 350 + Math.floor(Math.random() * 450);
}
