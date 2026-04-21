# Token Optimizer — Find Hidden Token Leaks

Audit the current session's context usage and identify token waste patterns.

## Audit steps

### 1. Identify large context contributors
List the top 5 biggest token consumers in the current context window:
- Long tool outputs that could have been summarized
- Files read in full when only a section was needed
- Repeated information stated multiple times
- Long error traces that could be truncated

### 2. Check for these silent killers

**Killer A — Full file reads when grep sufficed**
Flag any Read tool calls on files >200 lines where only 1–3 sections were actually used.
Fix: use Grep + targeted Read with offset/limit.

**Killer B — Repeated system context**
Flag if the same file or config was read more than once.
Fix: read once, reference in memory.

**Killer C — Verbose error output**
Flag bash outputs >100 lines that contain <10 actionable lines.
Fix: pipe through `grep -E "error|Error|FAIL|warn" | head -20`.

**Killer D — Chatty confirmations**
Flag multi-sentence acknowledgement responses ("Sure! I'll help you with that. Let me start by...").
Fix: respond with action only.

**Killer E — Over-specified tool calls**
Flag cases where a targeted Grep would have found what a full Read did.

### 3. Output report
```
TOKEN LEAK AUDIT
================
Estimated session tokens: ~<N>
Recoverable waste: ~<N> tokens (<N>%)

Top leaks:
1. [type] — description — ~<N> tokens wasted — fix: ...
2. ...

Quick wins for next session:
- ...
```

Run this audit now on the current session context.
