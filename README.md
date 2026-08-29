# 🤖 Poing Reviewer

[![CI](https://github.com/poingstudios/poing-reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/poingstudios/poing-reviewer/actions)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Poing Reviewer** is an AI-powered code review, issue triage, and multi-platform dependency automation bot powered by Google Gemini. Tailored for game engine plugins (**Godot**, **Unity**, **Unreal**) and multi-platform native mobile ecosystems (**Android**, **iOS**, **C#**, **C++**, **Rust**, **Python**).

---

## ✨ Features

- 🔍 **Intelligent Code Review**: Analyzes PR diffs with ground-truth full-file context (reads entire modified files to verify symbols across the whole file).
- 🛡️ **Anti-Hallucination & Live Verification**: Queries the live GitHub API in real time to verify GitHub Action versions and suppresses speculative/vague comments.
- 👎 **Thumbs-Down Learning**: Learns from developer `👎` reactions to permanently eliminate recurring false positives across future runs.
- 🔄 **Thread Auto-Resolution**: Automatically marks review comment threads as resolved via GraphQL when code fixes are pushed.
- 🎮 **Game Engine Analyzers**: Built-in guideline checks for **Godot Engine** (e.g. `:=` typing, `class_name` internal rules), **Unity**, and **Unreal Engine**.
- 🏷️ **Automated Issue & PR Triage**: Classifies incoming issues into labels, assigns priority (`high`, `medium`, `low`), checks duplicates, and ensures repository labels exist.
- 📦 **Multi-Platform Dependency Sync**: Automatically checks and bumps upstream dependencies (Google Maven, Maven Central, Swift Package Manager, Godot Releases, Unity UPM, NuGet) with AI release summaries.
- 🤖 **Official Bot Identity**: Easily runs as `poing-reviewer[bot]` via GitHub App integration ([Setup Guide](docs/github_app_setup.md)).
- 💻 **Local CLI Mode**: Review local git diffs, staged changes, and test triage/dependencies directly from your terminal without opening a PR.
- 🧩 **Pluggable & Extensible**: Modular Clean Architecture ready for Vector RAG search, local LLMs (Ollama / vLLM), OpenAI-compatible APIs, and Google Gemini.

---

## 🚀 Quick Start (GitHub Actions)

Any developer or repository can use **Poing Reviewer** in 2 simple steps:

---

### Step 1: Add your Gemini API Key

1. Get a free API key from **[Google AI Studio](https://aistudio.google.com/)**.
2. In your repository: Go to **Settings ➡️ Secrets and variables ➡️ Actions ➡️ New repository secret**.
3. Name: **`GEMINI_API_KEY`**  
   Value: *Your Gemini API key*.

---

### Step 2: Create Workflow (`.github/workflows/poing-reviewer.yml`)

Create `.github/workflows/poing-reviewer.yml` in your repository:

```yaml
name: "Poing Reviewer"

on:
  pull_request_target:
    types: [opened, synchronize, review_requested]
  issues:
    types: [opened]

jobs:
  review:
    if: github.event_name == 'pull_request_target'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout Code
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Run Reviewer
        uses: poingstudios/poing-reviewer@master
        with:
          mode: review
          github-token: ${{ secrets.GITHUB_TOKEN }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}

  triage:
    if: github.event_name == 'issues'
    runs-on: ubuntu-latest
    permissions:
      issues: write
    steps:
      - name: Checkout Code
        uses: actions/checkout@v7

      - name: Run Triage
        uses: poingstudios/poing-reviewer@master
        with:
          mode: triage
          github-token: ${{ secrets.GITHUB_TOKEN }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

*(Optional: Want the bot to post with the official `poing-reviewer[bot]` avatar? Follow the [GitHub App Setup Guide](docs/github_app_setup.md).)*

---

### 3. Dependency Sync Cron Workflow

Create `.github/workflows/cron-sync-dependencies.yml`:

```yaml
name: "[Cron] Sync Dependencies"

on:
  schedule:
    - cron: '0 0 * * 1' # Every Monday
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Checkout Code
        uses: actions/checkout@v7

      - name: Run Dependency Sync
        id: sync
        uses: poingstudios/poing-reviewer@master
        with:
          mode: sync
          github-token: ${{ secrets.GITHUB_TOKEN }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}

      - name: Create or Update Pull Request
        if: steps.sync.outputs.has_updates == 'true'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          BODY: ${{ steps.sync.outputs.pr_body }}
        run: |
          BRANCH="deps/sync-dependencies"
          git config user.name "poing-reviewer[bot]"
          git config user.email "296332247+poing-reviewer[bot]@users.noreply.github.com"
          git checkout -B "$BRANCH"
          git commit -am "chore(deps): synchronize upstream dependencies"
          git push -f origin "$BRANCH"
          gh pr create --title "chore(deps): sync upstream dependencies" --body "$BODY" --base master || gh pr edit --body "$BODY"
```

---

## ⚙️ Action Inputs Reference

| Input | Description | Required | Default |
|---|---|---|---|
| `mode` | Operation mode: `review`, `triage`, or `sync` | No | `review` |
| `github-token` | GitHub token for PR comments, reviews, or triage labels | No | `${{ github.token }}` |
| `gemini-api-key` | Google Gemini API Key | No | `""` |
| `model` | Primary model name to use | No | `gemini-3.7-flash` |
| `max-chars` | Maximum characters per batch before diff splitting | No | `100000` |
| `max-batches` | Maximum number of batches to review | No | `5` |
| `base-ref` | Base git reference branch for diff calculation | No | `master` |

---

## 🛠️ Configuration (`.github/poing.json`)

Configure optional repository rules in `.github/poing.json`:

```json
{
  "engine": "auto",
  "review": {
    "model": "gemini-3.7-flash",
    "fallback_models": ["gemini-3.6-flash", "gemini-3.5-flash"],
    "max_chars": 100000,
    "max_batches": 5
  },
  "dependencies": {
    "targets": [
      {
        "type": "gdscript_config",
        "paths": ["platforms/android/src/**/config/*.gd", "platforms/ios/src/**/config/*.gd"]
      },
      {
        "type": "gradle",
        "paths": ["platforms/android/build.gradle"]
      },
      {
        "type": "swift_package",
        "paths": ["platforms/ios/Package.swift"]
      }
    ]
  }
}
```

---

## 💻 Local CLI Usage

Install the package locally in editable mode:

```bash
pip install -e .
```

### 1. Running with Local Models (Ollama)

You can run Poing Reviewer 100% locally with zero cloud API keys using **[Ollama](https://ollama.com/)** and models like **DeepSeek-R1**, **DeepSeek-Coder**, **Qwen 2.5 Coder**, or **Llama 3.3**:

```bash
# 1. Start Ollama and pull your preferred model
ollama pull deepseek-r1:latest

# 2. Run local review against your uncommitted changes
poing-reviewer --local --provider ollama --model deepseek-r1:latest
```

### 2. Running with Remote Models

#### Google Gemini (Default)
```bash
export GEMINI_API_KEY="your-gemini-api-key"
poing-reviewer --local --provider gemini --model gemini-3.7-flash
```

#### DeepSeek API (Remote)
```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
poing-reviewer --local --provider deepseek --model deepseek-chat
```

#### OpenAI / OpenAI-Compatible (Groq, OpenRouter, vLLM, LM Studio)
```bash
export OPENAI_API_KEY="your-api-key"
poing-reviewer --local --provider openai --model gpt-4o-mini
```

### 3. Advanced Local Diff Options

```bash
# Review only staged changes (git diff --cached)
poing-reviewer --local --staged

# Review against a specific commit or branch diff
poing-reviewer --local --diff-target "origin/master...HEAD"

# Review specific modified file(s) only
poing-reviewer --local --files src/core/git.py src/services/review_service.py

# Format output as JSON (for tooling integration)
poing-reviewer --local --output json

# Git Pre-commit hook mode (returns exit code 1 on CHANGES_REQUESTED)
poing-reviewer --local --staged --fail-on-changes
```

### 4. Local Issue Triage & Dependency Sync

```bash
# Simulate issue triage locally
poing-reviewer --mode triage --local --issue-title "App crashes on launch" --issue-body "Null pointer on Android 14"

# Check and preview dependency updates (dry run)
poing-reviewer --mode sync --local --dry-run
```

---

## 🪝 Git Pre-Commit Hook Integration

Add Poing Reviewer to your `.git/hooks/pre-commit` to review staged code before committing:

```bash
#!/bin/sh
poing-reviewer --local --staged --provider ollama --model deepseek-r1:latest --fail-on-changes
```

---

## 📄 License

Apache License 2.0.
