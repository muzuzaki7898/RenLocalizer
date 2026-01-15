# 🌐 Proxy Management & Rate Limits

When using free translation services, you will eventually hit "Rate Limits"—temporary bans from the provider for sending too many requests. 

---

## 🛑 What is an HTTP 429 Error?
`HTTP 429: Too Many Requests` means your IP has been temporarily flagged. 
> 🛠️ **Solution:** Wait 10-20 minutes, or use **Proxies**.

---

## 🛠️ Using Proxies in RenLocalizer
1.  **Open Settings:** Go to **Tools > Proxy Settings**.
2.  **Add List:** Paste your proxies in `IP:PORT` format (one per line).
3.  **Rotation:** RenLocalizer automatically rotates through your list. If one proxy fails, it immediately tries another.

---

## ⚡ Multi-Endpoint vs. Proxies
In version 2.4.0+, the "Multi-Endpoint" feature significantly reduces the need for proxies by automatically switching between dozens of Google mirrors. 
*   **Enable this in Settings** to get the best out-of-the-box experience without a proxy list.

---

## 💡 Tips to Avoid Bans
*   **Increase Delay:** Set "Request Delay" to **1.0s - 2.0s**.
*   **Smaller Batches:** Reduce "Batch Size" to **50-100**.
*   **VPN:** Use a high-quality system-wide VPN.
*   **AI Providers:** Engines like **Gemini** and **OpenAI** handle high volume much better when using an API key.

---

## 📋 Proxy Quality Guide
*   ✅ **Residential Proxies:** Best success rate. Hard to detect.
*   ⚠️ **Datacenter Proxies:** Fast, but often already blocked by Google.
*   ❌ **Public Proxies:** Found on free websites. Usually slow, insecure, and non-functional.

---
> 📘 **Related:** See [[Performance-Optimization]] for tuning your speed.
