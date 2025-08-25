# Quick‑Query Architecture Overview

## Table of Contents
1. Repository Layout
2. High‑Level Data Flow
3. Module Responsibilities
4. Detailed Data Flow per Mode (completion / chat / template)
5. Refactoring Opportunities
   5.1 Architectural Improvements
   5.2 Code Quality & Maintainability
   5.3 Testability & Extensibility
6. Mermaid Diagram of System Flow

---

## 1️⃣ Repository Layout

| Path | Description |
|------|-------------|
| `cli.py` | Entry point: parses CLI arguments, loads configuration, boots the server and dispatches to the chosen mode (completion, chat, template). |
| `config.py` | Loads TOML configuration files (`conf.toml`, prompts), resolves profiles, tools, and returns a typed `Profile`. |
| `profile.py` | Immutable dataclass representing a single profile – model, credentials, tool list, extra request parameters, etc. |
| `openapi.py` | Wrapper around an OpenAI‑compatible HTTP API (`OpenAIServer`). Handles request construction and streaming response handling. |
| `streaming_response.py` | Implements `StreamProcesser`, turning raw streamed chunks into higher‑level messages and optional chain‑of‑thought (CoT) handling. |
| `formatter.py` | Provides output formatting (plain text vs Markdown) for terminal display or file writing (`get_formatter`). |
| `message.py` | Contains `MessageProcessor`; filters/rewrites messages, applies the optional regex‑based "re‑think" transformation and prepares payloads. |
| `chat.py` | Implements interactive chat mode via the `Chat` class; manages conversation history and streaming UI. |
| `prompter.py` | Handles single‑prompt (completion) mode: builds initial state and runs `run_prompt`. |
| `template.py` | Logic for Jinja2 templating mode – extracts templates, streams variable data, runs parallel requests (`Templater`). |
| `tools/` package | Built‑in tool implementations (`fs`, `memory`, `coding`, `builtins`). Provides a registry loader used by `config.py`. |
| `__init__.py` | Package metadata (`__version__`). |

---

## 2️⃣ High‑Level Data Flow (All Modes)

1. **CLI Start** – `cli_entrypoint()` → `parse_arguments()` → `args`.
2. **Configuration Loading** – `setup_api_params(args)`
   - Calls `get_profile()` → loads a `Profile` from `conf.toml`.
   - Resolves credentials, tools (via `load_tools_from_toml`).
3. **Server Initialization** – `OpenAIServer(host, api_key, model, …)`.
4. **Streaming Processor** – `StreamProcesser(cot_token, min_chunk_size)`.
5. **Formatter** – `get_formatter(cot_block_fd, format_markdown)`.
6. **Message Processing** – `MessageProcessor(re2_flag)`.
7. **Mode Dispatch (`args.mode`)**
   - *completion / prompt* → `run_prompt(initial_state, server, stream_processer, formatter, mp)`.
   - *chat* → instantiate `Chat` and call `.run()`.
   - *template* → set up Jinja2 extractor, variable streamer, then run `Templater`.
8. **During a Request**
   - `MessageProcessor` builds the payload (system prompt + user prompt).
   - Payload sent via `OpenAIServer.request_stream()` → yields raw JSON chunks.
   - `StreamProcesser` buffers / splits CoT blocks, passes to `Formatter`.
   - Output displayed or written according to the mode.

---

