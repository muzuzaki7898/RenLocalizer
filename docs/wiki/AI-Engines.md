# AI Translation Engines

RenLocalizer supports modern Large Language Models (LLMs) to provide context-aware, high-quality translations.

## 🟢 OpenAI / OpenRouter
Standard for high-quality translations.
- **Set up:** Enter your API key in the settings.
- **OpenRouter:** You can use OpenRouter to access models like Claude 3.5 or Llama 3 via the OpenAI provider by changing the **Base URL** to `https://openrouter.ai/api/v1`.

## 🟡 Google Gemini
Fast and often has a generous free tier for developers.
- **Provider:** Select `Gemini`.
- **API Key:** Get one from [Google AI Studio](https://aistudio.google.com/).
- **Safety Settings:** You can configure the safety threshold (BLOCK_NONE is recommended for uncensored game content).

## 🔵 Local LLM (Offline)
Run models locally on your own hardware for maximum privacy and zero cost.
- **Backends:** Supports **Ollama**, **LM Studio**, and **LocalAI**.
- **Model Recommendation:** `Qwen 2.5 7B`, `Llama 3.1 8B`, or `Dolphin-Mistral` (for uncensored content).
- **Default URL:** `http://localhost:11434/v1` (Ollama) or `http://localhost:1234/v1` (LM Studio).

## ⚙️ Advanced AI Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| **Temperature** | 0.3 | Lower values (0.1-0.3) make translation consistent. Higher values make it creative. |
| **Max Tokens** | 2048 | Max length of each translation response. |
| **Batch Size** | 5-10 | Number of strings sent in a single prompt. Higher is faster but riskier for small models. |
| **System Prompt** | *Auto* | A custom persona instruction for the AI (e.g., "You are a professional localizer"). |

## 🛡️ Content Safety & Censorship
Unlike traditional engines, AI models might refuse to translate "sensitive" content.
- **Gemini:** Set Safety Level to `BLOCK_NONE`.
- **Local LLMs:** Use "Uncensored" or "Instruct" fine-tuned models to bypass ethical filters.
- **Fallback:** If an AI refuses a string, RenLocalizer can automatically fallback to Google Translate to ensure 100% completion.
