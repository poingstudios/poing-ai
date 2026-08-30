# Issue & PR Triage

Poing AI automates triage by labeling issues and assessing priority levels upon creation.

---

## 🏷️ Features

- **Smart Labeling**: Assigns categories such as `bug`, `enhancement`, `documentation`, `android`, `ios`, etc.
- **Priority Assessment**: Evaluates urgency and assigns `high priority`, `medium priority`, or `low priority`.
- **Duplicate Detection**: Identifies if an issue describes an already-known bug or existing issue.
- **Auto-Label Creation**: If a required label doesn't exist on the repository, Poing AI creates it with standard colors and descriptions.

---

## ⚙️ Enabling Triage in GitHub Actions

Add the `triage` job to `.github/workflows/poing-ai.yml`:

```yaml
on:
  issues:
    types: [opened]

jobs:
  triage:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      pull-requests: write
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v7

      - name: 2. Run Poing AI Triage
        uses: poingstudios/poing-ai@v1
        with:
          mode: triage
          number: ${{ github.event.issue.number }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```
