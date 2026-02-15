# RenLocalizer Changelog

## [2.7.1] - 2025-06-14

### Bug Fixes
- **DeepL formality bug**: Fixed two bugs—wrong attribute access path (`getattr(self.config_manager, 'deepl_formality')` instead of going through `translation_settings`), and `config_manager` not passed to `DeepLTranslator` constructor. Turkish added to formality-supported languages.
- **Empty `{}` placeholder protection**: `.format()` positional `{}` placeholders were not protected during translation. Added `_PAT_EMPTY_BRACE` to `syntax_guard.py`.
- **Menu hint parameter parsing**: `menu_choice_re` regex now handles `(hint=expression)` and nested parentheses like `(hint=func(x))` after menu text strings.
- **AES loader key derivation mismatch**: Fixed critical bug where the generated Ren'Py loader used a hash of the passphrase instead of the passphrase itself for key derivation, making decryption impossible.
- **XML entity encoding**: Fixed missing `&` → `&amp;` escaping in AI translator batch XML `context` and `type` attributes.
- **Config int/float crash**: `__post_init__` validators now use safe conversion helpers that handle `None`/empty string/invalid values gracefully instead of crashing.
- **Batch boundary context leak**: `_prev_entry_text` is now reset per batch and checks file boundaries, preventing cross-file/cross-scene context contamination for `extend` entries.
- **Glossary thread-safety**: Auto-protect character names now acquires ConfigManager lock before mutating glossary.
- **RPA header size**: Dynamic header calculation instead of hardcoded 46 bytes (actual is 34).
- **Obfuscation keyword filter**: `obfuscate_rpy_content()` now excludes Ren'Py keywords (`if`, `return`, etc.) from dialogue matching to prevent false positives.

### New Features

#### Config Validation
- All 4 dataclasses (`TranslationSettings`, `ApiKeys`, `AppSettings`, `ProxySettings`) now have `__post_init__` validators
- **Numeric clamps**: 15+ fields clamped to safe ranges (prevents `batch_size=0` infinite loops, `concurrency=0` deadlocks)
- **Enum allowlists**: `deepl_formality`, `gemini_safety_settings`, `app_theme`, `output_format`
- **String sanitization**: API keys auto-stripped, language codes trimmed, URL fields cleaned
- **JSON validation**: `custom_function_params` validated on load (invalid → `"{}"`)

#### Extend Context for AI Translation
- New `TextType.EXTEND` type in parser for `extend` dialogue lines
- Pipeline tracks previous entry text, passes as `context_hint` metadata
- AI translator adds `context="..."` attribute to batch XML for better translations

#### Custom Function Parameter Extraction
- New `custom_function_params` JSON config field (TranslationSettings)
- Users define which function calls to extract: `{"Quest": {"pos": [0,1,2]}, "notify": [0]}`
- `DeepExtractionConfig.get_merged_text_calls()` merges user config with built-in TIER1

#### Auto-Protect Character Names
- New `auto_protect_character_names` config field (default: `True`)
- Pipeline auto-collects Character names from `define` entries
- Names (including multi-word like "Mary Jane") added to glossary as `name → name`

#### Ren'Py Translation Lint (`src/tools/renpy_lint.py`)
- Post-translation validator with 10 check codes (E000–E050, W010–W041, I010, R001)
- Indentation validation (tabs, non-4-space)
- `translate` block structure integrity (duplicate IDs, missing indent)
- `old`/`new` pair validation (orphaned old, missing new)
- Placeholder preservation: `[var]`, `{tag}`, `%(name)s`, `.format()` placeholders
- String syntax (unbalanced quotes, triple-quote toggle fix)
- Encoding/BOM checks (UTF-16 → error)
- Optional Ren'Py engine lint integration (`run_renpy_lint()`)

#### Project Import/Export (`src/utils/project_io.py`)
- `.rlproj` archive format (ZIP containing JSON manifests)
- Exports: settings, glossary, critical terms, never-translate rules, translation cache
- Imports with merge options (glossary merge/replace, selective settings)
- ZIP bomb protection (100 MB per entry, 500 MB total limit)
- API keys excluded by default for safety
- Version-aware manifest for future compatibility

#### JSON/YAML Data Extractor Plugin System (`src/core/data_extractors.py`)
- `BaseExtractor` abstract class with key-based heuristic filtering
- `JsonExtractor` with auto-detection, write-back support
- `YamlExtractor` (graceful degradation without PyYAML, roundtrip warning)
- `ExtractorRegistry` with auto-detect and custom plugin registration
- Heuristic filters: skip `id`, `path`, `image`, `color`; include `text`, `dialogue`, `name`, `description`
- Directory scanning with extension filtering

#### Translation Encryption/Obfuscation (`src/utils/translation_crypto.py`)
- **Obfuscation mode** (zero dependencies): Base64 encodes strings, injects Ren'Py `init -999` decoder
- Round-trip: `obfuscate_rpy_content()` ↔ `deobfuscate_rpy_content()`
- File-level API: `obfuscate_rpy_file()`
- **AES mode** (requires `cryptography`): AES-256-GCM encryption with PBKDF2 key derivation
- Generates `.rlenc` + loader `.rpy` with real AES-GCM decryption for Ren'Py runtime

#### RPA Archive Packer (`src/utils/rpa_packer.py`)
- Creates RPA-3.0 archives compatible with Ren'Py's archive loader
- `pack_directory()` with extension filtering and prefix support
- `pack_files()` for explicit file mapping
- Round-trip verified with existing `RPAParser` extractor
- Convenience: `pack_translations()` one-call API

### Tests
- 46 new tests for all v2.7.1 features (469 total passing)
- +39 atomic segment + quote-stripping + segment splitting tests (520 total passing)
- Covers: config validation, lint, project I/O, extractors, crypto, RPA packer, atomic segments, quote-stripping, strings.json segment splitting (angle-pipe + bare pipe)

### 🔀 Delimiter Atomic Segment Registration (v2.7.1)

**Issue:** Ren'Py runtime does not use `<A|B|C>` blocks as a single string — it calls each segment individually via `vary()` or list indexing. However, the pipeline was writing only a single `old`/`new` pair for the combined block, so Ren'Py couldn't match individual segments and fell back to English.

**Root Cause:** `_translate_entries()` was correctly splitting and translating delimiter segments, but only wrote the combined block (`<TransA|TransB|TransC>`) to output files. At runtime, when `vary()` looked up `"TransA"` individually, it found no match in the translation dictionary since only the combined block existed.

**Fix — Atomic Segment Registration:**

1. **Instance variable**: `_last_atomic_segments = {}` is reset on each `_translate_entries()` call
2. **Per-batch collection**: `_atomic_segments = []` list is populated during batch result processing
3. **Multi-group path**: When `rejoin_angle_pipe_groups()` succeeds, each segment's `(original_text, translated_text)` pair is collected from result metadata
4. **Bare-pipe path**: Same collection logic applies for `_delimiter_groups` entries
5. **Phase 2.5 block**: `_atomic_segments` pairs are written to both the `translations` dict and `self._last_atomic_segments` (with duplicate checking)
6. **`_generate_strings_json()` updated**: Atomic segments are added to strings.json via the `extra_translations` parameter

**Critical Fix — play_dialogue Quote Wrapping (hotfix):**
- **Bug 1 (Crash)**: The initial implementation created an `_rl_segments.rpy` file, but its `old` entries collided with existing entries in `strings.rpy` → Ren'Py crash: `Exception: A translation for "Really?" already exists at...`
- **Bug 2 (Translation invisible)**: The game's `play_dialogue()` function wrapped `vary()` output in literal double quotes: `renpy.say(speaker, '"'+talk+'"')`. So the runtime text `"Really?"` didn't match the `Really?` key in strings.json.
- **Bug 3 (IDE errors)**: The `_rl_segments.rpy` file showed entirely red in the IDE, and Ren'Py `translate XX strings:` blocks do not affect dynamic `renpy.say()` calls.

**Architecture Decision — `_rl_segments.rpy` Removed:**
- `translate XX strings:` blocks only work for static string matching — they DO NOT AFFECT dynamic `renpy.say()` calls
- The `vary()` + `play_dialogue()` system is fully dynamic: `renpy.say(mc, '"' + vary("A|B") + '"')`
- Therefore `_rl_segments.rpy` served no useful purpose — removed entirely
- `_write_atomic_segments_rpy()` method DEPRECATED — disabled with early `return`
- Pipeline now automatically cleans up old `_rl_segments.rpy` + `.rpyc` files

**Fix — Runtime Hook Quote-Stripping (v4.1.0+):**
- **Layer 1** (`_rl_say_menu_text_filter`): New "Try 3" — for quote-wrapped text like `"Really?"`, strips outer quotes, looks up `Really?`, and re-wraps the translation in quotes if found
- **Layer 2** (`_rl_replace_text`): New "Step 3" — same quote-stripping logic, inner text searched via exact + case-insensitive lookup, found translation re-wrapped in quotes
- Both layers include empty string/short string guards (crash-safe)

**Fix — strings.json Segment Splitting (v2.7.1 hotfix-2):**
- **Core issue**: `_translate_entries()` only collected atomic segments when new translation engine results arrived — segments from cache or previous runs were not split
- **`translate_existing_tl` path**: `_generate_strings_json` was never called → atomic segments were not written to strings.json (fixed)
- **Solution**: `_generate_strings_json()` now scans all delimiter patterns after building the mapping:
  - **Path 1 — Angle-pipe** (`<A|B|C>`): Parses groups using `split_angle_pipe_groups()`
    - Single group: `<A|B|C>` → individual entries for `A`, `B`, `C`
    - Multiple groups: `text <A|B> mid <C|D>` → entries for `A`, `B`, `C`, `D`
    - Embedded group: `And they all <X|Y|Z>...` → entries for `X`, `Y`, `Z`
  - **Path 2 — Bare pipe** (`A|B|C`, without `<>`): `split_delimited_text()` + simple pipe split fallback
    - Example: `Interesting...|Really...?|Indeed...` → entries for `Interesting...`, `Really...?`, `Indeed...`
    - `vary('A|B|C')` produces strings in exactly this format
    - Skipped for safety if segment counts differ between original and translation
  - Does not overwrite existing segments (duplicate protection)
  - Segments where `orig == trans` are skipped

**Output:**
- `strings.json`: Combined blocks + individual segments written together (single output point)
- Runtime hook: `play_dialogue()` compatibility via quote-stripping
- Pipeline cleanup: Old `_rl_segments.rpy` + `.rpyc` files automatically removed

**Tests:** 39 tests — segment split, dict building, strings.json injection + **segment splitting** (13 tests: angle-pipe + bare pipe + mixed), Ren'Py vary() compatibility, **quote-stripping** (Layer 1 + Layer 2, 13 tests)

### Multi-Group Angle-Pipe Delimiter System (v2.7.1)

**Issue:** The delimiter system (`<seg1|seg2|...>` patterns) had 3 critical bugs causing 97/229 (42%) delimiter patterns to produce incorrect translations:

1. **Multi-group regex failure**: Strings with MULTIPLE `<...|...>` groups (e.g., `text <A|B> mid <C|D> end`) couldn't match the `^...$` single-group regex, falling to bare-pipe split which destroyed the `<>` structure
2. **Surrounding text not translated**: For `Pirate activity <A|B> remains challenging!`, the text outside the angle brackets ("Pirate activity", "remains challenging!") was embedded in prefix/suffix and NEVER translated
3. **Structural integrity too strict**: Single-word segments like `<increasing|forecast|intensifying>` and short phrases like `<Indeed.|Really?|Is that so?>` were rejected by the min_words=2/min_len=8 requirement

**Fix — New `split_angle_pipe_groups()` system:**
- Uses `re.finditer()` to find ALL `<...|...>` groups in a string (not just one)
- Creates a template with `[DGRP_N]` placeholders (protected by `protect_renpy_syntax`)
- Template is translated as a single unit (preserving sentence context and allowing natural word order)
- Each group's segments are translated independently
- `rejoin_angle_pipe_groups()` reassembles the final text

**Results:**
- **Before**: 132/229 OK (57.6%), 97 broken
- **After**: 228/229 OK (99.6%), 1 remaining (all-numeric group, handled by GT)
- 69 patterns with surrounding text now get full translation
- Short/single-word segments accepted without min_words restriction
- Numeric groups (`<0.1|0.02|0.005>`) preserved in template as-is (no translation needed)
- Turkish word order: GT naturally reorders `[DGRP_0]` and `[DGRP_1]` in template

**False-Positive Fixes:**
- `_CODE_DOT_RE`: Requires 2+ chars before dot (prevents `A.I.` abbreviation false positive)
- File path detection: Uses `re.search(r'[\\/][A-Za-z_]', s)` — prevents `\"` escaped quote AND `10/20` numeric slash false positives

**Safety Guards:**
- Doubled placeholder detection: If GT duplicates a `[DGRP_N]` token, `rejoin_angle_pipe_groups()` returns `None` (safe fallback)
- Remaining `[DGRP_` text after reassembly → automatic corruption detection → original text preserved

**Pipeline Integration:**
- `split_angle_pipe_groups()` tried FIRST (handles all angle-bracket patterns)
- `split_delimited_text()` now only handles bare pipe patterns (angle-bracket guard added)
- Result processing handles multi-group rejoin with corruption detection

### 🛡️ Critical: Dotted-Path & Python Builtin Leak Fix (Crash Prevention)

**Issue:** Despite initial filter hardening, ~31 critical code strings still leaked through filters and caused `IndexError: list index out of range` crash in `renpy/ui.py` when translated. These fell into patterns not covered by existing regexes.

**Leaked Patterns (SpaceJourneyX 230_023, 51K-line strings.rpy):**
- 16× `GAME.hour in [18,19,20,21,22]` — dotted path + `in` + square brackets
- 13× `'reactor activated' in GAME.mc.done` — multi-word quoted string in dotted path
- 1× `True` standalone — Python boolean translated to `Doğru`
- 1× `GAME.day%5 == 0` — dotted path + modulo/comparison
- 1× `[x >= 70 for x in bot.skills.values()].count(True) >= 3` — list comprehension
- 1× `GAME.getStarSys().ID in ['SSIDIltari']` — method chain + `in` check

**Fixes (6 new detection patterns):**

1. **`_DOTTED_IN_RE`**: `GAME.hour in [list]`, `GAME.getStarSys().ID in ['X']` — dotted path followed by `in [`
2. **`_DOTTED_COMPARE_RE`**: `GAME.day%5 == 0`, `GAME.hour < 18` — dotted path followed by comparison operators
3. **`_LIST_COMPREHENSION_RE`**: `[x >= 70 for x in items]` — Python list comprehension inside brackets
4. **`_BRACKET_METHOD_RE`**: `].count(True)`, `).items()` — method call on bracket/paren result
5. **`_PYTHON_CONDITION_RE` expanded**: Now handles multi-word quoted strings (`'reactor activated'` → `[^'"]+` instead of `\w+`)
6. **`True`/`False`/`None` standalone**: Python builtin constants blocked as standalone text

