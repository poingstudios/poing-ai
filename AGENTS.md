# Poing Reviewer — Project Intelligence

This file provides architectural context, coding guidelines, and execution protocols for Poing Reviewer.

## Purpose

Poing Reviewer is an enterprise-grade AI bot and GitHub Action powered by Google Gemini that automates:
1. **Code Review**: Analyzes pull request diffs, checks repository guidelines, detects game-engine violations (Godot, Unity, Unreal), eliminates false positives, and posts structured reviews with line-level comments.
2. **Issue & PR Triage**: Classifies issues into categories, assigns priority, checks duplicates, and auto-manages labels.
3. **Dependency Automation**: Scans upstream datasources (Google Maven, Maven Central, SPM GitHub, Godot releases, Unity UPM, NuGet), updates manifest pins, and generates AI release changelog summaries.

## Repository Layout

```
src/poing_reviewer/
├── core/                  # Models, Config, Git, GitHub client, Logging
├── ai/                    # BaseAIProvider, GeminiProvider, False-Positive Filters, Thread Resolver
│   ├── rag/               # BaseRetriever, LocalFileRetriever
│   └── prompts/           # Review, Triage, and Changelog prompt templates
├── engines/               # Godot, Unity, Unreal, and Generic ecosystem analyzers
├── datasources/           # Maven, SPM, Godot Releases, UPM, NuGet fetchers
├── parsers/               # GDScript config, Gradle, Swift Package, Unity UPM parsers
├── services/              # ReviewService, TriageService, SyncService
├── cli.py                 # CLI interface
└── __main__.py            # Module entrypoint
```

## How It Works

### 1. Code Review (`mode: review`)
- Checks out diff (`origin/{base}...HEAD` or local diff).
- RAG retrieves guidelines (`AGENTS.md`, `docs/`) and detects engine (Godot, Unity, Unreal).
- Verifies live GitHub Action versions to avoid false positives.
- Splitting & batching: files are annotated with `[filepath L#]` and sent to Gemini with structured JSON schema.
- Thumbs-down suppression: previously `👎`'d bot findings are suppressed.
- Thread resolution: auto-resolves fixed review threads via GraphQL.

### 2. Triage (`mode: triage`)
- Analyzes issue/PR title and body.
- Uses Gemini structured output to determine labels, priority (`high`, `medium`, `low`), and summary.
- Creates missing labels with standard colors and descriptions.

### 3. Dependency Sync (`mode: sync`)
- Inspects target files configured in `.github/poing.json`.
- Queries upstream package registries for new versions.
- Generates structured PR changelog summary with breaking change warnings.

## Coding Standards

- Python: Clean architecture, SOLID principles, type annotations throughout.
- Use `argparse`, `Config`, or environment variables for all configuration; no hardcoded magic strings.
- All new files must include the standard Apache License 2.0 header.
