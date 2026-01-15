# 🔓 RPA & Script Extraction

Most Ren'Py games hide their assets and code inside `.rpa` (Archive) or `.rpyc` (Compiled) files. RenLocalizer provides built-in tools to unlock these without needing external software.

---

## 🔹 1. Native RPA Extraction (UnRPA)
RenLocalizer includes a native Python implementation of UnRPA.

### **How to Extract:**
1.  Go to **Tools > Extract RPA Archives**.
2.  Select the game's root directory (where the `.exe` or `game/` folder is).
3.  The app will scan, find all `.rpa` files, and extract them.
4.  Extracted files appear in the `game/` folder, ready for translation.

---

## 🔹 2. RPYC Reader (No Decompile Needed)
Many games delete their source `.rpy` files to prevent modding.
*   **The Old Way:** You'd have to use `UnRen` or `unrpyc` to turn them back into readable text.
*   **The RenLocalizer Way:** Use the **RPYC Reader** feature in Settings. It parses the binary bytecode directly, extracting translatable strings without requiring a full decompile.

---

## 🔹 3. Script Normalization
RenDeveloper automatically scans for legacy encodings (like Shift-JIS) and converts them to **UTF-8**. This ensures that once extracted, the files won't cause character errors in Ren'Py.

---

## 🛠️ Troubleshooting Extraction

| Issue | Solution |
| :--- | :--- |
| **"No RPA found"** | Ensure you selected the parent folder of the `game` directory. |
| **Permission Error** | Run RenLocalizer as Administrator (needed for `Program Files`). |
| **Disk Space** | Extraction can double the game's size. Ensure you have free space. |

---
> ⚠️ **Warning:** Always make a **Manual Backup** of your game folder before running heavy extraction tools!
