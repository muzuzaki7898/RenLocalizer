# Proxy Management & Rate Limits

When using free translation engines (like Google Web), you may encounter rate limits. RenLocalizer provides a robust proxy system to keep the pipeline moving.

## 🛑 What is a Rate Limit?
Translation providers (especially Google) will temporarily block your IP address if you make too many requests in a short period. You will see an `HTTP 429: Too Many Requests` error in the logs.

## 🛠️ Using Proxies
1.  **Open Proxy Dialog:** Go to **Tools > Proxy Settings**.
2.  **Add Proxies:** Paste a list of HTTP/HTTPS proxies. Format: `ip:port` or `username:password@ip:port`.
3.  **Rotation Logic:** When an IP is blocked, RenLocalizer automatically switches to the next proxy in your list and retries the failed translation.

## 🔄 Multi-Endpoint Feature
RenLocalizer 2.4.x includes a "Multi-Endpoint" feature for Google Translate. It automatically "races" between multiple Google mirrors and endpoints to find the fastest one that isn't blocked. 
- **Effect:** This significantly reduces the need for manual proxy lists.

## 💡 Tips to Avoid Bans
- **Request Delay:** In settings, increase the "Request Delay" (e.g., to 1.0 or 2.0 seconds).
- **Batch Size:** Decrease the batch size for traditional engines.
- **Switch Engines:** If Google blocks you, switch to **Lingva** (built-in fallback) or an **AI provider** (OpenRouter/Gemini), as they handle high volume much better with an API key.

## 📋 Recommended Proxy Sources
- Use high-quality "Residential" proxies for the best results.
- "Public" proxies (found on free lists) are often unreliable and already blocked by Google.
