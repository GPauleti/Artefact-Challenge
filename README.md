# AI Assistant — Gabriel Pauleti · Artefact Jr. AI Engineer Challenge

A minimal but production-minded AI assistant built with Python, LangChain, and Groq. The agent automatically decides when to use a tool versus answering directly — using the model's native tool-calling mechanism, not keyword matching or if-else routing.

---

## Features

- **Native tool calling** — the LLM decides which tool to invoke (or none) based on semantic understanding of the user's intent. No hard-coded routing logic.
- **Safe calculator** — evaluates arithmetic using Python's `ast` module with a strict operator whitelist. No `eval()`, no code injection risk.
- **Real-time weather** — fetches live conditions for any city via [Open-Meteo](https://open-meteo.com/) (free, no API key required). Two-step pipeline: geocoding → current forecast.
- **Conversation memory** — retains the full chat history within the session, enabling multi-turn context.
- **Multilingual** — the system prompt instructs the model to always respond in the user's language.
- **Streamlit UI** — a clean chat interface with no frontend code.

---

## Setup

### 1. Clone and enter the project

```bash
git clone https://github.com/GPauleti/Artefact-Challenge
cd ai-assistant
```

### 2. Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate  # Mac: source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your Groq API key:

```
GROQ_API_KEY=your_actual_key_here
```

Get a free key at [console.groq.com](https://console.groq.com). No credit card required.

### 5. Run the assistant

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`.

---

## Project structure

```
ai-assistant/
├── app.py                    # Streamlit UI + sidebar (token gauge, test suite)
├── assistant/
│   ├── agent.py              # LangChain agent, Groq LLM, error handling
│   └── tools/
│       ├── calculator.py     # Safe AST-based arithmetic tool
│       └── weather.py        # Real-time weather via Open-Meteo
├── .env                      # Your API key (not committed)
├── .env.example              # Key template
├── requirements.txt
└── README.md
```

---

## Key logical decisions

### Why native tool calling, not if-else routing

The simplest implementation would be to scan the user's message for keywords like "calculate" or "weather" and branch accordingly. I deliberately did not do this.

Instead, tools are registered with the LLM as typed schemas (name, description, parameters). The model decides whether and which tool to call based on its understanding of the user's *intent* — not the presence of specific words. This means:

- `"Quanto é 128 vezes 46?"` routes to the calculator without any Portuguese-specific logic
- `"Is it raining in Tokyo?"` routes to the weather tool without matching "rain" explicitly
- `"What is the capital of Brazil?"` answers directly because no tool is semantically needed

This is how production agents work. Keyword routing breaks on paraphrasing, other languages, and edge cases. Tool-calling generalises.

### Why a safe calculator instead of asking the LLM to do the math

LLMs are probabilistic. They can approximate arithmetic but they are not reliable calculators — especially for large numbers, nested expressions, or modular arithmetic. Delegating to a deterministic tool guarantees exact results every time.

The calculator uses `ast.parse()` in expression mode and recursively evaluates the AST against an explicit operator whitelist (`+`, `-`, `*`, `/`, `//`, `%`, `**`). Any node type not on the whitelist raises a `ValueError`. This means:

- `eval("__import__('os').system('ls')")` is rejected at the AST level — `ast.Call` is not a permitted node
- `sqrt(16)` is not in the whitelist, but the LLM reformulates it to `16 ** 0.5` before calling the tool — the model acts as a smart preprocessor
- Division by zero returns a controlled error string, not an exception that crashes the app

### Why Groq and Llama 3.3 70B

The challenge allows any accessible LLM. I chose [Groq](https://console.groq.com) as the inference provider for Meta's **Llama 3.3 70B** — an open-source model in the same family as those listed in the spec (Mistral, Zephyr, Llama via Ollama). Groq's free tier provides fast inference with native tool-calling support, no credit card required.

Compared to the alternatives listed in the spec:
- **HuggingFace free inference** — rate-throttled, weaker tool-calling reliability
- **Local models (Ollama)** — requires the reviewer to download the model locally, breaking reproducibility
- **Groq + Llama 3.3 70B** — runs in the cloud, free, reproducible, and has solid tool-calling support

### Agent flow

```
User message
    │
    ▼
LangChain agent (create_agent)
    │
    ├─ LLM decides: direct answer?  ──────────────────► text response
    │
    └─ LLM decides: call a tool?
           │
           ├─► calculator("expression") ──► result ──► LLM composes final answer
           └─► weather("city")         ──► result ──► LLM composes final answer
```

The agent loop is implemented via LangChain's `create_agent`, which internally uses LangGraph's `create_react_agent`. LangGraph is a transitive dependency of LangChain and does not need to be listed separately in `requirements.txt`.

### Error handling

Three distinct failure modes are caught and surfaced gracefully — the app never crashes:

| Error | Cause | Handling |
|---|---|---|
| `BadRequestError` (400) | Model generated a malformed tool call format | Shown in reasoning panel with the raw failed generation for transparency |
| `RateLimitError` (429) | Groq free-tier token limit exceeded | Shown in reasoning panel with a clear explanation that this is a Groq constraint, not an app failure |
| Tool execution errors | Division by zero, unknown city, invalid expression | Returned as error strings from the tool, shown in the reasoning panel output |

---

## Bonus features

These were not required by the challenge brief. I added them to think through end-user experience and to push myself technically.

### Reasoning panel (every response)

Every response includes an expandable panel explaining exactly what the agent did and why:

- **Classification** — did the model answer directly or invoke a tool?
- **Tool call details** — which tool was called, what input was sent, what output was returned
- **Rationale** — a plain-English explanation of *why* that tool was chosen (or not)
- **Token usage** — how many input and output tokens this response consumed

The goal is full transparency: a user or reviewer should be able to understand the agent's decision without reading the source code.

### Token usage gauge

The sidebar displays a circular SVG gauge tracking cumulative token consumption for the session against Groq's free-tier limits:

- **Daily limit:** 100,000 tokens (gauge fills as you use them)
- **Per-minute limit:** 12,000 tokens (shown as a static reference — it resets every 60 seconds, so a filling gauge would be misleading)
- The gauge changes colour from green → orange → red as you approach the daily cap
- Links directly to the Groq usage dashboard for full account-level tracking

### Automated test suite

The sidebar includes a built-in test runner covering 15 predefined test cases across four categories: Calculator (happy and sad paths), Weather (happy and sad paths), Direct answers, and Security inputs.

Each test defines a prompt and expected outcome. After running, results are displayed grouped by category with pass/fail indicators and the full model response for investigation.

The runner includes:
- **Rate limit handling** — catches `RateLimitError`, parses Groq's suggested retry delay from the error message, and automatically retries the failed test after waiting. No manual intervention needed.
- **Paced execution** — a 5-second delay between tests to stay within the per-minute token limit
- **Tolerant expectations** — tests that are susceptible to Groq's intermittent malformed-generation issue accept both `tool_use` and `error` as valid outcomes, since the routing intent is correct either way

---

## What I learned and what I'd do differently

**Learned:**

- How LangChain's tool-calling agent loop works under the hood: the LLM emits a structured `tool_use` response, the framework dispatches it, and the result is fed back to the LLM to compose the final answer. Understanding this loop is what makes agentic systems debuggable.
- Why safe expression evaluation with `ast` matters versus raw `eval` — and that the LLM itself can act as a preprocessing layer, reformulating `sqrt(16)` into `16 ** 0.5` before the tool even sees it.
- That open-source models on free inference tiers have inconsistent tool-call formatting under certain conditions (informal language, special syntax). This is a real production consideration: reliability of tool calling varies significantly between models and providers.
- How Groq's rate limiting works at the token level (TPM and TPD), and how to handle it gracefully with automatic retry rather than crashing.

**With more time:**
- **Use paid, higher-capability models** — this project deliberately uses free tools (Groq's free tier, Open-Meteo) as requested by the challenge. Given a production budget, I'd swap in models like GPT-4o or Claude Opus for more reliable tool-call routing, better reasoning, and stronger multilingual support
- Add **streaming responses** so the text appears token by token instead of all at once
- Persist conversation history across sessions (e.g., using SQLite or a file)
- Add error handling in the UI for missing API keys or network failures
- Write unit tests for the calculator's safe evaluator
