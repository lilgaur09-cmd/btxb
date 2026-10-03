# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['binarytxbot_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('binarytxbot_app.py', '.'), ('binary_analysis.py', '.'), ('crypto_analysis.py', '.'), ('live_chart.py', '.'), ('auth.py', '.'), ('assets/binarytxbot-logo.svg', 'assets'), ('assets/binarytxbot-favicon.svg', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BINARYTXBOT',
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
)