## 3️⃣ Module Responsibilities (Brief)
- **cli.py** – orchestrates everything; minimal business logic.
- **config.py** – pure I/O and validation, produces typed objects.
- **profile.py** – value object, immutable data holder.
- **openapi.py** – low‑level HTTP client, abstracts away endpoint details.
- **streaming_response.py** – transforms streamed bytes into logical message units (CoT handling).
- **formatter.py** – UI layer: plain text vs Markdown rendering.
- **message.py** – payload preparation; optional regex rewriting.
- **chat.py**, **prompter.py**, **template.py** – mode‑specific orchestration, each exposing a single `run` function/class.
- **tools/** – plug‑in style utilities that can be called by the model via OpenAI function calling.

---

## 4️⃣ Detailed Data Flow per Mode
### a) Completion (single prompt)
1. CLI receives `--prompt` / `--prompt-file` (or stdin).
2. `InitialState` is built in `cli.py`.
3. `run_prompt()` → uses `MessageProcessor` to embed the system‑prompt and user prompt into the request body.
4. Request sent through `OpenAIServer` -> streamed response.
5. `StreamProcesser` optionally splits CoT blocks, forwards to `Formatter` -> printed on stdout.

### b) Chat (interactive)
1. `Chat(initial_state, server, …)` creates a persistent conversation object.
2. Loop: read user input → feed into `MessageProcessor` together with full chat history → request → streaming → formatted output displayed → appended to history.
3. Supports optional regex re‑think (`--re2`) and structured streaming flags per profile.

### c) Template
1. Load Jinja2 template (either a file or a field in the variable payload).
2. Stream variable objects from JSON array / JSONL source (file, stdin, or inline `-v`).
3. For each variable set, spawn an independent request using the same pipeline as completion.
4. Concurrency controlled by `--concurrency` (defaults to CPU count). Results written in JSONL format (`prompt`, `variables`, `response`).

---

## 5️⃣ Refactoring Opportunities
### 5.1 Architectural Improvements
| Area | Issue | Suggested Refactor |
|------|-------|--------------------|
| CLI Coupling | `cli.py` directly creates server, formatter, stream processor, message processor – hard to test in isolation. | Extract a **Bootstrap** module that builds an `ApplicationContext` (config, server, processors) and injects it into mode classes. |
| Configuration Loading | Logic scattered across several functions (`load_toml_file`, `read_profiles`, `get_profile`). | Consolidate into a **ConfigLoader** class with clear responsibilities (validation, defaults, profile resolution). |
| Tool Registration | Mutating shared dict via `load_tools_from_toml`. | Introduce a **PluginRegistry** that registers tool factories once and provides an immutable view to callers. |
| Streaming & Formatting Separation | `StreamProcesser` knows about CoT tokens *and* directly calls the formatter. | Split into **ChunkAssembler** (buffering, CoT extraction) and **OutputRenderer** (formatter). |
| Mode Dispatch Logic | Large `match args.mode:` block in `cli.py`. | Move each mode implementation to its own class (`CompletionRunner`, `ChatRunner`, `TemplateRunner`) implementing a common interface (`run(context)`). |

### 5.2 Code Quality & Maintainability
- Add **type hints** throughout the repo (many functions lack return annotations).
- Replace repeated `if isinstance(..., str):` list‑conversion with a small helper `ensure_list(x)`.
- Consolidate system‑prompt loading logic into a single function (`load_system_prompt(args, profile)`).
- Use the standard **logging** module instead of raw `print` for debug/info messages.

### 5.3 Testability & Extensibility
| Target | Current Gap | Suggested Fix |
|--------|--------------|---------------|
| `OpenAIServer` | Direct `requests` calls; no injection point, hard to mock. | Accept a **Transport** interface (e.g., `httpx.AsyncClient`) that can be swapped in tests. |
| `MessageProcessor` | Regex flag (`re2`) toggles behavior internally – not easily unit‑tested. | Provide a **strategy pattern** where each processing step is a separate callable injected at construction. |
| `TemplateRunner` | Concurrency uses raw `multiprocessing.cpu_count()`; no explicit executor control. | Expose concurrency via config and wrap with `concurrent.futures.ThreadPoolExecutor`/`ProcessPoolExecutor`. |

---

## 6️⃣ Mermaid Diagram of System Flow
```mermaid
flowchart TD
    A[CLI Entry (cli_entrypoint)] --> B{Parse Args}
    B --> C[ConfigLoader]
    C --> D[Profile Object]
    D --> E[OpenAIServer Init]
    D --> F[Tool Registry Load]
    B --> G[StreamProcessor Init]
    B --> H[Formatter Init]
    B --> I[MessageProcessor Init]

    subgraph ModeDispatch
        J{args.mode}
        J -->|completion| K[CompletionRunner.run()]
        J -->|chat| L[ChatRunner.run()]
        J -->|template| M[TemplateRunner.run()]
    end

    E --> N[HTTP Request (stream)]
    I --> O[Build Payload]
    O --> N
    N --> P[StreamProcessor.buffer]
    P --> Q{CoT Token?}
    Q -- Yes --> R[ChunkAssembler.emit CoT block]
    Q -- No --> S[ChunkAssembler.pass through]
    R --> H
    S --> H

    K & L & M --> H
    H --> T[Display / Write Output]

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#bbf,stroke:#333,stroke-width:1px
    style J fill:#ffb,stroke:#333,stroke-width:1px
```

---

*This document provides a quick‑reference for new contributors to understand the overall structure and possible improvement areas of the Quick‑Query project.*
