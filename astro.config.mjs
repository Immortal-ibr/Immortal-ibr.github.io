// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// GitHub Pages user site: repo `Immortal-ibr.github.io`, so base stays "/".
export default defineConfig({
  site: 'https://immortal-ibr.github.io/',
  base: '/',
  trailingSlash: 'always',
  // The listing pages moved: /posts/ -> /blog/, and Research and Tools were
  // promoted out of /category/ to top-level paths. These URLs were already
  // published, so they redirect rather than 404. Individual posts did NOT move
  // — they stay at /posts/<slug>/ so every post keeps one canonical URL.
  // A static build emits a small meta-refresh page for each of these.
  redirects: {
    '/posts/': '/blog/',
    '/category/research/': '/research/',
    '/category/tools/': '/tools/',
  },
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
  },
});
