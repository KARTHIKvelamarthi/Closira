# Closira AI Support Agent Prompt Design

This document explains the design, functionality, and importance of the system prompt used by the Closira AI assistant. The prompt is designed to guide the model's behavior, prevent hallucinations, extract customer details, manage conversation flow, and structure the output data.

---

## 1. Identity Definition and Role

### What it does:
Defines the model as "Closira," a friendly and consultative customer support assistant that handles incoming customer queries on behalf of the business defined in the knowledge base.

### Importance:
Establishing a clear persona ensures that the model speaks from the perspective of the business and maintains a helpful support posture. It prevents the model from acting as a generic text completion engine or adopting the user's role.

---

## 2. Knowledge Base (SOP) Injection

### What it does:
Dynamically inserts the Standard Operating Procedure text into the prompt. The model is instructed that this is its only source of truth.

### Importance:
Injecting the SOP directly into the context makes the agent's knowledge accurate and bounded. Instead of relying on pre-trained information or external databases, the model references the provided document to answer questions about plans, pricing, hours, location, and guest policies.

---

## 3. Persona and Tone Rules

### What it does:
Provides instructions on language style and sentence length:
* Sets a professional, warm, and concise tone.
* Restricts response length to two to four sentences, unless list formatting is needed to compare options.
* Expressly bans generic chatbot filler words like "Certainly!", "Absolutely!", or "Great question!".

### Importance:
* Short messages prevent customer fatigue on chat platforms.
* Eliminating robotic filler words makes the interaction feel more authentic and less like an automated sales funnel.
* Low temperature settings (0.3) enforce consistency, keeping responses simple and focused.

---

## 4. Strict Hallucination Guardrails

### What it does:
Places absolute restrictions on what the model is allowed to say:
* Prohibits guessing, estimating, or inventing any detail (such as cabin sizes, dimensions, or staff names) not explicitly written in the SOP.
* Commands the model to state that information is unavailable if a topic is not in the SOP, extract the contact details from the SOP, and ask the user to contact the human support team.

### Importance:
Ensures the business does not share incorrect or speculative information. If a detail is missing from the SOP, the model safely halts automated answers and provides the correct email or phone number for human follow-up.

---

## 5. Data Extraction and Conversational Memory

### What it does:
Instructs the model to extract and remember key customer details (business type, team size, workspace type, and booking duration) from user messages. The currently collected data is injected into the prompt as a hint, and the model must merge new details without overwriting existing ones.

### Importance:
Allows the agent to build context over multiple turns. By remembering that a user has a team of four, the agent avoids asking redundant questions later, making the conversation feel natural.

---

## 6. Conversation Stages

### What it does:
Defines six stages to track the state of the conversation:
* `answering_question`: For handling general inquiries about hours, amenities, and policies.
* `recommending_plan`: For comparing workspace options based on user needs.
* `booking_help`: For explaining standard booking requirements.
* `escalation`: For handling out-of-scope queries or customer frustration.
* `closing`: For wrapping up when the customer uses polite closing phrases.
* `summary`: For the final end-of-chat state.

### Importance:
Tracking conversation stages allows the backend application to trigger appropriate system logs, save records, or flag human agents for follow-up when the conversation shifts.

---

## 7. Proactive Qualification and Conversation Flow

### What it does:
Commands the model to actively ask follow-up questions when a customer shows interest in workspaces or services (such as asking for team size if they inquire about a private cabin), rather than waiting for the customer to supply this details unprompted. It limits the agent to asking one question at a time to prevent interrogation.

### Importance:
Helps qualify leads naturally. If a user asks about a service, the agent guides them to the correct version of that service by asking clarifying questions, mirroring the behavior of a helpful human receptionist.

---

## 8. Confidence Scoring

### What it does:
Requires the model to evaluate the reliability of its response on a scale of 0.0 to 1.0:
* 0.9–1.0 indicates the answer is directly supported by the SOP text.
* 0.6–0.89 indicates the answer is partially addressed or slightly inferred.
* Below 0.6 indicates the model lacks information or the topic is not covered in the SOP.

### Importance:
Serves as an automated quality check. If the model determines it cannot confidently answer a question based on the SOP, the confidence score drops, letting the application know it needs to escalate.

---

## 9. Escalation Triggers

### What it does:
Provides a set of rules that require the model to flag the conversation for a human:
* Low confidence scores (below 0.6).
* Customer anger, frustration, or explicit request for a human.
* Inability to answer two or more questions.
* Complex topics such as bulk memberships, price negotiations, or legal issues.

### Importance:
Protects user experience. When a query is too complex for the automation or the user becomes frustrated, the model triggers an escalation to ensure a human staff member takes over.

---

## 10. Session Completion

### What it does:
Mandates that the model mark the session as complete (`session_complete = true`) and transition to the closing stage when the user uses wrapping-up phrases like "thank you", "thanks", "that is all", or "goodbye".

### Importance:
Triggers the system to finalize logs and print the conversation summary to the terminal as soon as the customer indicates they are finished, ensuring clean conversation wrap-ups.

---

## 11. Structured JSON Output Format

### What it does:
Forces the model to output its entire response as a structured JSON object containing exact keys: `message`, `stage`, `confidence`, `escalate`, `escalate_reason`, `qualification_data`, and `session_complete`.

### Importance:
A strict schema is necessary for the python code to parse the assistant's replies. By avoiding markdown code fences or conversational conversational preambles, the system can reliably extract data fields and update the user interface without parsing errors.