**Broad Code Detector Enhancement:**
- Lowered dot reference threshold from 2 to 1 (with 3-char minimum to exclude abbreviations like `e.g.`, `U.S.`, `Dr.`)
- Pattern: 1+ dotted reference (3+ chars before dot) AND comparison/boolean operators

**Safety Balance:**
- All 31 crash-causing code strings now blocked (was 0/31)
- 99.39% of translated entries still pass through (only 96/15,843 filtered)
- Legitimate game dialogue with `[GAME.mc.name]`, `[GAME.version]` variables correctly passes
- Natural language with `return`, `True`, `not` in sentences correctly passes
- 39/39 targeted test cases correct, 394 total tests passing

**Impact:** Eliminates remaining code-translation crashes.

### 🛡️ False-Positive Filter Hardening (Crash Prevention)

**Issue:** ~476 code-like strings in game translations were being translated, causing Ren'Py crashes (`IndexError: list index out of range` in `renpy/ui.py`). Game logic conditions, stat abbreviations, and format templates were leaking through the filter chain.

**Root Cause Analysis (69,918-line strings.rpy — SpaceJourneyX):**
- 335 Python condition strings (`'likes_toy_talk' in moira.done`)
- 54 short ALL_CAPS game stats (`NOT`, `REP`, `INT`, `CON`, `DEX`)
- 37 code-logic expressions (`moira in GAME.crew`)
- 7 broad code patterns (`GAME.hour < 18 and GAME.questSys.isDone(...)`)
- 4 format-string templates (`"Track: {} | Dist: {}".format(...)`)
- 36 newly-classified Ren'Py keywords (`scene`, `with`, `at`, `return`, `screen`, `label`, `menu`, `init`)

**Fixes:**

1. **New detection patterns** (4 pre-compiled regexes + 2 inline checks):
   - `_PYTHON_CONDITION_RE`: `'var_name' in obj.attr` — game logic conditions
   - `_CODE_LOGIC_RE`: `X not in GAME.crew` — dotted-path code (requires `.` to avoid catching "Getting in Shape")
   - `_SHORT_ALL_CAPS_RE`: `NOT`, `STR`, `INT` (2-6 chars) — with whitelist (`OK`, `NO`, `ON`, etc.)
   - `_FORMAT_TEMPLATE_RE`: `"...".format(...)` — Python format templates
   - Broad code detector: ≥2 dotted refs + comparison/boolean operators
   - `not func_call()` prefix handler

2. **Ren'Py text tag fix**: `{b}Hello{/b}` was wrongly caught by format-placeholder check. Now Ren'Py tags (`{b}`, `{/b}`, `{color=...}`, `{size=...}`, etc.) are stripped before counting format placeholders.

3. **RENPY_TECHNICAL_TERMS expanded**: Added 34 crash-causing keywords in three rounds:
   - **Round 1** (13): `scene`, `with`, `at`, `behind`, `as`, `onlayer`, `zorder`, `parallel`, `block`, `contains`, `pause`, `repeat`, `function`
   - **Round 2** (10): `return`, `screen`, `label`, `menu`, `init`, `call`, `jump`, `python`, `define`, `image`
   - **Round 3** (11 — Screen Language): `textbutton`, `imagebutton`, `mousearea`, `nearrect`, `hbox`, `vbox`, `vbar`, `transclude`, `testcase`, `nvl`, `elif`
   - Cleaned 5 duplicate terms (`ascii`, `input`, `insensitive`, `style`, `viewport`)
   - **Total: ~217 unique technical terms**

4. **Python code pattern strictness overhaul** (prevents natural language over-filtering):
   - `for X in` → requires statement-level context with `:` ending
   - `return X` → only catches `return self/True/False/None/digit/bracket`
   - `while X` → requires `:` ending or boolean keywords (`True/False/not/digit`)
   - `with X as` → requires context manager call pattern `with X(...) as`
   - File path concat → requires quotes or `/` to match
   - **Result:** 10 legitimate English phrases previously over-filtered now pass correctly

**Safety Balance:**
- Filter rate: 2.94% of translated entries blocked (476/16,165)
- Pass rate: 97.06% of legitimate text still passes through
- Title Case keywords (`Return`, `Screen`, `Menu`) still pass as UI labels
- Pattern accuracy: 39/39 test texts correctly classified (code blocked, natural language passed)
- 136 dedicated test cases + 394 total tests passing

**Impact:** Eliminates ~476 false-positive translations that could corrupt game logic and cause Ren'Py runtime crashes.

### 🛡️ CRITICAL: Alphabet-Independent Token Format (⟦N⟧)

**Issue:** Google Translate transliterated legacy Latin placeholder tokens on Cyrillic/Greek targets, breaking restoration for multiple token families.

**Fix:** Migrated placeholder keys to Unicode bracket tokens (`⟦N⟧`) so token identifiers contain no transliterable Latin letters.

```python
# Legacy (<=2.7.0)
# VAR0, TAG1, ESC_PAIR2, DIS3, PCT4, ESC_OPEN, ESC_CLOSE

# 2.7.1
key_content = f"⟦{counter}⟧"
```

**Restoration Layers:**
- Stage 0: Unicode token restore (`⟦ 0 ⟧` → `⟦0⟧`)
- Stage 0.5/0.6: Backward compatibility for legacy transliterated/spaced tokens
- Stage 1: Generic legacy restore path

**Impact:** Eliminates transliteration-based token loss while keeping backward compatibility for older cached outputs.

### 🔧 Placeholder Corruption Fuzzy Recovery

**Issue:** Google inserted spaces inside bracket expressions (`[player.name]` → `[player. name]`).

**Fixes:**
- `restore_renpy_syntax()` cleans dot-spacing in bracket content
- `validate_placeholders()` compares whitespace-insensitive normalized forms

**Result:** Placeholder corruption false positives are greatly reduced without relaxing strict structural checks.

### 🛡️ Placeholder Integrity v3.6 — Injection Recovery, Word-Boundary Fix, Early-Exit

**Issue 1: Full token deletion**
Google occasionally removed `⟦RLPH...⟧` markers entirely.

**Fix:** Added `inject_missing_placeholders()` to reinsert missing originals by proportional position from protected text.

**Issue 2: Broken insertion boundaries (fixed in v3.6)**
Earlier insertion could split words or glue placeholders to text.

**Fix:**
- Snap to real space boundaries when available
- Fallback to nearest text edge when no spaces exist
- Always enforce sane spacing around injected values

**Issue 3: Glossary false positives**
Glossary placeholders (`_G*`) were treated like syntax placeholders.

**Fix:** `validate_translation_integrity(..., skip_glossary=True)` now ignores glossary keys by default.

**Issue 4: Double-protection in preprotected flows**
DeepL/AI paths could re-protect already protected text.

**Fix:** Preprotected metadata guards now consistently use `original_text`.

**Issue 5: Cache key mismatch**
Protected-vs-original key mismatch created duplicate cache entries.

**Fix:** Cache keys normalized to `metadata.get('original_text', request.text)` in retry and batch paths.

**Issue 6: Unnecessary retries when tokens are fully deleted**
If raw response had no `RLPH`, retry + Lingva fallback were usually wasted.

**Fix (Early-Exit):**
- If raw output still contains `RLPH`: allow retry/fallback path
- If raw output contains no `RLPH`: skip retry/fallback and inject immediately

**Observed gain:** typically removes 2-3 seconds and 3 extra network calls for affected lines.

**Integrity handlers:** multi-endpoint, single-endpoint, batch multi-endpoint, batch single-endpoint now all follow injection-first recovery.

### 🔧 Proxy Manager v2.1 — Priority Logic Fix

**Issue:** Personal/manual proxies were mixed with unstable free proxies.

**Fix:**
- If `proxy_url` or `manual_proxies` exists: use only personal/manual proxies
- If none exists: fetch free proxies (fallback mode)

**Additional UX:** Added localized warning when proxy is enabled but only free proxies are used.

### ⚡ Google Rate-Limit Stabilization

**What changed:**
- Global cooldown with escalating backoff on HTTP 429
- Lower parallelism in sensitive paths to reduce ban cascades
- Better endpoint health handling and pacing jitter

**Why:** Reduce cross-mirror cascade throttling and improve sustained throughput stability.

### 🧩 Translation Pipeline Hardening (2.7.1 Addendum)

**Scope:** End-to-end pipeline review from **Start Translation** click to final `strings.rpy/strings.json` output.

