# Quick Start

Get Poing AI reviewing pull requests on your repository in under 2 minutes.

---

## Step 1: Add your Gemini API Key

1. Get a free API key from **[Google AI Studio](https://aistudio.google.com/)**.
2. In your GitHub repository:
   - Navigate to **Settings** ➡️ **Secrets and variables** ➡️ **Actions**.
   - Click **New repository secret**.
   - Name: **`GEMINI_API_KEY`**
   - Value: *Your Gemini API key*.

---

## Step 2: Create Workflow

Create `.github/workflows/poing-ai.yml` in your repository:

=== "⚡ Standard (Review + On-Demand `/review`)"

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

=== "🌱 Minimal (PR Open Only)"

    ```yaml
    name: "Poing AI"

    on:
      pull_request_target:
        types: [opened, ready_for_review]

    jobs:
      review:
        runs-on: ubuntu-latest
        permissions:
          contents: read
          pull-requests: write
        steps:
          - name: 1. Checkout Code
            uses: actions/checkout@v7
            with:
              fetch-depth: 0

          - name: 2. Run Poing AI
            uses: poingstudios/poing-ai@v1
            with:
              gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
    ```

=== "🚀 Complete (Review + Triage + Manual Dispatch)"

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

          - name: Checkout PR (workflow_dispatch or comment trigger)
            if: github.event_name == 'workflow_dispatch' || github.event_name == 'issue_comment'
            run: gh pr checkout "$PR_NUMBER"
            env:
              PR_NUMBER: ${{ inputs.number || github.event.issue.number }}
              GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

          - name: 2. Run Poing AI
            uses: poingstudios/poing-ai@v1
            with:
              mode: review
              number: ${{ inputs.number || github.event.issue.number }}
              github-token: ${{ secrets.GITHUB_TOKEN }}
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

          - name: 2. Run Poing AI
            uses: poingstudios/poing-ai@v1
            with:
              mode: triage
              number: ${{ inputs.number }}
              github-token: ${{ secrets.GITHUB_TOKEN }}
              gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
    ```

---

## What's Next?

- Learn how to interact with the bot using **[PR Commands](../guides/pr-commands.md)** (`/review`).
- Run code reviews on your machine with the **[Local Terminal CLI](../guides/local-cli.md)**.
