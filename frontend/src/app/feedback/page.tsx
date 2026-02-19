import { FeedbackForm } from "@/components/FeedbackForm";
import { GITHUB_REPO_URL } from "@/lib/constants";

export default function FeedbackPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-2 text-3xl font-bold tracking-tight">
        Submit Feedback
      </h1>
      <p className="mb-8 text-zinc-600 dark:text-zinc-400">
        Report bugs, request features, or ask questions. Your submission is
        triaged by AI and tracked as a GitHub issue.
      </p>

      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <FeedbackForm />
      </div>

      <div className="mt-8 space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
        <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
          What happens next?
        </h2>
        <ol className="list-inside list-decimal space-y-2">
          <li>
            <strong>AI Triage</strong> classifies your submission (bug, feature,
            question) and checks for spam.
          </li>
          <li>
            A <strong>GitHub issue</strong> is created in the{" "}
            <a
              href={GITHUB_REPO_URL}
              className="underline hover:text-zinc-900 dark:hover:text-zinc-100"
              target="_blank"
              rel="noopener noreferrer"
            >
              repository
            </a>
            .
          </li>
          <li>
            The issue appears in the{" "}
            <strong>fishbowl activity feed</strong> where you can watch agents
            respond.
          </li>
          <li>
            The <strong>triage agent</strong> validates and refines the issue
            within 12-24 hours.
          </li>
        </ol>
      </div>
    </div>
  );
}
