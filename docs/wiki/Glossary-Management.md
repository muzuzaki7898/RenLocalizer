# Glossary & Terminology Management

Ensuring consistent translations for character names, items, and world-building terms is critical for a high-quality localization.

## 📓 The Glossary Editor
You can access the Glossary Editor directly from the RenLocalizer GUI (**Tools > Glossary Editor**).

- **Source Word:** The original word in the game (e.g., "Sword").
- **Target Word:** Your preferred translation (e.g., "Kılıç").
- **Case Sensitive:** Choose whether the match should be exact regarding capitalization.

## 🚀 How it Works
The glossary is applied *after* the initial translation is received from the engine:
1.  RenLocalizer receives the translated text.
2.  It scans the text for your glossary terms.
3.  It performs a "Smart Replace" to ensure the terms are exactly as you defined them.

## ⚠️ Critical Terms
Critical terms are words that should **never** be translated (e.g., unique character names like "Xenon" or game titles).
- Any term added to the glossary with an identical Source and Target will be protected from the translation engine's internal logic.

## 📁 Storage
- **glossary.json:** Stores project-specific terms. 
- You can share this file with other translators to maintain consistency across the team.

## Best Practices
- **Character Names:** Always add character names to the glossary to prevent the AI from translating names that actually have literal meanings (e.g., naming a character "Summer").
- **UI Elements:** Consistent buttons like "Save", "Load", and "Quit" should be in your glossary.
- **Context:** Use the Glossary for specialized jargon unique to your game's setting (e.g., Sci-Fi or Fantasy terms).
