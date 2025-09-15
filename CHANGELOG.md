# Changelog

## [2.0.2] - 2025-09-15

### 🚀 New Translation Engine
- **OPUS-MT Offline Translation**: Added Helsinki-NLP OPUS-MT models for offline neural machine translation
- **16 Language Pairs**: Support for EN↔TR, DE, FR, ES, IT, RU, JA, ZH, KO, PT, AR, NL, PL, SV, NO, DA
- **Model Download Dialog**: User-controlled model download with progress tracking
- **Thread-Safe Implementation**: Proper async/sync integration with Qt GUI

### 🌐 Multi-Language UI Support
- **Complete UI Translation**: All interface elements now support English and Turkish
- **Dynamic Language Switching**: Real-time language switching without restart
- **Translation Engine Names**: Engine dropdown now adapts to selected UI language
- **Model Download Dialog**: Full multi-language support for offline model downloads

### 🔧 Architecture Improvements
- **Batch Translation Optimization**: Pre-check model availability before processing thousands of texts
- **Signal-Based Download Workflow**: Clean separation between translation worker and GUI dialogs
- **Error Prevention**: Eliminated infinite loop errors from missing models
- **Memory Management**: Efficient model caching and loading system

### 🐛 Critical Fixes
- Fixed OPUS-MT model download infinite loop that caused application crashes
- Resolved Qt thread safety issues with dialog creation
- Improved error handling for missing translation models
- Better fallback mechanisms when models are unavailable

### 📚 Documentation & GitHub Preparation
- Updated README.md with OPUS-MT information and installation instructions
- Enhanced .gitignore for better repository management
- Cleaned up debug prints and improved code quality
- Added GitHub community files (CODE_OF_CONDUCT.md, issue templates, PR template)

## [2.0.1] - 2025-09-11

### 🎯 RenPy Integration Overhaul
- **Conditional Menu Support**: Perfect handling of `"choice" if condition:` syntax
- **Technical String Filtering**: Automatically excludes color codes (#08f), font files (.ttf), performance metrics
- **Correct Output Format**: Individual `translate strings` blocks (RenPy standard compliance)
- **Modern Language Initialization**: Compatible language setup without deprecated APIs
- **Encoding Fixes**: Proper UTF-8 handling for all international characters

### 🔧 Parser Improvements
- **Enhanced Regex Engine**: Improved extraction of conditional menu choices
- **Smart Content Detection**: Better filtering of meaningful vs technical content
- **Multi-line String Handling**: Fixed parsing issues with complex string patterns
- **Variable Preservation**: Maintains `[character_name]` and placeholder integrity

### 🐛 Critical Bug Fixes
- Fixed "Could not parse string" errors in RenPy
- Resolved multi-line string parsing issues (line 2327 type errors)
- Corrected character encoding problems (Türkçe character corruption)
- Fixed language initialization file compatibility issues
- Eliminated technical string translation (fps, renderer, etc.)

### � Quality Improvements
- **Cache Management**: Built-in RenPy cache clearing functionality
- **Error Prevention**: Proactive filtering prevents RenPy parse errors
- **Output Validation**: Ensures all generated files are RenPy-compatible
- **Real-world Testing**: Validated with actual RenPy visual novel projects

### � Distribution Ready
- **Clean Repository**: Removed all temporary test and debug files
- **Professional Documentation**: Updated README, added CONTRIBUTING.md, RELEASE_NOTES.md
- **Example Configuration**: Sample config.json.example for users
- **GitHub Ready**: Proper .gitignore, structured for open source collaboration

### 🧪 Testing & Validation
- Comprehensive testing with Secret Obsessions 0.11 (RenPy 8.3.2)
- Menu choice translation validation
- Technical string exclusion verification
- Encoding and character preservation testing

## [2.0.0] - Previous Release
- Initial stable release with core translation functionality
- Basic RenPy file parsing and translation
- Multi-engine support (Google, DeepL, Bing, Yandex)
- Professional UI with theme support
