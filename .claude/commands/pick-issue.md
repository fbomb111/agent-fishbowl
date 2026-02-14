Find and claim the highest-priority unassigned issue.

## Steps

1. **List open issues** sorted by priority:
   ```bash
   gh issue list --state open --json number,title,labels,assignees --limit 20
   ```

2. **Filter for unassigned issues** — skip any issue that has an assignee.

3. **Prioritize** using labels:
   - `priority/high` first, then `priority/medium`, then unlabeled
   - Within the same priority, prefer issues labeled `type/bug` over `type/feature` over `type/chore`

4. **Check for blocked issues** — skip issues labeled `status/blocked`.

5. **Pick the top issue** and assign yourself:
   ```bash
   gh issue edit <NUMBER> --add-assignee @me --add-label status/in-progress
   ```

6. **Create a branch** for the issue:
   ```bash
   scripts/create-branch.sh <NUMBER> feat
   ```
   Use `fix` instead of `feat` if the issue is labeled `type/bug`.

7. **Comment on the issue** that you're starting work:
   ```bash
   gh issue comment <NUMBER> --body "Picking this up. Branch: `<branch_name>`"
   ```

8. **Report** what you picked and the branch name.

## Rules
- NEVER pick an issue that already has an assignee
- NEVER pick an issue labeled `status/blocked`
- If no issues are available, report "No unassigned issues found" and stop