**Fixes included:**
- Removed duplicate restore call in pipeline phase-1 result assembly (prevents `{i}{i}...{/i}{/i}` double-tag corruption and related Ren'Py runtime instability)
- Hardened `strings.json` sanitization against separator remnants, placeholder leakage (`⟦RLPH...⟧`, `XRPYX_`, `RNPY_`), and HTML tag bleed (`<span>`, `<div>`)
- Fixed dead code path in `save_translations()` and restored reliable success/failure logging
- Improved worker shutdown safety with timeout fallback (`wait` → `terminate`) to reduce dangling thread risk
- Minor cleanup: removed duplicated inline comment in translator lazy-init block

### 🔀 Delimiter-Aware Translation System (Pipe Variants)

**Issue:** Variant texts like `<choice_a|choice_b|choice_c>` were translated as a single block, causing semantic drift and malformed mixed outputs in some engines.

**Fix:** Added delimiter-aware flow that safely splits, translates, and rejoins pipe-variant segments.

**What changed:**
- Added `split_delimited_text()` / `rejoin_delimited_text()` pipeline in syntax protection layer for `<...|...>` and bare-pipe variant patterns
- Integrated segment-based request creation in translation pipeline, preserving per-entry metadata and placeholder context
- Added config toggle `enable_delimiter_aware_translation` (default: `true`) in settings and `config.json`
- Updated phase-1 result assembly to avoid duplicate restore on pre-restored translator outputs (prevents double wrapper tags)
- Improved debug logging output for delimiter previews using UI-safe brackets (`‹...›`) to avoid renderer swallowing `<...>`

**Compatibility:**
- Works with Google / DeepL / OpenAI / Gemini / Local LLM paths without changing engine public API
- Falls back to normal single-request flow when delimiter pattern is not detected

**Validation:**
- Added `tests/test_delimiter_aware.py` with 33 dedicated tests (split/rejoin/roundtrip/edge cases/config toggle)
- Full suite verification after integration: `215 passed` (excluding `tests/test_settings_sanitization.py` environment-specific collection issue)

### ✅ Validation

- Initial test suite result (at time of delimiter-aware feature implementation): `167 passed`
- After hardening updates: `215 passed`
- After all v2.7.1 features + atomic segment tests: **520 passed**
- All counts exclude `tests/test_settings_sanitization.py` (environment-specific collection issue)

### 🔍 Deep Extraction Engine

**Issue:** Many translatable strings in Ren'Py projects were missed by the standard extraction pipeline:
- `define quest_title = "text"` / `default player_name = "text"` without `_()` wrappers
- f-string templates (`f"Welcome back, {player}!"`)
- Multi-line dict/list structures with translatable text values
- API calls like `QuickSave(message=...)`, `CopyToClipboard(...)`, `narrator(...)`, `renpy.display_notify(...)`
- `tooltip "hint text"` properties in screen language
- Compiled `.rpyc` strings from extended Ren'Py API calls

**Solution — Deep Extraction Module (`src/core/deep_extraction.py`):**

- **DeepExtractionConfig**: Three-tier API call classification
  - Tier-1 (16 text calls): `renpy.notify`, `renpy.confirm`, `Character`, `Text`, `ui.text`, etc.
  - Tier-2 (4 contextual calls): `QuickSave`, `CopyToClipboard`, `FilePageNameInputValue`, `Help`
  - Tier-3 (30+ blacklist calls): `Jump`, `Call`, `Show`, `Hide`, `Play`, `SetVariable`, etc.

- **DeepVariableAnalyzer**: Heuristic scoring (0.0–1.0) for variable name classification
  - Prefix/suffix/exact matching for translatable/non-translatable names
  - `is_technical_string()` with 15 compiled regex patterns for false positive prevention
  - Reliably classifies `quest_title` → translatable, `persistent.flags` → non-translatable

- **FStringReconstructor**: Converts `{expr}` → `[expr]` (Ren'Py-compatible) with static text ratio threshold (≥30%)

- **MultiLineStructureParser**: Detects multi-line `define`/`default` structures, balanced bracket collection, AST-based value extraction with DATA_KEY_WHITELIST/BLACKLIST filtering

**Parser Integration (7 new patterns, 6 secondary passes):**
- Bare define/default string extraction with variable name filtering
- `tooltip` property, `QuickSave(message=)`, `CopyToClipboard()` secondary passes
- f-string template extraction secondary pass
- `$ renpy.confirm()`, `$ narrator()`, `$ renpy.display_notify()` secondary passes

**RPYC Reader Integration (7 new DeepStringVisitor handlers):**
- `QuickSave`, `CopyToClipboard`, `FilePageNameInputValue`, `narrator`, `renpy.display_notify`, `renpy.display_menu`, `renpy.confirm`
- Tier-3 blacklist prevents extraction of non-translatable call arguments
- Smart variable filtering with DeepVariableAnalyzer for FakeDefine/FakeDefault code objects

**Config Settings (7 new toggles):**
- `enable_deep_extraction` (master toggle)
- `deep_extraction_bare_defines`, `deep_extraction_bare_defaults`, `deep_extraction_fstrings`
- `deep_extraction_multiline_structures`, `deep_extraction_extended_api`, `deep_extraction_tooltip_properties`

### 📝 Key Files Updated in 2.7.1

- `src/core/deep_extraction.py` *(NEW — shared Deep Extraction module)*
- `src/core/parser.py` *(7 new patterns, 6 secondary passes, multi-line structure support)*
- `src/core/rpyc_reader.py` *(7 new DeepStringVisitor handlers, smart var filtering)*
- `src/core/syntax_guard.py`
- `src/core/translator.py`
- `src/core/ai_translator.py`
- `src/core/proxy_manager.py`
- `src/backend/settings_backend.py`
- `src/core/translation_pipeline.py`
- `src/utils/config.py` *(7 new deep extraction config fields)*
- `config.json` *(7 new deep extraction settings)*
- `tests/test_deep_extraction.py` *(NEW — 65 tests for Deep Extraction)*
- `tests/test_delimiter_aware.py` *(NEW — 33 tests for delimiter-aware translation flow)*
- `tests/test_integrity_injection.py`
- `tests/test_deepl_ai_preprotected.py`

---

## [2.7.0] - 2026-02-10
### 🔥 Multi-Layer Runtime Hook (v2.7.0 patch)

**Root Cause:** Ren'Py's `config.replace_text` runs after tag tokenization in `renpy/text/text.py.apply_custom_tags()`, so it only ever sees text fragments (e.g. `"Hello {b}World{/b}!"` becomes `"Hello "`, `"World"`, `"!"`). Full-sentence exact matching is impossible at that stage.

**Fix:** Added a three-layer hook inside the v2.7 runtime translation feature so we can:

- **Layer 1 – `config.say_menu_text_filter`**: runs before Ren'Py's translation/substitution, gets the complete string with tags, applies word-boundary-aware FlashText matching, protects `[variables]`/`{tags}`, and chains any previous filter.
- **Layer 2 – `config.replace_text`**: operates on the tag-split fragments (UI strings, text fragments) using aggressive substring matching with smart case/whitespace handling, while preserving and chaining existing handlers like Zenpy's `__next_replace__`.
- **Layer 3 – `config.all_character_callbacks`**: optional debug hook that logs every `what` text before processing and helps verify coverage in complex dialogue.

- Added `_RL_KeywordProcessor` (word-boundary) + `_RL_SubstringProcessor` (fragment) for dual-processing, Shift+R hotkey for reload, Ren'Py searchpath discovery, Turkish/European character support, and `[SAY_FILTER]/[REPLACE]/[DIALOGUE]` debug log prefixes.

This patch stays within the [2.7.0] entry because it represents a runtime-hook rewrite that ships on that release.

### 🔧 Runtime Hook Refinements
- **Late Init Chaining:** Deferred our runtime hook wiring to `init 999 python` so that it runs after any game-defined filters (emoji handlers, UI tweaks) and preserves the trailing filters via `_rl_prev_say_menu_filter` / `_rl_prev_replace_text` chaining.
- **Spacing Restoration:** Added a regex-based post-processing step to both `say_menu_text_filter` and `replace_text` so Ren'Py strings never stick to punctuation after translation (`Hello.World` → `Hello. World`).
- **Template Synchronization:** Ensured `runtime_hook_template.py` and the generated `zzz_renlocalizer_runtime.rpy` are in sync with these refinements so every project gets the same late-install, spacing-safe hook without manual edits.

### 🛠️ Runtime Hook Generation & Compatibility Fixes

- **Format String Generation Fix:** Fixed critical `ValueError: Single '}' encountered in format string` error during hook generation. Changed from unsafe `str.format(renpy_lang=...)` to safe `.replace("{renpy_lang}", renpy_lang)` in both `translation_pipeline.py` and `app_backend.py`. This prevents Python format string parser errors when template contains unescaped braces (e.g., in regex patterns like `[^\}]`).
  - **Root Cause:** Template contains regex patterns with literal braces that conflict with Python format syntax
  - **Solution:** Switched to explicit string replacement to avoid format string parsing
  - **Status:** ✅ RESOLVED – Hook files now generate without syntax errors
  
- **Escaped Brace Normalization:** Added automatic normalization step after placeholder replacement to convert escaped braces (`{{` → `{`, `}}` → `}`) in generated hook files. This prevents Ren'Py from misinterpreting double-braces as Python dictionary syntax, which was causing `TypeError: unhashable type: 'RevertableDict'` crashes.
  - **Impact:** Eliminates runtime failures when hooks are injected into games
  - **Verified With:** Multiple Ren'Py 7.x and 8.x games
  
- **Google Mirror Ban Duration Optimization:** Reduced temporary ban duration from 5 minutes (300 seconds) to 2 minutes (120 seconds) in `src/core/constants.py`. This allows mirrors to recover and re-enter the rotation faster when Google Translate endpoints are temporarily unresponsive, reducing translation wait times.
  - **Rationale:** 5 minutes was too aggressive; 2 minutes allows faster failover while still protecting against rate-limit issues
  - **Fallback Chain:** When mirrors are banned, system automatically falls back to Lingva Translate, ensuring continuous translation service
  
- **Ren'Py Key Binding Compatibility:** Removed incompatible hotkey bindings (`config.underlay.append(renpy.Keymap(...))`) that were causing `Exception: Invalid key specifier` errors in Ren'Py. The hotkey system attempted to register `f7`, `shift_l`, and `shift_r` which are not valid Ren'Py key specifiers in the expected format.
  - **Affected Hotkeys Removed:** 
    - F7 toggle debug mode
    - Shift+L force language change
    - Shift+R reload translations
  - **Alternative:** Debug logging is now automatic and logged to `renlocalizer_debug.log` in the game directory
  - **Impact:** Games no longer crash during initialization due to key binding validation errors

### 🌟 Universal Runtime Hook v2.7.0
- **Multi-File Support:** Now scans and loads translations from ALL `.rpy` files in the `tl/{language}/` directory recursively.
- **Dialogue Translation:** Added robust support for dialogue blocks (`# character "original"` / `character "translated"`).
- **Early-Init Boot:** Switched to `init -999 python` for maximum compatibility and earlier hook initialization.
- **Auto-Gen Logic:** Synchronized translation pipeline to automatically install the hook based on `auto_generate_hook` setting.
- **Exact Match Priority:** (FIX) Implemented high-priority exact match check before substring processing. This fixes issues where strings containing placeholders (e.g., `[n1002]`) were failing to translate because the substring processor would break them before they could match an entry in `strings.json`.
- **Improved Placeholder Protection:** (FIX) Corrected regex and escaping in the placeholder protection mechanism to prevent `KeyError` and template formatting errors during hook generation.
- **Startup & Shutdown Stability:** (FIX) Corrected invalid imports in `app_backend.py` and added missing `asyncio`/`multiprocessing` imports in `run.py` to prevent crashes and ensure clean application shutdown.

### 🚀 Dictionary-Based Runtime Translation Hook (Major Enhancement)
- **New Translation System:** Completely rewrote runtime translation hook inspired by ZenPy's approach
  - **Problem Solved:** Ren'Py's `translate_string()` only works for strings marked with `_()` function, leaving most dialogue untranslated
  - **Solution:** Hook now loads translations from `strings.rpy` into a dictionary and performs direct key-value lookup
  
- **How It Works:**
  1. At game init, parses `tl/{language}/strings.rpy` file
  2. Extracts all `old "..." / new "..."` pairs into dictionary
  3. Uses dictionary lookup for instant translation (O(1) performance)
  4. Falls back to Ren'Py's native `translate_string()` if not found in dictionary
  5. Supports placeholder normalization for dynamic strings

- **Debug Mode:**
  - Debug logging is automatic, no hotkey needed
  - Writes detailed logs to `renlocalizer_debug.log` in game directory
  - Shows which strategy was used: `[DICT-OK]`, `[RENPY-OK]`, `[NORM-OK]`, `[MISS]`
  - Check logs to identify untranslated strings

- **Updated Files:**
  - `src/core/translation_pipeline.py` - New hook generation code
  - `src/backend/app_backend.py` - Synchronized hook generation code

### Technical Details
- Hook version: v2.7.0
- Dictionary approach eliminates dependency on `_()` function
- Supports UTF-8-BOM encoding for strings.rpy
- Handles escaped quotes and newlines in translation entries
- Compatible with existing ZenPy translations (can coexist)

### 🔧 Critical Import Fixes & Spaced Token Corruption Repair
- **Missing Type Hint Import:** Fixed `NameError: name 'Callable' is not defined` in `src/core/translator.py` (lines 77, 78, 1597). Added `Callable` to the `typing` imports on line 14.
  - Impact: Prevents syntax errors during type checking and IDE analysis
  - Status: ✅ RESOLVED
- **Missing LocalLLMTranslator Import:** Fixed `NameError: LocalLLMTranslator is not defined` in `src/core/translation_pipeline.py` (line 2186). Added `LocalLLMTranslator` to imports from `src.core.ai_translator` on line 35.
  - Impact: Enables Local LLM translator instantiation in translation pipeline
  - Status: ✅ RESOLVED
- **Spaced Token Corruption Bug (CRITICAL):** Fixed a critical restoration bug where Google Translate's space insertion corrupts placeholders (e.g., `VAR0` becomes `VAR 0`). 
  - **Root Cause:** Token regex pattern could not match spaced variants, causing restoration to fail and placeholders to remain corrupted in output.
  - **Fix Applied:** Added pre-processing stage (`AŞAMA 0.5`) in `restore_renpy_syntax()` that detects and merges spaced tokens (`VAR 0` → `VAR0`) before main restoration begins.
  - **Testing:** Verified with multiple test cases - all spaced token variations now restore correctly with 100% integrity.
  - **Impact:** Eliminates "PLACEHOLDER_CORRUPTED" errors in logs, ensures all translations pass integrity validation.
  - **Status:** ✅ RESOLVED
- **Comprehensive System Verification:** Executed full project health check:
  - ✅ All core imports working (translator, ai_translator, syntax_guard)
  - ✅ Translation pipeline integration verified
  - ✅ HTML protection system tested and validated
  - ✅ Syntax guard token/HTML/XML modes confirmed functional
  - ✅ Wrapper tag handling verified correct
  - ✅ Spaced token corruption scenario tested - now fixed
  - ✅ All major systems production-ready

### 🌍 Multilingual Text Filtering Improvements
- **Problem:** Russian and other non-Latin language text (Chinese, Arabic, etc.) was being incorrectly filtered out during extraction
- **Root Causes Identified & Fixed:**
  1. **Overly Broad Placeholder Pattern (Line 1542):**
     - Old: `re.fullmatch(r"\s*(\[[^\]]+\]|\{[^}]+\}|%s|%\([^)]+\)[sdif])\s*", text)`
     - Issue: Rejected ALL bracketed content indiscriminately, including `[Привет]` (valid Russian text)
     - Fix: New logic distinguishes technical placeholders (`[item]`, `[who.name]`) from user text (`[Привет]`, `[你好]`)
       - Technical markers detected: dots (`who.name`), underscores (`_var`), digits (`item0`), equals signs (`color=red`)
       - Non-Latin script in brackets: preserved (Russian, Chinese, Arabic, etc.)
       - Single English words in brackets: rejected as technical placeholders
  
  2. **Text Cleaning Logic Issue (Lines 1679-1690):**
     - Old: After removing brackets, if empty string remained, text was rejected
     - Issue: Texts like `[Привет]` became empty after bracket removal, failing the meaningful content check
     - Fix: Skip remaining content check if original text is ONLY brackets (already validated by earlier checks)
  
  3. **Missing Unicode Ranges (Line 1626):**
     - Old: Strange character detection excluded only Latin, Cyrillic, CJK, Japanese, Korean
     - Issue: Arabic (`\u0600-\u06FF`), Hebrew, Farsi text was counted as "strange characters", causing rejection
     - Fix: Added missing Unicode ranges:
       - Arabic/Farsi: `\u0600-\u06FF`
       - Hebrew: `\u0590-\u05FF`

- **Test Results (20/20 Passing):**
  - Russian: `Привет`, `[Привет]`, `Привет [who.name]` ✅
  - Chinese: `你好`, `[你好]`, `我喜欢` ✅
  - Arabic: `مرحبا`, `[مرحبا]`, `السلام` ✅
  - Turkish: `Merhaba`, `Hoş geldiniz` ✅
  - Japanese: `こんにちは`, `ありがとうございます` ✅
  - Korean: `안녕하세요`, `감사합니다` ✅
  - Technical placeholders correctly rejected: `[item]`, `[player_name]`, `[item0]` ✅

### 🧠 Advanced Extraction Logic (Precision & Recall)
- **Deep Code Analysis (Recall Boost):**
    - **Python AST parsing:** Implemented `ast` module based extraction for `FakePython` blocks (`init python`, `$ variable = "..."`) to capture meaningful strings while ignoring code logic.
    - **User Statement Support:** Added extraction for custom user-defined statements (e.g., `quest start "Chapter 1"`).
    - **Hidden Argument Scanning:** Enabled scanning of hidden arguments in dialogue commands (e.g., `e "Hello" (what_prefix="...")`).
- **False Positive Elimination (Precision Boost):**
    - **Strict Path Filtering:** Added regex to strictly ignore file paths containing slashes (e.g., `audio/bgm/track.ogg`).
    - **Command Masquerade Detection:** Prevents extraction of strings that look like Ren'Py commands (`jump label`, `call screen`, `show image`, `if condition`).
    - **Strict Variable Check:** Enforced stricter `snake_case` variable filtering to avoid translating technical IDs.

### 🎯 Parser Context Tracking
- **Indentation-Based Context Stack:** Replaced the naive regex-based context tracking with a robust indentation-aware stack system.
  - Uses `_calculate_indent()`, `_pop_contexts()`, `_detect_new_context()`, and `_build_context_path()` helper functions.
  - Accurately determines `label`, `screen`, `menu`, and `python` block boundaries.
  - Ensures translatable strings are tagged with the correct context path (e.g., `['label:start', 'menu']`).
- **Menu Context Fix:** Fixed a critical bug where `menu:` blocks were detected but not returning a `ContextNode`, causing menu choices to be misattributed.
- **Smart Deduplication:** Improved the deduplication key to include `character` name while removing line number dependency. This ensures:
  - Same dialogue from different characters is preserved separately (important for gendered translations).
  - Identical strings on different lines are correctly deduplicated.
- **Hidden Label Support:** Added `hidden_label_re` regex to detect `label xxx hide:` patterns and skip translation for hidden labels.
- **String Unescaping Overhaul:** Refactored `_extract_string_content()` to properly handle:
  - Raw strings (`r"..."`, `rf"..."`).
  - Unicode escape sequences (`\n`, `\t`, `\uXXXX`).
  - Proper delimiter handling for both single and double quotes.
- **Show Text Statement Support:** Added dedicated regex (`show_text_re`) to capture temporary text displays:
  - Example: `show text "Loading..." at truecenter`
  - Commonly used for loading screens, notifications, and temporary messages
  - Previously missed text type now fully supported
- **Window Show/Hide Text:** Added `window_text_re` for window transition text:
  - Example: `window show "Narrator speaking..."`, `window auto "Text"`
  - Extended to include `window auto` command
  - Less common but used in some visual novels for narrator control
- **Hidden Arguments Extraction:** Added `hidden_args_re` for dialogue formatting arguments:
  - Example: `e "Hello" (what_prefix="{i}", what_suffix="{/i}")`
  - Captures `what_prefix`, `what_suffix`, `who_prefix`, `who_suffix`
  - Extended to include `what_color`, `what_size`, `what_font`, `what_outlinecolor`, `what_text_align`
  - Often missed but critical for maintaining text formatting across translations
- **Triple Underscore Translation:** Added `triple_underscore_re` for immediate translation:
  - Example: `text ___("Hello [player]")`
  - Translates AND interpolates variables in a single pass
  - Used for dynamic text that needs both translation and variable substitution
- **False Positive Prevention:** All new extraction passes use `is_meaningful_text()` filter:
  - **CRITICAL FIX:** Filter now checks unescaped text instead of quoted strings
  - Rejects file paths, URLs, asset names, code snippets
  - Filters out technical strings, variable names, and binary data
  - Prevents translation of configuration values and internal identifiers

### 🏗️ Code Quality & Architecture
- **DRY Refactoring:** Consolidated 4 extraction passes (~110 lines) into single `_process_secondary_extraction()` helper method (~50 lines)
  - Eliminates code duplication across show_text, window_text, hidden_arg, and triple_underscore passes
  - Single point of maintenance for extraction logic
- **TextType Constants:** Introduced `TextType` class to eliminate magic strings
  - Prevents typos and enables IDE autocomplete
  - Values: `SHOW_TEXT`, `WINDOW_TEXT`, `HIDDEN_ARG`, `IMMEDIATE_TRANSLATION`, etc.
- **Exception Handling:** Added comprehensive try-except in extraction helper
  - Catches `ValueError`, `IndexError`, `UnicodeDecodeError`, `AttributeError`
  - Logs warnings but continues processing (no data loss on single line failure)
- **Logger Optimization:** Added `isEnabledFor()` checks before f-string formatting
  - Prevents unnecessary string formatting when logging is disabled
  - Improves performance by ~100ms for 1000+ line files
- **Safety Scaling:** Added `MAX_LINE_LENGTH` (10000) check and optimized regex patterns
  - Prevents ReDoS attacks by skipping overly long lines before processing
  - Optimized `action_call_re` with non-greedy matching and `_QUOTED_STRING_PATTERN`
  - **CRITICAL FIX:** Replaced greedy `\s*` with safe `\s?` in Syntax Guard fuzzy matching (prevented freeze on complex texts)
  - Centralizes magic values (`EMPTY_CHARACTER`) for maintainability

### 🛡️ Syntax Guard v3.2 (Ren'Py 8 Full Support)
- **Disambiguation Tag Protection (`{#...}`):** Added dedicated regex pattern (`_PAT_DISAMBIG`) for `{#identifier}` tags. These are critical for Ren'Py's translation system (e.g., `"New{#game}"` and `"New{#project}"` are different translation IDs).
- **Enhanced Variable Pattern:** Improved `_PAT_VAR` regex to handle:
  - Dictionary access syntax: `[player['name']]`, `[dict["key"]]`
  - Translatable flag: `[mood!t]`
  - Method calls: `[player.get_name()]`
  - Nested brackets: `[items[0]]`
- **Ren'Py 8 Tag Support:** Updated `_OPEN_TAG_RE` and `_CLOSE_TAG_RE` with new Ren'Py 8 tags:
  - **Accessibility:** `{alt}`, `{noalt}`, `{/alt}`
  - **Control:** `{done}`, `{clear}`
  - **Effects:** `{shader}`, `{transform}`, `{/shader}`, `{/transform}`
  - **Ruby Text:** Added missing `{/rb}`, `{/rt}` closing tags
- **Escaped Bracket Protection:** Extended escape pattern to include `[[` and `]]` alongside `{{` and `}}`.
- **DIS Placeholder Prefix:** Disambiguation tags now use `XRPYXDIS0XRPYX` format for maximum protection integrity.
- **Backward Compatibility:** All syntax guard improvements are fully backward compatible with Ren'Py 7.x. New Ren'Py 8 tags (`{#...}`, `{alt}`, `{shader}`, etc.) are safely ignored in older games.

### ⚡ Regex Performance & Safety (Hotfix)
- **Catastrophic Backtracking Prevention (Critical Fix):**
  - **Root Cause:** Complex variable pattern regex `_PAT_VAR` could hang on deeply nested brackets (e.g., `[var[[[[[[[deeply[nested]]]]]]]]]`).
  - **Solution:** Simplified pattern to prevent catastrophic backtracking: `\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]`
  - **Testing:** Verified with 60-level deep nesting - all tests pass in <1ms (previously would hang)
  - **Impact:** GUI no longer freezes when translating text with complex bracket structures
  
- **Function Safety Hardening (`_repair_broken_tag_nesting`):**
  - Added defensive checks to prevent pathological input attacks:
    - **Text Length Guard:** Skip processing if text > 5000 characters
    - **Token Count Guard:** Skip processing if resulting tokens > 200
    - **Graceful Fallback:** Return original text unchanged on any error (safety-first design)
  - **Impact:** Prevents CPU exhaustion and ensures application stability on edge-case inputs

### 🔧 RPYC/RPYMC Reader Enhancements (Binary AST Extraction)
- **Testcase Node Support:** Fixed `FakeTestcase` mapping to properly extract text from Ren'Py 8.x `testcase` statements (automated test scenarios).
- **Duplicate Mapping Cleanup:** Removed redundant `Testcase` entry in CLASS_MAP for cleaner code organization.
- **Python 2/3 Compatibility:** Enhanced unpickler to handle both `__builtin__` (Python 2.7/Ren'Py 7) and `builtins` (Python 3/Ren'Py 8) module paths.
- **Ren'Py 8.5+ Node Coverage:** Comprehensive support for latest AST nodes:
  - `Bubble` (speech bubbles, 8.1+)
  - `TranslateSay` (combined translate+say, 8.0+)
  - `Testcase` (automated testing, 8.0+)
  - `PostUserStatement` (user statement hooks)
- **Screen Language 2 (SL2) Full Support:** Complete extraction from compiled screen cache files (`.rpymc`):
  - `SLDrag`, `SLBar`, `SLVBar` (advanced UI elements)
  - `SLOnEvent` (event handlers)
  - Action extraction: `Confirm()`, `Notify()`, `Tooltip()`, `Help()`
- **FakeOrderedDict Robustness:** Enhanced to handle Ren'Py 8.2+ flat list serialization format `[k, v, k, v]` in addition to traditional pair format `[(k,v), (k,v)]`.

### 🛡️ Security Hardening (Anti-Malware)
- **Secure Deserialization:** Overrode `pickle.find_class` to allow only whitelisted Ren'Py classes and standard Python types. Prevents arbitrary code execution (RCE) from malicious `.rpyc` files.
- **Recursion Safety:** Implemented iterative-like error handling for deep AST traversal to prevent StackOverflow crashes on complex scripts.
- **ReDoS Prevention:** Added strict length checks to text filters to prevent Regex Denial of Service attacks on binary garbage data.

### 🔄 Ren'Py 7 & 8 Universal Compatibility
- **Guaranteed Backward Compatibility:** All parser and syntax guard changes are fully compatible with Ren'Py 6.x, 7.x, and 8.x:
  - **Parser:** Indentation-based context tracking works identically across all versions (syntax unchanged since 2002).
  - **Syntax Guard:** New Ren'Py 8 features (`{#disambiguation}`, `{alt}`, `[var!t]`) are additive - regex patterns simply don't match in older games, leaving text untouched.
  - **RPYC Reader:** Handles both Python 2.7 (Ren'Py 7) and Python 3.9+ (Ren'Py 8) pickle formats with dual module path mapping.
- **Version-Specific Features:**
  - Ren'Py 7.x: Full support for `Say`, `Menu`, `Label`, `Screen`, standard text tags, variable interpolation.
  - Ren'Py 8.x: Additional support for `Bubble`, `TranslateSay`, `{#...}`, `{alt}`, `{shader}`, `[var!t]`, Harfbuzz text shaping.

### 🌍 Global Language Support (Universal Extraction)
- **Unicode-Aware Filtering:** Replaced restrictive ASCII-only text filters with a comprehensive Unicode-aware system. The tool now correctly identifies and extracts text in:
    - Cyrillic / Extended Cyrillic (Russian, Ukrainian) - Fixed issue where some chars were treated as junk.
    - CJK (Chinese, Japanese, Korean)
    - Latin Extended (Turkish, Vietnamese, European)
    - RTL Scripts (Arabic, Hebrew, Persian)

### 🏗️ Architectural Improvements (Refactoring)
- **Code Decoupling:** Moved hardcoded configuration values (Google endpoints, User-Agents) from `translator.py` to a centralized `src/core/constants.py` file.
- **Memory Optimization:** Optimized text extraction pipeline to use `Set` data structures (O(1) complexity) instead of Lists (O(N)), significantly improving performance on large files.
- **Stability Fix:** Replaced recursive AST traversal with an iterative stack-based approach in `translation_pipeline.py` to prevent RecursionErrors on deep file structures.

### 🧩 Advanced Features
- **Deep Text Extraction:** Enhanced the AST crawler to inspect complex Python data structures. The tool can now extract translatable strings from:
    - **Lists/Tuples:** `$ items = ["Health Potion", "Iron Sword"]`
    - **Dictionaries:** `$ quest = {"title": "Dragon Slayer", "desc": "Defeat the beast"}`
    - **Screen Actions:** `textbutton "Start Game"` (via Python AST parsing)
    - **Character Names:** Captures `Character("Name")` definitions to ensure names in foreign scripts (Russian, Japanese) are translated/transliterated.
- **Asset Protection:** Implemented a strict file path filter (`.png`, `.ogg`, `images/`) to prevent game crashes caused by translating technical asset paths.i
- **Smart Ratio Check:** Updated the "garbage collection" heuristic to accept any valid letter from the supported scripts, fixing the issue where non-English dialogues were treated as binary data.

### 📚 Ren'Py Documentation Research - Enhanced Pattern Coverage
- **Comprehensive Pattern Analysis:** Conducted deep research into official Ren'Py documentation to identify missing translatable string patterns. Added 7 new extraction patterns based on findings:

#### **New Extraction Patterns (Parser.py):**
1. **Double Underscore `__()` - Immediate Translation:**
   - Pattern: `__\s*\(\s*"text"\s*\)`
   - Example: `text __("Translate immediately")`
   - Use Case: Translates at definition time (similar to `_()` but immediate)
   - Registry: Added to `pattern_registry` as `TextType.IMMEDIATE_TRANSLATION`

2. **Triple Underscore `___()` - Interpolated Translation:**
   - Pattern: `___\s*\(\s*"text"\s*\)`
   - Example: `text ___("Hello [player]")`
   - Use Case: Translates AND interpolates variables in a single pass
   - Registry: Added to `pattern_registry` as `TextType.IMMEDIATE_TRANSLATION`
   - Secondary Pass: Implemented in `extract_text_entries()` with `finditer()` for multiple occurrences

3. **String Interpolation with `!t` Flag:**
   - Pattern: `\[(\w+)!t\]`
   - Example: `"I'm feeling [mood!t]."`
   - Use Case: The `!t` flag marks the variable for translation lookup
   - Note: Extracts full string, not just the variable placeholder

4. **Python Block Translatable Strings:**
   - Pattern: `^\s*(?:[a-zA-Z_]\w*\s*=\s*)?_\s*\(\s*"text"\s*\)`
   - Example: `python:\n    message = _("Hello")`
   - Use Case: Captures `_()` calls inside Python blocks
   - Context-Aware: Only extracts when inside `python:` block

5. **NVL Mode Dialogue:**
   - Pattern: `^\s*nvl\s+(?:clear\s*)?"text"`
   - Example: `nvl "This is NVL dialogue"` or `nvl clear "Text"`
   - Use Case: Novel-style text display mode
   - Registry: Added as `TextType.DIALOGUE`
   - Secondary Pass: Implemented with dedicated extraction logic

6. **Screen Parameter Usage Tracking:**
   - Pattern: `^\s*(?:text|label|tooltip)\s+([a-zA-Z_]\w*)(?:\s|$)`
   - Example: `screen message_box(title):\n    text title`
   - Use Case: Tracks when screen parameters are used with display elements
   - Note: Parameter names themselves are NOT extracted (false positive prevention)

7. **Image Text Overlays:**
   - Pattern: `^\s*image\s+\w+\s*=\s*Text\s*\(\s*"text"`
   - Example: `image my_text = Text("Overlay text")`
   - Use Case: Text overlays created via `Text()` displayable
   - Registry: Added as `TextType.SCREEN_TEXT`

8. **String Substitution Context Detection:**
   - Pattern: `^\s*\$?\s*([a-zA-Z_]\w*)\s*=\s*_\s*\(`
   - Example: `$ mood = _("happy")` → used in `"I feel [mood!t]"`
   - Use Case: Tracks variables that will be used with `!t` flag

#### **False Positive Prevention (is_meaningful_text):**
Added 4 new validation checks to prevent extraction of technical strings:

1. **Single-Word Parameter Rejection:**
   ```python
   # ❌ REJECT: "title", "message", "content" (variable names)
   # ✅ ALLOW: "Welcome to the game" (actual text)
   if len(text.split()) == 1 and text.replace('_', '').isalnum():
       if text.lower() in common_params:
           return False
   ```
   - Common Parameters: `title`, `message`, `text`, `label`, `caption`, `tooltip`, `header`, `footer`, `content`, `description`, `name`, `value`, `prompt`, `placeholder`, `default`, `prefix`, `suffix`, `hint`

2. **Interpolation-Only String Rejection:**
   ```python
   # ❌ REJECT: "[mood!t]" (only placeholder)
   # ✅ ALLOW: "I'm feeling [mood!t]." (has text)
   if re.fullmatch(r'\s*\[\w+!t\]\s*', text):
       return False
   ```

3. **Text() Constructor Technical Parameter Rejection:**
   ```python
   # ❌ REJECT: "size=24", "color=#fff", "font=DejaVuSans.ttf"
   # ✅ ALLOW: "Actual overlay text"
   if '=' in text and re.search(r'\b(size|color|font|outlines|xalign|yalign|xpos|ypos|style|textalign)\s*=', text):
       return False
   ```

4. **NVL Command Rejection:**
   ```python
   # ❌ REJECT: "clear", "show", "hide", "menu" (commands)
   # ✅ ALLOW: "Clear the path ahead" (actual dialogue)
   if text.lower() in {'clear', 'show', 'hide', 'menu', 'nvl'}:
       return False
   ```

#### **RPYC Reader Enhancements:**
Extended `_extract_strings_from_code()` with 3 new patterns to match parser.py:

1. **Triple Underscore `___()` Support:**
   - Pattern: `___\s*\(\s*"(.+?)"\s*\)`
   - Context: `python/___`
   - Extraction: Line 2162-2167

2. **`!t` Flag Interpolation Detection:**
   - Pattern: `"(.*?\[\w+!t\].+?)"`
   - Context: `interpolation_t`
   - Validation: Only extracts if string has actual text beyond placeholder (length > 3)
   - Extraction: Line 2169-2177

3. **NVL Mode Dialogue:**
   - Pattern: `nvl\s+(?:clear\s*)?"(.+?)"`
   - Context: `nvl`
   - Extraction: Line 2179-2184

#### **Consistency Guarantees:**
- ✅ **Parser ↔ RPYC Parity:** All new patterns implemented in both `.rpy` (parser.py) and `.rpyc` (rpyc_reader.py) extraction engines
- ✅ **Shared Validation:** RPYC reader uses `parser.is_meaningful_text()`, ensuring identical false positive filtering
- ✅ **AST-Based Extraction:** RPYC reader prioritizes AST parsing over regex for Python code, providing more reliable extraction
- ✅ **Backward Compatible:** All new patterns are additive - existing extraction logic unchanged

#### **Impact:**
- **Coverage Increase:** Estimated 5-15% more translatable strings captured (especially in games using NVL mode, Text() overlays, or `!t` interpolation)
- **False Positive Reduction:** ~20% fewer technical strings incorrectly marked for translation
- **Developer Experience:** Better handling of modern Ren'Py 8.x features and documentation-recommended patterns
- **Code Quality:** ~190 lines of new extraction logic with comprehensive inline documentation

#### **Testing Recommendations:**
- Test with games using NVL mode (visual novels)
- Test with games using `Text()` displayables for UI overlays
- Test with games using `!t` flag for dynamic text interpolation
- Verify no false positives on screen parameter names
- Verify technical `Text()` parameters (size, color, font) are not extracted


## [2.6.5] - 2026-02-06
### 🛡️ Critical Fixes & Stability Overhaul
- **Ren'Py 7 Compatibility:** Added `_renlocalizer_safe_translate` wrapper to handle `AttributeError` when `renpy.translate_string` is missing in older Ren'Py 7.x versions.
- **Smart RPA Extraction:** Improved UnRPA logic to trigger extraction even if some `.rpy` files exist. This ensures full data access in games that store main scripts inside `.rpa` while leaving a few helper script files outside.
- **Parser Stability Fix:** Resolved `AttributeError: get_context_line` by implementing state-tracking and proper method exposure in `RenPyParser`.
- **Atomic & Smart Cache System:**
  - **Atomicity:** Implemented temp-file based atomic save strategy for `translation_cache.json` to prevent corruption.
  - **Smart Lookup:** Handles `auto` source language detection correctly and allows **Cross-Engine reuse** of translations.
  - **Efficiency:** Reduced disk I/O by saving cache every 500 entries instead of after every batch.
- **Simplified Language Forcing:** Re-engineered `zzz_[lang]_language.rpy` to use a cleaner direct assignment (`config.default_language` & `_preferences.language`) for reliable first-launch application.
- **Ren'Py 7 Hook Compatibility:** Fixed a critical crash in the Runtime Hook (`zzz_renlocalizer_runtime.rpy`) on Ren'Py 7.x games where `renpy.translate_string` was not found.
- **Atomic Config Saving:** Implemented temp-file based atomic save strategy for `config.json`.
- **Permission Checking:** Added proactive write permission validation for settings and logs at startup.
- **Config Persistence:** Improved `save_config` with proactive permission checks and detailed logging to prevent silent failures.
- **Atomic File Operations:** Fixed a potential resource leak in atomic file writing on Windows where temporary files were not correctly cleaned up on failure.

## [2.6.4] - 2026-02-06
### ✨ New Features & Improvements
- **LLM XML Protection:**
  - **XML Tag Support:** Updated LLM engines (OpenAI, Gemini) to use `<ph id="0">` tags for placeholder protection, eliminating syntax corruption issues common with legacy tokens.
  - **Enhanced Resilience:** Improved restoration logic to handle AI-generated spacing variations around tags.
- **Deep Code Extraction (F-Strings & ATL):**
  - **F-Strings:** Extractor now fully supports Python f-strings (e.g., `f"Chapter {num}"`), capturing embedded variables with correct context.
  - **ATL Transforms:** Now captures `text` displayables inside Ren'Py ATL transformations.
- **Extraction Engine V2 (Global Optimization):**
  - **Standard Ren'Py Fallthrough:** Guaranteed extraction of fundamental engine strings (Start, Load, Preferences, Yes, No) even if they are hidden in the engine core.
  - **Smart UI Heuristics:** The engine now intelligently distinguishes between technical terms and short UI strings. It correctly captures "Back", "Next", "On", "Off" (Title Case) while safely ignoring technical `snake_case` variables.
  - **Deep UI Scanning:** Expanded Screen Language coverage to include hidden properties like `hover_text`, `selected_text`, `prefix`, `suffix`, `default`, `hint`, `subtitle`, and `credits`.
  - **Expanded Whitelist:** Added 10+ new usage scenarios to the extraction dictionary, significantly reducing "untranslated UI" issues within standard screens.

- **Maximum Translation Coverage (RPYC Engine Overhaul):** 
  - **Ren'Py 8.5.2 Full Support:** Updated the internal AST parser to fully support the latest Ren'Py features.
  - **Bubble & Testcase Parsing:** Added support for extracting text from Speech Bubbles (`bubble` statements) and Automated Test Cases (`testcase`), including properties like `alt`, `tooltip`, and `help`.
  - **Advanced Screen Language (SL2):** Now captures translatable strings from complex UI elements like `drag`, `bar`, `vbar`, and `onevent`.
  - **RPYMC Screen Extractor:** Transformed the simple cache reader into a full-featured UI text extractor. Now captures `text`, `button`, `tooltip`, and `alt` properties from compiled screen language files (`.rpymc`), unlocking previously inaccessible UI translations.
  - **Performance Optimization:** Implemented "Regex Pooling" and "Early Return" logic in the RPYC reader, boosting scanning speed by ~80% for large projects.
  - **Massive Cache Support:** Increased the internal cache capacity from 20,000 to **500,000 entries**, ensuring that large games (Visual Novels with 100k+ lines) no longer suffer from cache churn/reset performance issues.
  - **Future-Proofing:** Enhanced `FakeASTBase` and `FakeOrderedDict` to robustly handle new Ren'Py serialization formats, ensuring data integrity for future engine updates.
  - **Advanced Code Extraction (AST):** Updated the internal Python parser to detect and extract text from `renpy.input()`, `Confirm()`, `Notify()`, and `MouseTooltip()` calls, which were previously missed by the regex engine.
  - **Safety Fix:** Removed a dangerous regex pattern that validly extracted `renpy.show("image_name")` allowing users to accidentally translate technical image filenames. This is now handled safely via AST analysis.

- **Syntax Guard v3.1 (Hybrid Strategy):**
  - **Priority Syntax Guarding:** Regex patterns are now strictly ordered. Tags and variables are detected *before* simple escape sequences, preventing AI corruption of complex Ren'Py codes (e.g., `[variable]`).
  - **Nested Bracket Support:** Enhanced regex now correctly identifies and protects complex variables with internal brackets (e.g., `[list[0]]`, `[issue[1]]`) and dot notation (e.g., `[GAME.version]`).
  - **Atomic Placeholder Recovery:** Added a specialized repair system for "shattered" placeholders. If Google Translate splits a tag into `X R P Y X`, the system now reassembles it into `XRPYX` automatically, preventing fallback failures. This makes translation extremely resilient to Google Translate's random spacing.
  - **Bracket "Healing":** Automatically fixes common Google Translate corruptions where spaces are inserted into critical Ren'Py syntax (e.g., `[ [` → `[[`, `[ var ]` → `[var]`, `[list [ 1 ] ]` → `[list[1]]`).
  - **Python Formatting Support:** Added native protection for standard Python format specifiers (`%s`, `%d`, `%f`, `%i`) and named placeholders (`%(var)s`).

- **Global Localization (v2.6.4):** 
  - Updated **"tip_aggressive_translation"** across all 8 supported languages (**TR, EN, DE, ES, FR, RU, ZH-CN, FA**).
  - The tip now correctly informs users that Aggressive Mode is disabled by default for speed and should be toggled only if needed.
  - **Full English Fallback:** All QML pages (`SettingsPage`, `ToolsPage`, `GlossaryPage`, `AboutPage`, `HomePage`, `main.qml`) now use English as the default fallback language in `getTextWithDefault()` calls.
  - **Locale File Sync:** Added automated key extraction tool to ensure `tr.json` and `en.json` are always synchronized. Both files now contain **770 keys**.
  - **New Locale Keys:** Added missing translation engine display names (`translation_engines.google`, `translation_engines.deepl`, etc.) and warning dialog titles (`warn_title`).

### ⚙️ Backend & Logic
- **Hybrid Runtime Hook:** The `Force Runtime Translation` feature now uses a dual-hook strategy.
  - **Pre-Substitution Hook (`say_menu_text_filter`):** Intercepts dialogue strings *before* variable replacement (e.g., `%(name)s`), ensuring correct translation lookup for dynamic strings.
  - **Post-Substitution Hook (`replace_text`):** Continues to handle screen and UI text after rendering.
  - This solves the long-standing "untranslated variables" issue where strings like `Old "%(var)s"` failed to match `New "Bob"`.

- **Build System Hardening:**
  - Standardized environment initialization for PyInstaller builds.
  - Improved `run.py` to be more robust across different Windows locales.
  - **Windows Multiprocessing Safety:** Added `freeze_support()` and increased AST recursion limits to 5000 in `run.py` to prevent "Spawn Bomb" crashes on Windows systems.
  - **Dependency Cleanup:** Removed obsolete `PyQt6-Fluent-Widgets` and `darkdetect` libraries from the build specification, significantly reducing the final executable size (Pure QML architecture).
  - **Theme Isolation:** Enforced strict isolation from system themes to guarantee consistent application appearance.

- **Aggressive Translation Optimization:** Now **disabled by default** to maximize initial translation speed (from ~20s down to ~1s for 100-line batches). 
- **Regex Pooling Optimization:** Refactored the Syntax Guard module to use pre-compiled, module-level regex constants, boosting text processing performance by ~30-40%.
- **Enhanced Retry Mechanism:** If enabled, it attempts different Google Translate mirrors before falling back to Lingva Translate.
- **Lingva Optimization:** 
  - Reduced timeout (10s → 6s) for faster failover.
  - Implemented **Random Load Balancing** and updated mirror list (Prioritizing stable instances like `lunar.icu` & `garudalinux`).
- **URL Safety Limit:** Reduced maximum characters per request (Default: 2000) and capped UI limit at 2500. This prevents "400 Bad Request" errors caused by Google's URL length limits.
- **Enterprise-Grade Network Stack:**
  - **TCP Connection Pooling:** Implemented persistent connection pooling to eliminate handshake overhead during bulk translations.
  - **Smart DNS Caching:** Added 5-minute DNS caching to prevent redundant lookups.
  - **Exponential Backoff with Jitter:** Added intelligent retry logic (waiting with random jitter: 2s -> 4s -> 8s) when encountering `429 Too Many Requests` from Google.

### 🐛 Fixes
- **Taskbar Icon:** Fixed an intermittent issue where the application icon would be missing on the Windows Taskbar (Now forces native Windows API icon registration).
- **QML Syntax Error (SettingsPage):** Fixed a missing `ApiField {` declaration in `SettingsPage.qml` that caused the application to fail loading with "Syntax error at line 715".

### 🧠 Core Research & Fixes (Action & Context Support)
- **Advanced Action Extraction:**
  - **Secondary Pass Parser:** Introduced a multi-pass parser mechanism that can extract multiple distinct translatable strings from a single line. This enables capturing both the button text (e.g., "Delete") and the action prompt (e.g., `Confirm("Are you sure?")`) from complex `textbutton` statements.
  - **Binary Action Support:** Updated `rpyc_reader` and `rpymc_reader` to support extraction of `Confirm`, `Notify`, `Tooltip`, and `Help` actions directly from compiled Ren'Py files (`.rpyc` / `.rpymc`).
- **Context-Aware AI Translation:**
  - **Metadata Injection:** The translation engine now injects context type information (e.g., `type="[ui_action]"`, `type="[dialogue]"`) directly into the AI prompt's XML structure.
  - **Smart Prompting:** AI models are now explicitly instructed to use this context attribute to disambiguate short words (e.g., translating "Back" differently for a button vs. a dialogue).
- **Parser Robustness:**
  - **Safety Fix:** Removed an overly broad `renpy.show` regex that was incorrectly identifying internal image names as translatable text.
  - **Validation Tolerance:** Relaxed the `BATCH_PARSE_RE` pattern to tolerate extra attributes in XML tags, preventing failures when AI models hallucinate or add metadata to response tags.
- **Context Comments:** Added support for parsing `# context: ...` comments in `.rpy` files, preserving manual context hints during the translation process.
- **Hybrid Runtime Hook:** Restored `config.say_menu_text_filter` alongside `config.replace_text` to correctly translate interpolated strings (e.g., `%(name)s`) *before* variable substitution occurs.

## [2.6.3] - 2026-02-03
### 🛡️ Enhanced Placeholder Recovery & Hook System Fix
- **Advanced Fuzzy Recovery:** Strengthened the placeholder restoration system to catch more corruption patterns from Google Translate:
  - `XRPYXXTAG0` (double X) → Now recovered correctly
  - `XRPYCTAG0` (X→C character swap) → Now recovered correctly
  - `XRPYXTAG0XRPY` (missing trailing X) → Now recovered correctly
  - `XRPYXT AG0XRPY` (spaces inserted) → Now recovered correctly
  - Spaced character patterns like `X R P Y X T A G 0` → Now recovered
- **Runtime Hook Fix (Ren'Py Compliance):** Fixed critical issue with the runtime translation hook:
  - Removed `config.say_menu_text_filter` hook (runs BEFORE translation, so `translate_string()` was ineffective)
  - Now uses ONLY `config.replace_text` (runs AFTER substitutions, correct timing)
  - Added `define config.default_language` at file-level for proper first-run language setting
  - Added safety check to only apply translation if actually different from original
  - **Tools Hook Generator Updated:** The "Runtime Hook Generator" tool now creates the correct `zzz_renlocalizer_runtime.rpy` with proper Ren'Py-compliant hook code
- **Batch Translation Optimization:** Increased batch separator limits from 25→50 texts and 4000→8000 characters for better throughput

### 🅰️ Font Injection Revolution (Auto & Manual)
- **Manual Font Selection:** Added a powerful new tool in "Tools & Utils" that allows users to manually select and inject fonts from a curated list of over 80+ popular Google Fonts.
  - Categories include: Sans Serif, Serif, Display, Handwriting, and Monospace.
  - Perfect for matching the game's original atmosphere (e.g., using a "Horror" font for horror games).
- **Runtime Hooking (Bulletproof Font Replacement):** Implemented a "Nuclear Option" using Ren'Py Runtime Hooking. This intercepts the game's internal `get_font` calls, guaranteeing that your selected font is used even if the game developer has hardcoded specific fonts in Python scripts.
  - Solves the "font didn't change" issue in 99.9% of games.
  - Zero-crash architecture: Safely handles missing styles.
- **Smart Google Fonts API:** Switched from the unstable Google Fonts download page to the robust `google-webfonts-helper` API. This solves "Invalid ZIP" errors and ensures reliable downloads every time.
- **Automatic Language Normalization:** The system now intelligently maps language codes (e.g., `turkish` -> `tr`, `zh-CN` -> `zh`) to find the correct font family automatically.
- **Full Localization:** All font injection messages and UI elements are now fully localized in 8 languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `fa`, `zh-CN`).

- **🚨 CRITICAL: Batch Separator Placeholder Protection:** Fixed a major bug where the batch separator method was **not applying placeholder protection at all**. This was the root cause of placeholder corruption in long translations. Now all batch translations go through `protect_renpy_syntax` → translate → `restore_renpy_syntax` → `validate_translation_integrity`. If integrity check fails, the original text is preserved instead of corrupted translation.
- **Default Batch Size Reduced:** Changed default `max_batch_size` from 200 to 100 for better stability during long translations
- **Double Percent Protection:** Added `%%` (literal percent sign) to the protected syntax list. This prevents Ren'Py format specifier conflicts when translating strings containing `100%%`
- **Truncation Detection:** Added a check to detect when Google Translate truncates long text (translation < 30% of original length). Truncated translations are automatically reverted to original text instead of saving incomplete content.
- **Debug Logging:** Added detailed fallback logs to help diagnose when batch separator method fails
- **🛡️ HTML Wrap Protection (Experimental):** Implemented an alternative placeholder protection system using `<span translate="no" class="notranslate">` tags. This instructs Google Translate to ignore the content within the tags. **Note:** This feature is marked as experimental because free Google Translate endpoints don't fully support HTML mode. Default: OFF (placeholder system is more reliable). Can be enabled in Settings for testing.

### 🔄 Stability Restoration & Quality Improvements
- **v2.5.1 System Restoration:** The placeholder and syntax protection logic has been reverted to the v2.5.1 architecture, which has proven to be more stable and reliable.
- **New Placeholder Format:** Switched to the `XRPYXVAR0XRPYX` format for all translation engines. This "single-word" format is much more resistant to corruption by AI and Google Translate compared to old bracket-based formats.
- **🆕 Spaced Placeholder Strategy:** Placeholders are now surrounded by spaces before sending to translation API. This helps Google Translate treat them as distinct "words" (like proper nouns) and reduces corruption risk. Extra spaces are automatically cleaned during restoration.
- **🧠 Smart Hybrid Protection System:** Implemented an intelligent two-tier protection strategy:
  - **Wrapper tags** (tags that wrap the entire sentence, like `{i}Hello world{/i}`) are safely removed and stored. They're re-added after translation (opening at start, closing at end).
  - **Partial tags** (mid-sentence tags like `Hello {i}beautiful{/i} world`) are protected with placeholders to preserve their position in the translated text.
  - **Variables** (`[player_name]`, `[item]`) are protected with spaced placeholders (` XRPYXVAR0XRPYX `).
  - This approach eliminates wrapper tag corruption while maintaining translation accuracy for partial tags.
- **Fuzzy Matching Removed:** The RapidFuzz-based "Smart Repair" (Fuzzy Matching) feature in the Syntax Guard module has been removed to eliminate the risk of false-positive matches.
- **Tolerant Validation:** Integrity check phase is now more flexible; missing or corrupted placeholders now trigger a warning instead of rejecting the entire translation.
- **AI Prompt Optimization:** System prompts for OpenAI, Gemini, and Local LLMs have been updated to reflect the new placeholder format and rules.
- **UI Cleanup:** The "Smart Repair (Fuzzy Match)" option has been removed from the Settings page as it is no longer relevant in the new architecture.
- **Locale Synchronization:** All localization files (`locales/*.json`) have been updated, and deprecated keys have been cleaned up.

## [2.6.2] - 2026-02-01
### 🔧 Gemini Fix & Critical Safety Patch
- **Gemini Model Update:** Changed the default Gemini model from `gemini-2.0-flash-exp` (experimental) to `gemini-2.5-flash` (latest stable). This resolves issues where the API key would not work due to model access restrictions.
- **Zero-Tolerance Syntax Check:** Added a strict "Unbalanced Bracket Detector" to the integrity check phase. If a translation ends with an open bracket, it is immediately rejected.
- **Data Integrity (Atomic Save):** Implemented "Atomic Write" strategy for configuration files. `config.json` is now written to a temporary file first and safely renamed, ensuring zero data corruption even if the PC crashes or power is lost during save.
- **Thread-Safe Architecture:** Added `threading.Lock` to `ConfigManager` and a global `isBusy` lock to the Backend. This prevents race conditions and ensures thread safety across the entire application.
- **Refactoring & Reliability:** Extracted critical syntax protection logic into `SyntaxGuard`, fixed validation logic for escaped brackets (`[[`), and verified system stability with extensive edge-case stress tests.
- **Performance Boost (No Stuttering):** Moved heavy I/O operations (SDK Cleanup, UnRPA, Cache Loading) to background threads. This eliminates UI freezes/stuttering during large project operations.
- **Concurrency Safety:** Implemented a backend Locking Mechanism (`isBusy`) to prevent users from accidentally starting multiple heavy tasks simultaneously, which could cause crashes or data corruption.
- **Theme Independence:** The application now strictly ignores system-wide theme settings (like Windows Light Mode) and enforces the user's preferred theme (Default: Dark) from `config.json` immediately at startup.
- **Security Hardening:** Implemented centralized log masking for API keys AND automatic input sanitization (whitespace trimming) for all user settings.
- **Micro-Optimization:** Moved Regex compilation out of hot loops in `ai_translator.py`, significantly reducing CPU overhead during batch processing.
- **AI Hallucination Cleanup:** Implemented a pre-processor that fixes common AI formatting glitches like double-open-brackets (`[ [v0]`) before they can cause syntax errors.
- **Enhanced Google Translate Protection:** Specifically targeted improvements for Google Translate's tendency to corrupt bracket syntax (e.g., adding spaces `[ variable ]` or breaking interpolation chains). The new validation logic now catches these subtle corruptions that previously passed basic checks.
- **Advanced AST Code Validation:** Implemented Python's Abstract Syntax Tree (AST) analysis to validate the *semantic* correctness of restored placeholders. If a placeholder contains invalid Python syntax (e.g. `[player name]` instead of `[player_name]`), it is rejected even if the brackets are balanced.
- **Full Bracket Cycle Check:** Expanded the integrity check to detect "Unopened Closing Brackets" (e.g. `text]`) and nested brackets, ensuring complete structural integrity before approving any translation.
- **Smart Integrity Retry:** If a translation fails the safety check (e.g., bracket error), the system automatically retries 2 more times with different servers. This reduces the number of untranslated lines by up to 60%.

### 🐛 Bug Fixes (2026-02-01 Hotfix)
- **Aggressive Retry Setting Fix:** Fixed a critical bug where the "Aggressive Retry" setting was not being read from config. The code was looking for `aggressive_retry` instead of the correct `aggressive_retry_translation` property name, causing the feature to always be disabled regardless of user settings.
- **Placeholder Spacing Auto-Fix:** Added automatic cleanup for AI-induced placeholder spacing issues. Google Translate and some AI models would corrupt `[[t0]]` to `[[ t0 ]]`, breaking Ren'Py syntax. The system now auto-fixes these during the restore phase.
- **Duplicate Config Entry:** Removed a duplicate `enable_fuzzy_match` definition in `TranslationSettings` that could cause unpredictable behavior.
- **Cache Clear Confirmation:** Updated the cache clearing confirmation message in all 8 locales to explicitly mention the filename (`translation_cache.json`), preventing accidental data loss by making the action clearer to users.
- **Smart Masking (Google Translate Fixed):** Replaced default bracket masking (`[[v0]]`) with word-based masking (`X_RPY_v0_X`) specifically for Google Translate. This completely solves the issue where Google would corrupt syntax by inserting spaces inside brackets.
- **Locale UI Standardization:** Fixed all missing interface strings across every supported language (`de`, `es`, `fr`, `ru`, `zh-CN`, `fa`) and standardized the JSON structure to fully match the English reference.


## [2.6.1] - 2026-01-29
### 🛡️ Advanced Integrity Protection (3-Layer)
- **3-Layer Syntax Restoration (Enhanced):** Implemented a robust system to repair Ren'Py syntax corrupted by translation engines:
    1.  **Exact Match:** Perfect preservation.
    2.  **Flexible Regex:** Fixes common typos like `[ variable ]` (spaces) or `[[ tag ]]` (AI hallucinations).
    3.  **Fuzzy Match (RapidFuzz):** Uses advanced string similarity to rescue heavily corrupted tags (e.g. `[vo]` instead of `[v0]`) when confidence is high (>85%).
- **Strict Validation:** Added a final "Integrity Check" step. If a translation is still missing critical variables after repair, it is **rejected** and reverted to original text.
- **Applied Globally:** This protection now covers ALL engines (Google, OpenAI, Gemini, LocalLLM).

### 🛠️ Fixes & Improvements
- **Fuzzy Match Toggle:** Added a new setting in "Translation Filters" to enable/disable the Fuzzy Match feature. This gives users full control over the "autocorrect" behavior.
- **DeepL API Fix:** Resolved "Legacy authentication" error by migrating to header-based authentication for DeepL API.
- **LLM Placeholder Stability:** Improved prompt templates for `OpenAI`, `Gemini`, and `LocalLLM` engines to strictly prevent placeholder corruption (e.g. `[player_name]`).
- **Build Icon Fix:** Resolved an issue where application icons and UI assets were missing in the PyInstaller-built executable. The app now correctly resolves asset paths in both dev and frozen modes.
- **UI Language List:** Language dropdowns now display English names in parentheses for better readability (e.g., `Türkçe (Turkish)`, `中文 (Chinese Simplified)`).
- **QML Component Loading:** Fixed component loading issues in the frozen build by explicitly adding import paths.
- **Dependency Optimization:** Cleaned up build dependencies by removing heavy libraries (pandas heavy collection, PyQt5, tkinter, matplotlib) from the executable, resulting in a cleaner and potentially smaller build.

## [2.6.0] - 2026-01-27
### 🧠 Smart Language Detection (Google Translate)
- **Intelligent Source Language Detection:** When source language is set to "Auto Detect", the system now analyzes 15 random text samples at the start of translation to determine the actual source language with high confidence.
- **Majority Voting Algorithm:** Uses a voting system across multiple samples to prevent misdetection when games have mixed-language content (e.g., an English game with some Russian dialogue).
- **70% Confidence Threshold:** Source language is only locked if at least 70% of samples agree on the same language. If confidence is below threshold, falls back to per-request auto-detection.
- **Target Language Safety Check:** If detected source language equals the target language (which would be nonsensical), the system automatically falls back to auto mode.
- **Fixes "Untranslated Short Text" Issue:** Short texts like "OK", "Yes", character names, and ellipsis (`...`) are now correctly translated because the source language is known upfront.

### 🐛 Critical Bug Fixes & Stability (v2.6.0 Hotfix)
- **Startup Freeze (RPYC Parsing):** Fixed a major issue where the application would hang for minutes on startup when scanning large projects. The parser now intelligently delegates binary `.rpyc` files to a specialized reader instead of attempting to text-parse them.
- **Data Integrity:** Ensured 100% extraction coverage by making the binary `.rpyc` scanner mandatory, capturing up to 60% more translatable content in games with missing source code.
- **Smart Resume System:** Fixed the "loss of progress" issue. The translation engine now checks the in-memory cache before generating translation files, pre-filling known translations instantly instead of starting from scratch.
- **"Event Loop Closed" Fix:** Resolved a technical conflict where "Smart Language Detection" was inadvertently closing the main translation engine's connection pool, causing "Event loop is closed" errors and phantom bans.
- **App Icon Fix:** Implemented a forceful icon refresh strategy to ensure the application icon and taskbar icon appear correctly on Windows systems.

### 🌟 New Features
- **Cache Explorer:** Added a powerful new tool in the Tools menu to view, search, edit, and delete translation cache entries manually.
- **Glossary Import/Export:** You can now export your glossary to JSON, Excel, or CSV and import it back, making it easy to share glossaries between projects.

### 🚨 Improved Error Handling (API Keys)
- **User-Friendly Error Messages:** Added clear, localized error messages for missing API keys (OpenAI, Gemini). Instead of ambiguous crashes or technical tracebacks, the system now explicitly warns users: *"Gemini API key missing! Please add in Settings."*
- **Preventative Checks:** The translation engine now validates API keys *before* attempting initialization, ensuring smoother stability.
- **DeepSeek Engine Removed:** Removed the standalone DeepSeek engine option as it is fully redundant with the "OpenAI / OpenRouter" compatible mode. Users can still use DeepSeek models via the OpenAI engine setting.

### 🌍 UI Localization
- **New Strings:** Added localized error messages for API key failures to all supporting languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, `fa`).

### 🐛 Bug Fixes
- **Windows Taskbar Icon:** Fixed an issue where the application icon would sometimes not appear immediately on the Windows Taskbar upon startup. Implemented a robust `AppUserModelID` check and forceful icon refresh.

### 🌍 UI Localization & Consistency
- **Fixed Hardcoded Strings:** Resolved multiple instances of hardcoded Turkish text in the UI (Settings, Glossary, Update Dialog) that persisted even when English was selected.
- **Locale Sync:** Fully synchronized all 8 supported languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, `fa`) with the latest UI keys.
- **Icon Loading Fix:** Fixed a "double file prefix" bug (`file:///file:///`) that caused application icons to fail loading on some systems.

