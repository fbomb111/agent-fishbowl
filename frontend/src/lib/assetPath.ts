/** Prepend the Next.js basePath to a public asset path. */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

export function assetPath(path: string): string {
  return `${basePath}${path}`;
}
