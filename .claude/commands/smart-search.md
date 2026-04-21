# Claude Context — Smart Repo Search

Turn this repository into a targeted search index. Read only what's relevant — 40% cheaper than naive full-file reads.

## Usage
Invoke this command with a query: `/smart-search <what you're looking for>`

## Search strategy

### Step 1 — Symbol-first lookup
Before reading any file, search for the exact symbol, function, or string:
```
Grep(pattern="<query>", output_mode="files_with_matches")
```
This gives a hit list without reading file contents.

### Step 2 — Rank files by relevance
Score each hit file:
- Exact name match in file path: +3
- Query term appears in function/class definition: +2  
- Query term in comment or string: +1
- Query term only in test file: -1 (unless tests are the focus)

### Step 3 — Read only the relevant slice
For each file, read only the containing function/class — not the whole file.
Use `offset` + `limit` in Read to target the section.

Heuristic: function starts at the `def`/`fn`/`function`/`class` line above the match, ends at the next same-level definition.

### Step 4 — Cross-reference lazily
Only follow imports/references if:
- The answer isn't clear from the first file
- The reference is in the same repo (not node_modules, vendor, etc.)

### Step 5 — Report format
```
SEARCH: <query>
Files scanned: <N> (of <total> in repo)
Tokens used: ~<estimated>

RESULTS:
- <file>:<line> — <1-line description>
- ...
```

Apply this search strategy now for the provided query.
