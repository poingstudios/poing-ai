# 🤖 GitHub App Setup Guide (Poing Reviewer Bot Identity)

This guide walks you through setting up the GitHub App so **Poing Reviewer** comments and approves PRs under the official **`poing-reviewer[bot]`** identity.

---

## 🛠️ Step 1: Create the GitHub App

1. Go to **GitHub App Creation**:
   - **For Personal Accounts**: [github.com/settings/apps/new](https://github.com/settings/apps/new)
   - **For Organizations**: `https://github.com/organizations/<YOUR_ORG>/settings/apps/new`
2. Fill in the basic info:
   - **GitHub App name**: `Poing Reviewer`
   - **Homepage URL**: `https://github.com/poingstudios/poing-reviewer`
   - **Webhook**: **Uncheck "Active"** *(not needed when running in GitHub Actions)*.

---

## 🔐 Step 2: Set Permissions

Under **Repository permissions**, configure the following:

| Permission | Access | Why it's needed |
|---|---|---|
| **Pull requests** | **Read & write** | To post line comments, summaries, and approvals (`APPROVE` / `REQUEST_CHANGES`) |
| **Issues** | **Read & write** | To triage issues, add labels, and set priority |
| **Contents** | **Read-only** | To read files, PR diffs, and guidelines |
| **Metadata** | **Read-only** | Auto-selected by GitHub |

Under **Where can this GitHub App be installed?**:
- Choose **"Only on this account"** (for private/org use) or **"Any account"** (public).

Click **"Create GitHub App"**.

---

## 🔑 Step 3: Get `APP_ID` and `APP_PRIVATE_KEY`

1. **Get `APP_ID`**:
   - On the **General** settings page of your new app, find **App ID** (e.g., `123456`).
   - Copy this number.
2. **Generate `APP_PRIVATE_KEY`**:
   - Scroll down to the **Private keys** section.
   - Click **"Generate a private key"**.
   - A `.pem` file will be downloaded to your computer. Open it in a text editor and copy the entire text (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`).

---

## 📦 Step 4: Install the App on your Repositories

1. In the left sidebar of your GitHub App settings, click **"Install App"**.
2. Click **"Install"** next to your account or organization.
3. Select **"All repositories"** (recommended) or choose specific repositories.
4. Click **"Install"**.

---

## 🔒 Step 5: Add Secrets to GitHub

Go to your repository (or Organization Settings ➡️ **Secrets and variables** ➡️ **Actions**):

Add the following **Repository Secrets**:

| Secret Name | Value |
|---|---|
| **`APP_ID`** | The App ID number from Step 3 (e.g., `123456`) |
| **`APP_PRIVATE_KEY`** | The full text of the `.pem` private key file |
| **`GEMINI_API_KEY`** | Your Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/) |

---

## 🚀 Step 6: Use in your Workflow

In your `.github/workflows/poing-reviewer.yml`:

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
      - name: 1. Generate Bot App Token
        id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ secrets.APP_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}

      - name: 2. Checkout Code
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: 3. Run Reviewer
        uses: poingstudios/poing-reviewer@master
        with:
          mode: review
          github-token: ${{ steps.app-token.outputs.token }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}

  triage:
    if: github.event_name == 'issues'
    runs-on: ubuntu-latest
    permissions:
      issues: write
    steps:
      - name: 1. Generate Bot App Token
        id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ secrets.APP_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}

      - name: 2. Checkout Code
        uses: actions/checkout@v7

      - name: 3. Run Triage
        uses: poingstudios/poing-reviewer@master
        with:
          mode: triage
          github-token: ${{ steps.app-token.outputs.token }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

🎉 **All reviews and triage labels will now appear under the official poing-reviewer[bot] avatar and name!**
