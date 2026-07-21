/**
 * Client-side mirror of backend knowledge packs.
 * When adding a new Companion expert, register pack metadata here
 * and add the matching pack in backend/app/services/companion_packs.py.
 */

export type KnowledgePackId = 'vy';

export type KnowledgePack = {
  id: KnowledgePackId;
  /** Short expertise lines shown on profile */
  expertise: string[];
  /** Live data this character is trained to use */
  dataSources: Array<'quotes' | 'indices' | 'news' | 'fundamentals'>;
};

export const KNOWLEDGE_PACKS: Record<KnowledgePackId, KnowledgePack> = {
  vy: {
    id: 'vy',
    expertise: [
      'Đồng hành cảm xúc trên sàn',
      'Giá & chỉ số live VStock',
      'Tin ngắn theo mã',
      'Kỷ luật quyết định (không khuyến nghị)',
    ],
    dataSources: ['quotes', 'indices', 'news'],
  },
};

export function getKnowledgePack(id: KnowledgePackId = 'vy'): KnowledgePack {
  return KNOWLEDGE_PACKS[id] ?? KNOWLEDGE_PACKS.vy;
}
