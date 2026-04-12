import json
import streamlit as st
from assistant.agent import ask
from assistant.test_suite import TEST_CASES, run_tests

# Groq free-tier limits for llama-3.3-70b-versatile
# Source: https://console.groq.com/docs/rate-limits
_TPM_LIMIT = 12_000
_TPD_LIMIT = 100_000


def _gauge_svg(used: int, limit: int) -> str:
    """Return an SVG circular gauge as an HTML string."""
    pct = min(used / limit, 1.0) if limit > 0 else 0
    circumference = 282.74  # 2 * pi * r=45
    filled = pct * circumference
    remaining = circumference - filled
    color = "#4CAF50" if pct < 0.7 else ("#FF9800" if pct < 0.9 else "#f44336")
    pct_label = f"{int(pct * 100)}%"
    token_label = f"{used:,} / {limit:,}"
    return (
        '<div style="display:flex;justify-content:center;margin:6px 0;">'
        '<svg width="110" height="110" viewBox="0 0 110 110">'
        f'<circle cx="55" cy="55" r="45" fill="none" stroke="#444" stroke-width="9"/>'
        f'<circle cx="55" cy="55" r="45" fill="none" stroke="{color}" stroke-width="9" '
        f'stroke-dasharray="{filled:.2f} {remaining:.2f}" '
        f'stroke-linecap="round" transform="rotate(-90 55 55)"/>'
        f'<text x="55" y="50" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="18" font-weight="bold" fill="white">{pct_label}</text>'
        f'<text x="55" y="68" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="9" fill="#aaa">{token_label}</text>'
        "</svg></div>"
    )

