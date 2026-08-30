# Installation

Poing AI can be installed as a command-line tool, used as a GitHub Action, or run in a Docker container.

---

## 1. Local CLI Installation (PyPI)

Install the official Python package from PyPI:

```bash
pip install --upgrade poing-ai
```

Verify installation:

```bash
poing --version
```

*(Both `poing` and `poing-ai` CLI commands are available).*

---

## 2. GitHub Actions Setup

To use Poing AI inside GitHub Actions workflows, reference the action directly:

```yaml
- name: Run Poing AI
  uses: poingstudios/poing-ai@v1
  with:
    gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

See the **[Quick Start Guide](quickstart.md)** for complete workflow examples.

---

## 3. Docker Container

Pull the pre-built image from GitHub Container Registry (GHCR):

```bash
docker pull ghcr.io/poingstudios/poing-ai:latest
```

Run locally inside your git repository:

```bash
docker run --rm -it \
  -v $(pwd):/workspace \
  -w /workspace \
  -e GEMINI_API_KEY="your-api-key" \
  ghcr.io/poingstudios/poing-ai:latest --local
```