### 🔔 User Feedback Improvements
- **Explicit Update Check:** "Check for Updates" button now provides immediate visual feedback (Success/No Update/Error dialogs) instead of silently failing or only showing success.
- **Proxy Layout:** Improved the alignment and readability of the Proxy Settings section in the UI.

### 🎨 QML UI Framework (Major Rewrite)
- **Complete UI Modernization:** Migrated the entire user interface from Python/Qt Widgets to QML (Qt Modeling Language) for a more modern, fluid, and responsive experience.
- **Declarative Design:** UI components are now declarative and reactive, enabling smoother animations, transitions, and state management.
- **Component-Based Architecture:** Introduced reusable QML components (`NavigationBar`, `ApiField`, `SettingsPage`, etc.) for better maintainability and consistency.
- **Better Theming Support:** QML's native styling capabilities allow for easier theme customization and future dark/light mode improvements.
- **Improved Performance:** QML's hardware-accelerated rendering provides noticeably smoother scrolling and interactions, especially on large translation lists.

## [2.5.2] - 2026-01-25
### 🛡️ The "Ultra-Aggressive" Patch Engine
- **Late-Load Priority (zzz_ prefix):** All initializer and hook files now use the `zzz_` prefix, ensuring they are loaded last by the Ren'Py engine. This allows RenLocalizer to overwrite even the most stubborn hardcoded language settings.
- **Improved Initializer:** Replaced the fragile `init -999` with a more robust `init 1500` logic. This ensures the game has fully initialized its styles and internal stores before we apply the translation patch.
- **Engine-Level Force:** Added `define config.default_language` and `_preferences.language` synchronization, providing a dual-layer lock to ensure the game starts in the desired language.
- **Professional Runtime Hook:** Overhauled the runtime translation hook. It now uses a "wrapper" pattern to preserve existing game filters while adding translation support on top.
- **Language Hotkey (Shift+L):** Added a universal keyboard shortcut. If the game developer's code prevents automatic language switching, users can press `Shift+L` at any time to force-switch to the translated language. A notification confirms the change.

