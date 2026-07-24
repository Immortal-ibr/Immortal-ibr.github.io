export const SITE_TITLE = 'Tarek Ibrahim Salama';
export const SITE_DESCRIPTION =
  'Security research, DFIR & malware analysis, and CTF writeups.';
export const AUTHOR = 'Tarek Ibrahim Salama';
// Shown top-left on every page. The handle, not the full name — SITE_TITLE
// still carries the real name for <title>, OG tags and the footer.
export const WORDMARK = 'Immortal-ibr';

// Hero copy — plain and factual. Your own framing from GitHub, not a slogan.
export const HERO_HEADLINE = 'Tarek Ibrahim Salama';
export const HERO_HEADLINE_MUTED = '';
export const HERO_SUB = 'Cybersecurity researcher working in DFIR';
// A quiet signature line under the hero.
export const HERO_QUOTE = 'Why so serious?';

export const NAV_LINKS = [
  { href: '', label: 'Home' },
  { href: 'blog/', label: 'Blog' },
  { href: 'research/', label: 'Research' },
  { href: 'tools/', label: 'Tools' },
  { href: 'about/', label: 'About' },
];

// Categories promoted out of the blog into their own top-level nav section.
// Their posts are kept out of the Blog index and out of its filter row, so a
// post is only ever listed in one place. Keep these in sync with NAV_LINKS —
// the names must match the `category` frontmatter exactly.
export const SECTION_CATEGORIES = ['Research', 'Tools'];

export const SOCIAL_LINKS = [
  { label: 'GitHub', href: 'https://github.com/Immortal-ibr' },
  { label: 'LinkedIn', href: 'https://www.linkedin.com/in/tarek-ibrahim' },
  { label: 'Medium', href: 'https://medium.com/@tarek.ibr007' },
  { label: 'Discord', href: 'https://discord.com/users/541465360080044032' },
  { label: 'Email', href: 'mailto:tarek.ibr007@gmail.com' },
];

// Order controls how categories appear in the filter row.
export const CATEGORY_ORDER = [
  'Research',
  'Writeups',
  'CTF Author',
  'Tools',
  'Journal',
];
