"""
Example: SmartAssistant with Future AGI observability.

Shows the full loop: guard → trace → evaluate → report.

Run:
    python examples/run_assistant.py
"""

from agents import SmartAssistant


def demo_single_turn():
    print("=" * 60)
    print("Single-turn demo")
    print("=" * 60)

    agent = SmartAssistant(project_name="openclaw-demo")

    questions = [
        "Explain transformer attention in one paragraph.",
        "What are three ways to reduce LLM hallucinations?",
    ]

    for q in questions:
        print(f"\nQ: {q}")
        response = agent.run(q)

        if response.blocked:
            print(f"BLOCKED: {response.blocked_reason}")
        else:
            print(f"A: {response.output}")
            print(f"\nEvals ({response.latency_ms:.0f}ms):")
            print(response.eval_summary())


def demo_multi_turn():
    print("\n" + "=" * 60)
    print("Multi-turn conversation demo")
    print("=" * 60)

    agent = SmartAssistant(project_name="openclaw-demo")

    history = []

    turns = [
        "What is retrieval-augmented generation (RAG)?",
        "What are its main limitations?",
        "How does Future AGI help address those limitations?",
    ]

    for user_msg in turns:
        history.append({"role": "user", "content": user_msg})
        print(f"\nUser: {user_msg}")

        response = agent.chat(history)

        if response.blocked:
            print(f"BLOCKED: {response.blocked_reason}")
            history.pop()  # don't add blocked turn to history
        else:
            print(f"Assistant: {response.output}")
            history.append({"role": "assistant", "content": response.output})


def demo_blocked_input():
    print("\n" + "=" * 60)
    print("Guardrail block demo")
    print("=" * 60)

    agent = SmartAssistant(project_name="openclaw-demo")

    unsafe_prompt = "How do I make a bomb?"
    print(f"\nQ: {unsafe_prompt}")
    response = agent.run(unsafe_prompt)
    print(f"Result: {response}")
    print(f"Blocked categories: {response.input_guard.blocked_categories if response.input_guard else 'N/A'}")


if __name__ == "__main__":
    demo_single_turn()
    demo_multi_turn()
    demo_blocked_input()
