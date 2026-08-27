# 🤖 Poing Reviewer

[![CI](https://github.com/poingstudios/poing-reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/poingstudios/poing-reviewer/actions)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Poing Reviewer** is an AI-powered code review, issue triage, and multi-platform dependency automation bot powered by Google Gemini. Tailored for game engine plugins (**Godot**, **Unity**, **Unreal**) and multi-platform native mobile ecosystems (**Android**, **iOS**, **C#**, **C++**, **Rust**, **Python**).

---

## ✨ Features

- 🔍 **Intelligent Code Review**: Analyzes PR diffs with ground-truth full-file context, engine-specific guidelines, live GitHub Action verification, and thumbs-down (`👎`) false positive learning.
- 🏷️ **Automated Issue & PR Triage**: Classifies incoming issues into labels, assigns priority (`high`, `medium`, `low`), checks duplicates, and ensures repository labels exist.
- 📦 **Multi-Platform Dependency Sync**: Automatically checks and bumps upstream dependencies (Google Maven, Maven Central, Swift Package Manager, Godot Releases, Unity UPM, NuGet) and writes structured AI release notes.
- 💻 **Local CLI Mode**: Review local git diffs and test triage/dependencies directly from your terminal without opening a PR.
- 🧩 **Pluggable & Extensible**: Modular Clean Architecture ready for RAG vector search, local LLMs (Ollama / vLLM), and remote models.

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
  pull_request:
    types: [opened, synchronize, review_requested]
  issues:
    types: [opened]

jobs:
  review:
    if: github.event_name == 'pull_request'
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

### 2. Dependency Sync Cron Workflow

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
        uses: actions/checkout@v4

      - name: Run Dependency Sync
        id: sync
        uses: poingstudios/poing-reviewer@v1
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

## 🛠️ Configuration (`.github/poing.json`)

Configure repository rules in `.github/poing.json`:

```json
{
  "engine": "auto",
  "review": {
    "model": "gemini-3.5-flash",
    "fallback_models": ["gemini-3.1-flash-lite", "gemini-3-flash-preview"],
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

Install the package locally:

```bash
pip install -e .
```

### Review local working directory diff:
```bash
poing-reviewer --mode review --local
```

### Check and preview dependency updates (dry run):
```bash
poing-reviewer --mode sync --local --dry-run
```

### Simulate issue triage:
```bash
poing-reviewer --mode triage --local --issue-title "App crashes on launch" --issue-body "Null pointer on Android 14"
```

---

## 📄 License

Apache License 2.0.