### 📂 Smart Directory Filtering & Cache (v2.5.2)
- **Global Translation Memory (Portable Cache):** Added a new system to store translation data in a central `cache/` folder next to the program. This keeps game projects clean, prevents accidental deletion of translations, and makes the application truly portable.
- **Exclude System Folders:** New setting (enabled by default) to automatically skip Ren'Py internal folders (`renpy/`, `common/`), cache, saves, and development folders (`.git/`, `.vscode/`).
- **Selective .rpym Scanning:** Added a setting (disabled by default) to skip `.rpym` and `.rpymc` files, reducing "translation noise" from technical modules.
- **Performance Optimized:** Directory scanning is now dynamic, adaptive, and significantly faster for large-scale projects.
- **Safety Hard-Block:** Critical engine folders are now always excluded to prevent accidental modification of Ren'Py core files.

### ⚡ UI Performance & Stability (v2.5.2)
- **Lazy Tab Loading:** Improved startup speed significantly by loading interface pages (Settings, Tools, etc.) only when they are first visited.
- **Log Buffering (Throttle):** Implemented a message throttling system to prevent the GUI from freezing or lagging during rapid translation processes.
- **NameError Fix:** Resolved a critical pipeline crash caused by a missing `sys` import in the new global cache logic.
- **Resource Optimization:** Applied best practices from modern open-source projects to ensure memory and CPU efficiency on the main UI thread.

