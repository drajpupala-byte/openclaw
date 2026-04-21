# Token Savior — Symbol-Based Navigation

Navigate codebases using symbols instead of file contents. Achieves 97% token reduction vs reading full files.

## Core principle
A symbol (function name, class, type, constant) is a pointer to the exact location you need. Read the pointer first — read the content only if the pointer isn't enough.

## Navigation commands

### Find a symbol
```
Grep(pattern="(def|fn|function|class|const|type|interface)\s+<SymbolName>", output_mode="content")
```
Returns: file + line number. Cost: ~10 tokens. vs reading the file: ~2,000+ tokens.

### Find all usages
```
Grep(pattern="<SymbolName>", output_mode="files_with_matches")
```
Then read only the relevant lines in each file using offset+limit.

### Understand a function signature without reading body
Read 1 line (the definition) + next N lines until the closing paren:
```
Read(file, offset=<def_line>, limit=10)
```

### Trace a call chain
1. Find caller with Grep
2. Read only caller's function body (not full file)
3. Find callee with Grep
4. Read only callee signature

### Navigate types/interfaces
```
Grep(pattern="(type|interface|struct|class)\s+<TypeName>", output_mode="content")
```
Read the type definition (usually <20 lines). Don't read every file that uses it.

## Anti-patterns this replaces

| Wasteful | Token-Savior equivalent |
|----------|------------------------|
| Read entire 800-line file to find one function | Grep for function name → Read 30 lines |
| Read all imports to understand dependencies | Grep for import pattern |
| Read test file to understand API shape | Grep for function signature |
| Re-read same file for second symbol | Grep for second symbol → targeted Read |

## Session activation
Apply symbol-first navigation for all code exploration in this session. Before any Read call on a file >100 lines, first run a Grep to find the exact location needed.

Report token savings at end: `[Token Savior: read <N> lines vs estimated <N> with full reads — saved ~<N>%]`
