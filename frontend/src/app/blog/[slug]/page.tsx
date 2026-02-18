import { BlogPostViewer } from "@/components/BlogPostViewer";

export function generateStaticParams() {
  return [];
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <BlogPostViewer slug={slug} />;
}
