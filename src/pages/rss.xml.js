import rss from '@astrojs/rss';
import { SITE_TITLE, SITE_DESCRIPTION } from '../consts';
import { getPosts, url } from '../utils';

export async function GET(context) {
  const posts = await getPosts();
  return rss({
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    site: context.site,
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.published,
      categories: [post.data.category, ...(post.data.tags ?? [])].filter(Boolean),
      link: url(`posts/${post.id}/`),
    })),
  });
}
