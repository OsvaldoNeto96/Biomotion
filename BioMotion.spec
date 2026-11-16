# -*- mode: python ; coding: utf-8 -*-
"""
BioMotion – Spec de build para PyInstaller 6.x
Gera um pacote onedir (pasta BioMotion/) pronto para distribuição.
"""

import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Coleta de pacotes com arquivos de dados nativos ──────────────────────────
med_d, med_b, med_h = collect_all('mediapipe')
pg_d,  pg_b,  pg_h  = collect_all('pyqtgraph')
oni_d, oni_b, oni_h = collect_all('openni')

datas    = med_d    + pg_d    + oni_d
binaries = med_b    + pg_b    + oni_b
hiddenimports = med_h + pg_h + oni_h + [
    # OpenCV
    'cv2',
    # OpenNI
    'openni', 'openni.openni2', 'openni._openni2', 'openni.utils',
    # PyQt5
    'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui',
    'PyQt5.QtSvg', 'PyQt5.sip',
    # PyQtGraph (importações dinâmicas internas)
    'pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyqt5',
    'pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyqt5',
    'pyqtgraph.imageview.ImageViewTemplate_pyqt5',
    # Pillow (texto com acentos no overlay do vídeo)
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
    # Científico
    'scipy', 'scipy.spatial', 'scipy.linalg', 'scipy.special',
    'numpy', 'numpy.core', 'numpy.lib',
    # Stdlib que às vezes fica de fora
    'pkg_resources', 'pkg_resources.py2_compat',
]

# ── DLLs e drivers do OpenNI2 (bundled junto ao exe) ─────────────────────────
OPENNI2_REDIST = r"C:\Program Files\OpenNI2\Redist"

if os.path.exists(OPENNI2_REDIST):
    # DLLs principais na raiz do bundle
    for dll in glob.glob(os.path.join(OPENNI2_REDIST, "*.dll")):
        binaries.append((dll, "."))
    # Arquivo de configuração
    ini = os.path.join(OPENNI2_REDIST, "OpenNI.ini")
    if os.path.exists(ini):
        datas.append((ini, "."))
    # Subpasta OpenNI2/Drivers/ (drivers de câmera)
    drivers_dir = os.path.join(OPENNI2_REDIST, "OpenNI2")
    if os.path.exists(drivers_dir):
        datas.append((drivers_dir, "OpenNI2"))

# ── Análise ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['app_final.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'IPython', 'jupyter',
        'notebook', 'pytest', 'xmlrunner',
        # O app usa só PyQt5; outros bindings Qt no ambiente quebram o build/execução
        'PySide6', 'shiboken6', 'PySide2', 'shiboken2', 'PyQt6',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BioMotion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX desativado: evita falsos-positivos de antivírus
    console=False,      # Sem janela de console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BioMotion',
)
