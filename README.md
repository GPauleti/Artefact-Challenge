# AI Assistant

A minimal AI assistant built with Python, LangChain, and Groq that automatically decides when to use tools versus answering from its own knowledge.

## Features

- **Smart routing** — the LLM decides which tool to call (or none), with no hard-coded keyword matching
- **Safe calculator** — evaluates arithmetic expressions using Python's `ast` module (no `eval`)
- **Real-time weather** — fetches live conditions for any city via [Open-Meteo](https://open-meteo.com/) (free, no API key needed)
- **Conversation memory** — retains chat history within the session
- **Streamlit UI** — clean chat interface, no frontend code needed

## Model Used

[Groq](https://console.groq.com) — `llama-3.3-70b-versatile`

Groq provides free API access to Meta's Llama 3.3 70B model with very fast inference. This model supports native tool/function calling, which LangChain uses to route math questions to the calculator automatically.

## Setup

### 1. Clone and enter the project

```bash
git clone <your-repo-url>
cd ai-assistant
```

### 2. Create a virtual environment (optional but recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then open `.env` and replace the placeholder with your Groq API key:

```
GROQ_API_KEY=your_actual_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

### 5. Run the assistant

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

## Example interactions

| Input | What happens |
|-------|-------------|
| `Quanto é 128 vezes 46?` | Agent calls `calculator("128 * 46")` → returns **5888** |
| `(10 + 5) / 3` | Agent calls `calculator("(10 + 5) / 3")` → returns **5.0** |
| `Como está o tempo em Tokyo?` | Agent calls `weather("Tokyo")` → returns live temperature, humidity, wind |
| `What's the weather like in London?` | Agent calls `weather("London")` → returns live conditions |
| `Quem foi Albert Einstein?` | Agent answers directly from its knowledge |
| `What is the capital of Brazil?` | Agent answers directly from its knowledge |

## Project structure

```
ai-assistant/
├── app.py                        # Streamlit UI
├── assistant/
│   ├── agent.py                  # LangChain agent + Groq LLM setup
│   └── tools/
│       ├── calculator.py         # Safe arithmetic tool (@tool)
│       └── weather.py            # Real-time weather via Open-Meteo (@tool)
├── .env                          # Your API key (not committed)
├── .env.example                  # Template
├── requirements.txt
└── README.md
```

## Implementation logic

The core idea is to let the LLM itself decide when to use a tool — this is called **tool calling** (also known as function calling). Here is the flow:

1. The user sends a message via the Streamlit chat interface.
2. The message and conversation history are passed to a LangChain agent (a compiled LangGraph graph).
3. The agent sends the input to the Groq LLM along with a description of available tools.
4. If the LLM determines a tool is needed, it emits a structured tool call. The agent intercepts it, runs the tool, and feeds the result back to the LLM.
5. The LLM composes a final response using the tool's output.
6. If no tool is needed, the LLM answers directly.

The calculator uses Python's `ast` module to parse and evaluate expressions safely — only arithmetic operators are allowed, preventing any code injection.

The weather tool makes two sequential calls to Open-Meteo's free public APIs: first to the geocoding endpoint to resolve a city name into coordinates, then to the forecast endpoint to fetch current conditions. No API key is required.

## What I learned and what I'd do differently with more time

**Learned:**
- How LangChain's tool-calling agent loop works under the hood (LLM → tool call → result → LLM)
- Why safe expression evaluation with `ast` is important versus raw `eval`
- How Groq's free API tier makes rapid prototyping with powerful LLMs accessible

**With more time:**
- **Use paid, higher-capability models** — this project deliberately uses free tools (Groq's free tier, Open-Meteo) as requested by the challenge. Given a production budget, I'd swap in models like GPT-4o or Claude Opus for more reliable tool-call routing, better reasoning, and stronger multilingual support
- Add **streaming responses** so the text appears token by token instead of all at once
- Persist conversation history across sessions (e.g., using SQLite or a file)
- Add error handling in the UI for missing API keys or network failures
- Write unit tests for the calculator's safe evaluator
- 
