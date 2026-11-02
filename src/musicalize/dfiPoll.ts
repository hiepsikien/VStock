export type DfiPollKeyInput = {
  symbol: string;
  span: string;
  variant: string;
  ensemble: string;
  index: number;
  ready: boolean;
  name: string;
  audible: boolean;
};

/**
 * Identity of one DFI/title refresh budget. Pausing changes `audible`, so the
 * next play starts a fresh budget instead of inheriting an exhausted one.
 */
export function dfiPollKey(input: DfiPollKeyInput): string {
  return [
    input.symbol,
    input.span,
    input.variant,
    input.ensemble,
    input.index,
    input.ready ? 'ready' : 'wait',
    input.name.trim() ? 'name' : 'noname',
    input.audible ? 'play' : 'idle',
  ].join('|');
}
