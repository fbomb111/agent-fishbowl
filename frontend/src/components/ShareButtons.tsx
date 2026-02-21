"use client";

import { useState } from "react";

export function ShareButtons({ title }: { title: string }) {
  const [copied, setCopied] = useState(false);

  function getPageUrl() {
    return window.location.href;
  }

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(getPageUrl());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select from a temporary input
      const input = document.createElement("input");
      input.value = getPageUrl();
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  function handleShareTwitter() {
    const url = getPageUrl();
    const text = encodeURIComponent(title);
    window.open(
      `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${text}`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  function handleShareLinkedIn() {
    const url = getPageUrl();
    window.open(
      `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  const buttonClass =
    "inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200";

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <span className="text-xs text-zinc-400 dark:text-zinc-500">Share:</span>
      <button
        onClick={handleCopyLink}
        className={buttonClass}
        aria-label="Copy link to clipboard"
      >
        <svg
          className="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
        </svg>
        {copied ? "Copied!" : "Copy link"}
      </button>
      <button
        onClick={handleShareTwitter}
        className={buttonClass}
        aria-label="Share on X (Twitter)"
      >
        <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
        X / Twitter
      </button>
      <button
        onClick={handleShareLinkedIn}
        className={buttonClass}
        aria-label="Share on LinkedIn"
      >
        <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
        </svg>
        LinkedIn
      </button>
    </div>
  );
}
