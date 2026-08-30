# 🤖 AI Agent Skills

You can equip your favorite AI coding assistant (**Google Antigravity**, **Cursor IDE**, **Claude Code**, **Windsurf**, or **Copilot**) with specialized Poing AI skills.

---

## 🛠️ 1. Repository Setup Skill (`setup-poing-ai`)

Give this skill or prompt to your AI assistant to **automatically install and configure Poing AI in any repository**:

````markdown
---
name: setup-poing-ai
description: Automatically install and configure Poing AI code reviewer, issue triager, and dependency automation in this repository.
---

# Setup Poing AI — Installer Skill

Follow these steps to set up Poing AI in the current repository:

## Step 1: Create GitHub Actions Workflow

Create `.github/workflows/poing-ai.yml` with the following content:

```yaml
name: "Poing AI"

on:
  pull_request_target:
    types: [opened, ready_for_review]
  issues:
    types: [opened]
  issue_comment:
    types: [created]
  workflow_dispatch:
    inputs:
      mode:
        description: 'Mode: review or triage'
        required: true
        default: 'review'
        type: choice
        options:
          - review
          - triage
      number:
        description: 'PR or Issue number'
        required: true

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.event.issue.number || github.ref }}
  cancel-in-progress: true

jobs:
  review:
    if: >
      (github.event_name == 'pull_request_target' && !github.event.pull_request.draft) ||
      (github.event_name == 'issue_comment' && github.event.issue.pull_request && (contains(github.event.comment.body, '/review') || contains(github.event.comment.body, '@poing-ai review'))) ||
      (github.event_name == 'workflow_dispatch' && inputs.mode == 'review')
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Checkout PR (for comment or manual trigger)
        if: github.event_name == 'issue_comment' || github.event_name == 'workflow_dispatch'
        run: gh pr checkout "$PR_NUMBER"
        env:
          PR_NUMBER: ${{ inputs.number || github.event.issue.number }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: 2. Run Poing AI
        uses: poingstudios/poing-ai@v1
        with:
          number: ${{ inputs.number || github.event.issue.number || github.event.pull_request.number }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}

  triage:
    if: >
      github.event_name == 'issues' ||
      (github.event_name == 'workflow_dispatch' && inputs.mode == 'triage')
    runs-on: ubuntu-latest
    permissions:
      issues: write
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v7

      - name: 2. Run Poing AI Triage
        uses: poingstudios/poing-ai@v1
        with:
          mode: triage
          number: ${{ inputs.number || github.event.issue.number }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

## Step 2: Configure Gemini API Key

Instruct the user or run via GitHub CLI:
```bash
gh secret set GEMINI_API_KEY
```
*(Get a free key from [Google AI Studio](https://aistudio.google.com/)).*

## Step 3: (Optional) Create Configuration File

Create `.github/poing.json` to customize rules and models:
```json
{
  "provider": "gemini",
  "review": {
    "model": "gemini-3.7-flash",
    "strict_ground_truth": true,
    "rag": {
      "provider": "local",
      "guidelines_dirs": [".agents", "docs"]
    }
  }
}
```

## Step 4: Install Local CLI

```bash
pip install --upgrade poing-ai
```

Test the setup:
```bash
poing --local
```
````

---

## ⚡ 2. Day-to-Day Review Skill (`poing-ai`)

Give this skill to your AI assistant so it can **run reviews, triage issues, and check dependencies directly inside your IDE**:

````markdown
---
name: poing-ai
description: Run automated AI code reviews, issue triage, and multi-platform dependency updates using Poing AI CLI.
---

# Poing AI — Assistant Skill

Use Poing AI CLI to analyze working tree diffs against repository guidelines, check for bugs, triage issues, or update upstream dependencies.

## 🛠️ CLI Execution Commands

### 1. Code Review (`mode: review`)
Run an AI code review on local changes before creating or pushing a commit:

```bash
# Review uncommitted working tree changes (uses free Gemini or local Ollama)
poing --local

# Review staged changes only
poing --local --staged

# Review changes compared to master/main branch
poing --local --diff-target master

# Run 100% offline using a local Ollama model
poing --local --provider ollama --model deepseek-r1:latest

# Output as JSON (ideal for AI parsing)
poing --local --output json
```

### 2. Issue & PR Triage (`mode: triage`)
Classify an issue, assign labels, check priority, and detect duplicates:

```bash
poing --mode triage --local --issue-title "<ISSUE_TITLE>" --issue-body "<ISSUE_DESCRIPTION>"
```

### 3. Upstream Dependency Sync (`mode: sync`)
Inspect package manifests (Gradle, SPM, Godot Releases, Unity UPM, NuGet) and check for new releases:

```bash
# Check for updates without modifying files (dry run)
poing --mode sync --local --dry-run

# Apply version bumps directly to manifest files
poing --mode sync --local
```
````

---

## 📁 How to Install Skills in Your Tools

| Tool | Installation Path |
|---|---|
| **Google Antigravity / Gemini** | `.agents/skills/poing-ai/SKILL.md` |
| **Cursor IDE** | `.cursor/rules/poing-ai.mdc` |
| **Claude Code / Claude Desktop** | Add to `CLAUDE.md` or system prompt |
| **Windsurf / Cline** | `.windsurfrules` or `.clinerules` |
