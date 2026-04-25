# openclaw

**openclaw** is a lightweight integration layer that plugs any AI agent into the [Future AGI](https://futureagi.com) self-improvement platform — tracing, guardrails, evals, and prompt optimization, all in one loop.

## What it does

| Layer | What runs | Future AGI feature |
|---|---|---|
| **Trace** | Every LLM call, tool use, and chain step | TraceAI (OpenTelemetry) |
| **Guard** | Input & output safety checks | Guardrails (sub-100ms) |
| **Evaluate** | Relevance, toxicity, coherence, faithfulness | AI Evals (50+ metrics) |
| **Optimize** | Evolves your system prompt toward higher scores | agent-opt / GEPA |

## Quick start

```bash
git clone https://github.com/drajpupala-byte/openclaw
cd openclaw
pip install -r requirements.txt
cp .env.example .env   # add your API keys
python examples/run_assistant.py
```

## Structure

```
openclaw/
  futureagi/          ← integration wrapper (install once, reuse everywhere)
    client.py         ← FutureAGI(project_name=...) — one-line setup
    tracer.py         ← @traced decorator + span() context manager
    evaluator.py      ← evaluate(["relevance", "toxicity"], output=...)
    guardrails.py     ← Guardrail().screen_input / screen_output
    optimizer.py      ← optimize_prompt(initial, scorer_fn)
  agents/
    base.py           ← BaseAgent — subclass & override _run()
    smart_assistant.py← SmartAssistant — Claude-powered demo agent
  examples/
    run_assistant.py  ← single-turn, multi-turn, and blocked-input demos
    optimize_agent.py ← GEPA prompt optimization loop
    custom_agent.py   ← plug in your own LLM in ~20 lines
```

## Using the wrapper

### One-line setup

```python
from futureagi import FutureAGI

fagi = FutureAGI(project_name="my-agent")
fagi.instrument_openai()     # auto-trace all OpenAI calls
fagi.instrument_anthropic()  # auto-trace all Anthropic calls
```

### Guard input & output

```python
result = fagi.guard_input("user message")
if not result.passed:
    return f"Blocked: {result.blocked_categories}"

output = my_llm(prompt)

result = fagi.guard_output(output)
if not result.passed:
    return "Response blocked by safety filters."
```

### Run evaluations

```python
evals = fagi.evaluate(
    ["relevance", "toxicity", "coherence"],
    output=response,
    input=user_query,
)
for e in evals:
    print(e)  # EvalResult(relevance: PASS, score=0.91)
```

### Trace manually

```python
from futureagi import traced, span

@traced
def retrieve_docs(query: str) -> list[str]:
    ...

with span("rerank", {"n_docs": len(docs)}):
    ranked = reranker.rank(docs)
```

### Optimize a system prompt

```python
from futureagi import optimize_prompt, evaluate

def score(prompt: str) -> float:
    response = run_agent_with_prompt(prompt, test_input)
    return evaluate(["relevance"], output=response)[0].score

result = optimize_prompt("Answer questions helpfully: {query}", score)
print(result.best_prompt)
```

## Building your own agent

Subclass `BaseAgent` and override `_run()`. Tracing, guardrails, and evals are applied automatically:

```python
from agents.base import BaseAgent

class MyAgent(BaseAgent):
    def _run(self, prompt: str) -> str:
        return my_llm_call(prompt)

agent = MyAgent(project_name="my-project")
response = agent.run("What is RAG?")

print(response.output)
print(response.eval_summary())
print(f"{response.latency_ms:.0f}ms")
```

## Environment variables

```
FI_API_KEY          Future AGI API key
FI_SECRET_KEY       Future AGI secret key
ANTHROPIC_API_KEY   For SmartAssistant
OPENAI_API_KEY      For OpenAIAgent / traceai-openai
```

Copy `.env.example` → `.env` and fill in your keys.

## Dependencies

Core: `anthropic`, `futureagi`, `fi-instrumentation`
Tracing: `traceai-openai` (or `-langchain`, `-crewai`, `-llamaindex`)
Optimization: `agent-opt` or `gepa` (optional)

See `requirements.txt` for pinned versions.
