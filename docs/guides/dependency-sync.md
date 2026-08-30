# Multi-Platform Dependency Automation

Poing AI automatically scans upstream registries, updates manifest files, and generates release summaries with breaking change warnings.

---

## 📦 Supported Ecosystems & Datasources

| Platform | Manifest File | Upstream Datasource |
|---|---|---|
| **Android** | `build.gradle`, `build.gradle.kts` | Google Maven & Maven Central |
| **iOS** | `Package.swift`, `*.podspec` | Swift Package Manager & GitHub Releases |
| **Godot Engine** | `plugin.cfg`, `config.gd` | Godot Official GitHub Releases |
| **Unity** | `package.json` | Unity Package Manager (UPM) |
| **.NET / C#** | `*.csproj`, `packages.config` | NuGet API |

---

## ⏰ Cron Automation Workflow

Create `.github/workflows/cron-sync-dependencies.yml`:

```yaml
name: "[Cron] Sync Dependencies"

on:
  schedule:
    - cron: '0 0 * * 1' # Every Monday at midnight UTC
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v7

      - name: 2. Run Dependency Sync
        uses: poingstudios/poing-ai@v1
        with:
          mode: sync
          github-token: ${{ secrets.GITHUB_TOKEN }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```
