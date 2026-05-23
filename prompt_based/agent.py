"""
agent.py — Core AI agent logic for the Closira customer support workflow.

Manages:
- Conversation history (stateful within session)
- OpenAI API calls with structured JSON output
- Stage transitions (faq → qualification → summary)
- Escalation detection and logging
- Unanswered question tracking for auto-escalation
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Optional
from openai import OpenAI

from prompts.system_prompt import build_system_prompt
from logger import log_escalation, log_summary

MAX_RETRIES = 3
UNANSWERED_THRESHOLD = 2  # escalate after this many unanswered questions


# Agent class

class ClosiraAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("\n[INFO] OPENAI_API_KEY not found. Falling back to local Llama3 8B model...")
            local_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
            self.model_name = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
            self.client = OpenAI(base_url=local_url, api_key="ollama")
        else:
            self.model_name = "gpt-4o"
            self.client = OpenAI(api_key=api_key)
        self.system_prompt = build_system_prompt()
        self.history: list[dict] = []           # full conversation history
        self.stage = "answering_question"
        self.escalated = False
        self.critical_escalation = False
        self.handoff_notified = False
        self.session_complete = False
        self.unanswered_count = 0
        self.qualification_data = {
            "business_type": None,
            "team_size": None,
            "workspace_type": None,
            "booking_duration": None
        }
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")


    def chat(self, user_message: str) -> dict:
        """Send a user message and return the structured agent response."""
        if not self.history:
            # First turn: return greeting directly to avoid LLM startup latency/role confusion
            response = {
                "message": "Hello! Welcome to NexHub Co-Working Space. I'm Closira, your friendly AI customer support assistant. How can I help you today?",
                "stage": "answering_question",
                "confidence": 1.0,
                "escalate": False,
                "escalate_reason": "",
                "qualification_data": {
                    "business_type": None,
                    "team_size": None,
                    "workspace_type": None,
                    "booking_duration": None
                },
                "session_complete": False
            }
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": response["message"]})
            return response

        # Append any stage-specific instruction hints to the user turn
        augmented_message = self._augment_message(user_message)
        self.history.append({"role": "user", "content": augmented_message})

        response = self._call_api()

        # Store assistant reply in history (just the message text for context)
        self.history.append({"role": "assistant", "content": response.get("message", "")})

        # Post-process: update internal state from response
        self._update_state(response, user_message)

        return response


    def _augment_message(self, user_message: str) -> str:
        """Append conversational memory hint to the customer message so the model remembers preferences."""
        collected = {k: v for k, v in self.qualification_data.items() if v is not None}
        collected_str = json.dumps(collected)
        return (
            f"{user_message}\n\n"
            f"[SYSTEM HINT: Stored conversation memory: {collected_str}. "
            f"Extract new details from user's message, merge them, and output in 'qualification_data'. "
            f"CRITICAL: If the user asks about any service, policy, amenity, or feature NOT explicitly mentioned in the SOP "
            f"(e.g., catering, pets, student discounts, customized layouts, cabin sizes/dimensions/square footage, virtual office pricing, etc.), "
            f"you MUST set confidence=0.0, escalate=true, and stage='escalation' in your JSON, state that the info is unavailable, and recommend "
            f"they contact the team using the email/WhatsApp/phone numbers from the SOP contact section. "
            f"If the user says 'thank you', 'thanks', 'ok thank you', 'goodbye', or similar wrapping-up remarks, "
            f"you MUST set stage='closing' and session_complete=true in your JSON response.]"
        )

    def _call_api(self, retry: int = 0) -> dict:
        """Call OpenAI API and parse JSON response. Retries on failure."""
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                temperature=0.3,        # low temp = more deterministic, safer for support
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *self.history
                ]
            )
            raw = completion.choices[0].message.content
            return json.loads(raw)

        except json.JSONDecodeError as e:
            if retry < MAX_RETRIES:
                time.sleep(1)
                return self._call_api(retry + 1)
            return self._fallback_response(f"JSON parse error: {e}")

        except Exception as e:
            if retry < MAX_RETRIES:
                time.sleep(2)
                return self._call_api(retry + 1)
            return self._fallback_response(str(e))

    def _fallback_response(self, error: str) -> dict:
        """Safe fallback when API fails — always escalates."""
        return {
            "message": "I'm having a bit of trouble right now. Let me connect you with a team member who can help immediately.",
            "stage": self.stage,
            "confidence": 0.0,
            "escalate": True,
            "escalate_reason": f"API/parsing error: {error}",
            "qualification_data": self.qualification_data,
            "session_complete": False
        }

    def _update_state(self, response: dict, original_message: str):
        """Update agent state based on API response."""

        # Merge qualification data (accept any keys returned by the model)
        incoming_qd = response.get("qualification_data", {})
        if isinstance(incoming_qd, dict):
            for field, val in incoming_qd.items():
                if val and val not in (None, "null", "", "None", "unknown"):
                    self.qualification_data[field] = val

        # Sync response's qualification_data with our canonical store
        response["qualification_data"] = self.qualification_data

        # Stage transitions
        new_stage = response.get("stage", self.stage)
        valid_stages = ("answering_question", "recommending_plan", "booking_help", "escalation", "closing", "summary")
        if new_stage in valid_stages:
            self.stage = new_stage

        # Track unanswered questions for auto-escalation
        confidence = float(response.get("confidence", 1.0))
        if confidence < 0.6:
            self.unanswered_count += 1
        if self.unanswered_count >= UNANSWERED_THRESHOLD and not response.get("escalate"):
            response["escalate"] = True
            response["escalate_reason"] = f"Auto-escalated: {self.unanswered_count} low-confidence answers in session"

        # Log escalation
        if response.get("escalate") and not self.escalated:
            self.escalated = True
            escalate_reason = response.get("escalate_reason", "unknown")
            
            # Classify critical escalation
            reason_lower = escalate_reason.lower()
            user_msg_lower = original_message.lower()
            critical_keywords = ["abuse", "abusive", "threat", "threatening", "anger", "angry", "frustrated", "frustration", "disgusting", "dirty"]
            if any(k in reason_lower or k in user_msg_lower for k in critical_keywords):
                self.critical_escalation = True
                
            log_escalation(
                session_id=self.session_id,
                reason=escalate_reason,
                trigger_message=original_message,
                stage=self.stage,
                confidence=confidence
            )

        # Session complete
        if response.get("session_complete"):
            self.session_complete = True
            log_summary(self.session_id, self._build_summary(response))

    def _build_summary(self, final_response: dict) -> dict:
        """Build a structured end-of-session summary."""
        return {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "total_turns": len([m for m in self.history if m["role"] == "user"]),
            "final_stage": self.stage,
            "escalated": self.escalated,
            "qualification_data": self.qualification_data,
            "unanswered_count": self.unanswered_count,
        }

    def generate_summary(self) -> str:
        """Force-generate a conversation summary (called at session end)."""
        summary_prompt = (
            "The customer conversation is now ending. Please generate a comprehensive session summary "
            "as a single plain text string (containing newlines) inside the 'message' field of your JSON response. "
            "Do NOT output a JSON object or dictionary inside the 'message' field; 'message' must be a raw string. "
            "Use the following Markdown template for the text inside 'message':\n\n"
            "**Customer Intent:** <what they wanted>\n"
            "**Key Details Collected:**\n- <detail 1>\n- <detail 2>\n"
            "**SOP Gaps Identified:** <list any questions or topics asked by the user that were not mentioned in the SOP, or 'None' if everything was answered>\n"
            "**Recommended Next Action:** <what NexHub team should do next to help the customer>\n\n"
            "Set session_complete=true and stage='summary' in your JSON keys."
        )
        self.history.append({"role": "user", "content": summary_prompt})
        response = self._call_api()
        self.history.append({"role": "assistant", "content": response.get("message", "")})
        self._update_state(response, "[session summary request]")
        return response.get("message", "No summary generated.")
