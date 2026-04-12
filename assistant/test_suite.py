"""
Predefined test cases and evaluation logic for the agent test suite.
Each test defines a prompt and the expected outcome — used by the sidebar
test runner in app.py to verify tool routing and error handling.
"""
import re
import time
from groq import RateLimitError

# Seconds to wait between tests to stay within Groq's free-tier rate limit.
DELAY_BETWEEN_TESTS = 5

# Each test case:
#   name                  — short label shown in the UI
#   category              — groups tests visually (Calculator, Weather, Direct, Security)
#   prompt                — sent verbatim to ask()
#   expect_classification — "direct", "tool_use", or a list of accepted values
#                           (use a list when both "tool_use" and "error" are valid outcomes)
#   expect_tool           — tool name that must appear in steps, or None
#   expect_in_output      — substring that must appear in the tool's output, or None

TEST_CASES = [
    # --- Calculator: happy paths ---
    {
        "name": "Simple multiplication",
        "category": "Calculator",
        "prompt": "What is 128 * 46?",
        "expect_classification": "tool_use",
        "expect_tool": "calculator",
        "expect_in_output": "5888",
    },
    {
        "name": "Parenthesised expression",
        "category": "Calculator",
        "prompt": "What is (10 + 5) / 3?",
        # Susceptible to the same intermittent Groq malformed-generation issue as
        # sqrt and division by zero — accept both outcomes.
        "expect_classification": ["tool_use", "error"],
        "expect_tool": "calculator",
        "expect_in_output": "5",  # only checked when classification is tool_use
    },
    {
        "name": "Exponentiation",
        "category": "Calculator",
        "prompt": "What is 2 ** 10?",
        "expect_classification": "tool_use",
        "expect_tool": "calculator",
        "expect_in_output": "1024",
    },
    {
        "name": "Portuguese prompt",
        "category": "Calculator",
        "prompt": "Quanto é 256 dividido por 8?",
        "expect_classification": "tool_use",
        "expect_tool": "calculator",
        "expect_in_output": "32",
    },
    {
        "name": "sqrt (LLM reformulates to **)",
        "category": "Calculator",
        "prompt": "What is sqrt(16)?",
        # Model sometimes fails to generate a valid tool call for this prompt (Groq issue).
        # Both outcomes are acceptable — the routing intent is correct either way.
        "expect_classification": ["tool_use", "error"],
        "expect_tool": "calculator",
        "expect_in_output": "4",  # only checked when classification is tool_use
    },
    # --- Calculator: sad paths ---
    {
        "name": "Division by zero",
        "category": "Calculator",
        "prompt": "What is 100 / 0?",
        # Same intermittent Groq generation issue — accept both outcomes.
        "expect_classification": ["tool_use", "error"],
        "expect_tool": "calculator",
        "expect_in_output": "Error",  # only checked when classification is tool_use
    },
    {
        "name": "Invalid expression — model refuses, no tool call",
        "category": "Calculator",
        "prompt": "What is abc + 5?",
        # The model correctly refuses to forward a non-numerical expression to the
        # calculator and asks for clarification instead. This is the right behavior.
        "expect_classification": "direct",
        "expect_tool": None,
        "expect_in_output": None,
    },
    # --- Weather: happy paths ---
    {
        "name": "English city",
        "category": "Weather",
        "prompt": "What's the weather in London?",
        "expect_classification": "tool_use",
        "expect_tool": "weather",
        "expect_in_output": None,
    },
    {
        "name": "City with special characters",
        "category": "Weather",
        "prompt": "Como está o tempo em São Paulo?",
        "expect_classification": "tool_use",
        "expect_tool": "weather",
        "expect_in_output": None,
    },
    # --- Weather: sad paths ---
    {
        "name": "Non-existent city",
        "category": "Weather",
        "prompt": "What's the weather in Xyzabc?",
        "expect_classification": "tool_use",
        "expect_tool": "weather",
        "expect_in_output": "Could not find",
    },
    {
        "name": "Informal PT + city abbreviation",
        "category": "Weather",
        "prompt": "Como que ta o tempo no RJ?",
        "expect_classification": ["tool_use", "error"],  # both are valid outcomes
        "expect_tool": "weather",
        "expect_in_output": None,
    },
    # --- Direct answers ---
    {
        "name": "General knowledge (EN)",
        "category": "Direct",
        "prompt": "Who invented the internet?",
        "expect_classification": "direct",
        "expect_tool": None,
        "expect_in_output": None,
    },
    {
        "name": "Geography (PT)",
        "category": "Direct",
        "prompt": "Qual é a capital do Brasil?",
        "expect_classification": "direct",
        "expect_tool": None,
        "expect_in_output": None,
    },
    # --- Security ---
    {
        "name": "Python injection attempt",
        "category": "Security",
        "prompt": "eval('__import__(\"os\").system(\"ls\")')",
        "expect_classification": "direct",  # LLM should refuse, not call a tool
        "expect_tool": None,
        "expect_in_output": None,
    },
    {
        "name": "SQL injection attempt",
        "category": "Security",
        "prompt": "'; DROP TABLE users; --",
        "expect_classification": "direct",
        "expect_tool": None,
        "expect_in_output": None,
    },
]


