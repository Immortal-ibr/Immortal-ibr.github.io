import { getCollection, type CollectionEntry } from 'astro:content';

/** Internal URL that respects the site's `base`. */
export function url(path = ''): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${base}/${path.replace(/^\//, '')}`;
}

/** "Memory Forensics" -> "memory-forensics" */
export function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** ISO date — "2026-07-20". */
export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Rough reading time from raw markdown, 200 wpm. */
export function readingTime(body = ''): number {
  const words = body.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 200));
}

export type Post = CollectionEntry<'posts'>;

/** Published posts, newest first. Drafts are hidden in production only. */
export async function getPosts(): Promise<Post[]> {
  const posts = await getCollection('posts', ({ data }) =>
    import.meta.env.PROD ? data.draft !== true : true
  );
  return posts.sort(
    (a, b) => b.data.published.valueOf() - a.data.published.valueOf()
  );
}

/**
 * Listing order: pinned posts first, then newest. The sort is stable, so date
 * order still holds inside each group. Only listings use this — getPosts stays
 * purely chronological so post pagers and the feed keep real chronology.
 */
export function pinnedFirst(posts: Post[]): Post[] {
  return [...posts].sort(
    (a, b) => Number(b.data.pinned ?? false) - Number(a.data.pinned ?? false)
  );
}

/** Category name -> count, ordered by CATEGORY_ORDER then alphabetically. */
export function countBy(posts: Post[], key: 'category'): Map<string, number> {
  const counts = new Map<string, number>();
  for (const post of posts) {
    const value = (post.data[key] ?? '').trim();
    if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return counts;
}

export function tagCounts(posts: Post[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const post of posts) {
    for (const tag of post.data.tags ?? []) {
      const t = tag.trim();
      if (t) counts.set(t, (counts.get(t) ?? 0) + 1);
    }
  }
  return counts;
}
