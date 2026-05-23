# Automated Customer Support Agent

This repository implements a customer support agent named Closira, designed to automate lead qualification, answer FAQs, and handle escalations for coworking spaces. The project showcases two implementation patterns: a full-context prompt-based approach and a dynamic Retrieval-Augmented Generation (RAG) approach.

---

## 1. Project Objectives

The project aims to build an AI assistant that behaves safely, qualifications sales leads naturally, adheres strictly to a company's Standard Operating Procedure (SOP), and hands off to human support whenever it encounters unlisted topics or customer frustration.

The system is designed to run locally on consumer hardware without cost, while remaining fully compatible with cloud-based API endpoints (such as OpenAI) for production deployments.

---

## 2. Project Architecture & Approaches

The repository is organized into two distinct implementations:

### A. Dynamic RAG-Based Approach (Root Directory)
Designed to scale to larger SOP manuals. Instead of sending the entire SOP to the model on every message, this approach dynamically parses the SOP into semantic document chunks and retrieves only the most relevant sections.
* **Key Components**:
  * `main_rag.py`: Terminal-based user interface.
  * `agent_rag.py`: Orchestrates state transitions, builds the dynamic system prompt, and updates qualification memory.
  * `sop_rag.py`: Recursively parses nested JSON structures into logical text chunks without hardcoded keys.
  * `retriever_rag.py`: Handles vector searching using a three-tier fallback mechanism (OpenAI -> SentenceTransformers -> BM25).
  * `logger_rag.py`: Records session summaries and escalation details.

### B. Prompt-Based Approach (`prompt_based/`)
A simpler configuration where the entire SOP text is rendered and injected directly into the system prompt on every turn. Useful for small SOP files that fit comfortably within an LLM's context window.
* **Files**: Located inside the `prompt_based/` folder.

---

## 3. RAG System Data Flow (Input to Output)

When a user sends a message, execution flows between the Python modules based on the conversational state:

```mermaid
flowchart TD
    UserInput([User Message]) ──► MainRAG["main_rag.py (CLI Chat Loop)"]
    
    MainRAG ──►|1. Calls chat| AgentRAG["agent_rag.py (ClosiraRAGAgent)"]
    
    AgentRAG ──►|2. Calls retrieve| RetrieverRAG["retriever_rag.py (ClosiraRAGRetriever)"]
    
    %% SOP parsing dependency
    RetrieverRAG ──►|3. Loads chunks| SopRAG["sop_rag.py (Chunker)"]
    SopRAG ──►|4. Reads| SopJson[(sop.json)]
    
    %% Context Construction
    RetrieverRAG ──►|5. Returns matched chunks| AgentRAG
    AgentRAG ──►|6. Generates prompt| SysPrompt["prompts/system_prompt_rag.py (build_system_prompt_rag)"]
    
    %% LLM Execution
    AgentRAG ──►|7. Sends context + history| LLM([Local Llama or OpenAI])
    LLM ──►|8. Returns structured JSON| AgentRAG
    
    %% Case routing
    AgentRAG ──►|Case: Normal Turn| MainRAG
    
    AgentRAG ──►|Case: Escalation (low confidence / unlisted detail)| LoggerRAG["logger_rag.py (log_escalation)"]
    LoggerRAG ──►|Notifies handoff| MainRAG
    
    AgentRAG ──►|Case: Session Complete (closing input)| MainRAGSummary["main_rag.py (Triggers generate_summary)"]
    MainRAGSummary ──►|Requests final summary| AgentRAG
    AgentRAG ──►|Writes summary| LoggerRAG
```

### Module Execution & Case Routing Rules:

1. **Query & Retrieval**: `main_rag.py` captures the user input and invokes `agent_rag.py`. The agent requests document matches from `retriever_rag.py`.
2. **Dynamic Context Building**: `retriever_rag.py` checks for semantic relevance against the chunks prepared by `sop_rag.py` (which parses `sop.json`). 
   * *Special Case (Plan Recommendation/Booking Help)*: If the current conversational stage is in a qualifying phase, the retriever automatically injects plans and booking policy chunks even if they are not the top semantic hits.
