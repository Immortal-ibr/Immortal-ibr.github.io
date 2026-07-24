// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// GitHub Pages user site: repo `Immortal-ibr.github.io`, so base stays "/".
export default defineConfig({
  site: 'https://immortal-ibr.github.io/',
  base: '/',
  trailingSlash: 'always',
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
  },
});
