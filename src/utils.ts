import { getCollection, type CollectionEntry } from 'astro:content';
import { SECTION_CATEGORIES } from './consts';

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

/** Remove fenced code while leaving inline code in the surrounding prose. */
function stripFencedCode(markdown: string): string {
  const prose: string[] = [];
  let fenceCharacter: string | null = null;
  let fenceLength = 0;

  for (const line of markdown.split(/\r?\n/)) {
    if (fenceCharacter === null) {
      const opening = line.match(/^ {0,3}(`{3,}|~{3,})/);
      const marker = opening?.[1];

      if (marker) {
        fenceCharacter = marker.charAt(0);
        fenceLength = marker.length;
      } else {
        prose.push(line);
      }

      continue;
    }

    const closing = line.match(/^ {0,3}(`{3,}|~{3,})[ \t]*$/);
    const marker = closing?.[1];

    if (
      marker &&
      marker.charAt(0) === fenceCharacter &&
      marker.length >= fenceLength
    ) {
      fenceCharacter = null;
      fenceLength = 0;
    }
  }

  return prose.join('\n');
}

/** Rough prose reading time from markdown, 200 wpm. */
export function readingTime(body = ''): number {
  const words = stripFencedCode(body).trim().split(/\s+/).filter(Boolean).length;
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

/** True when a category has its own nav section rather than living in Blog. */
export function isSectionCategory(name = ''): boolean {
  return SECTION_CATEGORIES.includes(name.trim());
}

/**
 * What the Blog index and its filter row list: everything that hasn't been
 * promoted to its own nav section. Research and Tools have their own pages, so
 * repeating them here would list the same post in two places.
 */
export function blogPosts(posts: Post[]): Post[] {
  return posts.filter((p) => !isSectionCategory(p.data.category ?? ''));
}

/**
 * Where a category's listing lives. Section categories get a top-level path of
 * their own (/research/); the rest stay under /category/. Only one route is
 * ever generated per category, so there's no duplicate content.
 */
export function categoryPath(name = ''): string {
  const n = name.trim();
  return isSectionCategory(n) ? `${slugify(n)}/` : `category/${slugify(n)}/`;
}

/**
 * Which nav entry owns a post. Posts all live under /posts/<slug>/ whatever
 * their category, so the nav can't work this out from the URL — it has to come
 * from the post's own category, or every post would light up "Blog".
 */
export function navSectionFor(category = ''): string {
  return isSectionCategory(category) ? categoryPath(category) : 'blog/';
}

/**
 * Whether a listing leads with the full-width featured card.
 *
 * A real pin always earns the big slot. Failing that it comes down to parity:
 * the featured card swallows a whole row, so the cards behind it only pair up
 * cleanly when the total is odd. On an even count the big card would strand a
 * single card alone on the last row — so every card stays the same size and
 * they sit two to a level instead.
 */
export function shouldFeature(posts: Post[]): boolean {
  if (posts.some((p) => p.data.pinned)) return true;
  return posts.length % 2 === 1;
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
