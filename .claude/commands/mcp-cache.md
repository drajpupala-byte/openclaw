# Token Optimizer MCP — Smart Caching

Set up and activate prompt caching strategy for this session to achieve 95%+ token reduction on repeated content.

## What prompt caching does
Anthropic's prompt caching lets large, stable blocks of context (system prompts, file contents, docs) be cached server-side. Cached tokens cost ~10% of normal input token price and don't count toward context refills.

## Caching strategy for this session

### Identify cache candidates (stable, large, reused content)
Run this analysis:
1. What files have been read more than once this session? → Cache them.
2. Is there a large CLAUDE.md or system prompt? → Mark for caching.
3. Are there reference docs, schemas, or API specs loaded? → Cache.

### Structure for maximum cache hits
When building prompts, order content as:
```
[CACHED BLOCK - stable]
  - System instructions
  - Large reference files  
  - Codebase context / CLAUDE.md

[DYNAMIC BLOCK - changes each turn]
  - Current task
  - Latest tool results
  - New user message
```

Cache breaks when dynamic content is inserted before stable content — always put stable content first.

### Cache warm-up
At session start, read all files likely to be needed (CLAUDE.md, key source files, schemas) in one batch. This fills the cache before task work begins.

### Report cache efficiency
After warm-up, estimate:
```
CACHE STATUS
Cached tokens: ~<N>
Cache hit savings this session: ~<N> tokens
Effective cost reduction: ~<N>%
```

Activate this strategy now. Identify and list the top cache candidates in this project.
