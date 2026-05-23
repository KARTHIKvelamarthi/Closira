# Closira Customer Support Agent (Prompt-Based Approach)

This folder contains the original, prompt-based (full-context injection) implementation of the Closira AI customer support agent.

## How it Works
In this approach, the entire content of `sop.json` is converted into a plain text representation and injected directly into the system prompt of the language model on every single conversation turn.

This approach is highly effective and simple for small to medium standard operating procedures (SOPs). However, as the SOP grows, sending the entire document with every message increases token costs and latency.

## Directory Structure
* **`main.py`**: Runs the interactive terminal chat loop.
* **`agent.py`**: Coordinates state transitions, handles LLM completions, and merges conversation memory.
* **`sop.py`**: Reads `sop.json` and renders it recursively to a text format.
* **`logger.py`**: Records session summaries and escalation logs.
* **`prompts/system_prompt.py`**: Formats the base system prompt instructions.
* **`test_transcripts/`**: Contains transcripts of verified dialogue flows using this approach.
* **`prompt_design.md`**: Explains the system prompt directives, memory hints, and confidence scoring.

## How to Run
Ensure your local Ollama server is running with the `llama3.1:8b` model (or you have set your `OPENAI_API_KEY`), and run:

```bash
python prompt_based/main.py
```
