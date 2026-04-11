import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

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


def ask(question: str, history: list[dict]) -> str:
    """
    Send a question to the agent and return the response string.

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

    result = _agent.invoke({"messages": messages})
    return result["messages"][-1].content