st.set_page_config(page_title="Ask me anything", page_icon="🧠")
st.title("Ask me anything.")
st.markdown(
    "I know quite a lot. Math I delegate to a real calculator,  because precision matters. "
    "Weather I fetch live,  because guessing is for amateurs. Everything else, ask away."
)
st.info(
    "**Built by Gabriel Pauleti for Artefact's Jr. AI Engineer interview process.**\n\n"
    "This assistant runs a LangChain agent backed by Llama 3.3 70B on Groq with native tool calling. "
    "Routing decisions are made by the model itself, not by keyword matching or hand-written rules. "
    "Every response includes a reasoning panel explaining exactly how the agent classified your question "
    "and why it made the choices it did.\n\n"
    "**Try:** `What is 2 ** 32?` · `How's the weather in São Paulo?` · `Who invented the internet?`\n\n"
    "Calculator supports: `+` `-` `*` `/` `//` `%` `**` and parentheses. "
    "Ask me anything in any language and I'll reply in the same language."
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = 0

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle new input
if prompt := st.chat_input("Ask me anything..."):
    # Show and store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get assistant response (pass history minus the message we just added)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            history = st.session_state.messages[:-1]  # exclude current message
            result = ask(prompt, history)

        response = result["response"]
        classification = result["classification"]
        steps = result["steps"]
        tokens = result["tokens"]
        st.session_state.session_tokens += tokens["total"]

        # --- Reasoning panel ---
        with st.expander(" Agent reasoning", expanded=True):
            if classification == "rate_limited":
                st.warning("**Rate limit reached — this is not an application error**")
                st.markdown(
                    "Groq, the service that hosts the Llama 3.3 70B model, imposes a token-per-minute "
                    "limit on its free tier. This request exceeded that limit. The application and the "
                    "model are working correctly — you simply need to wait a moment before sending "
                    "another message."
                    "To find out more about this error: please consult the documentation at: https://console.groq.com/docs/rate-limits and search for the Llama 3.3 70B model"
                )

            elif classification == "error":
                st.error("**Classification: Tool call failed**")
                st.markdown(
                    "The model identified that a tool was needed and attempted to invoke it, "
                    "but the function call it generated was malformed — the Groq API rejected it "
                    "before any tool was executed. This is a known intermittent issue with "
                    "`llama-3.3-70b-versatile` on informal or non-English prompts: the model "
                    "sometimes outputs a legacy `<function=...>` syntax instead of the expected "
                    "JSON format, which the API cannot parse."
                )
                if result.get("failed_generation"):
                    st.markdown("**Raw output the model generated (malformed):**")
                    st.code(result["failed_generation"], language="")
                st.markdown(
                    "**What to try:** rephrase the question in more formal language, "
                    "or ask again — the model's output is non-deterministic and may succeed on retry."
                )

            elif classification == "direct":
                st.markdown("**Classification: Direct answer**")
                st.markdown(
                    "The model responded from its own training knowledge — no tool was invoked. "
                    "This path is taken for factual, conversational, or general-knowledge questions "
                    "where the LLM can produce a reliable answer without external data."
                )
            else:
                st.markdown(f"**Classification: Tool use** — {len(steps)} tool call(s)")
                st.markdown(
                    "The model determined that answering this question requires external computation "
                    "or real-time data. Instead of generating a direct text response, it issued a "
                    "structured tool call and used the result to compose its final answer."
                )
                for i, step in enumerate(steps, 1):
                    st.divider()
                    tool = step["tool"]
                    args = step["input"]
                    output = step["output"]

                    if tool == "calculator":
                        rationale = (
                            "Arithmetic is routed to a deterministic calculator. "
                            "LLMs are probabilistic and can produce incorrect numerical results — "
                            "delegating to a purpose-built tool guarantees an exact answer every time."
                        )
                    elif tool == "weather":
                        rationale = (
                            "Weather is real-time data. The model's training knowledge is static and "
                            "cannot reflect current conditions, so it fetches live data from "
                            "Open-Meteo's free public API instead of guessing."
                        )
                    else:
                        rationale = "The model determined this question requires data from an external source."

                    st.markdown(f"**Tool {i} of {len(steps)}: `{tool}`**")
                    st.markdown(f"*Why this tool:* {rationale}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Input sent to tool**")
                        st.code(json.dumps(args, ensure_ascii=False, indent=2), language="json")
                    with col2:
                        st.markdown("**Output returned by tool**")
                        st.code(output or "", language="")

            # Token usage footer — shown for every classification except errors with 0 tokens
            if tokens["total"] > 0:
                st.divider()
                st.caption(
                    f"This response used **{tokens['total']:,} tokens** "
                    f"(input: {tokens['input']:,} · output: {tokens['output']:,})"
                )

        st.markdown(response)

    # Store assistant message
    st.session_state.messages.append({"role": "assistant", "content": response})

# ── Sidebar:  ────────────────────────────────────────────────────────
with st.sidebar:
    # ── Token Usage ───────────────────────────────────────────────────────────
    st.header("Token Usage")
    session_tokens = st.session_state.session_tokens
    st.markdown(_gauge_svg(session_tokens, _TPD_LIMIT), unsafe_allow_html=True)
    st.caption(
        f"**{session_tokens:,}** tokens used this session · "
        f"Daily limit: **{_TPD_LIMIT:,}**"
    )
    st.caption(f"Per-minute limit: **{_TPM_LIMIT:,}** tokens — resets every 60 s")
    st.caption(
        "Gauge tracks this browser session only. "
        "Full account usage: [console.groq.com](https://console.groq.com/settings/organization/usage?tab=activity)"
    )

    st.divider()

    # ── Test Suite ────────────────────────────────────────────────────────────
    st.header("Test Suite")
    st.caption(
        f"{len(TEST_CASES)} predefined tests covering calculator, weather, "
        "direct answers, and security inputs.\n\n"
        "There exists a non-issue with Groq's `llama-3.3-70b-versatile` model where certain informal or non-English prompts can sometimes trigger a malformed generation that causes the tool call to fail." 
        "This is classified as an 'error' in the reasoning panel but is actually a known intermittent issue with the model's output format, not a failure of the application or the tool itself." 
        "If you encounter this, please try using the prompt in the assistant interface directly and validating the result."
    )

    # Show all planned tests before running so the user knows what's queued
    with st.expander(f"View all {len(TEST_CASES)} test cases", expanded=False):
        categories = dict.fromkeys(t["category"] for t in TEST_CASES)
        for category in categories:
            st.markdown(f"**{category}**")
            for t in TEST_CASES:
                if t["category"] != category:
                    continue
                expected = t["expect_classification"]
                if isinstance(expected, list):
                    expected = " or ".join(expected)
                st.markdown(
                    f"- `{t['name']}`  \n"
                    f"  *Prompt:* {t['prompt']}  \n"
                    f"  *Expects:* {expected}"
                    + (f" · tool: `{t['expect_tool']}`" if t.get("expect_tool") else "")
                    + (f" · output contains: `{t['expect_in_output']}`" if t.get("expect_in_output") else "")
                )

    if st.button("Run all tests", use_container_width=True):
        progress = st.progress(0, text="Starting…")

        def on_progress(current, total, name):
            progress.progress(current / total, text=f"Running {current}/{total}: {name}")

        st.session_state.test_results = run_tests(ask, progress_callback=on_progress)
        progress.empty()
        for r in st.session_state.test_results:
            st.session_state.session_tokens += r["result"].get("tokens", {}).get("total", 0)

    if "test_results" in st.session_state:
        results = st.session_state.test_results
        n_passed = sum(1 for r in results if r["passed"])
        n_total = len(results)

        if n_passed == n_total:
            st.success(f"All {n_total} tests passed")
        else:
            st.warning(f"{n_passed} / {n_total} passed")

        # Group by category for readability
        result_categories = dict.fromkeys(r["test"]["category"] for r in results)
        for category in result_categories:
            st.markdown(f"**{category}**")
            for r in results:
                if r["test"]["category"] != category:
                    continue
                icon = "✅" if r["passed"] else "❌"
                with st.expander(f"{icon} {r['test']['name']}"):
                    st.markdown(f"**Prompt:** `{r['test']['prompt']}`")
                    for label, ok, detail in r["checks"]:
                        mark = "✅" if ok else "❌"
                        st.markdown(f"{mark} **{label}:** {detail}")
                    st.markdown("**Full response:**")
                    st.markdown(r["result"]["response"])
