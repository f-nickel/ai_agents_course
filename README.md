# KiWoAI: Intelligent Event Assistant

A small ReAct-style LLM agent that helps visitors find activities during **Kieler Woche (KiWo)** — the sailing and festival event held annually in Kiel, Germany.

This project is primarily an educational exercise in building a tool-using agent loop **from scratch**, without relying on a framework's built-in agent abstractions. The agent reasons in a THOUGHT → ACTION → OBSERVATION loop, calls tools to gather weather, date, and event information, and keeps track of everything it learns in an external **state** object that lives outside the LLM's own memory.

## How it works

- The agent communicates entirely in JSON. Every model response is a single JSON object describing a `thought`, an `action` to take, the `args` for that action, and an updated `state`.
- A lightweight Python loop parses each response, dispatches the requested action to a real Python function, and feeds the result back to the model as an `observation`.
- The `state` (current date, weather, time, and inferred user preferences) is stored outside the model and re-injected into the system prompt on every turn, so the agent doesn't have to rely on inferring past context from the raw conversation log alone.

### Available tools

| Action | Arguments | Description |
|---|---|---|
| `get_date` | none | Returns the current datetime (during KiWo 2026, or a random datetime within the KiWo window otherwise, for testing) |
| `get_weather_kiel` | `target_datetime` (ISO date string) | Returns forecast or historical weather for Kiel on the given date |
| `get_activities` | `description` (string) | Returns matching KiWo programme entries for a described type of activity |
| `answer` | `answer_text` (string) | Sends a message to the user and waits for their reply |

## Requirements

- Python 3.9+
- An OpenAI-compatible chat completions client (this project uses the `openai` Python package)
- A `programm.json` file in the project root containing the KiWo event programme (not included — see [Data](#data) below)

Install dependencies:

```bash
pip install openai requests
```

## Configuration

The agent can run against two different backends, toggled via the `PROVIDER` variable at the top of the script:

| `PROVIDER` value | Backend | Notes |
|---|---|---|
| `"ollama"` | Local [Ollama](https://ollama.com/) server | Requires Ollama running locally with the `qwen3:4b` model pulled |
| `"hf"` | [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers) | Requires an `HF_TOKEN` environment variable |

Set your Hugging Face token before running (if using the `"hf"` provider):

```bash
export HF_TOKEN="your_token_here"
```

## Usage

```bash
python agent.py
```

The agent will greet you and ask how it can help. Type your questions or preferences naturally — the agent will decide what to look up (date, weather, activities) and when to respond. Type `exit` or `quit` at any prompt to end the session.

## Data

The agent expects a `programm.json` file describing the KiWo event schedule (times, locations, activity types). This file is not included in the repository — supply your own, structured as an array/object of events, matching the shape your `get_activities` consumers expect.

## Known limitations

This is a small educational prototype, not a production system. Some notable caveats:

- **No schema validation** on the state or tool arguments returned by the model — malformed output from the LLM can produce runtime errors or corrupted state.
- **No network error handling** around the weather API calls; a failed request will crash the loop.
- **Unbounded conversation log** — the full message history grows for the entire session with no trimming or summarization.
- **JSON-only output is enforced only via prompting** (plus `response_format={"type": "json_object"}` on supported backends), not a strict schema — smaller/local models may occasionally produce invalid JSON.

## Project structure

```
.
├── agent.py         # Main agent loop, tool definitions, and system prompt
├── programm.json    # KiWo event programme data (not included)
└── README.md
```

## License

Add a license of your choice (e.g. MIT) if you plan to share this publicly.