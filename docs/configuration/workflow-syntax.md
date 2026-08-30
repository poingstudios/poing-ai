# Workflow Reference & Inputs

Complete reference of all inputs, environment variables, and parameters accepted by the Poing AI action.

---

## Action Inputs (`action.yml`)

| Input | Description | Default | Required |
|---|---|---|---|
| `mode` | Execution mode: `review`, `triage`, or `sync` | `review` | No |
| `gemini-api-key` | Google Gemini API Key | `""` | Optional (if using Gemini) |
| `openai-api-key` | OpenAI / DeepSeek API Key | `""` | Optional (if using OpenAI) |
| `api-base` | Custom Base URL for OpenAI/Ollama compatible endpoint | `""` | No |
| `provider` | AI Provider: `gemini`, `ollama`, `openai`, `deepseek`, or `auto` | `auto` | No |
| `model` | Specific model name to use | Provider default | No |
| `github-token` | GitHub Token for posting reviews and labels | `${{ github.token }}` | No |
| `number` | PR or Issue number to process | Auto-detected | No |
| `max-chars` | Max characters per diff batch chunk | `100000` | No |
| `max-batches` | Max number of diff batches to analyze | `10` | No |
| `fail-on-changes` | Exit with code 1 if changes are requested | `false` | No |

---

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Gemini API Key |
| `OPENAI_API_KEY` | OpenAI API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `OLLAMA_HOST` / `OLLAMA_BASE_URL` | Ollama server URL (e.g. `http://localhost:11434`) |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub API Token |
| `MODE` | Mode: `review`, `triage`, `sync` |
| `MODEL_NAME` | Primary model name |
| `FALLBACK_MODELS` | Comma-separated list of fallback models |
