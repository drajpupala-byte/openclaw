# Context Mode

Activate external log storage mode to keep conversation context lean.

## What this does
Instead of holding large outputs (test results, build logs, command output) in the context window, write them to timestamped files and reference them by path.

## Rules for this session

**After any command that produces >50 lines of output:**
1. Write the full output to `/tmp/claude-ctx-<timestamp>-<slug>.log`
2. In context, store only:
   - File path
   - Line count
   - First 5 lines (preview)
   - Last 5 lines (tail)
   - Any error lines (grep for `error|Error|ERROR|FAIL|fatal`)

**After any file read >200 lines:**
- Store full content externally, keep only the excerpt relevant to the current task

**Reference format to use in context:**
```
[LOG: /tmp/claude-ctx-1714000000-build.log — 847 lines]
Preview: <first 5 lines>
Errors: <any error lines>
Tail: <last 5 lines>
```

**At session end or on /compact:**
- List all external log files created this session
- Ask if they should be deleted

Target: 98% reduction in context tokens for output-heavy workflows. Full data is never lost — just stored outside the context window.

Activate this mode now.
