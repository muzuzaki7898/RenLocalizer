# 🏥 LM Studio Integration Guide

LM Studio allows you to run powerful Large Language Models **locally** on your computer. This guide explains how to connect it to RenLocalizer for 100% private and free translation.

---

## 🔹 1. Setup LM Studio
1.  **Download:** Get LM Studio from [lmstudio.ai](https://lmstudio.ai/).
2.  **Download a Model:** Look for **"Instruct"** versions of:
    *   `Qwen 2.5 7B Instruct` (Highly recommended for speed/quality).
    *   `Llama 3.1 8B Instruct`.
3.  **Start the Server:**
    *   Click the **Local Server** icon (↔️) on the left sidebar.
    *   Load your model.
    *   Click **Start Server**.
    *   Verify the port (default is usually **1234**).

---

## 🔹 2. Connect RenLocalizer
In the RenLocalizer **Settings** tab:

*   **Provider:** `Local LLM`
*   **API Key:** `local` (any text works).
*   **Base URL:** `http://localhost:1234/v1` (**Crucial:** Must end with `/v1`).
*   **Model Name:** Copy the exact ID from LM Studio (e.g., `qwen2.5-7b-instruct`).

---

## 🔹 3. Optimization Tips

| Tip | Reasoning |
| :--- | :--- |
| **GPU Offload** | Enable this in LM Studio to use your Graphics Card (much faster than CPU). |
| **Temperature 0.3** | Keeps translations consistent and less "random". |
| **Batch Size 5** | Prevents the local model from losing context. |

---

## ❓ Troubleshooting
*   **Connection Refused:** Check if LM Studio's server is "Started". Ensure no other app is using port 1234.
*   **Gibberish Output:** Ensure you downloaded an **"Instruct"** model, not a "Base" model.
*   **Slow Speed:** Increase "GPU Offload" layers in LM Studio if you have enough VRAM.

---

## 🌟 Why use LM Studio?
*   ✅ **Privacy:** No data is sent to the internet.
*   ✅ **Uncensored:** Local models won't refuse to translate "spicy" game content.
*   ✅ **Cost:** Forever free.

---
> 🔗 **Learn More:** Check out the [[AI-Engines]] guide for other providers.