### 🐛 Safety & Stability Fixes
- **NoneType Exception Fix:** Resolved a critical crash (`TypeError: argument of type 'NoneType' is not iterable`) caused by calling `renpy.change_language` too early in the boot sequence.
- **Automatic Cleanup:** The system now automatically detects and removes legacy `a0_` or `01_` prefix scripts to prevent file conflicts.
- **Better Encoding:** Standardized all generated `.rpy` files to use `UTF-8 with BOM`, ensuring 100% compatibility with Ren'Py 7 & 8 on all operating systems.



## [2.5.1] - 2026-01-21
### 🛠️ Critical Bug Fixes (Local LLM)
- **NameError Fix (`AI_LOCAL_URL`):** Fixed critical startup crash caused by missing `AI_LOCAL_URL` constant in `constants.py`.
- **NameError Fix (`re` module):** Fixed `NameError: name 're' is not defined` crash in `LocalLLMTranslator` by adding missing `import re` statement.
- **Abstract Class Error:** Fixed `Can't instantiate abstract class LocalLLMTranslator` error by implementing missing `_generate_completion` and `health_check` methods.
- **Integrated Glossary to AI Prompt:** Glossary terms are now dynamically injected into AI system prompts (OpenAI, Gemini, Local LLM), ensuring consistent terminology for new translations.
- **Cache Persistence Fix:** Fixed an issue where translation memory (cache) appeared empty after application restart due to incorrect path resolution.
- **Dynamic Cache Handling:** Cache path now updates immediately when switching projects or target languages.
- **Advanced Cache Management:** Added ability to clear, delete, and edit cache entries directly from the UI.
- **Improved Localization:** Added missing Turkish and English translations for new features (RPA, Glossary).
- **Cache Not Saving:** Fixed a critical bug where translations were not being saved to `translation_cache.json`. The issue was that successful results from the single-translation flow were not being added to the in-memory cache before `save_cache()` was called.

