# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['tradexbot_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('app.py', '.'), ('auth.py', '.'), ('crypto_analysis.py', '.'), ('live_chart.py', '.'), ('assets/tradexbot-logo.svg', 'assets'), ('assets/tradexbot-favicon.svg', 'assets')],
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
    name='TRADEXBOT',
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
