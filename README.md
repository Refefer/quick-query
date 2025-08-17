# quick-query

**quick-query** is a command‑line utility for interacting with Large Language Models (LLMs) through any OpenAI‑compatible API (OpenAI, OpenRouter, Cerebras, etc.).  It supports three primary workflows:

1. **Completion** — a single prompt → single response.
2. **Chat** — an interactive REPL‑style conversation.
3. **Template** — generate many completions by feeding a Jinja2 template and a stream of variable records.

The tool is intentionally lightweight: it reads configuration from simple TOML files, builds the request, streams the response, and optionally formats the output as markdown.

---

## Installation

### Using `pip`
```bash
pip install quick-query
```

#### Optional extras
* `markdown` — install the optional markdown formatter (`pip install "quick-query[markdown]"`).
* `jinja` — needed for the *template* mode (`pip install "quick-query[jinja]"`).
* `all` — install everything (`pip install "quick-query[all]"`).

### Using `pipx` (isolated, globally‑available CLI)
`pipx` creates an isolated virtual‑environment for the command while keeping the executable on your `PATH`.
```bash
pipx install quick-query
```
*Prefer `pipx` when you only need the CLI and want to avoid polluting your main Python environment.*

---

## Configuration

quick‑query expects two TOML files placed under ``$XDG_CONFIG_HOME/quick-query`` (fallback to ``~/.config/quick-query``):

| File | Purpose | Example location |
|------|---------|-------------------|
| `conf.toml` | Server definitions, model IDs, credentials, and optional tool specifications. | `examples/conf.toml` |
| `prompts.toml` | Named system prompts that can be selected with `--system-prompt-name`. | `examples/prompts.toml` |

### Minimal `conf.toml`
```toml
[default]
model = "gpt-4o-mini"

[default.credentials]
host = "https://openrouter.ai/api/v1"
api_key = "YOUR_API_KEY"
```

### Minimal `prompts.toml`
```toml
[default]
prompt = "You are a helpful assistant."
```

Both files can contain multiple sections (e.g., `[openrouter]`, `[cerebras]`).  Choose the desired section with `--server` and `--system-prompt-name`.

---

## Command‑line usage

quick‑query is invoked via the `qq` entry‑point (installed by the package).  The top‑level syntax is:
```
qq <mode> [options]
```
where `<mode>` is one of `completion`, `chat`, `template` or `list`.

---

## Global command‑line options
These flags are available for **all** modes (including `list`).  The defaults shown are the values used when the flag is omitted.

| Flag | Description |
|------|-------------|
| `--system-prompt-file` | Path to the TOML file containing system prompts (default: `$XDG_CONFIG_HOME/quick-query/prompts.toml` or `~/.config/quick-query/prompts.toml`). |
| `-sp, --system-prompt-name` | Name of the system‑prompt section in the TOML file (default: `default`). |
| `--conf-file` | Path to the TOML file containing server configuration (default: `$XDG_CONFIG_HOME/quick-query/conf.toml` or `~/.config/quick-query/conf.toml`). |
| `-s, --server` | Name of the server configuration section in `conf.toml` (default: `default`). |
| `-t, --tools` | Loads a set of tools from a TOML file (default: none). |
| `-m, --format-markdown` | When set, formats output as markdown; otherwise plain text (default: disabled). |
| `--cot-block-fd` | File descriptor where chain‑of‑thought (CoT) blocks are emitted (default: `/dev/tty`). |
| `--cot-token` | Tag name used to delimit CoT sections (default: `think`). |
| `--re2` | Enables re‑think prompting (default: disabled). |
| `--min-chunk-size` | Minimum characters to emit per streaming chunk (default: `10`). |

---

## 1. Completion mode
> **Purpose:** Generate a single response for a one‑off prompt. Useful for quick look‑ups, code snippets, or any situation where you only need one answer.
```bash
qq completion \
    -p "Explain the difference between TCP and UDP." \
    --system-prompt-name default \
    --conf-file examples/conf.toml
```
Or read the prompt from a file:
```bash
qq completion -f examples/completion_prompt.txt \
    --conf-file examples/conf.toml
```
The response is printed to stdout.

