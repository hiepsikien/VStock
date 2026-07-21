export type NewsFilter =
  | 'all'
  | 'stock_news'
  | 'macro_news'
  | 'company_news'
  | 'commodity_news'
  | 'real_estate_news'
  | 'disclosure';

export function filterNewsItems(items: NewsItem[], filter: NewsFilter): NewsItem[] {
  if (filter === 'all') return items;
  return items.filter((item) => item.category === filter);
}

export type NewsItem = {
  id: string;
  title: string;
  summary: string;
  source: string;
  publishedAt: string;
  url: string;
  imageUrl?: string | null;
  symbols: string[];
  category: string;
};

export function formatNewsTime(iso: string): string {
  if (!iso || iso.length < 10) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) {
      const [datePart, timePart] = iso.split('T');
      return `${datePart}${timePart ? ` · ${timePart.slice(0, 5)}` : ''}`;
    }
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffH = Math.floor(diffMs / 3_600_000);
    if (diffH < 1) return 'Vừa xong';
    if (diffH < 24) return `${diffH} giờ trước`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 7) return `${diffD} ngày trước`;
    return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return iso.slice(0, 10);
  }
}

export function categoryLabel(category: string): string {
  switch (category) {
    case 'stock_news':
      return 'Chứng khoán';
    case 'macro_news':
      return 'Kinh tế';
    case 'company_news':
      return 'Doanh nghiệp';
    case 'commodity_news':
      return 'Vàng & hàng hóa';
    case 'real_estate_news':
      return 'Bất động sản';
    case 'disclosure':
      return 'Công bố';
    default:
      return 'Tin tức';
  }
}
