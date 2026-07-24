# Tarek Ibrahim Salama

Personal site and blog: security research, DFIR & malware analysis, and CTF
writeups. Built with [Astro](https://astro.build), searched with
[Pagefind](https://pagefind.app), deployed to GitHub Pages.

Live at <https://immortal-ibr.github.io/>

## Running it locally

```bash
npm install
npm run dev
```

The dev server comes up on <http://localhost:4321>.

| Script            | What it does                                              |
| ----------------- | --------------------------------------------------------- |
| `npm run dev`     | Dev server with hot reload                                 |
| `npm run build`   | Production build to `dist/`, then builds the search index  |
| `npm run preview` | Serve the built `dist/` locally                            |

Note: `npm run build` is `astro build && pagefind --site dist`. Running plain
`astro build` skips the search index, and search silently returns nothing.

## Layout

```
public/            static assets served as-is (covers, favicons, hero video)
src/
  assets/images/   images processed by Astro's image pipeline
  components/      Hero, PostList, Filters, SocialIcon
  content/
    posts/         blog posts (markdown)
    spec/          standalone page copy (About)
  layouts/Base.astro
  pages/           routes — index, posts, tags, categories, about, 404, RSS
  styles/global.css
  consts.ts        site title, nav links, social links, category order
  content.config.ts  frontmatter schema for posts
```

## Writing a post

Add a markdown file to `src/content/posts/`. The frontmatter schema lives in
[`src/content.config.ts`](src/content.config.ts) — `title` and `published` are
required, everything else is optional:

```yaml
---
title: 'Post title'
published: 2026-01-15
description: 'One-line summary used for cards, OG tags and RSS.'
image: '/covers/my-cover.webp'
category: 'Writeups' # Research | Writeups | CTF Author | Tools | Journal
tags: ['dfir', 'forensics']
draft: false
pinned: false # float to the featured slot on the blog index
---
```

Optional extras: `updated`, `contributors`, and the call-to-action fields
`repoUrl`, `challengeUrl`, `externalUrl` / `externalLabel`, `event`,
`difficulty`.

Site-wide settings — title, hero copy, nav, social links, category order —
are all in [`src/consts.ts`](src/consts.ts).

## Deploying

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) builds and
deploys to GitHub Pages on every push to `main`, and can be triggered manually
from the Actions tab. It needs Pages set to the **GitHub Actions** source in
the repository settings.

If you fork this, change `site` in
[`astro.config.mjs`](astro.config.mjs) to your own URL.

## License

[MIT](LICENSE). The project started from the
[Fuwari](https://github.com/saicaca/fuwari) Astro template; its copyright
notice is retained in the license file. Blog post content and images are not
covered by the MIT license.