3. **Structured Response Generation**: `agent_rag.py` constructs the system prompt via `prompts/system_prompt_rag.py` and calls the LLM endpoint, forcing a structured JSON output.
4. **State Transition & Case Action**:
   * **Normal Turn Case**: The user's input qualifies a lead details parameter. `agent_rag.py` extracts this, merges it into the persistent session memory, and passes the assistant's reply back to `main_rag.py` to print.
   * **Escalation Case** (Unlisted information, negative sentiment, or low confidence): The agent flags the turn, runs `logger_rag.py` to write to `logs/escalation_log_rag.json`, and hands off the session to a human operator.
   * **Closing / Complete Case**: When closing keywords are matched, the agent transitions the stage to `"closing"`. `main_rag.py` calls the summary generator to fetch a final formatted summary, logs it to `logs/session_summaries_rag.json` via `logger_rag.py`, and exits.


---

## 4. Handling Dialogue Scenarios

### In-SOP Inquiries
If a customer asks a question covered by the SOP (e.g., location, opening hours, pricing), the retriever pulls the corresponding text chunks. The agent answers the question using only those details, sets a high confidence score (1.0), and maintains the stage as `answering_question`.

### Out-of-SOP Inquiries & Hallucination Guardrails
If the user asks about a service or policy not listed in the SOP (e.g., catering options, pets, cabin dimensions), the retriever fails to find a high-similarity match. The system prompt forces the model to state that it does not have the information, provide the team's email and phone number, set `confidence` to 0.0, and set `escalate` to true. This stops the model from hallucinating or guessing details.

### Lead Qualification
When a user asks about renting or booking workspace plans, the agent transitions to `recommending_plan` or `booking_help`. It tracks parameters like `team_size` and `workspace_type` in a persistent memory object. If details are missing, the agent asks consultative, friendly questions (one at a time) to qualify the lead without sounding like an interrogation.

### Escalation Triggers
The Python runtime triggers an immediate human handoff if:
1. **Low Confidence**: The model's self-reported confidence is below 0.6 on two consecutive turns.
2. **Missing Information**: The model cannot answer a question based on the SOP (confidence = 0.0).
3. **Sentiment Trigger**: The model or user message detects anger, frustration, or abusive language.
4. **Direct Request**: The customer asks to speak with a human.

### Session Exit and Summarization
The chat loop exits when the user says goodbye or thank you. The agent transitions to `closing` and sets `session_complete` to true. 

The agent then automatically requests a final summary. The model returns a Markdown string detailing:
* Customer Intent
* Key Details Collected
* SOP Gaps Identified
* Recommended Next Action

This summary is printed to the console and written to `logs/session_summaries_rag.json`.

---

## 5. Technology Choices & Hardware Calibration

### Local Fallback (Ollama & all-MiniLM-L6-v2)
* **Local LLM**: By default, the application runs offline using **Llama 3.1 (8B)** hosted locally via Ollama. This permits unlimited, free local development and testing.
* **Local Retriever**: When running offline, the retriever uses the **`all-MiniLM-L6-v2`** model via the `sentence-transformers` library to calculate query embeddings. It runs completely locally on CPU or GPU.
* **Cosine Similarity Threshold**: We calibrated the local similarity threshold to **`0.30`** to fit MiniLM vector characteristics. This allows exact FAQ mapping (such as matching location queries to the address chunk) while avoiding false matches for out-of-scope queries.
* **Performance Note**: Running two neural networks locally (MiniLM for embeddings and Llama for text generation) on consumer CPUs will introduce latency due to hardware resource competition.

### Transition to OpenAI API
If you set the `OPENAI_API_KEY` environment variable:
* The LLM switches to **`gpt-4o`**.
* The retriever switches to **`text-embedding-3-small`**.
* Vector calculations and text generation are handled entirely on cloud GPU servers, lowering latency to under 2 seconds. The code handles this transition automatically.

---

## 6. Installation & Execution

### Installation
Ensure Python 3.10+ is installed. Clone the repository and install the dependencies:

```bash
pip install -r requirements.txt
```

### Running RAG Mode (Root Directory)
Start your local Ollama server, then run:

```bash
python main_rag.py
```

### Running Prompt-Based Mode (Subfolder)
To run the full-context injection version, run:

```bash
python prompt_based/main.py
```
