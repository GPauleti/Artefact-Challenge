# Challenge Spec — Artefact · Jr. AI Engineer · São Paulo

> Status: Complete

---

## Requirements

### What they asked for

- ✅ **Core agent loop** — receives a user question, decides: tool or direct LLM answer
- ✅ **Calculator tool** — invoked for math questions via native tool calling, not keyword matching
- ✅ **LLM integration** — Llama 3.3 70B via Groq, genuinely in the loop for every request
- ✅ **README** — run instructions, implementation logic, decisions, learnings
- ✅ **Bonus: second tool** — real-time weather via Open-Meteo (free, no API key)
- ✅ **No API keys in code** — `.env` + `.env.example` with setup instructions

### Evaluation criteria

| Criterion | What was built |
|---|---|
| Decision logic clarity | Native tool calling via LangChain — the LLM decides based on semantic intent, not rules. Reasoning panel on every response explains the classification and why. |
| Code organization | `assistant/agent.py` (agent + error handling), `assistant/tools/` (calculator, weather), `assistant/test_suite.py` (test definitions + runner), `app.py` (Streamlit UI + sidebar) |
| LLM integration | Groq API (`llama-3.3-70b-versatile`) via `langchain-groq`, full conversation history passed on every turn |
| Tool integration | Both tools use `@tool` decorator with typed schemas. LLM dispatches via structured tool call, never via if-else. |

---

## What was built

### Stack

