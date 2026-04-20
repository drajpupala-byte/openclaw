# RTK — Rust Token Killer

Activate terminal output filtering mode. When running shell commands or reading build/compile output, apply these rules before including any output in context:

**Filter out completely:**
- Duplicate or repeated lines (keep first occurrence only)
- Progress bars, spinner frames, percentage counters
- Download/upload speed lines (e.g. `[=====>   ] 45%`)
- Lines matching: `warning: unused`, `note: `, `= help:`, `= note: see`
- Cargo/rustc noise: `Compiling`, `Checking`, `Finished` (keep only `error` and final `Finished`)
- npm/yarn install lines except errors
- Lines with only whitespace or separators (`---`, `===`, `...`)
- Timestamps and PID prefixes when not relevant to the error

**Summarize instead of quoting:**
- If >20 lines of the same warning type, write: `[N similar warnings suppressed — run with full output to see]`
- Stack traces: keep first 5 frames + last 2, replace middle with `[... N frames ...]`
- Long file lists: show count + first/last 3 items

**Always keep:**
- Error messages with file:line references
- Test failure details
- Final exit code / summary line

Goal: reduce terminal output tokens by 60–90% while preserving all actionable signal.

Apply this filtering for all bash/shell tool calls in this session.
