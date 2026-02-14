Create a draft PR for the current branch with proper format.

## Prerequisites
- You must be on a feature/fix branch (not `main`)
- Changes must be committed
- `scripts/run-checks.sh` must pass

## Steps

1. **Verify branch name** matches convention:
   ```bash
   scripts/lint-conventions.sh
   ```
   If it fails, fix the issue before continuing.

2. **Run quality checks**:
   ```bash
   scripts/run-checks.sh
   ```
   If any check fails, fix the issues first. Do NOT skip checks.

3. **Extract issue number** from branch name (e.g., `feat/issue-42-add-filter` → `42`).

4. **Read the issue** to understand acceptance criteria:
   ```bash
   gh issue view <NUMBER>
   ```

5. **Push the branch**:
   ```bash
   git push -u origin HEAD
   ```

6. **Create draft PR** with this format:
   ```bash
   gh pr create --draft --title "<concise title>" --body "$(cat <<'EOF'
   ## Summary

   <1-3 bullet points describing what changed and why>

   ## Changes

   <list of files changed with brief explanation>

   ## Testing

   - [ ] `scripts/run-checks.sh` passes
   - [ ] <specific test steps for this change>

   Closes #<NUMBER>
   EOF
   )"
   ```

7. **Comment on the issue** with a link to the PR:
   ```bash
   gh issue comment <NUMBER> --body "Draft PR opened: <PR_URL>"
   ```

## Rules
- PR title should be concise (under 70 chars)
- PR body MUST include `Closes #N` to link the issue
- Always create as **draft** — human reviews and merges
- Never force-push