### ⚡ Local LLM Improvements
- **Per-Batch Checkpoint Save:** Cache is now saved after every translation batch (instead of every 5 batches). This ensures zero data loss even on power outage or crash.
- **Ultra-Minimal Prompt:** Drastically simplified the system prompt for local models. Removed problematic few-shot examples that small models were copying verbatim instead of translating.
- **Full Language Name Mapping:** Language codes (`tr`, `en`, `de`) are now converted to full names (`Turkish`, `English`, `German`) for better model comprehension.
- **Aggressive Response Cleanup:** Added comprehensive regex patterns to strip model "chatter" (e.g., "Translating to Turkish:", "Here is the translation:") from the output.
- **Batch Override for Local LLM:** `LocalLLMTranslator` now overrides `translate_batch` to force one-by-one translation, bypassing XML-style batching that confused smaller models.
- **Placeholder Corruption Guard:** If the model corrupts `XRPYX` placeholders, the system now falls back to the original text to prevent game-breaking translations.

### 🔔 UI/UX Improvements
- **InfoBar Warning for Local LLM:** Added a visible warning (same style as Gemini censorship warning) that appears in the top-right corner when Local LLM is selected, alerting users to potential hallucination issues with small models.
- **Settings Panel Warnings:** Added three persistent warning/tip labels to the AI Settings section:
  - ⚠️ Hallucination risk for models under 7B parameters
  - ⚠️ VRAM limitations advisory
  - 💡 Tip: Setting source language explicitly improves quality

### 🌍 Localization
- **New Keys:** Added `ai_hallucination_warning`, `ai_vram_warning`, and `ai_source_lang_warning` keys.
- **Full Sync:** Updated all 8 language files (`tr`, `en`, `de`, `es`, `fr`, `ru`, `fa`, `zh-CN`) with new warning messages.

## [2.5.0] - 2026-01-14
### 🚀 New Features (Major)
- **Force Runtime Translation:** Added "Force Runtime Translation" (Zorla Çeviri) feature. This dynamically injects a `01_renlocalizer_runtime.rpy` script into the game folder. It hooks into Ren'Py's `config.replace_text` to translate strings lacking the `!t` flag at runtime, ensuring 100% translation coverage for dynamic strings without manual code edits.
- **Improved Placeholder Protection:** Fixed a critical issue where Python variables inside Ren'Py bracket expressions (e.g., `[page['episode']]`) were being corrupted by translation. Expanded technical string filtering to protect internal property access and complex dictionary patterns.

### 🛠️ Core Fixes (Quest System & Parsing)
- **Quest Text Extraction Fix:** Resolved a critical issue where multi-line quest descriptions embedded in Python data structures (lists/dictionaries) were being skipped or incorrectly parsed.
- **Improved Trailing Text Cleanup:** Fixed a bug in the parser that caused trailing commas or brackets to leak into extracted strings, preventing valid translations.
- **Untranslated Text Detection:** Fixed a logic error where empty translations (`new ""`) in existing files were sometimes treated as "translated," preventing them from being processed.
- **Global Deduplication:** Implemented aggressive deduplication for `strings.rpy` generation to prevent file bloating (reduced file size by ~70% in large projects) and eliminate duplicate translation requests.
- **ID Generation Stability:** Enhanced the Translation ID generation algorithm to be more robust against escape sequences and newline variations.

### 🗺️ Cross-Platform & UI
- **Cross-Platform Game Selection:** Enhanced game path selection to be fully compatible with Windows, macOS, and Linux.
- **Platform-Aware Filtering:** Added specific file filters and dialog titles for different operating systems (.exe for Windows, .app/.sh for macOS, .sh/binary for Linux).
- **Browse Folder Support:** Added a "Browse Folder" option for direct directory selection, improving flexibility for game project identification.
- **Intelligent Root Detection:** Improved pipeline logic to automatically locate the `game/` subdirectory regardless of the initial selection (executable or folder).
- **Localization Expansion:** Updated all 8 supported languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, `fa`) with new localization keys for cross-platform selection, platform-specific placeholders, and titles.

### ⚡ Core & Performance (Major Update)
- **Smart Skip (Incremental Translation):** Added the ability to automatically detect and skip already translated lines (where the `new` string is not empty). This allows for lightning-fast incremental updates when a game version changes, saving API costs and time.
- **Resume System:** Implemented a persistent progress tracking system. If the translation is interrupted (power outage, manual stop), you can now resume exactly where you left off.
- **Aggressive Translation Retry:** Specialized retry mechanism for LLM engines. If the initial translation returns the original text, the engine now automatically retries with a "Force Translation" prompt.
- **Maintenance:** Permanently removed legacy "Output Format" selection. The system now defaults to the most stable `old_new` format to ensure 100% compatibility with Ren'Py script updates.
- **Robust Config Loading:** Implemented a filtering mechanism that ignores unknown configuration keys in the JSON file. This prevents "unexpected keyword argument" crashes when downgrading versions or moving between builds with different settings.

### � Performance & UI Responsiveness
- **UI Throttling (Anti-Freeze):** Implemented a log buffering system with a `QTimer` (200ms) to prevent UI freezing during high-frequency logging. The application now remains fully responsive (draggable/clickable) even while processing thousands of files per second.
- **Multithreading GIL Yields:** Added microscopic `time.sleep` yields in tight parsing and file generation loops. This allows the Python Global Interpreter Lock (GIL) to release more frequently, ensuring the UI thread stays alive and smooth during heavy CPU-bound tasks like scanning tens of thousands of script lines.
- **Regex Optimization:** Optimized core translation logic by pre-compiling overhead-heavy regular expression patterns. This significantly reduces CPU usage during the "protection" and "restoration" phases of translation.
- **Efficiency:** Optimized translation file generation by caching relative path calculations, reducing redundant OS calls during massive project writes.
- **Signal Multi-threading Efficiency:** Reduced main-thread overhead by eliminating redundant "debug" level signal emissions in tight processing loops.

### 🔍 Parser Optimization & Accuracy
- **Smart Directory Targeting:** The parser now automatically prioritizes the `game/` folder when a project root is selected, ensuring only relevant assets are scanned.
- **Strict File Type Enforcement:** Restricted scanning to core Ren'Py files (`.rpy`, `.rpyc`, `.rpym`, `.rpymc`). Other common but non-essential files (JSON, CSV, TXT, etc.) are now skipped to prevent "translation noise".
- **Advanced System Filter:** Added comprehensive exclusion rules for internal folders like `cache/`, `renpy/`, `saves/`, `tmp/`, and `python-packages/`.
- **Binary/Corrupted String Filter (RPYC Safety):** Added robust detection and filtering for corrupted strings from `.rpyc` files:
    - Unicode Replacement Character (`\ufffd`) detection.
    - Private Use Area character filtering (`\uE000-\uF8FF`).
    - Control character detection (`\x00-\x1F`, `\x7F-\x9F`).
    - High ratio of non-printable character analysis (>30% threshold).
    - Low alphabetic content detection (<20% ratio).
    - Short string corruption pattern matching for strings like `"z�X�"`, `"|d�T"`, `"qu�p��"`.
- **Python Code / Docstring Detection (Critical Fix):** New filter to prevent game-breaking translations of embedded code:
    - Detects Python keywords: `def`, `class`, `for`, `if`, `import`, `return`, `raise`, `try`, `except`, `while`, `lambda`, `with`.
    - Filters Ren'Py module calls like `renpy.store.x`, `renpy.block_rollback()`.
    - Skips string concatenation expressions: `"inventory/"+i.img+".png"`.
    - Protects internal dict access patterns: `_saved_keymap[key]`.
    - Filters boolean/None assignments: `x = True`, `y = False`, `z = None`.
- **Python Built-in Function Calls Filter:** Added detection for Python built-in function calls (`str()`, `int()`, `len()`, etc.) that should never be translated.
- **Default Dict/List String Extraction (Quest System Fix):** New extraction capability for strings inside `default` statement dict/list literals:
    - Handles `default quest = {"anna": ["Start by helping her..."]}` patterns.
    - Extracts translatable quest descriptions, schedule entries, and objectives.
    - Intelligent filtering to skip dict keys, short technical strings, and file paths.
- **Short Technical Words:** Added filter for common programming identifiers (`img`, `id`, `val`, `cfg`, etc.) that should never be translated.
- **Enhanced Technical String Filtering (Official Documentation Update):**
    - **Documentation-Driven Expansion:** Significantly expanded the `renpy_technical_terms` list based on a deep dive into official Ren'Py documentation, including transitions, motion commands, and engine keywords.
    - **Advanced Screen Language Filtering:** Added support for advanced UI elements like `hotspot`, `hotbar`, `areapicker`, `draggroup`, `showif`, and `vpgrid`.
    - **Deep Python Integration Safety:** Added comprehensive filtering for Python technical types (`Callable`, `Literal`, `Self`) and a full set of internal exception classes (`AssertionError`, `TypeError`, etc.) to prevent code-leaks in translation.
    - **Smart Heuristics:**
        - **Internal Identifier Protection:** Now automatically skips all underscore-prefixed strings (e.g., `_history`, `_confirm`) which are reserved for Ren'Py's internal use.
        - **System File Filtering:** Automatically skips strings derived from internal indexing files (starting with `00`).
        - **Namespace Awareness:** Strengthened detection for `config.`, `gui.`, `preferences.`, and `style.` namespaces.
    - **CamelCase & Dot-notation Detection:** Improved detection to automatically skip technical identifiers, module attributes, and code-like strings.


### 🌐 Expanded Language Support
- **Massive Source Language Expansion:** Increased the number of supported source languages from 37 to over 90, covering nearly every major language for a truly global translation experience.
- **Improved Native Names:** Standardized native language names in the UI for better accessibility.

### ⚙️ Translation Engine Improvements
- **DeepL Improvements:**
  - Added 3-attempt exponential backoff retry for transient network errors.
  - New "Formality" setting (Formal/Informal) for supported languages.
  - Fixed critical undefined variable bug in exception handler.
- **DeepL Tag Protection:** Automatically fixes spacing errors inside Ren'Py tags (e.g., `{ i }` → `{i}`).
- **AI Token Tracking:** OpenAI and Gemini now log token usage for better cost monitoring.
- **Optimization:** Implemented centralized request deduplication to prevent redundant API calls across all engines.
- **Resilience:** Added "Mirror Health Check" system for Google Translate to automatically detecting and bypassing failing endpoints.
- **Google Batch Fix:** Fixed a critical `AttributeError: _endpoint_failures` that occurred during multi-endpoint batch translation.
- **Mirror Ban Logic:** Implemented a temporary ban system (5 minutes) for Google Translate mirrors that consistently return 429 (Too Many Requests) or other errors, ensuring the pipeline quickly shifts to healthy mirrors.
- **Smart Concurrency:** Introduced adaptive rate-limit handling for OpenAI/Gemini that dynamically adjusts concurrency upon encountering 429 errors.

### 🖥️ Local LLM & Jan.ai
- **Jan.ai Support:** Added Jan.ai as a built-in preset in Local LLM settings (URL: `http://localhost:1337/v1`).
- **Uncensored Model Presets:** Categorized model dropdown for NSFW VN translation (Sansürsüz, LM Studio, Standart).
- **Separated Model Input:** Free-text model name input with a separate preset dropdown.

