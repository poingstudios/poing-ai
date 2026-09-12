# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- Resolve conflict between Gemini search grounding (`tools`) and structured JSON output (`responseMimeType: application/json`). The API rejects requests that combine both; grounding is now opt-in (`USE_SEARCH_GROUNDING=false` by default) and automatically stripped on 400/429 errors with an automatic retry.
- Disable search grounding during `generate_triage` and `generate_fix` calls to avoid API schema conflicts.
- Add auto-fallback: if a model request fails with a recoverable error, the system retries without `tools` before escalating to the next model in `FALLBACK_MODELS`.

### Added
- Transparent logo and adoption badges in README.
- Brand logo in automated bot review/fix responses.
- Unit tests for auto-fallback mechanism and schema payload validation.
