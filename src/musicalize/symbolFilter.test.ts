import { filterSymbols } from './symbolFilter';

function deepEqual(actual: unknown, expected: unknown, label = '') {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) throw new Error(`${label} expected ${right}, got ${left}`);
}

const symbols = [
  { symbol: 'VNINDEX', name: 'VN-Index', ranges: ['1D'], kind: 'index' as const },
  { symbol: 'VNM', name: 'Vinamilk', ranges: ['1D', '1M'], kind: 'stock' as const },
  { symbol: 'FPT', name: 'FPT', ranges: [], kind: 'stock' as const },
  { symbol: 'OLD', name: 'Old backend row' },
];

deepEqual(
  filterSymbols(symbols, '', 'VNM').map((item) => item.symbol),
  ['VNINDEX', 'VNM'],
  'default view hides symbols without candles',
);

deepEqual(
  filterSymbols(symbols, '', 'FPT').map((item) => item.symbol),
  ['VNINDEX', 'VNM', 'FPT'],
  'selected symbol stays visible even without candles',
);

deepEqual(
  filterSymbols(symbols, 'fp', 'VNM').map((item) => item.symbol),
  ['FPT'],
  'typing searches the whole market',
);

deepEqual(
  filterSymbols(symbols, '', 'VNM').map((item) => item.symbol).includes('VNINDEX'),
  true,
  'pinned indices survive the default filter',
);

const oldBackend = symbols.map(({ ranges: _ranges, ...rest }) => rest);
deepEqual(
  filterSymbols(oldBackend, '', 'VNM').map((item) => item.symbol),
  ['VNINDEX', 'VNM', 'FPT', 'OLD'],
  'old backend without ranges still shows every row',
);

console.log('musicalize symbol filter tests passed');
