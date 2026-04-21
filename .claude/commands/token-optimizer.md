# Claude Token Optimizer

Rewrite the provided prompt to be maximally token-efficient while preserving full intent.

## Usage
Paste a prompt after invoking this command. The optimizer will return a compressed version.

## Compression rules applied

**Remove without changing meaning:**
- "Please", "Could you", "I would like you to", "Can you", "I need you to" → delete, start with the verb
- "In order to" → "To"
- "Make sure to" → delete
- "It's important that" → delete
- "Feel free to" → delete
- "As an AI language model" → delete any such disclaimers
- Redundant context already implied by the task

**Shorten:**
- "the following" → remove when obvious
- "a list of" → remove (just list them)
- Repeated constraint restatements → keep first, delete repeats
- Example verbosity: "For each item in the list, you should..." → "For each item..."

**Restructure:**
- Long paragraphs of instructions → bullet points
- Nested qualifications → flatten with explicit conditions
- Vague scope ("look at things") → specific targets ("read src/")

**Output format:**
```
ORIGINAL: <N> tokens (estimated)
OPTIMIZED: <N> tokens (estimated)
REDUCTION: <N>% 

---
<optimized prompt>
```

Estimate tokens as: character_count / 4 (rough approximation).

Target: reduce 11K-token prompts to ~1.3K (88% reduction) by eliminating all redundancy.
