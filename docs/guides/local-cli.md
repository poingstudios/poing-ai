# Local Terminal CLI

Run code reviews, triage evaluations, and dependency checks directly on your local machine before pushing code.

---

## 💻 CLI Commands

### 1. Code Review

```bash
# Review uncommitted changes in current working tree
poing --local

# Review only staged changes
poing --local --staged

# Compare against a specific git target or base branch
poing --local --diff-target main

# Output structured JSON for piping or CI
poing --local --format json
```

---

### 2. Autonomous Code Repair (`--fix`)

```bash
# Automatically repair bugs with Google Antigravity Agent
poing --local --fix --provider antigravity

# Automatically repair bugs using local Ollama (100% offline)
poing --local --fix --provider ollama

# Repair bugs using Gemini Flash
poing --local --fix --provider gemini --model gemini-3.7-flash
```

---

### 3. Issue Triage

```bash
poing --mode triage --local \
  --issue-title "App crash on iOS 18" \
  --issue-body "Null pointer exception when initializing plugin on startup."
```

---

### 3. Dependency Check

```bash
# Check for available dependency updates (dry-run)
poing --mode sync --local --dry-run
```

---

## 🤖 Using Different AI Backends

### Google Gemini (Cloud)
```bash
export GEMINI_API_KEY="your-api-key"
poing --local
```

### Local Ollama / vLLM (Offline / Private)
```bash
# Ensure Ollama is running (`ollama serve`)
poing --local --provider ollama --model deepseek-r1:latest
```

### OpenAI / DeepSeek
```bash
export OPENAI_API_KEY="sk-..."
poing --local --provider openai --model gpt-4o-mini
```
