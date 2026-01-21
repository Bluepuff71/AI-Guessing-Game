# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for LOOT RUN

Build command:
    pyinstaller LootRun.spec

Output:
    dist/LootRun (or LootRun.exe on Windows)
"""

import sys
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH).resolve()

# Analysis configuration
a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # VERSION file
        ('VERSION', '.'),
        # Config directory with JSON files
        ('config', 'config'),
        # Client assets for web interface (index.html, css, js)
        ('client/index.html', 'client'),
        ('client/css', 'client/css'),
        ('client/js', 'client/js'),
        # Assets directory (elimination.gif)
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # Rich console library
        'rich',
        'rich.console',
        'rich.table',
        'rich.panel',
        'rich.text',
        'rich.live',
        'rich.progress',
        'rich.prompt',
        'rich.markdown',
        # Questionary for interactive prompts
        'questionary',
        'prompt_toolkit',
        'prompt_toolkit.input',
        'prompt_toolkit.input.defaults',
        'prompt_toolkit.output',
        'prompt_toolkit.output.defaults',
        # WebSockets
        'websockets',
        'websockets.client',
        'websockets.server',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.server',
        # LightGBM and ML dependencies
        'lightgbm',
        'sklearn',
        'sklearn.preprocessing',
        'sklearn.utils',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        'sklearn.utils._weight_vector',
        # NumPy
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        # Asyncio
        'asyncio',
        # JSON handling
        'json',
        # Pickle for model serialization
        'pickle',
        # Standard library modules used by the game
        'uuid',
        'hashlib',
        'random',
        'datetime',
        'pathlib',
        'typing',
        'dataclasses',
        'enum',
        'copy',
        'socket',
        'struct',
        'threading',
        'time',
        'platform',
        'urllib.request',
        'urllib.error',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test frameworks and test directory
        'pytest',
        'pytest_cov',
        'pytest_mock',
        'pytest_asyncio',
        '_pytest',
        'unittest',
        'tests',
        'conftest',
        # Exclude tkinter (not used)
        'tkinter',
        '_tkinter',
        # Exclude development tools
        'IPython',
        'jupyter',
        'notebook',
        'pip',
        'setuptools',
        # Exclude unnecessary matplotlib backends
        'matplotlib',
    ],
    noarchive=False,
    optimize=0,
)

# Create the PYZ archive
pyz = PYZ(a.pure)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LootRun',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows-specific icon (optional - can be added later)
    # icon='assets/icon.ico',
)
