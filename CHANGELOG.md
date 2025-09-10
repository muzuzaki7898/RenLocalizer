# Changelog

## [2.1.0] - 2025-09-10

### ✨ Major Features Added
- **Enhanced Placeholder Preservation System**: Complete RenPy variable protection during translation
- **Case-Insensitive Variable Restoration**: Handles translation engine case changes automatically
- **Advanced Translation Worker**: Integrated placeholder preservation into the translation pipeline
- **Robust Error Handling**: Comprehensive variable case mismatch detection and fixing

### 🔧 Improvements
- **Translation Quality**: Variables like `[r1name]`, `[mcname]`, `[player_name]` are now perfectly preserved
- **RenPy Compatibility**: Full compatibility with RenPy 8.3+ (removed deprecated APIs)
- **Memory Optimization**: Improved parser performance and reduced memory usage
- **User Experience**: Better error messages and progress reporting

### 🐛 Bug Fixes
- Fixed variable case mismatches causing `NameError` in RenPy games
- Resolved placeholder preservation issues with complex text formatting
- Fixed translation worker metadata passing
- Corrected language initialization for RenPy integration

### 🔒 Security
- Removed API keys from version control
- Added comprehensive .gitignore for sensitive data protection
- Cleaned up test files and temporary data

### 📖 Documentation
- Updated README with new features and troubleshooting
- Added Turkish documentation (README.tr.md)
- Improved code comments and documentation strings

### 🧪 Testing
- Comprehensive test suite for placeholder preservation
- Real-world scenario testing with actual RenPy projects
- Variable case validation and automatic fixing tools

## [2.0.0] - Previous Release
- Initial stable release with core translation functionality
- Basic RenPy file parsing and translation
- Multi-engine support (Google, DeepL, Bing, Yandex)
- Professional UI with theme support
