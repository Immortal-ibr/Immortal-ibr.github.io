import { glob } from 'astro/loaders';
import { defineCollection, z } from 'astro:content';

// Posts keep the exact frontmatter you were already writing, so nothing in
// src/content/posts/ had to change during the redesign.
const posts = defineCollection({
  loader: glob({ base: './src/content/posts', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    published: z.coerce.date(),
    updated: z.coerce.date().optional(),
    description: z.string().optional().default(''),
    image: z.string().optional().default(''),
    tags: z.array(z.string()).optional().default([]),
    category: z.string().optional().default('Journal'),
    draft: z.boolean().optional().default(false),
    // Float a post to the featured (big) slot on the blog index. If nothing is
    // pinned, the newest post takes that slot instead.
    pinned: z.boolean().optional().default(false),

    // People who worked on this with you — co-authors, collaborators. Optional,
    // add per post. Each is a name and (optionally) a link to their profile.
    contributors: z
      .array(z.object({ name: z.string(), url: z.string().optional().default('') }))
      .optional()
      .default([]),

    // call-to-action links — a post can be mostly a pointer elsewhere
    challengeUrl: z.string().optional().default(''),
    repoUrl: z.string().optional().default(''),
    externalUrl: z.string().optional().default(''),
    externalLabel: z.string().optional().default('Read the full post'),
    event: z.string().optional().default(''),
    difficulty: z.string().optional().default(''),
  }),
});

// Standalone page content (currently just the About text).
const spec = defineCollection({
  loader: glob({ base: './src/content/spec', pattern: '**/*.md' }),
  schema: z.object({}).passthrough(),
});

export const collections = { posts, spec };
