# Code Review Graph

Perform a token-efficient code review by reading only the files that matter.

## Step 1 — Build the change graph
```
git diff --name-only HEAD~1 2>/dev/null || git diff --name-only origin/main...HEAD
```
List changed files. For each, note: lines added, lines deleted.

## Step 2 — Prioritize by impact
Score each file:
- +3 if it touches auth, payments, security, or data migrations
- +2 if it's a public API surface (routes, controllers, exported functions)
- +1 if it has corresponding test changes
- -1 if it's only config, docs, or lockfile changes

Read files in score order, highest first. Stop reading once you've consumed 80% of the changed lines or hit 15 files — whichever comes first.

## Step 3 — Read only diffs, not full files
For large files (>300 lines), read only the changed hunks:
```
git diff HEAD~1 -- <file>
```
Not the full file content.

## Step 4 — Review output format
Report findings in this exact structure (no other prose):

**Critical** (must fix before merge):
- `file:line` — issue

**Warnings** (should fix):
- `file:line` — issue

**Nits** (optional):
- `file:line` — issue

**Summary:** 1 sentence.

Skip sections that have no findings. Target: 49x fewer tokens than reading the entire repo.