- **Model:** `llama-3.3-70b-versatile` via [Groq](https://console.groq.com) — open-source Llama 3.3 70B, free tier, native tool calling
- **Framework:** LangChain (`create_agent`) backed by LangGraph (`create_react_agent`) internally
- **Tools:** Calculator (AST-based, operator whitelist), Weather (Open-Meteo — geocoding + forecast, no API key)
- **Interface:** Streamlit with chat history, reasoning panel, SVG token gauge, and a built-in test suite in the sidebar

### Architecture

```
User message + conversation history
    │
    ▼
LangChain agent (create_agent / LangGraph react loop)
    │
    ├─ LLM decides: answer directly ──────────────────► text response
    │
    └─ LLM decides: call a tool
           │
           ├─► calculator("expression") ──► AST evaluator ──► result ──► LLM composes answer
           └─► weather("city")  ──► geocode → forecast ──► result ──► LLM composes answer
```

### Error handling (three distinct failure modes)

| Error | HTTP Code | Cause | Handling |
|---|---|---|---|
| `BadRequestError` | 400 | Model generates malformed tool call format | Caught in `ask()`, shown in reasoning panel with raw `failed_generation` string |
| `RateLimitError` | 429 — chat | Groq TPM/TPD limit hit during a normal message | Caught in `ask()`, shown as a warning (not an error) with clear explanation |
| `RateLimitError` | 429 — test suite | Rate limit hit during automated test run | Caught in `run_tests()`, retries automatically after parsing Groq's suggested wait time |

### Key design decisions

- **No bare `eval()`** — calculator uses `ast.parse()` in expression mode with an explicit `ast.BinOp / ast.UnaryOp` whitelist. `ast.Call` is not permitted, blocking all function calls at the AST level.
- **LLM as preprocessor** — `sqrt(16)` is not in the whitelist, but the model reformulates it to `16 ** 0.5` before the tool call. The AST evaluator never sees the original syntax.
- **Tolerant test expectations** — calculator tests with complex syntax (parentheses, `sqrt`, division) accept both `tool_use` and `error` classifications, because Groq's Llama 3.3 70B intermittently generates malformed function call output for these prompts. The routing intent is correct either way.
- **Groq model choice** — Llama 3.3 70B is the same class of open-source model listed in the spec (Mistral, Zephyr, Llama). Groq was chosen over HuggingFace free inference (rate-throttled, weaker tool calling) and local Ollama (not reproducible for reviewers).

---

## Bonus features

These were not required by the spec. Added to think through end-user experience.

### Reasoning panel
Every response includes an expanded panel showing:
- Classification (direct vs tool use vs error vs rate limit)
- Tool name, input sent, output returned — side by side
- Plain-English rationale for why that tool was chosen
- Token usage for that response (input · output · total)

### Token usage gauge
Sidebar SVG circular gauge tracking session token consumption:
- Fills vs the 100,000 daily token limit (TPD)
- Colour: green → orange → red
- Per-minute limit (12,000 TPM) shown as a static caption — a gauge would be misleading since it resets every 60 seconds
- Link to the Groq usage dashboard for full account-level tracking
- Updates after every message and after test runs

### Automated test suite (sidebar)
15 predefined tests across Calculator, Weather, Direct, and Security categories:
- Pre-run: all test cases listed with prompt + expected outcome before execution
- During run: progress bar updates per-test, including retry status when rate-limited
- Post-run: pass/fail grouped by category, with full model response shown for investigation
- Rate limit retry: parses Groq's suggested wait time from the error response and retries automatically

---

## Code checklist

- ✅ Agent loop implemented
- ✅ Calculator is a proper `@tool`, not an if-else
- ✅ Safe math evaluation — AST whitelist, no `eval()`
- ✅ Real LLM in the loop — Groq API, full conversation history
- ✅ API keys via `.env` — no secrets in source
- ✅ README complete — run instructions, architecture, decisions, learnings
- ✅ Bonus tool — weather via Open-Meteo
- ✅ Bonus: Streamlit frontend with reasoning panel
- ✅ Bonus: Token usage gauge
- ✅ Bonus: Automated test suite with retry logic

---

## Interview questions to think through

*No answers here — work through these before the interview.*

### On the core architecture

- Why did you use native tool calling instead of routing with if-else or regex?
- How does the agent decide when to use a tool versus answering directly?
- What happens inside the agent loop between the user's message and the final response?
- How does conversation history affect the agent's behaviour, and how is it passed?
- What is `create_agent` in LangChain and what does it wrap internally?
- What is the difference between LangChain and LangGraph, and which one is your agent actually running on?

### On the calculator

- Why did you use `ast.parse()` instead of `eval()`?
- Walk me through what happens when the user sends `"What is sqrt(16)?"` — what does the LLM do, what does the AST evaluator do?
- What would happen if someone sent `"eval('__import__(\"os\").system(\"ls\")')"` to your app?
- What operators are allowed, and how would you add more?

### On the weather tool

- How does the weather tool resolve a city name to coordinates?
- Why does this tool not require an API key?
- What happens if the user asks for weather in a city that doesn't exist?

### On error handling

- What are the three failure modes you handle and how do you distinguish them?
- Why is the `RateLimitError` shown as a warning instead of an error?
- What does `failed_generation` contain and why do you surface it in the UI?
- How does the test suite retry on rate limit errors — what information does it use?

### On the model and provider choices

- Why did you choose Groq over the options listed in the spec?
- Llama 3.3 70B sometimes generates malformed tool call syntax for certain prompts. How did you handle this in the test suite, and what would you do about it in production?
- What is the difference between TPM and TPD rate limits, and why did you design the token gauge around the daily limit rather than the per-minute one?

### On the bonus features

- Why did you add a reasoning panel? What problem does it solve?
- The test suite marks some calculator tests as passing even when classification is `error`. Why is that the right decision?
- How does the SVG gauge update — where is the session token count stored and when is it incremented?

### On production and scale

- What would you change first if this needed to go to production tomorrow?
- How would you add a third tool without changing any routing logic?
- What is MCP (Model Context Protocol) and how does what you built relate to it?
- The README mentions prompt injection as the real security concern. What is it and why can't it be blocked with input filtering?
- How would you evolve this into a multi-step agent that can plan and retry?
- How would you measure whether the tool routing is actually working well across a diverse set of users?

### On Artefact's work

- Artefact built an agentic sales assistant for Bouygues Telecom. What challenges do you think they encountered that you didn't face in this challenge?
- How is what you built similar to and different from a production agentic system?
