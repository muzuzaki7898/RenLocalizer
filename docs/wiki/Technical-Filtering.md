# Technical String Filtering

Ren'Py games contain a mix of dialogue, UI, and technical code. RenLocalizer uses a sophisticated filtering system to ensure only "human" text is translated.

## 🛡️ Placeholder Protection
Ren'Py uses special syntax for variable interpolation and styling.
- **Variables:** `[player_name]`, `[score]`, `[persistent.day]`
- **Styling:** `{i}Text{/i}`, `{color=#f00}Alert{/color}`
- **Ruby:** `{rb}kanji{/rb}{rt}kana{/rt}`

**How it works:**
Before sending text to a translation engine (especially AI), RenLocalizer "protects" these segments by replacing them with unique technical tokens (e.g., `?V001?`). After translation, it precisely restores the original code.

## 🎛️ Technical Keyword Filter
The system automatically detects and skips internal Ren'Py keywords that look like strings but are actually code:
- `renpy.dissolve`
- `gui.text_font`
- `config.name`
- `persistent.unlocked`

These are matched using a comprehensive heuristic engine that checks for common programming patterns, file paths, and known engine identifiers.

## ⚙️ Custom Filters (Advanced)
Starting in v2.4.10, the filter engine uses "Symbol Density" heuristics. If a string has an unusually high density of dots, underscores, or brackets, it is flagged as "Technical" and skipped to prevent corrupting the game's logic.

## ⚠️ Common Issues
- **Unwanted Translation:** If a technical string *is* translated, add it to the [[Glossary-Management]] with the same Source and Target to protect it.
- **Missing Translation:** If a menu item or button is missed, check if the corresponding "Filter" is enabled in the **Translation Settings** tab (e.g., "Translate Buttons", "Translate Notify").
