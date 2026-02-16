"use client";

import { useState } from "react";
import { submitFeedback } from "@/lib/api";

export function FeedbackForm() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{
    message: string;
    issueUrl: string;
    issueNumber: number;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await submitFeedback({
        title,
        description,
        email: email || undefined,
        website,
      });

      setSuccess({
        message: response.message,
        issueUrl: response.issue_url,
        issueNumber: response.issue_number,
      });
      setTitle("");
      setDescription("");
      setEmail("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to submit feedback"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-6 dark:border-green-900 dark:bg-green-950">
        <h3 className="mb-2 text-lg font-semibold text-green-900 dark:text-green-100">
          Feedback Submitted
        </h3>
        <p className="mb-4 text-sm text-green-700 dark:text-green-300">
          {success.message}
        </p>
        {success.issueNumber > 0 && (
          <div className="space-y-2">
            <a
              href={success.issueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-sm font-medium text-green-700 underline hover:text-green-900 dark:text-green-300 dark:hover:text-green-100"
            >
              Track your feedback (#{success.issueNumber}) — opens in a new tab
            </a>
            <p className="text-xs text-green-600 dark:text-green-400">
              Your feedback is now being tracked publicly. It will appear in the
              fishbowl activity feed shortly.
            </p>
          </div>
        )}
        <button
          onClick={() => setSuccess(null)}
          className="mt-4 text-sm font-medium text-green-700 hover:text-green-900 dark:text-green-300 dark:hover:text-green-100"
        >
          Submit another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label
          htmlFor="title"
          className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          Title <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          minLength={5}
          maxLength={200}
          placeholder="Brief summary of your feedback"
          className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
      </div>

      <div>
        <label
          htmlFor="description"
          className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          Description <span className="text-red-500">*</span>
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
          minLength={20}
          maxLength={5000}
          rows={6}
          placeholder="Describe the bug, feature request, or question in detail"
          className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          {description.length}/5000
        </p>
      </div>

      <div>
        <label
          htmlFor="email"
          className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          Email{" "}
          <span className="font-normal text-zinc-400">(optional)</span>
        </label>
        <input
          type="email"
          id="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          maxLength={200}
          placeholder="your@email.com"
          className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
      </div>

      {/* Honeypot — hidden from real users, bots fill it */}
      <input
        type="text"
        name="website"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        tabIndex={-1}
        autoComplete="off"
        className="absolute left-[-9999px]"
        aria-hidden="true"
      />

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        {isSubmitting ? "Submitting..." : "Submit Feedback"}
      </button>

      <p className="text-center text-xs text-zinc-500 dark:text-zinc-400">
        Your submission is triaged by AI and created as a public GitHub issue.
      </p>
    </form>
  );
}
