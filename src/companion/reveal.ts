/**
 * Reveal a reply in chunks so it feels like someone typing,
 * without relying on flaky RN SSE streams.
 * Chunks are coarse on purpose — fine-grained updates thrash FlatList.
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

  const minChunk = opts?.minChunk ?? 10;
  const maxChunk = opts?.maxChunk ?? 22;
  const delayMs = opts?.delayMs ?? 42;

  let i = 0;
  while (i < text.length) {
    const chunk = Math.min(
      text.length - i,
      minChunk + Math.floor(Math.random() * (maxChunk - minChunk + 1)),
    );
    let end = i + chunk;
    if (end < text.length) {
      const slice = text.slice(i, Math.min(text.length, i + maxChunk + 12));
      const space = slice.search(/[\s,.!?;:]/);
      if (space > 0 && space <= maxChunk + 8) {
        end = i + space + 1;
      }
    }
    i = end;
    onUpdate(text.slice(0, i));
    await sleep(delayMs + Math.floor(Math.random() * 18));
  }
  onUpdate(text);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Short “saw your message” pause before typing indicator. */
export function thinkingPauseMs(): number {
  return 280 + Math.floor(Math.random() * 320);
}
