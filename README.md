# PROJECT FRIDAY — V1

Private, PC-first AI engineering assistant.

## V1 privacy requirement

**Local inference only. No cloud LLM fallback.** FRIDAY talks to Ollama through its loopback API and rejects non-local Ollama endpoints and Ollama cloud-model names.

```mermaid
flowchart TD
    U["Developer"] --> F["FRIDAY"]
    F --> O["Ollama - localhost"]
    O --> L["Local coding model"]
    F --> TOOLS["Local tools"]
    TOOLS --> REPO["Repository"]
    TOOLS --> GIT["Git"]
    TOOLS --> TERM["Terminal"]
    CLOUD["Hosted LLM"] -. "not used" .- F
```

## Current V1 goal

FRIDAY can converse, inspect a repository, plan changes, read/search code, edit files, run development commands, inspect Git status/diff, and iterate after tool results.

## Setup

Requirements: Windows 10/11, Python 3.11+, Git, Ollama.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

Copy `.env.example` to `.env` and set `FRIDAY_WORKSPACE` to the repository FRIDAY is allowed to control. Do not point it at the whole `C:\` drive.

Install a local model. Good starting candidates are `qwen3-coder:30b` or `devstral:24b`, but the right choice depends on your machine.

```powershell
ollama pull qwen3-coder:30b
```

Check the local server:

```powershell
curl http://127.0.0.1:11434/api/tags
```

Start FRIDAY:

```powershell
fastapi dev app/main.py
```

Or use the terminal interface:

```powershell
python -m app.cli
```

The CLI performs a local Ollama health/model check at startup.

## Architecture

```mermaid
flowchart TD
    U["Developer"]
    CLI["FRIDAY CLI"]
    API["FastAPI"]
    ORCH["Agent Orchestrator"]
    LLM["Ollama / Local LLM"]
    TOOLS["Tool Registry"]
    MEM["Conversation Memory"]
    FS["Filesystem"]
    GIT["Git"]
    SHELL["Terminal"]

    U --> CLI
    U --> API
    CLI --> ORCH
    API --> ORCH
    ORCH --> LLM
    ORCH --> TOOLS
    ORCH --> MEM
    TOOLS --> FS
    TOOLS --> GIT
    TOOLS --> SHELL
```

## Development workflow

```text
You
  -> "Friday, inspect the authentication flow"
  -> FRIDAY searches/reads repository
  -> FRIDAY explains findings
  -> "Design the change"
  -> FRIDAY proposes plan
  -> "Start building"
  -> FRIDAY requests approval for writes/commands
  -> files change
  -> tests run
  -> git diff reviewed
  -> FRIDAY reports verified result
```

## Roadmap

- V1.0: text-first local coding agent
- V1.1: local speech-to-text + text-to-speech
- V1.2: wake word `Friday`
- V1.3: persistent project memory + pgvector
- V1.4: Home Assistant / room tools
- V2: Pepper's Ghost visual interface
