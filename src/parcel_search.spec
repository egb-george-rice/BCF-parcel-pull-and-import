# parcel_search.spec
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[r'C:\OSGeo4W\apps\Python312\Lib\site-packages'],
    binaries=[],
    datas=[
        ('tx_prox_analysis.py', '.'),
        # Add any other required data files here
    ],
    hiddenimports=[
        'geopandas',
        'shapely',
        'pyproj',
        'fiona',
        'numpy',
        'pandas',
        'rtree'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='parcel_search',
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
    entitlements_file=None
)