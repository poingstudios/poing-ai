# On-Demand PR Commands

You can interact with Poing AI directly from GitHub pull request comment threads.

---

## Available Commands

| Command | Description | Example |
|---|---|---|
| `/review` | Triggers an immediate re-review of the pull request | `/review` |
| `@poing-ai review` | Alternative mention format to trigger a re-review | `@poing-ai review` |

---

## ⚡ Enabling PR Commands in Your Workflow

GitHub Actions requires your workflow to listen for the `issue_comment` event to respond to comments.

Add the following to your `.github/workflows/poing-ai.yml`:

```yaml
on:
  pull_request_target:
    types: [opened, ready_for_review] # Runs ONCE on open
  issue_comment:
    types: [created]                  # Wakes up on comments

jobs:
  review:
    if: >
      (github.event_name == 'pull_request_target' && !github.event.pull_request.draft) ||
      (github.event_name == 'issue_comment' && github.event.issue.pull_request && contains(github.event.comment.body, '/review'))
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      # When comment trigger fires, check out the specific PR branch
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

## 💡 How It Works

1. You type `/review` in the PR discussion.
2. GitHub sends an `issue_comment` event to GitHub Actions.
3. The workflow validates the comment contains `/review`, checks out the PR branch with `gh pr checkout`, and runs Poing AI.
4. Poing AI posts an updated review comment showing the evaluated commit and AI model.
