# Automated Code Review

Poing AI provides thorough, multi-file code reviews with ground-truth verification.

---

## 🔍 How It Works

1. **Diff Extraction**: Computes the exact git diff between the PR branch and base branch (`master`/`main`).
2. **Ground-Truth File Reading**: For every file modified in the diff, Poing AI loads the entire file so the AI can verify declarations, imports, and method signatures across the whole file.
3. **Engine-Specific Verification**: Checks rules for **Godot** (e.g. `:=` typing, internal `class_name` prohibitions), **Unity**, and **Unreal**.
4. **Anti-Hallucination Checks**: Queries live GitHub releases to ensure action tags are real and stable.
5. **False-Positive Suppression**: Automatically filters out speculative language and findings matching past `👎` reactions.
6. **Posting Structured Reviews**: Posts a top-level review with verdict (`APPROVED`, `APPROVED_WITH_SUGGESTIONS`, or `CHANGES_REQUESTED`) alongside inline comments on specific lines.

---

## 🛡️ Anti-Hallucination & Quality Safeguards

### Ground-Truth Full File Loading
AI models often hallucinate that variables or functions are missing because traditional reviewers only send diff hunks. Poing AI loads the full source code of every modified file into context.

### Thumbs-Down (`👎`) Learning
When developers react with `👎` to any review comment posted by Poing AI:
- Poing AI records the comment fingerprint.
- On subsequent runs across the repository, findings matching that pattern are automatically suppressed.

### Thread Auto-Resolution
When developers push new commits that resolve existing inline comments, Poing AI connects to the GitHub GraphQL API and automatically marks those review threads as resolved!