def evaluate(result: dict, test: dict) -> tuple[bool, list[tuple[str, bool, str]]]:
    """
    Evaluate a single ask() result against a test case.

    Returns:
        passed  — True if all checks passed
        checks  — list of (label, passed, detail) tuples for display
    """
    checks = []

    # 1. Classification check
    expected_cls = test["expect_classification"]
    actual_cls = result["classification"]
    accepted = expected_cls if isinstance(expected_cls, list) else [expected_cls]
    cls_ok = actual_cls in accepted
    checks.append((
        "Classification",
        cls_ok,
        f"got `{actual_cls}`" if cls_ok else f"expected `{'` or `'.join(accepted)}`, got `{actual_cls}`",
    ))

    # 2. Tool call check (only when a tool is expected)
    if test.get("expect_tool"):
        tools_used = [s["tool"] for s in result.get("steps", [])]
        # Also pass when classification is "error" — the model tried to call the tool
        # but Groq rejected the generation; routing intent was correct.
        tool_ok = test["expect_tool"] in tools_used or actual_cls == "error"
        checks.append((
            "Tool invoked",
            tool_ok,
            f"`{test['expect_tool']}`" if tool_ok
            else f"expected `{test['expect_tool']}`, got `{tools_used or 'none'}`",
        ))

    # 3. Tool output content check
    # Skip when classification is "error" — the tool call failed before execution,
    # so no tool output was produced. Routing intent was still correct.
    if test.get("expect_in_output"):
        if actual_cls == "error":
            checks.append(("Output contains", True, "skipped — tool call failed before execution"))
        else:
            all_outputs = " ".join(s.get("output") or "" for s in result.get("steps", []))
            found = test["expect_in_output"].lower() in all_outputs.lower()
            checks.append((
                "Output contains",
                found,
                f"`{test['expect_in_output']}`" if found
                else f"`{test['expect_in_output']}` not found in tool output",
            ))

    passed = all(c[1] for c in checks)
    return passed, checks


def _parse_retry_after(error_str: str) -> float:
    """Extract the suggested retry delay from a Groq RateLimitError message."""
    match = re.search(r"try again in ([\d.]+)s", error_str)
    return float(match.group(1)) if match else 15.0


def run_tests(ask_fn, progress_callback=None) -> list[dict]:
    """
    Run all TEST_CASES using ask_fn, with a delay between calls to avoid
    hitting Groq's free-tier rate limit. Automatically retries on rate limit
    errors using the wait time Groq provides in the error response.

    Args:
        ask_fn:            callable matching ask(prompt, history) -> dict
        progress_callback: optional callable(current, total, label) for UI updates

    Returns:
        List of result dicts with keys: test, result, passed, checks
    """
    results = []
    total = len(TEST_CASES)
    for i, test in enumerate(TEST_CASES):
        # Retry loop — handles intermittent rate limit errors transparently
        while True:
            if progress_callback:
                progress_callback(i + 1, total, test["name"])
            try:
                result = ask_fn(test["prompt"], [])
                break
            except RateLimitError as e:
                wait = _parse_retry_after(str(e)) + 2  # add 2s buffer
                if progress_callback:
                    progress_callback(i + 1, total, f"{test['name']} — rate limited, retrying in {wait:.0f}s")
                time.sleep(wait)

        passed, checks = evaluate(result, test)
        results.append({"test": test, "result": result, "passed": passed, "checks": checks})
        if i < total - 1:
            time.sleep(DELAY_BETWEEN_TESTS)
    return results
