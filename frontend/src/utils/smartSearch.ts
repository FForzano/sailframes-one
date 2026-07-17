/** Accent/case-insensitive relevance search over a list of entities, used to
 * search clubs and groups together (see EntitySearch). Not a full-text engine —
 * just enough scoring (exact > prefix > substring > word match) to surface
 * the right result first without a backend round-trip, since both lists are
 * already fully loaded via clubsService.list()/groupsService.list(). */

// Combining diacritical marks (U+0300-U+036F), stripped after NFD
// decomposition so e.g. "è" and "e" match the same query.
const DIACRITICS = new RegExp("[̀-ͯ]", "g");

function normalize(value: string): string {
  return value.normalize("NFD").replace(DIACRITICS, "").toLowerCase().trim();
}

function fieldScore(field: string, query: string): number {
  const f = normalize(field);
  if (!f) return 0;
  if (f === query) return 100;
  if (f.startsWith(query)) return 80;
  if (f.includes(query)) return 60;
  const words = f.split(/\s+/);
  if (words.some((w) => w.startsWith(query))) return 50;
  if (words.some((w) => w.includes(query))) return 30;
  return 0;
}

/** Returns `items` whose `getFields` values match `query`, sorted by
 * relevance (best first). Empty query returns `items` unfiltered. */
export function smartSearch<T>(
  query: string,
  items: T[],
  getFields: (item: T) => (string | null | undefined)[],
): T[] {
  const q = normalize(query);
  if (!q) return items;
  return items
    .map((item) => {
      const score = Math.max(0, ...getFields(item).map((f) => (f ? fieldScore(f, q) : 0)));
      return { item, score };
    })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .map(({ item }) => item);
}
