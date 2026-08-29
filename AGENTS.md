# Poing Reviewer — Project Intelligence

This file provides architectural context, coding guidelines, and execution protocols for Poing Reviewer.

## Purpose

Poing Reviewer is an enterprise-grade AI bot, CLI tool, and GitHub Action powered by LLMs (Gemini, Ollama, OpenAI-compatible) that automates:
1. **Code Review**: Analyzes pull request diffs, checks repository guidelines, detects game-engine violations (Godot, Unity, Unreal), eliminates false positives, and posts structured reviews with line-level comments.
2. **Issue & PR Triage**: Classifies issues into categories, assigns priority, checks duplicates, and auto-manages labels.
3. **Dependency Automation**: Scans upstream datasources (Google Maven, Maven Central, SPM GitHub, Godot releases, Unity UPM, NuGet), updates manifest pins, and generates AI release changelog summaries.

## Repository Layout

```
src/poing_reviewer/
├── core/                  # Models, Config, Git, GitHub client, Logging
├── ai/                    # BaseAIProvider, GeminiProvider, False-Positive Filters, Thread Resolver
│   ├── rag/               # BaseRetriever, LocalFileRetriever, Embedders, Vector RAG
│   └── prompts/           # Review, Triage, and Changelog prompt templates
├── engines/               # Godot, Unity, Unreal, and Generic ecosystem analyzers
├── datasources/           # Maven, SPM, Godot Releases, UPM, NuGet fetchers
├── parsers/               # GDScript config, Gradle, Swift Package, Unity UPM parsers
├── services/              # ReviewService, TriageService, SyncService
├── server/                # GitHub App webhook receiver (FastAPI/Uvicorn)
├── cli.py                 # CLI interface
└── __main__.py            # Module entrypoint
```

## Key Components & File Map

| File / Module | Responsibility |
| :--- | :--- |
| `src/poing_reviewer/cli.py` | Argument parsing (`--mode`, `--local`, `--model`, `--provider`, etc.) and entrypoint dispatcher |
| `src/poing_reviewer/core/config.py` | Central `Config` object, environment variable mappings, `poing.json` discovery |
| `src/poing_reviewer/core/git.py` | Git diff extraction (`get_git_diff`), batch splitting, hunk annotation `[file L#]` |
| `src/poing_reviewer/core/github_client.py` | REST & GraphQL GitHub API client (reviews, comments, threads, reactions, labels) |
| `src/poing_reviewer/core/models.py` | Dataclasses & Enums (`ReviewResult`, `ReviewVerdict`, `TriageResult`, `DependencyUpdate`) |
| `src/poing_reviewer/ai/base.py` | `BaseAIProvider` abstract class (`generate_review`, `generate_triage`, `generate_changelog_summary`) |
| `src/poing_reviewer/ai/gemini.py` | Google Gemini REST API implementation with structured JSON schema output |
| `src/poing_reviewer/ai/rag/` | `LocalFileRetriever` (markdown scanner), `GeminiEmbedder`, `VectorRAGRetriever` |
| `src/poing_reviewer/services/review_service.py` | End-to-end review lifecycle: git diff, RAG guidelines, engine rules, AI batching, false-positive filtering, local display / GitHub submission |
| `src/poing_reviewer/services/triage_service.py` | Issue & PR triage categorization and label synchronization |
| `src/poing_reviewer/services/sync_service.py` | Dependency parsing, upstream release checking, changelog generation |

## Testing & Verification

Run tests using Python's built-in `unittest` runner (no external test runner dependencies needed):
```bash
python3 -m unittest discover tests
```

## How It Works

### 1. Code Review (`mode: review`)
- Checks out diff (`origin/{base}...HEAD`, uncommitted working tree changes, or staged diff).
- RAG retrieves guidelines (`AGENTS.md`, `docs/`) and detects engine (Godot, Unity, Unreal).
- Verifies live GitHub Action versions to avoid false positives.
- Splitting & batching: files are annotated with `[filepath L#]` and sent to Gemini with structured JSON schema.
- Thumbs-down suppression: previously `👎`'d bot findings are suppressed.
- Thread resolution: auto-resolves fixed review threads via GraphQL.

### Local CLI Execution
```bash
# Run local review on uncommitted/staged changes
python3 -m poing_reviewer.cli --local

# Run triage locally
python3 -m poing_reviewer.cli --mode triage --local --issue-title "Bug title" --issue-body "Description"

# Run dependency sync locally in dry-run mode
python3 -m poing_reviewer.cli --mode sync --local --dry-run
```

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
