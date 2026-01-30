# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None
root = os.path.abspath('.')
src = os.path.join(root, 'src')

launcher = Analysis(
    [os.path.join(src, 'launcher.py')],
    pathex=[src],
    binaries=[],
    datas=[(os.path.join(root, 'assets'), 'assets')],
    hiddenimports=[
        'websockets', 'websockets.legacy', 'websockets.legacy.client', 'websockets.legacy.server',
        'combat', 'overworld', 'protocol', 'client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    cipher=block_cipher,
    noarchive=False,
)
launcher_pyz = PYZ(launcher.pure, launcher.zipped_data, cipher=block_cipher)
launcher_exe = EXE(
    launcher_pyz,
    launcher.scripts,
    launcher.binaries,
    launcher.zipfiles,
    launcher.datas,
    [],
    name='wager-launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

server = Analysis(
    [os.path.join(src, 'server.py')],
    pathex=[src],
    binaries=[],
    datas=[],
    hiddenimports=[
        'websockets', 'websockets.legacy', 'websockets.legacy.client', 'websockets.legacy.server',
        'combat', 'overworld', 'protocol',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    cipher=block_cipher,
    noarchive=False,
)
server_pyz = PYZ(server.pure, server.zipped_data, cipher=block_cipher)
server_exe = EXE(
    server_pyz,
    server.scripts,
    server.binaries,
    server.zipfiles,
    server.datas,
    [],
    name='wager-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
