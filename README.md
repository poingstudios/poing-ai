# 🤖 Poing AI

[![Documentation](https://img.shields.io/badge/Docs-poingstudios.github.io%2Fpoing--ai-purple?logo=materialformkdocs)](https://poingstudios.github.io/poing-ai/)
[![PyPI](https://img.shields.io/pypi/v/poing-ai.svg)](https://pypi.org/project/poing-ai/)
[![GitHub Actions Marketplace](https://img.shields.io/badge/Marketplace-Poing%20AI-blue?logo=github)](https://github.com/marketplace/actions/poing-ai)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Poing AI** is an AI-powered code review, issue triage, and multi-platform dependency automation bot powered by Google Gemini. Tailored for game engine plugins (**Godot**, **Unity**, **Unreal**) and multi-platform native software (**Android**, **iOS**, **C#**, **C++**, **Rust**, **Python**).

📖 **[Read the Full Documentation](https://poingstudios.github.io/poing-ai/)**

---

## ✨ Features

- 🔍 **Intelligent Code Review**: Full-file ground-truth context with built-in game engine analyzers (**Godot Engine** `:=` static typing & encapsulation rules, Unity, Unreal).
- 🛡️ **Anti-Hallucination**: Queries live GitHub releases in real time to verify actions and dependencies.
- 👎 **Thumbs-Down Learning**: Learns from developer `👎` reactions to permanently eliminate recurring false positives.
- 🔄 **Thread Auto-Resolution**: Resolves fixed review comment threads automatically via GitHub GraphQL.
- 💬 **On-Demand PR Commands**: Type `/review` or `@poing-ai review` in any PR comment to trigger a fresh re-review.
- 🏷️ **Issue & PR Triage**: Classifies issues into labels, assigns priority (`high`, `medium`, `low`), and checks duplicates.
- 📦 **Dependency Automation**: Automatically checks and bumps upstream dependencies (Google Maven, Maven Central, SPM, Godot Releases, Unity UPM, NuGet).
- 💻 **Local CLI Mode**: Review local git diffs and test triage directly from your terminal.

---

## 🚀 Quick Start (GitHub Actions)

Add Poing AI to your repository in 2 steps:

### 1. Add Gemini API Key
In your repository: **Settings ➡️ Secrets and variables ➡️ Actions ➡️ New repository secret**
- Name: **`GEMINI_API_KEY`** (Get a free key from **[Google AI Studio](https://aistudio.google.com/)**).

### 2. Create Workflow (`.github/workflows/poing-ai.yml`)

```yaml
name: "Poing AI"

on:
  pull_request_target:
    types: [opened, ready_for_review]
  issue_comment:
    types: [created]

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.event.issue.number || github.ref }}
  cancel-in-progress: true

jobs:
  review:
    if: >
      (github.event_name == 'pull_request_target' && !github.event.pull_request.draft) ||
      (github.event_name == 'issue_comment' && github.event.issue.pull_request && (contains(github.event.comment.body, '/review') || contains(github.event.comment.body, '@poing-ai review')))
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Checkout PR (for comment trigger)
        if: github.event_name == 'issue_comment'
        run: gh pr checkout "$PR_NUMBER"
        env:
          PR_NUMBER: ${{ github.event.issue.number }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: 2. Run Poing AI
        uses: poingstudios/poing-ai@v1
        with:
          number: ${{ github.event.issue.number || github.event.pull_request.number }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

---

## 💬 PR Commands

Interact with Poing AI directly from pull request comments:

| Command | Description |
|---|---|
| `/review` | Requests an immediate, fresh code review |
| `@poing-ai review` | Alternative mention format to trigger review |

---

## 💻 Local Terminal CLI

Install via PyPI:

```bash
pip install --upgrade poing-ai
```

Run code reviews on your local working tree before pushing:

```bash
# Review uncommitted changes
poing --local

# Review staged changes only
poing --local --staged

# Use a local offline Ollama model
poing --local --provider ollama --model deepseek-r1:latest
```

---

## 📖 Documentation & Guides

For complete guides, configuration options, and custom AI provider setup:

👉 **[https://poingstudios.github.io/poing-ai/](https://poingstudios.github.io/poing-ai/)**

---

## 📜 License

Poing AI is open-source software licensed under the [Apache License 2.0](LICENSE).
