# FRIDAY Local AI Policy

## Goal

FRIDAY V1 is designed for private, local inference. During normal operation:

```mermaid
flowchart LR
    U["You"] --> F["FRIDAY"]
    F --> O["Ollama on this PC"]
    O --> M["Local model"]
    F --> R["Your repository"]
    F --> T["Local terminal / tools"]

    X["Cloud LLM"] -. "not used by V1" .- F
```

## Hard boundaries

1. `FRIDAY_OLLAMA_BASE_URL` must resolve to `localhost`, `127.0.0.1`, or `::1`.
2. Ollama model names containing `-cloud` are rejected.
3. FRIDAY does not contain an OpenAI, Anthropic, Gemini, or other remote LLM client.
4. The normal agent path has no cloud fallback.
5. Repository data stays in the local FRIDAY process and local Ollama process during inference.

## Important distinction

The **model download** is a network operation because the model must initially be obtained from a model registry. After the model is installed, FRIDAY's inference path targets the local Ollama server.

For maximum isolation after installation, you can run FRIDAY on a machine/network where outbound internet access is blocked. That should be tested operationally rather than assumed from application code alone.

## Model options

### Qwen3-Coder 30B

A strong starting point for an agentic coding workload. Ollama lists a 19 GB quantized package, 256K context, tool support, and local execution for the 30B version.

```powershell
ollama pull qwen3-coder:30b
ollama run qwen3-coder:30b
```

### Devstral 24B

Another coding-agent-oriented local model. Ollama lists a 14 GB package and 128K context and describes it as suitable for tool-driven software engineering workflows.

```powershell
ollama pull devstral:24b
ollama run devstral:24b
```

Which model is practical depends on your RAM/VRAM. We should select the model after checking your PC hardware rather than guessing.
