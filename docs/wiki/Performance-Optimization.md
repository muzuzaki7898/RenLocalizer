# 🚀 Performance Optimization Guide

RenLocalizer is built for speed, capable of processing projects with over 100,000 lines. Use this guide to squeeze every bit of performance out of the tool.

---

## 🔹 Multi-Endpoint Google Architecture
Instead of using a single connection, RenLocalizer "races" multiple requests across different Google mirrors.

*   **Lingva Fallback:** If the primary service rate-limits you, the app automatically switches to Lingva servers.
*   **Result:** Translation speed jumps from ~3 strings/sec to **~10+ strings/sec**.

---

## ⚙️ Key Tuning Settings

| Setting | Recommended | Description |
| :--- | :--- | :--- |
| **Parser Workers** | 4-8 | Number of CPU threads used for file scanning. Match your CPU core count. |
| **Concurrent Threads** | 32-64 | Simultaneous translation requests. Set higher for fast fiber internet. |
| **Batch Size** | 200-500 | How many strings are sent in one block. Larger is faster but uses more RAM. |
| **Request Delay** | 100ms | Pause between requests. Increase if you see `HTTP 429` errors. |

---

## 🧠 Memory & System Load
For low-end systems or very massive games:

1.  **Lower Batch Size:** Reduces peak memory (RAM) usage.
2.  **Lower Workers:** prevents the UI from freezing during the initial "Extracting" phase.
3.  **Use SIMPLE Format:** Produces smaller `.rpy` files that are easier for both the tool and the game to handle.

---

## 🌐 Engine Selection
*   **Fastest:** Google (via Multi-Endpoint).
*   **High Quality:** DeepL (Requires API Key).
*   **Smartest:** AI Engines (GPT/Gemini). **Note:** These are much slower due to the nature of Large Language Models.

---
> 💡 **Tip:** Use **Google** for the bulk of the game and switch to **AI** only for the most important story dialogue to save time.
