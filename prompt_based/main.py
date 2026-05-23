import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from agent import ClosiraAgent

BANNER = """
---------------------------------------------------
  Closira — AI Customer Support Assistant
---------------------------------------------------
  Type your message to chat with Closira.
"""


def print_agent_message(response: dict, debug_mode: bool):
    """Print the agent's response to the terminal."""
    message = response.get("message", "")
    stage = response.get("stage", "?")
    confidence = float(response.get("confidence", 1.0))
    escalate = response.get("escalate", False)
    escalate_reason = response.get("escalate_reason", "")

    print(f"\nClosira [{stage.upper()}] (confidence: {confidence:.2f})")
    print(f"  {message}")

    if escalate:
        print(f"\n  WARNING: ESCALATION TRIGGERED")
        print(f"  Reason: {escalate_reason}")
        print(f"  -> Handing off to a human agent. The conversation log has been saved.")

    if debug_mode:
        print("\n[DEBUG JSON]")
        print(json.dumps(response, indent=2))


def run_session():
    """Run a single conversation session."""
    print(BANNER)
    agent = ClosiraAgent()
    debug_mode = False

    # Greeting
    greeting = agent.chat("Hello, I just started a chat.")
    print_agent_message(greeting, debug_mode)

    while not agent.session_complete:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            break

        if not user_input:
            continue

        # --- Normal message ---
        response = agent.chat(user_input)
        print_agent_message(response, debug_mode)

        # Auto-end if critical escalation (abusive or threatening)
        if agent.escalated and agent.critical_escalation and not response.get("session_complete"):
            print("\n[Session terminated due to critical escalation. Generating summary...]")
            summary = agent.generate_summary()
            print("\nSession Summary")
            print(f"  {summary}")
            break

        # Standard escalation notification (does NOT end the conversation)
        if agent.escalated and not agent.critical_escalation and not agent.handoff_notified:
            print("\n[Inquiry flagged for human follow-up]")
            agent.handoff_notified = True

        if agent.session_complete:
            print("\nSession complete. Thank you!")
            print("\nSession Summary")
            summary = agent.generate_summary()
            print(f"  {summary}")
            break

    print("  Session logs saved to ./logs/")


if __name__ == "__main__":
    run_session()
