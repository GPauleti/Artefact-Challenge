import os
from dotenv import load_dotenv
from groq import BadRequestError, RateLimitError
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from assistant.tools.calculator import calculator
from assistant.tools.weather import weather

load_dotenv()

SYSTEM_PROMPT = """You are a helpful AI assistant. You can answer general knowledge questions, \
perform mathematical calculations, and fetch real-time weather data.

When the user asks you to compute or calculate something numerical, you MUST use the calculator tool \
to get the exact result — do not try to compute it yourself.

When the user asks about the weather, temperature, or conditions in any location, you MUST use the \
weather tool to get real-time data — do not guess or use your training knowledge for current weather.

For all other questions, answer directly using your knowledge.

Always respond in the same language the user writes in."""

_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.environ["GROQ_API_KEY"],
)

_agent = create_agent(
    model=_llm,
    tools=[calculator, weather],
    system_prompt=SYSTEM_PROMPT,
)


def ask(question: str, history: list[dict]) -> dict:
    """
    Send a question to the agent and return a dict with:
      - response:       the final text answer
      - classification: 'tool_use' or 'direct'
      - steps:          list of {tool, input, output} dicts for each tool call made

    Args:
        question: The user's latest message.
        history: List of previous turns as dicts with keys 'role' and 'content'.
                 Roles are 'user' and 'assistant'.
    """
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))

    input_length = len(messages)
    try:
        result = _agent.invoke({"messages": messages})
    except RateLimitError as e:
        return {
            "response": (
                "The request could not be completed because the API rate limit has been reached. "
                "This is a restriction imposed by Groq — the service that hosts the model — "
                "not a failure of the application or the LLM itself. Please wait a moment and try again."
            ),
            "classification": "rate_limited",
            "steps": [],
            "tokens": {"input": 0, "output": 0, "total": 0},
            "error_detail": str(e),
            "failed_generation": None,
        }
    except BadRequestError as e:
        error_detail = str(e)
        # Extract the raw failed_generation string if present for display
        failed_gen = None
        if "failed_generation" in error_detail:
            try:
                import json as _json
                payload = _json.loads(error_detail[error_detail.index("{"):])
                failed_gen = payload.get("error", {}).get("failed_generation")
            except Exception:
                pass
        return {
            "response": (
                "I wasn't able to complete that request. The model tried to call a tool "
                "but produced a response the API couldn't parse. Try rephrasing your question."
            ),
            "classification": "error",
            "steps": [],
            "tokens": {"input": 0, "output": 0, "total": 0},
            "error_detail": error_detail,
            "failed_generation": failed_gen,
        }

    new_messages = result["messages"][input_length:]

    # Walk only the messages the agent added and reconstruct tool call steps
    steps = []
    for msg in new_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({"tool": tc["name"], "input": tc["args"], "output": None})
        elif isinstance(msg, ToolMessage):
            # Pair the output with the most recent unresolved step
            for step in reversed(steps):
                if step["output"] is None:
                    step["output"] = msg.content
                    break

    # Sum token usage across all AIMessages in this response
    tokens: dict[str, int] = {"input": 0, "output": 0, "total": 0}
    for msg in new_messages:
        if isinstance(msg, AIMessage):
            meta = getattr(msg, "usage_metadata", None) or {}
            tokens["input"] += meta.get("input_tokens", 0)
            tokens["output"] += meta.get("output_tokens", 0)
            tokens["total"] += meta.get("total_tokens", 0)

    return {
        "response": new_messages[-1].content,
        "classification": "tool_use" if steps else "direct",
        "steps": steps,
        "tokens": tokens,
        "error_detail": None,
        "failed_generation": None,
    }
