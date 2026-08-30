# AI Providers & Model Selection

Poing AI supports multiple AI backends, from cloud APIs to 100% private local models.

---

## 1. Google Antigravity Managed Agent (`provider: antigravity`)

Powered by Google's **Interactions API** (`antigravity-preview-05-2026`) featuring remote Linux sandboxing, multi-step autonomous tool use, and self-healing test execution.

- **Primary Agent**: `antigravity-preview-05-2026`
- **Setup**:
  ```bash
  export GEMINI_API_KEY="your-gemini-key"
  poing --local --provider antigravity --fix
  ```

---

## 2. Google Gemini (Default)

Powered by the official Google Gemini REST API.

- **Primary Models**: `gemini-3.7-flash`, `gemini-3.5-flash`
- **Setup**:
  ```bash
  export GEMINI_API_KEY="your-gemini-key"
  ```

---

## 3. Local Ollama & vLLM (Offline / Private)

Run completely offline on your own machine without sending code to the cloud.

- **Supported Models**: `deepseek-r1:latest`, `deepseek-coder:6.7b`, `qwen2.5-coder:7b`, `llama3.3:latest`
- **Setup**:
  ```bash
  ollama serve
  poing --local --provider ollama --model deepseek-r1:latest
  ```

---

## 3. OpenAI & DeepSeek

Connect to OpenAI or any OpenAI-compatible endpoint (DeepSeek, Groq, OpenRouter, LM Studio).

- **Supported Models**: `gpt-4o-mini`, `gpt-4o`, `deepseek-chat`, `deepseek-reasoner`
- **Setup (DeepSeek)**:
  ```bash
  export DEEPSEEK_API_KEY="sk-..."
  poing --local --provider deepseek --model deepseek-chat
  ```
- **Setup (Custom Base URL)**:
  ```bash
  export OPENAI_API_KEY="sk-..."
  poing --local --provider openai --api-base "https://openrouter.ai/api/v1" --model "anthropic/claude-3.5-sonnet"
  ```
