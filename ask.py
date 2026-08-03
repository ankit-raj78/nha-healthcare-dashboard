#!/usr/bin/env python
"""
ask.py — natural-language querying over the health-facility database (CLI).

    ./ask.py "how many ABDM-enabled facilities are in Bihar?"
    ./ask.py                 # interactive

For the web UI, see dashboard.py. Both share agent.py, so the schema card,
guardrails, and model choice stay identical between them.

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile).
"""
import os
import sys
import textwrap

import agent


def main() -> None:
    if not os.path.exists(agent.DB):
        sys.exit(f"Database not found at {agent.DB}\n"
                 "Build it first:  .venv/bin/python eda/build_v0.py")
    try:
        client = agent.build_client()
    except Exception as e:
        sys.exit(f"Could not create an Anthropic client: {e}\n"
                 "Set ANTHROPIC_API_KEY, or run `ant auth login`.")

    show_sql = "--sql" in sys.argv
    argv = [a for a in sys.argv[1:] if a != "--sql"]

    def turn(question: str, messages: list) -> list:
        messages = messages + [{"role": "user", "content": question}]
        text, messages, queries = agent.answer(client, messages)
        if show_sql:
            for q in queries:
                print(f"\n\033[2m{q['sql']}\033[0m")
                if q["error"]:
                    print(f"\033[31m  error: {q['error']}\033[0m")
        print("\n" + textwrap.fill(text, width=100, replace_whitespace=False))
        return messages

    if argv:
        turn(" ".join(argv), [])
        return

    print("Ask about the facility database. Ctrl-C or 'exit' to quit.")
    print("Pass --sql to see the queries.\n")
    messages: list = []
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if q.lower() in {"exit", "quit"}:
            return
        if q:
            messages = turn(q, messages)


if __name__ == "__main__":
    main()
