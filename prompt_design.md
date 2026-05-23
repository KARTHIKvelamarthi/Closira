# Closira RAG Prompt Design

This document details the architecture, design patterns, and constraints of the prompts used in the RAG-enabled Closira AI assistant. 

---

## 1. Design Objectives

The prompt design is structured to achieve three primary goals:
1. **Factual Grounding**: Ensure the assistant answers queries using only the provided Standard Operating Procedure (SOP) context, eliminating guesses or hallucinations.
2. **Structured JSON Output**: Enforce a strict JSON schema for every response, allowing the Python runtime to track conversation state, extract metadata, and trigger system actions.
3. **Conversational Memory Integration**: Feed previous user details back into the LLM context to prevent repetitive questions and enable natural lead qualification.

---

## 2. Core Prompt Structure

The agent uses a two-part prompt architecture on each turn: a dynamic system prompt containing the retrieved context, and a system hint appended to the user's message.

### A. Dynamic System Prompt (`prompts/system_prompt_rag.py`)
This prompt establishes the agent's identity, tone constraints, stage-based behaviors, and safety guardrails. It has a placeholder where the RAG retriever injects matching SOP text.

If no relevant match is found in the SOP, the retriever injects:
`[No matching information found in the Standard Operating Procedure.]`

The system prompt instructs the model:
* Refer only to the facts directly stated in the context.
* If the context contains the empty bracket note above, or does not contain details to answer the query, the model must set `confidence` to 0.0, `escalate` to true, and explain that the information is unavailable.
* Maintain a professional, consultative, and warm receptionist persona.
* Restrict responses to two to four sentences.

### B. User Message Augmentation (System Hint)
To maintain state across turns, the Python application appends a hint block to the end of the user's message before sending it to the LLM:

`[SYSTEM HINT: Stored conversation memory: {"team_size": 4, "workspace_type": "Private Cabin"}. Extract new details from the user's message, merge them, and output in 'qualification_data'. If the user asks about anything not in the SOP, set confidence=0.0, escalate=true, and stage='escalation'. If the user wraps up, set stage='closing' and session_complete=true.]`

This serves as a high-priority instruction modifier that reinforces the memory state and exit conditions.

---

## 3. JSON Output Schema

To integrate the LLM with the Python application, the model is instructed to output a single JSON object. The keys are defined as follows:

* **`message`** (string): The conversational response to the user.
* **`stage`** (string): The current conversation state (`answering_question`, `recommending_plan`, `booking_help`, `escalation`, `closing`, or `summary`).
* **`confidence`** (float): A self-evaluation score from 0.0 to 1.0 representing how well the SOP covers the user's query.
* **`escalate`** (boolean): True if the conversation requires handoff to a human.
* **`escalate_reason`** (string): Explains why the handoff was triggered.
* **`qualification_data`** (object): Tracks parameters (`business_type`, `team_size`, `workspace_type`, and `booking_duration`).
* **`session_complete`** (boolean): True if the session has concluded.

---

## 4. Handling Dialogue Scenarios

### In-SOP Queries
When the user asks a question covered in the SOP (e.g., pricing or locations), the retriever injects the relevant chunk. The model reads the context, drafts a direct answer, sets `confidence` to 1.0, and keeps the stage as `answering_question`.

### Out-of-SOP Queries & Hallucination Guardrails
If the query is unaddressed in the SOP (e.g., asking about parking details or custom office layouts), the retriever injects an empty context warning. The system prompt instructs the model to:
1. Identify that the details are missing.
2. State the limitation clearly in the `message` field.
3. Recommend contacting the team at the phone/email extracted from the SOP.
4. Set `confidence` to 0.0, `escalate` to true, and `stage` to `"escalation"`.

### Lead Qualification
When a user expresses interest in booking or plans, the agent transitions to `recommending_plan` or `booking_help`. The system prompt commands the model to:
* Look at the current `qualification_data` memory.
* Ask friendly, open-ended follow-up questions to fill in missing details (e.g., asking for team size if they mention a cabin).
* Ask only **one question at a time** to avoid sounding like an interrogation.

### Proactive Qualification Rule
Rather than waiting for the user to volunteer details, the prompt
instructs the model to look up the relevant SOP entry when interest
is expressed, identify what variables are needed for that specific
service (e.g. team size for cabins, duration for meeting rooms,
frequency for hot desk), and ask about those specifics one at a time.

Example: User says "I'm interested in a private cabin"
→ SOP shows cabins come in 2-person and 4-person options
→ Agent asks: "We have cabins for teams of 2 or 4 — how many are on your team?"

This was added because testing showed the model would passively
collect details only if the user volunteered them, never asking
proactively. The explicit rule fixes this behaviour.

### Escalation Triggers
Handoffs are triggered by the following conditions:
* **Missing SOP Information**: Confidence score drops to 0.0.
* **Negative Sentiment / Frustration**: If the user shows anger, the model detects the tone shift, sets `escalate` to true, and transitions to the escalation stage.
* **Direct Handoff Request**: If the user asks to speak to a human.
* **Unanswered Counts**: If the model scores a low confidence (< 0.6) on two consecutive turns, the python runtime automatically overrides and escalates.
Additional escalation triggers enforced by the prompt:
- Complaint about staff, cleanliness, or facilities
- Medical emergency or safety concern  
- Legal, contractual, or enterprise deal questions
- Pricing negotiation requests

### Closing and Summary Generation
When the user says "thank you" or indicates they are done, the agent transitions to `closing`. The application then requests a final summary. 

The prompt instructs the model to populate the `message` field with a Markdown summary string structured as:
* **Customer Intent**
* **Key Details Collected**
* **SOP Gaps Identified**
* **Recommended Next Action**

### Session Completion Detection
The prompt includes an explicit keyword list to detect when a user
is wrapping up: "thank you", "thanks", "that's all", "bye",
"no more questions", "ok thank you". When any of these are detected,
the model sets session_complete=true and stage="closing".

This explicit list was necessary because smaller local models
(Llama 3.1, Gemma) often miss implicit closing cues without it.

To prevent the model from nesting JSON objects inside the `message` key (which confuses parser scripts), the summary prompt explicitly forbids returning a dictionary structure under `"message"` and mandates a raw Markdown string.
