# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_dir = os.path.abspath(os.getcwd())

# Automatically collect all submodules from src package
hidden_imports = collect_submodules('src')

# Aggressively collect submodules for external libraries to prevent missing imports
hidden_imports += collect_submodules('qfluentwidgets')
hidden_imports += collect_submodules('aiohttp')
hidden_imports += collect_submodules('requests')
hidden_imports += collect_submodules('httpx')
hidden_imports += collect_submodules('urllib3')
hidden_imports += collect_submodules('PIL')
hidden_imports += collect_submodules('rapidfuzz')  # Often used for fuzzy matching
hidden_imports += collect_submodules('packaging')
hidden_imports += collect_submodules('chardet')
hidden_imports += collect_submodules('charset_normalizer')
hidden_imports += collect_submodules('unrpa')
hidden_imports += collect_submodules('openai')
hidden_imports += collect_submodules('google.genai')
hidden_imports += collect_submodules('yaml')
hidden_imports += collect_submodules('darkdetect')
hidden_imports += collect_submodules('fontTools')
hidden_imports += collect_submodules('pyparsing')
hidden_imports += collect_submodules('certifi')
# Pandas submodules are too heavy (includes tests, matplotlib, etc). 
# Basic pandas import is usually enough or handled by auto-analysis.
# If needed, add only specific submodules manually.


# Manual additions for specific edge cases
if sys.platform == 'win32':
    hidden_imports.extend([
        'PIL._tkinter_finder', 
        'win32timezone',
    ])
else:
    hidden_imports.extend([
        'PIL._tkinter_finder',
    ])

# Collect data files for libraries that need them (e.g. QFluentWidgets icons)
qfluent_datas = collect_data_files('qfluentwidgets')

# Define datas with absolute paths to avoid not found errors
datas_list = [
    (os.path.join(project_dir, 'locales'), 'locales'),
    (os.path.join(project_dir, 'icon.ico'), '.'),
    # Add QML files
    (os.path.join(project_dir, 'src', 'gui', 'qml'), os.path.join('src', 'gui', 'qml')),
] + qfluent_datas

# Add Linux/Mac shell scripts only when building on those platforms
# These are for source-based execution assistance, not required for bundled apps
if sys.platform != 'win32':
    sh_files = [
        (os.path.join(project_dir, 'RenLocalizer.sh'), '.'),
        (os.path.join(project_dir, 'RenLocalizerCLI.sh'), '.')
    ]
    # Only add if files exist
    for sh_src, sh_dst in sh_files:
        if os.path.exists(sh_src):
            datas_list.append((sh_src, sh_dst))


# =========================================================
# GUI Application Analysis (RenLocalizer)
# =========================================================
a = Analysis(
    ['run.py'],
    pathex=[project_dir],
    binaries=[],
    datas=datas_list,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'tkinter', 'matplotlib', 'IPython', 'notebook', 'scipy.stats.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RenLocalizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, 'icon.ico')
)

# =========================================================
# CLI Application Analysis (RenLocalizerCLI)
# =========================================================
b = Analysis(
    ['run_cli.py'],
    pathex=[project_dir],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'tkinter', 'matplotlib', 'IPython', 'notebook', 'scipy.stats.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_cli = PYZ(b.pure, b.zipped_data, cipher=block_cipher)

exe_cli = EXE(
    pyz_cli,
    b.scripts,
    [],
    exclude_binaries=True,
    name='RenLocalizerCLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, 'icon.ico')
)

# =========================================================
# COLLECT (Folder Output)
# =========================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    
    exe_cli,
    b.binaries,
    b.zipfiles,
    b.datas,
    
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RenLocalizer',
)