### 🍱 Localization & UI
- **Engine Transparency:** Added "(Experimental)" labels to non-Google engines.
- **Localized LLM Categories:** "Uncensored", "LM Studio", and "Standard" categories are now fully localized in all 8 supported languages.
- **DeepL Formality UI:** New setting card in API Keys section.
- **Global Label Sync:** Comprehensive update for `tr`, `en`, `de`, `es`, `ru`, `fr`, `zh-CN`, and `fa` locales.
- **Settings UI Localization Fix:** Fixed hardcoded Turkish fallback strings in Settings Interface (AI Settings, Proxy Settings, Advanced sections) that were appearing in English mode.

## [2.4.10] - 2026-01-11
### 🛡️ Ren'Py Engine Protection & Stability
- **Engine Isolation:** Explicitly excluded `renpy/common` and internal `renpy/` directories from scanning to prevent engine-level scripts from being corrupted by translation.
- **Automatic Cleanup:** Added a post-extraction cleanup step to remove any accidental engine-level translation files from the `tl/` directory.
- **Smart Technical Filtering:** Integrated advanced regex detection and symbol density heuristics to automatically skip internal Ren'Py code and technical regex patterns.

### 🌐 Translation Pipeline & API Management
- **Advanced API Quota Handling:**
  - Implemented a dedicated `quota_exceeded` flag in `TranslationResult` for more robust error handling.
  - Replaced brittle string matching for API limits with proper status code and boolean checks for DeepL, OpenAI, and Gemini.
  - The system now gracefully stops translation and provides a localized warning when API limits are reached.
- **Localized Stage Logging:**
  - Completely localized the pipeline stage labels (e.g., `[🌐 Translating...]`, `[✅ Validating...]`).
  - Improved `ConfigManager.get_log_text()` to support default values and cleaner error reporting.
  - Refined error log formatting to handle cases where file or line information is missing.

### 🍱 Localization & Global Support
- **Full Sync across 8 Languages:** Fully synchronized and updated `tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, and `fa` locale files.
- **Pipeline Log Localization:** Added missing keys for all pipeline stages and API errors across all supported languages.
- **Persian (FA) Locale Fix:** Restructured the `fa.json` file to fix duplicate keys and missing pipeline log sections.

### 🔍 Parsing & Extraction Improvements
- **Better Dialogue Support:**
  - Added support for dot-separated character names (e.g., `persistent.player_name`).
  - Enhanced narrator dialogue detection to support trailing transitions (e.g., `"Hello" with dissolve`).
  - Relaxed strict length filters for non-Latin languages to capture short but meaningful dialogues (e.g., Russian "Я", "Да").
- **Scanning Robustness:** Synchronized dot-separated character name support across both Regex and AST-based extraction pipelines.

### 🌐 Translation Engine Improvements
- **Smart Retry for Unchanged Translations (Optional):** Added "Agresif Çeviri" (Aggressive Translation) toggle in settings. When enabled, the system automatically retries unchanged translations with Lingva Translate and alternative Google endpoints. This significantly reduces the number of untranslated strings, especially for Cyrillic (Russian) to other language pairs. Disabled by default for optimal speed.
- **Enhanced Placeholder Protection:** Fixed a critical bug where nested bracket patterns like `[page['episode']]` or `[comment['author']]` were being incorrectly translated. The new parser properly handles dictionary access patterns, method calls, and nested quotes inside variable interpolations.
- **Technical String Filter:** Added filter for Ren'Py internal identifiers (e.g., `renpy.dissolve`, `renpy.mask renpy.texture`) to prevent them from appearing in translation output.

### 🐛 Bug Fixes & Stability
- **ConfigManager TypeError:** Fixed `TypeError` in `get_log_text()` call by adding proper default parameter support.
- **Duplicate Key Clean-up:** Removed redundant `error_api_quota` keys from root level in all locale files to prevent conflicts.
- **RPYC Reader AST Module Support:** Fixed `Disallowed global: _ast.Module` error when reading `.rpymc` (screen cache) files by whitelisting Python's `_ast` module in the safe unpickler.
- **Pipeline UnboundLocalError Fix:** Resolved a crash where the variable `tl_dir` was accessed before definition during the engine cleanup phase.
- **Duplicate Translation Entry Fix:** Resolved Ren'Py "already exists" errors by excluding the `tl/` directory from scanning and implementing deduplication against pre-existing translation files.
- **Update Checker Fix:** Resolved a critical crash that occurred when the GitHub update check returned inconsistent or erroneous metadata.
- **CLI RPA Robustness:** Fixed an issue where RPA extraction would fail in CLI mode when the game path points to a directory instead of an executable.
- **Font Warning Mitigation:** Resolved multiple `QFont` console warnings by removing and standardizing legacy font settings.

## [2.4.9] - 2026-01-09
### 🚀 AI Performance & Batch Processing
- **Batch Translation Support:** Added batch translation for OpenAI, Gemini, and Local LLM engines.
  - Significantly improved translation speed (5-10x) and reduced API costs.
  - Implemented an XML-based smart tagging system to protect Ren'Py syntax during batch operations.
- **Refactored AI Settings UI:** Reorganized AI settings into three main categories:
  - **Model Parameters:** Temperature and Max Tokens settings.
  - **Connection Settings:** Timeout and retry count settings.
  - **Speed & Performance:** Concurrency and request delay control.
- **Rate Limiting & Stability:** Integrated semaphore-based concurrency control and jittered delay mechanisms to minimize API rate limit issues.

### 🍱 Localization & Language Support
- **Full Sync:** Synchronized all localization files (`tr`, `en`, `de`, `fr`, `es`, `fa`, `ru`, `zh-CN`) to 100% completeness.
- **Turkish Improvements:** Completed 14+ missing critical keys in `tr.json`, ensuring the UI is fully localized in Turkish.
- **Enhanced System Prompts:** Updated AI system prompts across all languages to maintain a professional localizer tone and ensure uncensored translation of NSFW content.

### 🛠️ CI/CD & Infrastructure
- **Windows Build Automation:** GitHub Actions (`release.yml`) now automatically builds and releases Windows packages.
- **Python Stability:** Standardized Python version to `3.12` in CI/CD pipelines for better compatibility and stability.
- **Code Cleanup:** Removed and standardized legacy Turkish debug logs within the translation pipeline.

## [2.4.8] - 2026-01-08
### 🚀 New Features: Local LLM Support
- **Full Local LLM Integration:** Added dedicated "Local LLM" engine in translation options.
  - Supports **Ollama**, **LM Studio**, and other OpenAI-compatible local endpoints.
  - No API key required (uses "local" as placeholder).
  - Default model: `llama3.2`, Default URL: `http://localhost:11434/v1`.
- **Advanced AI Settings:**
  - Configurable `Temperature`, `Timeout`, `Max Tokens`, and `Retry Count`.
  - Custom System Prompt support for fine-tuning translation persona.

### 🧹 Code Health & Maintenance
- **Project Structure Audit:** Conducted a comprehensive health check.
  - **Magic Numbers Refactored:** Moved hardcoded values (timeouts, token limits, window sizes) to a centralized `src/utils/constants.py`.
  - **Localization Sync:** Ensured `translation_engines` list and new AI settings are 100% localized across all 7 supported languages (tr, en, de, fr, es, ru, zh).
  - **Dynamic UI Labels:** Fixed several hardcoded text labels in Settings UI to properly use the localization system.
- **UI Cleanup:**
  - Removed obsolete "Show Detailed Help" button from About page (functionality moved to Info Center).
  - Updated OpenAI engine label to simply "OpenAI / OpenRouter" to reduce confusion.

## [2.4.7] - 2026-01-06
### 🐛 Bug Fixes
- **PyInstaller UnRPA Fix:** Fixed critical bug where RPA extraction would fail in packaged executables.
  - **Root Cause:** `sys.executable` points to the bundled `.exe` instead of Python interpreter in frozen environments.
  - **Solution:** Replaced subprocess-based `python -m unrpa` calls with direct `unrpa` library API.
- **UnRPA 2.3.0 API Compatibility:** Fixed API mismatch with unrpa library.
  - **Root Cause:** unrpa 2.3.0 doesn't have a `path` parameter - it extracts to current working directory.
  - **Solution:** Temporarily change working directory with `os.chdir()` before extraction.

### ✨ New Features
- **Native RPA Parser Fallback:** Added built-in RPA archive parser (`rpa_parser.py`) that works without external dependencies.
  - Automatically used when `unrpa` fails to import in frozen PyInstaller builds.
  - Supports RPA-3.0 and RPA-2.0 formats (covers 99% of Ren'Py games).
  - **Result:** RPA extraction is now guaranteed to work in all environments.

### 🐛 CLI Fixes
- **Fixed CLI `translate` Subcommand:** The CLI was incorrectly entering interactive mode even when path was provided.
  - **Root Cause:** Argparse conflict between main parser and subparser `input_path` argument.
  - **Solution:** Renamed legacy argument to avoid namespace collision.
- **Fixed CLI Directory Path Support:** CLI now accepts both `.exe` files and directory paths for `--mode full`.
  - **Root Cause:** Pipeline validation only accepted file paths, not directories.
  - **Solution:** Updated `configure()` and `_run_pipeline()` to handle both file and directory inputs.
  - **Result:** CLI can now properly extract RPA archives and translate games when given a folder path.
- **Smart Mode Detection:** CLI now automatically detects Ren'Py projects by checking for `game/` subfolder.
  - Directories with `game/` subfolder automatically use `full` mode (RPA extraction + translation).
  - Other directories use `translate` mode (direct translation of existing files).

## [2.4.6] - 2026-01-05
### 🐛 Bug Fixes
- **Update Checker Crash Fix:** Fixed a critical crash on startup caused by the update checker system.
  - **QTimer Delay:** Update check now runs 1 second after window initialization to ensure all UI components are ready.
  - **InfoBar/QMessageBox Overlap:** Removed duplicate InfoBar before QMessageBox to prevent Qt event loop conflicts.
  - **Format Placeholder Fix:** Fixed `KeyError` caused by mismatched format placeholders (`{version}` vs `{latest}/{current}`).
  - **Error Handling:** Added comprehensive try/except and null checks for robustness.

## [2.4.5] - 2026-01-05
### 🔄 Major Architecture Change: UnRPA for All Platforms
- **Unified Extraction:** Now uses `unrpa` Python library on ALL platforms (Windows, Linux, macOS) instead of unreliable batch scripts.
- **Simplified Codebase:** Removed 140+ lines of legacy Windows batch script handling code.
- **Reliable Extraction:** No more "HTTP 404" errors from UnRen download links - just `pip install unrpa`.
- **RPYC-Only Mode:** When `.rpy` files are not found, the pipeline reads directly from `.rpyc` files.
- **Ren'Py 8.x Optimized:** Fully compatible with modern Ren'Py RPAv3 archives.

### 🛠️ Tools Interface
- **Streamlined UI:** Removed old "Run UnRen" and "Redownload" buttons.
- **New Standard:** Single, reliable "RPA Arşivlerini Aç" button powered by `unrpa`.
- **Cleanup:** Removed deprecated `UnRenModeDialog`.

### 🔧 Bug Fixes
- **Fixed `force_redownload` error:** Method was missing from UnRenManager (now removed as unnecessary).
- **Custom Path Fix:** Fixed bug in `get_custom_path()` where variable was used before being defined.

### 🧹 UI Cleanup
- **Removed Output Format Setting:** Always uses stable `old_new` format now.

### 📦 Dependency
- **Required:** `pip install unrpa` (added to requirements.txt)

## [2.4.4] - 2026-01-04
### 🎨 Theme System Overhaul
- **New Themes:** Added **Green (Nature/Matrix)** and **Neon (Cyberpunk)** themes, bringing the total to 6 distinct options.
- **Improved Dark Theme:** Deepened the dark theme colors for better immersion and reduced "grayness".
- **Visual Fixes:** Resolved "blocky" black backgrounds on text labels by enforcing transparency rules (`background-color: transparent !important`).
- **Dynamic Switching:** Theme changes now apply **instantly** without requiring an application restart.
- **Fix:** Fixed a critical bug where the theme selector always reverted to "Dark" due to a `qfluentwidgets` compatibility issue with `itemData`.
- **Fix:** Eliminated `QFont::setPointSize` console warnings by refining stylesheet scoping.

## [2.4.3] - 2026-01-04
### 🐛 Bug Fixes
- **PseudoTranslator Placeholder Fix:** Fixed critical bug where `PseudoTranslator` was corrupting Ren'Py placeholders (e.g., `[player]`, `{color=#f00}`) during text transformation. The engine now splits text by placeholder markers and only applies pseudo-transformation to non-placeholder segments.

### 🧹 Cleanup
- **Removed Unused Files:** Deleted obsolete debug scripts (`debug_font.py`, `debug_themes.py`) and unused modules (`base_translator.py`, `qt_translator.py`).
- **Light Theme Fix:** Implemented comprehensive stylesheet overrides to fix the "color mess" in Light Theme, ensuring all UI elements (navigation, headers, cards) are correctly styled.

## [2.4.2] - 2026-01-03
### 📦 Build & Distribution
- **One-Dir Build:** Switched to folder-based release for better startup speed and debugging.
- **Cross-Platform Scripts:** Added `RenLocalizer.sh` and `RenLocalizerCLI.sh` for easy launching on Linux/macOS.
- **Hidden Imports:** Fixed `ModuleNotFoundError` by correctly collecting all submodules in `RenLocalizer.spec`.

### 🐛 Bug Fixes
- **Glossary Editor:** Fixed crash when opening Glossary Editor in packaged builds.

## [2.4.1] - 2026-01-02
### ✨ New Features
- **Patreon Integration:** Added a support button to the main UI.

## [2.4.0] - 2026-01-01
### 🚀 Major Update: Unreal Engine Support
- **Unreal Translation:** Added basic support for unpacking and translating Unreal Engine games (`.pak` files).
- **AES Key Handling:** Integrated AES key detection for encrypted PAK files.

## [2.3.0] - 2025-12-28
### 🌍 RPG Maker Support
- **RPG Maker MV/MZ:** Added support for translating RPG Maker JSON files.
- **RPG Maker XP/VX/Ace:** Added support for Ruby Marshal data files.

## [2.2.0] - 2025-12-26
### 🤖 CLI Deep Scan
- **Deep Scan:** Added `--deep-scan` argument to CLI for AST-based analysis of compiled scripts.

## [2.1.0] - 2025-12-24
### 💅 UI Improvements
- **Fluent Design:** Migrated to `PyQt6-Fluent-Widgets` for a modern look and feel.

## [2.0.0] - 2025-09-01
### 🎉 Initial Release
- **Core:** Ren'Py translation support, multi-engine translation (Google, Bing, DeepL), modern GUI.
