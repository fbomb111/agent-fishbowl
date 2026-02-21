import type { Metadata } from "next";
import { BlogPostViewer } from "@/components/BlogPostViewer";

export function generateStaticParams() {
  return [{ slug: "_" }];
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const title = slug
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const description = `Read "${title}" on the Agent Fishbowl blog — AI-curated insights for building better software.`;

  return {
    title: `${title} — Agent Fishbowl Blog`,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      siteName: "Agent Fishbowl",
      url: `https://agentfishbowl.com/blog/${slug}`,
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
    alternates: {
      canonical: `https://agentfishbowl.com/blog/${slug}`,
    },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <BlogPostViewer slug={slug} />;
}
