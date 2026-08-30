# poing.json Configuration

You can customize Poing AI behavior across your repository using an optional `.github/poing.json` file.

---

## Example `.github/poing.json`

```json
{
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "review": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "fallback_models": ["gemini-3.7-flash", "gemini-3.5-flash"],
    "max_chars": 100000,
    "max_batches": 10,
    "rag": {
      "enabled": true,
      "provider": "local",
      "guidelines_dirs": [".agents", "docs"]
    }
  },
  "triage": {
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "dependencies": {
    "auto_pr": true,
    "branch_prefix": "deps/sync-"
  }
}
```

---

## Configuration Keys

- **`provider`**: Default provider (`gemini`, `ollama`, `openai`, `deepseek`).
- **`model`**: Default model name.
- **`review.rag.guidelines_dirs`**: Folders to scan for custom guidelines and rules.
- **`review.fallback_models`**: Backup models to automatically retry if the primary model hits rate limits or timeouts.
