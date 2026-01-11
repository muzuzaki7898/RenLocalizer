# LM Studio Integration Guide

LM Studio is an excellent tool for running local LLMs with a user-friendly interface. This guide explains how to connect it to RenLocalizer safely.

## 1. LM Studio Configuration
1.  **Download & Install:** Get LM Studio from [lmstudio.ai](https://lmstudio.ai/).
2.  **Download a Model:** We recommend **Qwen 2.5 7B Instruct** or **Llama 3.1 8B Instruct**.
3.  **Start the Server:**
    - Click the **Local Server** icon (the double-headed arrow) on the left sidebar.
    - Select your model and click **Start Server**.
    - Take note of the port. By default, LM Studio uses **1234**.

## 2. RenLocalizer Setup
Open RenLocalizer Settings and apply these values:

- **Translation Engine:** Local LLM
- **API Key:** `local` (LM Studio doesn't require a real key)
- **Base URL:** `http://localhost:1234/v1` (Make sure to include `/v1`!)
- **Model Name:** Enter the exact ID shown in LM Studio (e.g., `qwen2.5-7b-instruct`)

## 3. Optimization for Qwen Models
Qwen is highly effective at following syntax instructions. To get the best results:

- **Temperature:** Set to **0.2** or **0.3**.
- **Max Batch Size:** Start with **5**. If your GPU has more than 12GB VRAM, you can try **10**.
- **System Prompt:** Ensure the default localized system prompt is used. It contains critical instructions about preserving `[variables]` and `{tags}`.

## 4. Common Troubleshooting
- **Connection Refused:** Ensure the server is actually "Started" in LM Studio. Check if a firewall is blocking port 1234.
- **Garbage Output:** Make sure you are using an "Instruct" or "Chat" version of the model, not a "Base" model.
- **Speed Issues:** Ensure "GPU Offload" is enabled in LM Studio settings to use your graphics card instead of your CPU.

## Why use LM Studio?
- **100% Offline:** No data leaves your computer.
- **No Limits:** No API quotas or monthly fees.
- **Censorship Free:** Unlike Gemini or OpenAI, you can translate any content as long as the model allows it.