#### Completion‑specific flags (only these differ from other modes)
| Flag | Description |
|------|-------------|
| `-p, --prompt` | Inline prompt string to send to the model. Mutually exclusive with `-f/--prompt-file`. |
| `-f, --prompt-file` | Path to a file containing the prompt. Allows multi‑line prompts and reuse of saved prompts. |

---

## 2. Chat mode
> **Purpose:** Enter an interactive session where you can have a back‑and‑forth conversation with the model, preserving context across turns.
```bash
qq chat \
    --system-prompt-name default \
    --conf-file examples/conf.toml
```
Enter a REPL where each line you type is sent to the model and the streamed answer is displayed. Use `Ctrl‑D` (EOF) to exit.

#### Chat‑specific flags
> Chat does not introduce any flags that are not already available in the other modes; it relies entirely on the common set of options (system prompt, server selection, formatting, etc.).

---

## 3. Template mode
> **Purpose:** Batch‑process many inputs by applying a Jinja2 template to a set of variable records, then sending each rendered prompt to the model. Ideal for data‑driven generation (e.g., code scaffolding, bulk content creation).
```bash
qq template \
    --template-from-file examples/template_example.j2 \
    --variables-from-file examples/variables_example.jsonl \
    -o results.jsonl \
    --conf-file examples/conf.toml
```
* `--template-from-file` — a Jinja2 template file.
* `--variables` or `--variables-from-file` — JSON (single object) or JSONL (one record per line) providing the variables for each iteration.
* `-o, --output` — write results to a JSONL file; if omitted, results are printed to stdout.

#### Template‑specific flags (unique to this mode)
| Flag | Description |
|------|-------------|
| `--template-from-file` | Path to a Jinja2 template file. Mutually exclusive with `--template-from-field`. |
| `--template-from-field` | Name of the field inside each variable record that contains the template string. |
| `--variables, -v` | Inline JSON string representing variables (single run) — convenient for quick tests. |
| `--variables-from-file, -vj` | Path to a JSONL file where each line is a JSON object of variables. Use `-` to read from stdin. |
| `-o, --output` | Destination file for results (default: stdout). Results are JSONL records with keys `prompt`, `variables`, `response`. |
| `-c, --concurrency` | Number of worker processes for parallel template rendering (default: CPU count). |

---

## 4. List configuration
> **Purpose:** Quickly inspect the currently available system prompts or model configurations without running a query.
```bash
qq list --system-prompts   # shows all prompts in prompts.toml
qq list --models           # shows all server sections in conf.toml
```

#### List‑specific flags (only these apply to the `list` mode)
| Flag | Description |
|------|-------------|
| `--system-prompts` | Display every system prompt defined in the prompts TOML file. |
| `--models` | Display the model configurations (excluding secret `api_key`). |

---

## Development / Release

The project now builds with **PEP 517** via a `pyproject.toml`.  To create a source distribution and a wheel locally, run:

```bash
python -m build .
```

The repository includes a helper script **`publish.sh`** that automates the full release cycle:

| Command | What it does |
|---------|--------------|
| `./publish.sh clean` | Remove previous build artefacts (`build/`, `dist/`, `*.egg-info`). |
| `./publish.sh bump [patch|minor|major]` | Increment the version stored in the `VERSION` file, commit the change, and tag the commit (`vX.Y.Z`). |
| `./publish.sh build` | Run `python -m build` to produce `dist/*.tar.gz` and `dist/*.whl`. |
| `./publish.sh upload` | Upload the contents of `dist/` to PyPI using **twine**.  It reads credentials from `TWINE_USERNAME`/`TWINE_PASSWORD` or `TWINE_API_TOKEN`. |
| `./publish.sh release [patch|minor|major]` | Executes **clean → bump → build → upload** in one step. |

Make the script executable once:

```bash
chmod +x publish.sh
```

Before uploading, ensure the required tools are installed and your PyPI token is set:

```bash
pip install --upgrade build twine
export TWINE_API_TOKEN="pypi-<your-token>"
```

Now you can publish a new version with, for example:

```bash
./publish.sh release minor
```

--- 

## License

quick‑query is dual‑licensed under the **MIT** and **Apache‑2.0** licenses.  See the `LICENSE` files in the repository for full terms.

---

## Contributors

A list of contributors is maintained in the [CONTRIBUTORS](CONTRIBUTORS) file.
