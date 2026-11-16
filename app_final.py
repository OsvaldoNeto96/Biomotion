import sys
import os
import csv

def _base_dir():
    """Pasta para gravar sessões: ao lado do exe (frozen) ou do script (dev)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)   # dist/BioMotion/
    return os.path.dirname(os.path.abspath(__file__))

def _openni2_redist_path():
    """Pasta com OpenNI2.dll: _internal/ no bundle (PyInstaller 6.x) ou instalação padrão."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS                       # dist/BioMotion/_internal/
    return r"C:\Program Files\OpenNI2\Redist"
import time
import threading
import unicodedata
from datetime import datetime
import re
import cv2
import numpy as np
import mediapipe as mp
import math
from openni import openni2
from collections import deque
from types import SimpleNamespace
# O .venv também tem PySide6; sem isto o pyqtgraph escolhe o PySide6 e o processo
# acaba com dois Qt carregados (PySide6 + PyQt5) -> crash nativo ao criar o gráfico.
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")
import PyQt5.QtWidgets  # noqa: F401  (garante o PyQt5 carregado antes do pyqtgraph)
import pyqtgraph as pg
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
                             QVBoxLayout, QHBoxLayout, QCheckBox,
                             QSlider, QPushButton, QSplitter, QSizePolicy,
                             QLineEdit, QScrollArea, QGridLayout, QFrame,
                             QButtonGroup, QComboBox, QStackedWidget, QProgressBar,
                             QShortcut, QSplashScreen, QGraphicsOpacityEffect)
from PyQt5.QtCore import (QThread, pyqtSignal, Qt, QTimer, QSettings, QSize, QRectF,
                          QPointF, QPropertyAnimation, QEasingCurve)
from PyQt5.QtGui import (QImage, QPixmap, QPainter, QColor, QFont, QFontDatabase, QIcon,
                         QLinearGradient, QPen, QPolygonF, QPalette, QKeySequence)

# ── Identidade visual ───────────────────────────────────────────────────────────
# Design tokens. Tema escuro: dá mais contraste ao vídeo e cansa menos a vista em
# sessões longas. Uma única cor de marca (teal) para ações principais, vermelho
# reservado para gravação/erro e uma cor fixa por articulação (vídeo, cards e
# gráfico usam a mesma cor -> o usuário associa sem precisar de legenda).
BG         = "#0A0E13"   # fundo da aplicação
SURFACE    = "#10151C"   # barra superior e laterais
CARD       = "#151B23"   # cartões
RAISED     = "#1C232D"   # inputs e botões secundários
HOVER      = "#242D39"
BORDER     = "#222A35"
BORDER2    = "#303B49"
TEXT       = "#E9EEF4"
TEXT2      = "#A3AEBD"
TEXT3      = "#6B7685"
PRIMARY    = "#2DD4BF"
PRIMARY_H  = "#5EEAD4"
PRIMARY_P  = "#14B8A6"
ON_PRIMARY = "#04211D"
DANGER     = "#F25F5C"
DANGER_H   = "#FF7B78"
SUCCESS    = "#34D399"
WARNING    = "#FBBF24"
INFO       = "#60A5FA"
VIDEO_BG   = "#06090D"

CORES_ARTIC = {
    'quadril':    "#FBBF24",
    'joelho':     "#2DD4BF",
    'tornozelo':  "#FB923C",
    'ombro':      "#60A5FA",
    'cotovelo':   "#A78BFA",
    'punho':      "#F472B6",
    'ombro_abd':  "#22D3EE",
    'ombro_flex': "#818CF8",
    'ombro_rot':  "#E879F9",
}
NOMES_ARTIC = {'quadril': 'Quadril', 'joelho': 'Joelho', 'tornozelo': 'Tornozelo',
               'ombro': 'Ombro', 'cotovelo': 'Cotovelo', 'punho': 'Punho',
               'ombro_abd': 'Abdução', 'ombro_flex': 'Flexão', 'ombro_rot': 'Rotação'}
# Rótulo curto usado sobre o vídeo
ROTULO_VIDEO = {'ombro_abd': 'Abd', 'ombro_flex': 'Flex', 'ombro_rot': 'Rot'}
INFERIORES = ['quadril', 'joelho', 'tornozelo']
SUPERIORES = ['ombro', 'cotovelo', 'punho']
OMBRO_3D   = ['ombro_abd', 'ombro_flex', 'ombro_rot']
GRUPOS_ARTIC = [("Membro inferior", INFERIORES), ("Membro superior", SUPERIORES),
                ("Ombro 3D · abdução, flexão e rotação", OMBRO_3D)]

def info_artic(chave):
    """'joelho_esquerdo' -> ('joelho', 'E', cor, 'Joelho');
    'ombro_abd_direito' -> ('ombro_abd', 'D', cor, 'Abdução')"""
    tipo, lado = chave.rsplit('_', 1)
    return tipo, ('E' if lado.startswith('esq') else 'D'), CORES_ARTIC[tipo], NOMES_ARTIC[tipo]

def tipo_artic(chave):
    return chave.rsplit('_', 1)[0]

def rgba(cor_hex, alfa):
    h = cor_hex.lstrip('#')
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{alfa})"

def hex_bgr(cor_hex):
    h = cor_hex.lstrip('#')
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))

# Glifos da fonte Segoe Fluent Icons / Segoe MDL2 Assets (nativas do Windows)
ICO = dict(gravar="", parar="", pasta="", proximo="",
           camera="", video="", atleta="", elenco="",
           ajustes="", check="", ok="", ver="",
           reset="", info="", alerta="", grafico="")

FONTE_UI = "Segoe UI"
FONTE_DISPLAY = "Segoe UI"
FONTE_ICONES = "Segoe MDL2 Assets"

QSS = f"""
* {{ outline: 0; }}
QMainWindow, QFrame#app {{ background: {BG}; }}
QWidget {{ background: transparent; color: {TEXT}; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER2};
            border-radius: 6px; padding: 6px 8px; font-size: 12px; }}

QFrame#topbar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QFrame#sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QFrame#painelDireito {{ background: {SURFACE}; border-left: 1px solid {BORDER}; }}
QFrame#divisor {{ background: {BORDER2}; }}

QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#cardVideo {{ background: {VIDEO_BG}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#cardVideo[gravando="true"] {{ border: 2px solid {DANGER}; }}
QFrame#barraVideo {{ background: {CARD}; border: none; border-bottom: 1px solid {BORDER};
                     border-top-left-radius: 11px; border-top-right-radius: 11px; }}
QLabel#tela {{ background: {VIDEO_BG}; color: {TEXT3}; font-size: 13px;
               border-bottom-left-radius: 11px; border-bottom-right-radius: 11px; }}
QFrame#jcard {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#chip {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 13px; }}
QFrame#toast {{ background: {RAISED}; border: 1px solid {BORDER2}; border-radius: 10px; }}
QFrame#vazio {{ background: transparent; border: 1px dashed {BORDER2}; border-radius: 12px; }}

QLabel#marca {{ font-size: 16px; font-weight: 700; color: {TEXT}; }}
QLabel#titulo {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
QLabel#tituloPainel {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
QLabel#secao {{ font-size: 11px; font-weight: 700; color: {TEXT3}; }}
QLabel#muted {{ font-size: 12px; color: {TEXT2}; }}
QLabel#sutil {{ font-size: 11px; color: {TEXT3}; }}
QLabel#jnome {{ font-size: 12px; font-weight: 600; color: {TEXT2}; }}
QLabel#tag {{ font-size: 10px; font-weight: 700; color: {TEXT2}; background: {RAISED};
              border-radius: 4px; padding: 1px 5px; }}
QLabel#chipTexto {{ font-size: 12px; font-weight: 600; color: {TEXT2}; }}
QLabel#toastTexto {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
QLabel#rec {{ background: {rgba(DANGER, 0.16)}; color: {DANGER}; border-radius: 6px;
              padding: 3px 8px; font-size: 11px; font-weight: 700; }}
QLabel#kbd {{ background: {RAISED}; color: {TEXT2}; border: 1px solid {BORDER2};
              border-radius: 4px; padding: 0px 5px; font-size: 10px; font-weight: 700; }}

QLineEdit {{ background: {RAISED}; border: 1px solid {BORDER2}; border-radius: 8px;
             padding: 9px 10px; color: {TEXT}; font-size: 14px;
             selection-background-color: {PRIMARY_P}; }}
QLineEdit:hover {{ border-color: #3A4656; }}
QLineEdit:focus {{ border: 1px solid {PRIMARY}; background: {HOVER}; }}
QLineEdit:disabled {{ color: {TEXT2}; background: {CARD}; border-color: {BORDER}; }}

QComboBox {{ background: {RAISED}; border: 1px solid {BORDER2}; border-radius: 8px;
             padding: 7px 10px; color: {TEXT}; font-size: 13px; }}
QComboBox:hover {{ border-color: #3A4656; }}
QComboBox:disabled {{ color: {TEXT3}; background: {CARD}; border-color: {BORDER}; }}
QComboBox QAbstractItemView {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER2};
                               selection-background-color: {HOVER}; padding: 4px; outline: 0; }}

QPushButton {{ background: {RAISED}; color: {TEXT}; border: none; border-radius: 8px;
               padding: 8px 14px; font-size: 13px; font-weight: 600; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:disabled {{ color: {TEXT3}; }}
QPushButton[variant="primary"] {{ background: {PRIMARY}; color: {ON_PRIMARY}; border-radius: 10px;
                                  font-size: 14px; font-weight: 700; }}
QPushButton[variant="primary"]:hover {{ background: {PRIMARY_H}; }}
QPushButton[variant="primary"]:pressed {{ background: {PRIMARY_P}; }}
QPushButton[variant="danger"] {{ background: {DANGER}; color: #FFFFFF; border-radius: 10px;
                                 font-size: 14px; font-weight: 700; }}
QPushButton[variant="danger"]:hover {{ background: {DANGER_H}; }}
QPushButton[variant="secondary"] {{ background: {RAISED}; border: 1px solid {BORDER2}; color: {TEXT}; }}
QPushButton[variant="secondary"]:hover {{ background: {HOVER}; border-color: #3A4656; }}
QPushButton[variant="secondary"]:disabled {{ color: {TEXT3}; border-color: {BORDER}; background: {CARD}; }}
QPushButton[variant="ghost"] {{ background: transparent; color: {TEXT2}; padding: 5px 9px;
                                font-size: 12px; border-radius: 6px; }}
QPushButton[variant="ghost"]:hover {{ background: {RAISED}; color: {TEXT}; }}
QPushButton[variant="vista"] {{ background: {RAISED}; border: 1px solid {BORDER2}; color: {TEXT2};
                                padding: 9px 2px; font-size: 12px; }}
QPushButton[variant="vista"]:hover {{ color: {TEXT}; border-color: #3A4656; }}
QPushButton[variant="vista"]:checked {{ background: {rgba(PRIMARY, 0.13)}; border: 1px solid {PRIMARY};
                                        color: {PRIMARY}; }}
QPushButton[variant="vista"]:disabled {{ color: {TEXT3}; }}
QPushButton[variant="vista"]:checked:disabled {{ color: {PRIMARY_P}; border-color: {PRIMARY_P}; }}
QFrame#segmentado {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 10px; }}
QPushButton[variant="seg"] {{ background: transparent; color: {TEXT2}; padding: 7px 4px;
                              border-radius: 7px; font-size: 12px; }}
QPushButton[variant="seg"]:hover {{ color: {TEXT}; }}
QPushButton[variant="seg"]:checked {{ background: {RAISED}; color: {TEXT}; }}

QProgressBar {{ background: {RAISED}; border: none; border-radius: 2px; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 2px; }}

QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER2}; border-radius: 3px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #3A4656; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QSlider::groove:horizontal {{ height: 4px; background: {RAISED}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #FFFFFF; border: 3px solid {PRIMARY};
                              width: 10px; height: 10px; margin: -6px 0; border-radius: 8px; }}
QSlider:disabled {{ }}
QSlider::sub-page:horizontal:disabled {{ background: {BORDER2}; }}
QSlider::handle:horizontal:disabled {{ border-color: {BORDER2}; background: {TEXT3}; }}

QSplitter::handle {{ background: {BG}; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; color: {TEXT3}; font-size: 11px; }}
QStatusBar QLabel {{ color: {TEXT3}; font-size: 11px; padding: 0 10px; }}
QStatusBar::item {{ border: none; }}
"""

_aparencia_ok = False

def configurar_aparencia(app):
    """Fontes, paleta e folha de estilo — chamado uma vez."""
    global FONTE_UI, FONTE_DISPLAY, FONTE_ICONES, _aparencia_ok
    if _aparencia_ok or app is None: return
    _aparencia_ok = True
    fams = set(QFontDatabase().families())
    FONTE_UI = "Segoe UI Variable Text" if "Segoe UI Variable Text" in fams else "Segoe UI"
    FONTE_DISPLAY = "Segoe UI Variable Display" if "Segoe UI Variable Display" in fams else FONTE_UI
    FONTE_ICONES = "Segoe Fluent Icons" if "Segoe Fluent Icons" in fams else "Segoe MDL2 Assets"
    f = QFont(FONTE_UI); f.setPixelSize(13); f.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(f)
    pal = QPalette()
    for papel, cor in ((QPalette.Window, BG), (QPalette.WindowText, TEXT), (QPalette.Base, RAISED),
                       (QPalette.AlternateBase, CARD), (QPalette.Text, TEXT), (QPalette.Button, RAISED),
                       (QPalette.ButtonText, TEXT), (QPalette.Highlight, PRIMARY_P),
                       (QPalette.HighlightedText, "#FFFFFF"), (QPalette.ToolTipBase, RAISED),
                       (QPalette.ToolTipText, TEXT), (QPalette.PlaceholderText, TEXT3)):
        pal.setColor(papel, QColor(cor))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(TEXT3))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(TEXT3))
    app.setPalette(pal)
    app.setStyleSheet(QSS)

def _dpr():
    app = QApplication.instance()
    return app.devicePixelRatio() if app else 1.0

def icone_pixmap(glifo, cor, px=16):
    dpr = _dpr()
    pm = QPixmap(int(px * dpr), int(px * dpr)); pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    f = QFont(FONTE_ICONES); f.setPixelSize(max(8, int(px * 0.92)))
    p.setFont(f); p.setPen(QColor(cor))
    p.drawText(QRectF(0, 0, px, px), Qt.AlignCenter, glifo)
    p.end()
    return pm

def icone(glifo, cor, px=16):
    return QIcon(icone_pixmap(glifo, cor, px))

def icone_ponto(cor, px=10):
    dpr = _dpr()
    pm = QPixmap(int(px * dpr), int(px * dpr)); pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen); p.setBrush(QColor(cor)); p.drawEllipse(QRectF(1, 1, px - 2, px - 2)); p.end()
    return pm

def desenhar_logo(px=32):
    """Marca: quadrado arredondado em gradiente com um 'ângulo articular' estilizado."""
    dpr = _dpr()
    pm = QPixmap(int(px * dpr), int(px * dpr)); pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, px, px)
    g.setColorAt(0, QColor(PRIMARY)); g.setColorAt(1, QColor("#3B82F6"))
    p.setPen(Qt.NoPen); p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, px, px), px * 0.28, px * 0.28)
    s = px / 32.0
    A, B, C = QPointF(9 * s, 24 * s), QPointF(15 * s, 10.5 * s), QPointF(24.5 * s, 21 * s)
    p.setPen(QPen(QColor(255, 255, 255, 150), 1.6 * s))
    a1 = math.degrees(math.atan2(-(A.y() - B.y()), A.x() - B.x()))
    a2 = math.degrees(math.atan2(-(C.y() - B.y()), C.x() - B.x()))
    d = (a2 - a1) % 360
    ini, var = (a2, 360 - d) if d > 180 else (a1, d)
    r = 6.5 * s
    p.drawArc(QRectF(B.x() - r, B.y() - r, 2 * r, 2 * r), int(ini * 16), int(var * 16))
    pen = QPen(QColor("#FFFFFF"), 2.6 * s); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen); p.drawPolyline(QPolygonF([A, B, C]))
    p.setPen(Qt.NoPen); p.setBrush(QColor("#FFFFFF"))
    for pt, rr in ((A, 2.3), (B, 3.2), (C, 2.3)):
        p.drawEllipse(pt, rr * s, rr * s)
    p.end()
    return pm

def set_variant(w, variante):
    w.setProperty("variant", variante)
    w.style().unpolish(w); w.style().polish(w)

def repolir(w):
    w.style().unpolish(w); w.style().polish(w); w.update()

def secao(texto):
    lbl = QLabel(texto.upper()); lbl.setObjectName("secao")
    f = lbl.font(); f.setLetterSpacing(QFont.AbsoluteSpacing, 0.9); lbl.setFont(f)
    return lbl

def fonte_display(px, peso=QFont.DemiBold):
    f = QFont(FONTE_DISPLAY); f.setPixelSize(px); f.setWeight(peso)
    return f


# ── Organização por atleta ──────────────────────────────────────────────────────
# Cada atleta tem a sua pasta: Analises_Salvas/Atletas/<Nome>/
# com um vídeo (+ CSV) por vista: Frontal, Lateral e Posterior.
VISTAS = ["Frontal", "Lateral", "Posterior"]

def nome_para_pasta(nome):
    """'João da Silva' -> 'Joao_da_Silva' (ASCII: o OpenCV no Windows falha com acentos no caminho)."""
    s = unicodedata.normalize('NFKD', nome.strip()).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_')

def pasta_atletas():
    return os.path.join(_base_dir(), "Analises_Salvas", "Atletas")

def pasta_atleta(nome):
    return os.path.join(pasta_atletas(), nome_para_pasta(nome))

def vistas_gravadas(nome):
    """Devolve {vista: nº de vídeos gravados} para o atleta."""
    contagem = {v: 0 for v in VISTAS}
    if not nome_para_pasta(nome): return contagem
    pasta = pasta_atleta(nome)
    if not os.path.isdir(pasta): return contagem
    for arq in os.listdir(pasta):
        if not arq.lower().endswith(".avi"): continue
        for v in VISTAS:
            if f"_{v}_" in arq:
                contagem[v] += 1
    return contagem

def contar_atletas():
    """(atletas com pasta, atletas com as 3 vistas completas)."""
    raiz = pasta_atletas()
    if not os.path.isdir(raiz): return 0, 0
    total = completos = 0
    for nome in os.listdir(raiz):
        if not os.path.isdir(os.path.join(raiz, nome)): continue
        total += 1
        if all(n > 0 for n in vistas_gravadas(nome).values()):
            completos += 1
    return total, completos


# ── Câmeras ─────────────────────────────────────────────────────────────────────
# Usa DirectShow para os índices serem estáveis. Câmeras virtuais (OBS Virtual
# Camera, celular espelhado) costumam entregar só quadros pretos quando inativas;
# por isso a escolha automática prefere a primeira câmera "com sinal" (ex.: C270).
def abrir_camera(indice):
    return cv2.VideoCapture(indice, cv2.CAP_DSHOW)

def listar_cameras(max_indices=5):
    cams = []
    for i in range(max_indices):
        c = abrir_camera(i)
        if not c.isOpened():
            c.release(); continue
        w = h = 0; brilho = 0.0
        for _ in range(20):                      # aquecimento (auto-exposição)
            ok, f = c.read()
            if ok and f is not None:
                h, w = f.shape[:2]; brilho = float(f.mean())
                if brilho > 8: break
        c.release()
        cams.append({'indice': i, 'largura': w, 'altura': h, 'com_sinal': brilho > 8})
    return cams

def escolher_camera(cams, preferida=None):
    indices = [c['indice'] for c in cams]
    if preferida is not None and preferida in indices: return preferida
    for c in cams:
        if c['com_sinal']: return c['indice']
    return indices[0] if indices else None


# ── Funções biomecânicas ────────────────────────────────────────────────────────
THRESHOLD_VISIBILIDADE = 0.5
JANELA_SUAVIZACAO = 5
# Quadril: threshold menor pois roupas reduzem visibilidade, mais frames de histórico
THRESHOLD_VISIBILIDADE_QUADRIL = 0.35
JANELA_POSICAO_QUADRIL = 8
LIMIAR_SALTO_QUADRIL = 0.07   # salto máximo em coordenadas normalizadas por frame
MAX_FRAMES_INTERPOLACAO_QUADRIL = 15

def extrair_coordenada_3d(landmark, w, h, depth_img):
    px, py = int(landmark.x * w), int(landmark.y * h)
    if px < 0 or px >= w or py < 0 or py >= h: return None
    z_mm = depth_img[py, px]
    if z_mm == 0: return None
    fx, fy, cx, cy = 594.21, 591.04, 320.0, 240.0
    return [(px - cx) * z_mm / fx, (py - cy) * z_mm / fy, z_mm]

def calcular_angulo_3d(ponto_a, ponto_b, ponto_c):
    if ponto_a is None or ponto_b is None or ponto_c is None: return 0.0
    a, b, c = np.array(ponto_a), np.array(ponto_b), np.array(ponto_c)
    vetor_ba, vetor_bc = a - b, c - b
    ta, tb = np.linalg.norm(vetor_ba), np.linalg.norm(vetor_bc)
    if ta == 0 or tb == 0: return 0.0
    return math.degrees(math.acos(np.clip(np.dot(vetor_ba, vetor_bc) / (ta * tb), -1.0, 1.0)))

def calcular_angulo_2d(lm_a, lm_b, lm_c, w, h):
    a = np.array([lm_a.x * w, lm_a.y * h])
    b = np.array([lm_b.x * w, lm_b.y * h])
    c = np.array([lm_c.x * w, lm_c.y * h])
    ba, bc = a - b, c - b
    normas = np.linalg.norm(ba) * np.linalg.norm(bc)
    if normas == 0: return 0.0
    return math.degrees(math.acos(np.clip(np.dot(ba, bc) / normas, -1.0, 1.0)))


# Chaves das métricas 3D do ombro
_CHAVES_OMBRO_3D = (
    'ombro_abd_esquerdo', 'ombro_abd_direito',
    'ombro_flex_esquerdo', 'ombro_flex_direito',
    'ombro_rot_esquerdo', 'ombro_rot_direito',
)

def _angulo_frontal_ombro(sh, hip, el):
    """Abducao/aducao: angulo tronco-braco no plano frontal (X-Y, ignora Z)."""
    tx, ty = hip.x - sh.x, hip.y - sh.y
    bx, by = el.x - sh.x, el.y - sh.y
    nt = math.sqrt(tx*tx + ty*ty)
    nb = math.sqrt(bx*bx + by*by)
    if nt == 0 or nb == 0: return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, (tx*bx + ty*by) / (nt * nb)))))

def _angulo_sagital_ombro(sh, hip, el):
    """Flexao/extensao: angulo tronco-braco no plano sagital (Y-Z, ignora X)."""
    ty, tz = hip.y - sh.y, hip.z - sh.z
    by_, bz = el.y - sh.y, el.z - sh.z
    nt = math.sqrt(ty*ty + tz*tz)
    nb = math.sqrt(by_*by_ + bz*bz)
    if nt == 0 or nb == 0: return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, (ty*by_ + tz*bz) / (nt * nb)))))

def _angulo_rotacao_ombro(sh, el, wr):
    """Rotacao: angulo do antebraco projetado no plano perpendicular ao braco superior."""
    u = np.array([el.x - sh.x, el.y - sh.y, el.z - sh.z], dtype=float)
    nu = np.linalg.norm(u)
    if nu < 1e-6: return 0.0
    u /= nu
    f = np.array([wr.x - el.x, wr.y - el.y, wr.z - el.z], dtype=float)
    nf = np.linalg.norm(f)
    if nf < 1e-6: return 0.0
    f /= nf
    # Referencia: vertical do mundo (Y negativo = cima nos world landmarks)
    vert = np.array([0.0, -1.0, 0.0])
    ref = vert - np.dot(vert, u) * u
    nr = np.linalg.norm(ref)
    if nr < 1e-6: return 0.0
    ref /= nr
    # Antebraco projetado no mesmo plano
    f_perp = f - np.dot(f, u) * u
    nfp = np.linalg.norm(f_perp)
    if nfp < 1e-6: return 0.0
    f_perp /= nfp
    return math.degrees(math.acos(max(-1.0, min(1.0, np.dot(ref, f_perp)))))

# Ordem das colunas do CSV (mantém as 13 originais e acrescenta o ombro 3D no fim)
COLUNAS_CSV = [
    ('ombro_esquerdo', 'Ombro_Esq'), ('ombro_direito', 'Ombro_Dir'),
    ('cotovelo_esquerdo', 'Cotovelo_Esq'), ('cotovelo_direito', 'Cotovelo_Dir'),
    ('punho_esquerdo', 'Punho_Esq'), ('punho_direito', 'Punho_Dir'),
    ('quadril_esquerdo', 'Quadril_Esq'), ('quadril_direito', 'Quadril_Dir'),
    ('joelho_esquerdo', 'Joelho_Esq'), ('joelho_direito', 'Joelho_Dir'),
    ('tornozelo_esquerdo', 'Tornozelo_Esq'), ('tornozelo_direito', 'Tornozelo_Dir'),
    ('inclinacao_cabeca', 'Inclinacao_Cabeca'),
    ('ombro_abd_esquerdo', 'Ombro_Abd_Esq'), ('ombro_abd_direito', 'Ombro_Abd_Dir'),
    ('ombro_flex_esquerdo', 'Ombro_Flex_Esq'), ('ombro_flex_direito', 'Ombro_Flex_Dir'),
    ('ombro_rot_esquerdo', 'Ombro_Rot_Esq'), ('ombro_rot_direito', 'Ombro_Rot_Dir'),
]


# ── Desenho sobre o vídeo (overlay) ─────────────────────────────────────────────
# Linhas com anti-aliasing, esqueleto neutro e destaque colorido só nas
# articulações em análise (mesma cor do card e do gráfico).
COR_OSSO     = (236, 232, 228)
COR_PONTO    = (245, 245, 245)
COR_CONTORNO = (34, 28, 22)
COR_ROSTO    = hex_bgr("#2DD4BF")
COR_ROSTO2   = hex_bgr("#94A3B8")
COR_MAO      = (214, 208, 200)
FONTE_CV     = cv2.FONT_HERSHEY_DUPLEX

def _px(lm, w, h):
    return (int(lm.x * w), int(lm.y * h))

def _desenhar_conexoes(img, lms, conexoes, w, h, cor, esp=1):
    for a, b in conexoes:
        cv2.line(img, _px(lms[a], w, h), _px(lms[b], w, h), cor, esp, cv2.LINE_AA)

def _desenhar_esqueleto(img, lms, conexoes, w, h):
    vis = [lm.visibility >= THRESHOLD_VISIBILIDADE for lm in lms]
    usados = set()
    for a, b in conexoes:
        if a < 11 or b < 11 or not (vis[a] and vis[b]): continue   # rosto fica com o Face Mesh
        cv2.line(img, _px(lms[a], w, h), _px(lms[b], w, h), COR_OSSO, 2, cv2.LINE_AA)
        usados.update((a, b))
    for i in usados:
        p = _px(lms[i], w, h)
        cv2.circle(img, p, 4, COR_CONTORNO, -1, cv2.LINE_AA)
        cv2.circle(img, p, 3, COR_PONTO, -1, cv2.LINE_AA)

def _arco(img, b, a, c, cor, r=24):
    """Setor do ângulo no vértice b: preenchimento translúcido + contorno."""
    a1 = math.degrees(math.atan2(a[1] - b[1], a[0] - b[0]))
    a2 = math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]))
    d = (a2 - a1) % 360
    ini, fim = (a2, a2 + (360 - d)) if d > 180 else (a1, a1 + d)
    x0, y0 = max(0, b[0] - r - 2), max(0, b[1] - r - 2)
    x1, y1 = min(img.shape[1], b[0] + r + 3), min(img.shape[0], b[1] + r + 3)
    if x1 > x0 and y1 > y0:
        roi = img[y0:y1, x0:x1]
        sobre = roi.copy()
        cv2.ellipse(sobre, (b[0] - x0, b[1] - y0), (r, r), 0, ini, fim, cor, -1, cv2.LINE_AA)
        img[y0:y1, x0:x1] = cv2.addWeighted(sobre, 0.28, roi, 0.72, 0)
    cv2.ellipse(img, b, (r, r), 0, ini, fim, cor, 2, cv2.LINE_AA)

# Texto do overlay com a fonte do Windows (acentos e "°"); Hershey só como reserva
try:
    from PIL import Image, ImageDraw, ImageFont
    _TEM_PIL = True
except Exception:
    _TEM_PIL = False
_fonte_pil = None
_cache_texto = {}

def _fonte_overlay():
    global _fonte_pil
    if _fonte_pil is None:
        _fonte_pil = False
        if _TEM_PIL:
            pasta = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
            for arq in ("seguisb.ttf", "segoeui.ttf", "arial.ttf"):
                try:
                    _fonte_pil = ImageFont.truetype(os.path.join(pasta, arq), 15); break
                except Exception:
                    continue
    return _fonte_pil

def _mascara_texto(texto):
    m = _cache_texto.get(texto)
    if m is None:
        f = _fonte_overlay()
        x0, _, x1, _ = f.getbbox(texto)
        asc, desc = f.getmetrics()
        im = Image.new("L", (max(1, x1 - x0), asc + desc), 0)
        ImageDraw.Draw(im).text((-x0, 0), texto, font=f, fill=255)
        m = np.asarray(im, dtype=np.float32) / 255.0
        if len(_cache_texto) > 800: _cache_texto.clear()
        _cache_texto[texto] = m
    return m

def _pill(img, x, y, texto, cor, alinhar_direita=False, escala=0.55):
    """Etiqueta arredondada semitransparente: ● texto"""
    usa_pil = bool(_fonte_overlay())
    if usa_pil:
        mascara = _mascara_texto(texto); th, tw = mascara.shape
        pad_x, pad_y = 10, 4
    else:
        texto = texto.replace("°", "").replace("ç", "c")
        (tw, th), _ = cv2.getTextSize(texto, FONTE_CV, escala, 1)
        pad_x, pad_y = 9, 7
    larg = pad_x + 15 + tw + pad_x
    alt = th + pad_y * 2
    H, W = img.shape[:2]
    if alinhar_direita: x -= larg
    y -= alt // 2
    x = max(0, min(W - larg - 1, x)); y = max(0, min(H - alt - 1, y))
    roi = img[y:y + alt, x:x + larg]
    if roi.shape[0] != alt or roi.shape[1] != larg: return
    mask = np.zeros((alt, larg), np.uint8); r = alt // 2
    cv2.rectangle(mask, (r, 0), (larg - r - 1, alt - 1), 255, -1)
    cv2.circle(mask, (r, r), r, 255, -1, cv2.LINE_AA)
    cv2.circle(mask, (larg - r - 1, r), r, 255, -1, cv2.LINE_AA)
    a = (mask.astype(np.float32) / 255.0 * 0.80)[..., None]
    fundo = np.empty_like(roi); fundo[:] = (23, 18, 13)
    roi[:] = (roi.astype(np.float32) * (1 - a) + fundo.astype(np.float32) * a).astype(np.uint8)
    cy = y + alt // 2
    cv2.circle(img, (x + pad_x + 4, cy), 4, cor, -1, cv2.LINE_AA)
    tx = x + pad_x + 15
    if usa_pil:
        sub = img[y + pad_y:y + pad_y + th, tx:tx + tw]
        a = mascara[..., None]
        sub[:] = (sub.astype(np.float32) * (1 - a) + 246.0 * a).astype(np.uint8)
    else:
        cv2.putText(img, texto, (tx, y + pad_y + th), FONTE_CV, escala, (246, 246, 246), 1, cv2.LINE_AA)


# ── Motor de bastidores ─────────────────────────────────────────────────────────
class MotorBiomecanico(QThread):
    sinal_frames_prontos = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, str, dict)

    def __init__(self, camera_preferida=None):
        super().__init__()
        self.rodando = True
        self.articulacoes_ativas = []
        self.desenhar_rosto = True
        self.desenhar_maos = True
        self.angulo_rotacao_x = 0.0
        self.angulo_rotacao_y = 0.0
        self.angulo_rotacao_z = 0.0
        self.gravando = False
        self.arquivo_csv = None
        self.escritor_csv = None
        self.tempo_inicio_gravacao = 0.0
        self.video_writer = None
        # Lock: a GUI abre/fecha os ficheiros enquanto esta thread escreve neles
        self._lock_gravacao = threading.Lock()
        # FPS real do loop (o vídeo é gravado com este FPS para não ficar acelerado)
        self.fps_medido = 25.0
        self._t_ultimo_loop = None

        self.mp_holistic = mp.solutions.holistic
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.mp_face_mesh = mp.solutions.face_mesh

        self.holistic = self.mp_holistic.Holistic(
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
            model_complexity=1,
            smooth_landmarks=True,
        )

        PL = self.mp_holistic.PoseLandmark
        self.MAPA_ARTICULACOES = {
            'ombro_esquerdo':     (PL.LEFT_HIP,        PL.LEFT_SHOULDER,  PL.LEFT_ELBOW),
            'ombro_direito':      (PL.RIGHT_HIP,       PL.RIGHT_SHOULDER, PL.RIGHT_ELBOW),
            'cotovelo_esquerdo':  (PL.LEFT_SHOULDER,   PL.LEFT_ELBOW,     PL.LEFT_WRIST),
            'cotovelo_direito':   (PL.RIGHT_SHOULDER,  PL.RIGHT_ELBOW,    PL.RIGHT_WRIST),
            'punho_esquerdo':     (PL.LEFT_ELBOW,      PL.LEFT_WRIST,     PL.LEFT_INDEX),
            'punho_direito':      (PL.RIGHT_ELBOW,     PL.RIGHT_WRIST,    PL.RIGHT_INDEX),
            'quadril_esquerdo':   (PL.LEFT_SHOULDER,   PL.LEFT_HIP,       PL.LEFT_KNEE),
            'quadril_direito':    (PL.RIGHT_SHOULDER,  PL.RIGHT_HIP,      PL.RIGHT_KNEE),
            'joelho_esquerdo':    (PL.LEFT_HIP,        PL.LEFT_KNEE,      PL.LEFT_ANKLE),
            'joelho_direito':     (PL.RIGHT_HIP,       PL.RIGHT_KNEE,     PL.RIGHT_ANKLE),
            'tornozelo_esquerdo': (PL.LEFT_KNEE,       PL.LEFT_ANKLE,     PL.LEFT_FOOT_INDEX),
            'tornozelo_direito':  (PL.RIGHT_KNEE,      PL.RIGHT_ANKLE,    PL.RIGHT_FOOT_INDEX),
        }
        self.suavizador = {k: deque(maxlen=JANELA_SUAVIZACAO) for k in self.MAPA_ARTICULACOES}
        for _k in _CHAVES_OMBRO_3D:
            self.suavizador[_k] = deque(maxlen=JANELA_SUAVIZACAO)

        # Suavizador de posição para landmarks do quadril e joelho
        self._idx_quadril = {
            PL.LEFT_HIP.value, PL.RIGHT_HIP.value,
            PL.LEFT_KNEE.value, PL.RIGHT_KNEE.value,
        }
        self._hist_pos       = {i: deque(maxlen=JANELA_POSICAO_QUADRIL) for i in self._idx_quadril}
        self._ultima_pos     = {i: None for i in self._idx_quadril}
        self._frames_perdido = {i: 0    for i in self._idx_quadril}
        self._lm_frame       = {}   # cache por quadro: cada landmark é suavizado uma única vez

        self.kinect_ativo = False
        self.webcam_ativa = False
        self._camera_pedida = None
        self.cameras = listar_cameras()
        self.camera_indice = escolher_camera(self.cameras, camera_preferida)
        self.webcam = abrir_camera(self.camera_indice) if self.camera_indice is not None else cv2.VideoCapture()
        if self.webcam.isOpened():
            self.webcam_ativa = True

        try:
            openni2.initialize(_openni2_redist_path())
            uris = []
            try: uris = openni2.Device.enumerate_uris()
            except: pass
            if len(uris) > 0:
                self.dev = openni2.Device.open_file(uris[0]) if hasattr(openni2.Device, 'open_file') else openni2.Device(uris[0])
            else:
                self.dev = openni2.Device.open_any()
            self.depth_stream = self.dev.create_depth_stream()
            self.color_stream = self.dev.create_color_stream()
            try: self.dev.set_image_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)
            except: pass
            self.depth_stream.start()
            self.color_stream.start()
            self.kinect_ativo = True
            PASSO = 4
            u, v = np.meshgrid(np.arange(0, 640, PASSO), np.arange(0, 480, PASSO))
            self.x_grid = (u.flatten() - 320.0) / 594.21
            self.y_grid = (v.flatten() - 240.0) / 591.04
            self.PASSO = PASSO
        except Exception:
            pass

    def trocar_camera(self, indice):
        """Pedido da GUI; a troca é feita na thread do motor (fora de gravação)."""
        self._camera_pedida = indice

    def _aplicar_troca_camera(self):
        indice, self._camera_pedida = self._camera_pedida, None
        if indice is None or self.gravando or indice == self.camera_indice: return
        self.webcam.release()
        self.webcam = abrir_camera(indice)
        self.camera_indice = indice
        self.webcam_ativa = self.webcam.isOpened()
        for d in self.suavizador.values(): d.clear()

    def _resolucao_captura(self):
        if self.kinect_ativo: return (640, 480)
        if self.webcam_ativa:
            w = int(self.webcam.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.webcam.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (w if w > 0 else 640, h if h > 0 else 480)
        return (640, 480)

    def iniciar_gravacao(self, nome_atleta, vista):
        """Grava em Analises_Salvas/Atletas/<Nome>/<Nome>_<Vista>_<data_hora>.avi/.csv
        Devolve o caminho da pasta do atleta."""
        pasta = pasta_atleta(nome_atleta)
        os.makedirs(pasta, exist_ok=True)
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{nome_para_pasta(nome_atleta)}_{vista}_{data_hora}"

        arquivo_csv = open(os.path.join(pasta, base + ".csv"), 'w', newline='', encoding='utf-8')
        escritor_csv = csv.writer(arquivo_csv, delimiter=';')
        escritor_csv.writerow(['Tempo_Segundos'] + [col for _, col in COLUNAS_CSV])
        larg, alt = self._resolucao_captura()
        fps = float(min(30, max(5, round(self.fps_medido))))
        video_writer = cv2.VideoWriter(
            os.path.join(pasta, base + ".avi"),
            cv2.VideoWriter_fourcc(*'XVID'), fps, (larg, alt))

        with self._lock_gravacao:
            self.arquivo_csv, self.escritor_csv = arquivo_csv, escritor_csv
            self.video_writer = video_writer
            self.tempo_inicio_gravacao = time.time()
            self.gravando = True
        return pasta

    def parar_gravacao(self, assincrono=True):
        with self._lock_gravacao:
            self.gravando = False
            if self.arquivo_csv: self.arquivo_csv.close(); self.arquivo_csv = None
            self.escritor_csv = None
            vw, self.video_writer = self.video_writer, None
        if vw:
            # release() pode bloquear vários segundos (flush do codec XVID);
            # em background evita congelar o feed da câmera. Ao fechar o app é síncrono,
            # para o AVI não ficar truncado.
            if assincrono:
                threading.Thread(target=vw.release, daemon=True).start()
            else:
                vw.release()

    def _inclinacao_cabeca(self, fl, w, h):
        e, d = fl.landmark[33], fl.landmark[263]
        return round(math.degrees(math.atan2((d.y - e.y) * h, (d.x - e.x) * w)), 1)

    def _posicao_quadril(self, idx, lm):
        """Retorna (x_norm, y_norm) suavizados para landmarks do quadril/joelho.
        Aplica rejeição de outlier e interpolação quando o tracking é perdido."""
        hist = self._hist_pos[idx]
        if lm.visibility >= THRESHOLD_VISIBILIDADE_QUADRIL:
            x_raw, y_raw = lm.x, lm.y
            # Rejeita saltos bruscos usando a média histórica
            if len(hist) >= 3:
                x_med = sum(p[0] for p in hist) / len(hist)
                y_med = sum(p[1] for p in hist) / len(hist)
                if math.sqrt((x_raw - x_med) ** 2 + (y_raw - y_med) ** 2) > LIMIAR_SALTO_QUADRIL:
                    x_raw, y_raw = x_med, y_med
            hist.append((x_raw, y_raw))
            x_s = sum(p[0] for p in hist) / len(hist)
            y_s = sum(p[1] for p in hist) / len(hist)
            self._ultima_pos[idx]     = (x_s, y_s)
            self._frames_perdido[idx] = 0
            return (x_s, y_s)
        else:
            self._frames_perdido[idx] += 1
            if self._frames_perdido[idx] <= MAX_FRAMES_INTERPOLACAO_QUADRIL and self._ultima_pos[idx]:
                return self._ultima_pos[idx]
            return None

    def _lm_efetivo(self, idx, lm):
        """Landmark efetivo: suavizado para quadril/joelho, bruto para os demais.
        Cacheado por quadro — o quadril entra em vários ângulos (quadril, joelho, ombro)
        e não pode ser empurrado no histórico mais de uma vez por quadro."""
        if idx in self._lm_frame:
            return self._lm_frame[idx]
        if idx in self._idx_quadril:
            pos = self._posicao_quadril(idx, lm)
            res = None if pos is None else SimpleNamespace(x=pos[0], y=pos[1], visibility=1.0)
        else:
            res = lm if lm.visibility >= THRESHOLD_VISIBILIDADE else None
        self._lm_frame[idx] = res
        return res

    def _calcular_ombros_3d(self, wlms, slms, w, h, img_bgr, img_ir_color, ang, meio_x):
        """Calcula abducao, flexao e rotacao do ombro usando pose_world_landmarks 3D."""
        PL = self.mp_holistic.PoseLandmark
        lados = [
            ('esquerdo', PL.LEFT_SHOULDER,  PL.LEFT_HIP,  PL.LEFT_ELBOW,  PL.LEFT_WRIST),
            ('direito',  PL.RIGHT_SHOULDER, PL.RIGHT_HIP, PL.RIGHT_ELBOW, PL.RIGHT_WRIST),
        ]
        for lado, pl_sh, pl_hip, pl_el, pl_wr in lados:
            iSH, iHIP, iEL, iWR = pl_sh.value, pl_hip.value, pl_el.value, pl_wr.value
            if min(slms[iSH].visibility, slms[iHIP].visibility,
                   slms[iEL].visibility, slms[iWR].visibility) < THRESHOLD_VISIBILIDADE:
                continue
            sh, hip, el, wr = wlms[iSH], wlms[iHIP], wlms[iEL], wlms[iWR]
            for chave, val in [
                (f'ombro_abd_{lado}',  _angulo_frontal_ombro(sh, hip, el)),
                (f'ombro_flex_{lado}', _angulo_sagital_ombro(sh, hip, el)),
                (f'ombro_rot_{lado}',  _angulo_rotacao_ombro(sh, el, wr)),
            ]:
                if val > 0:
                    self.suavizador[chave].append(val)
                    ang[chave] = round(sum(self.suavizador[chave]) / len(self.suavizador[chave]), 1)
            # Etiquetas empilhadas abaixo do ombro (só as métricas selecionadas)
            px, py = _px(slms[iSH], w, h)
            fora = px >= meio_x
            linha = 0
            for tipo in OMBRO_3D:
                chave = f'{tipo}_{lado}'
                v = ang.get(chave, 0)
                if chave in self.articulacoes_ativas and v > 0:
                    for alvo in (img_bgr, img_ir_color):
                        if alvo is not None:
                            _pill(alvo, px + (16 if fora else -16), py + 30 + linha * 26,
                                  f"{ROTULO_VIDEO[tipo]} {v:.0f}°", hex_bgr(CORES_ARTIC[tipo]),
                                  alinhar_direita=not fora)
                    linha += 1

    def processar_e_desenhar(self, img_bgr, img_ir_color, img_depth):
        h, w = img_bgr.shape[:2]
        results = self.holistic.process(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        ang = {k: 0.0 for k in self.MAPA_ARTICULACOES}
        ang['inclinacao_cabeca'] = 0.0

        tem = (results.face_landmarks or results.pose_landmarks
               or results.left_hand_landmarks or results.right_hand_landmarks)
        if not tem:
            return img_bgr, img_ir_color, ang

        # Rosto: contorno, olhos e lábios em traço fino
        inc = None
        if results.face_landmarks:
            fl = results.face_landmarks
            inc = self._inclinacao_cabeca(fl, w, h)
            ang['inclinacao_cabeca'] = inc
            if self.desenhar_rosto:
                FM = self.mp_face_mesh
                _desenhar_conexoes(img_bgr, fl.landmark, FM.FACEMESH_FACE_OVAL, w, h, COR_ROSTO, 1)
                for con in (FM.FACEMESH_LEFT_EYE, FM.FACEMESH_RIGHT_EYE, FM.FACEMESH_LIPS):
                    _desenhar_conexoes(img_bgr, fl.landmark, con, w, h, COR_ROSTO2, 1)

        # Mãos
        if self.desenhar_maos:
            for mao in (results.left_hand_landmarks, results.right_hand_landmarks):
                if mao:
                    _desenhar_conexoes(img_bgr, mao.landmark, self.mp_holistic.HAND_CONNECTIONS, w, h, COR_MAO, 1)
                    for lm in mao.landmark:
                        cv2.circle(img_bgr, _px(lm, w, h), 2, COR_ROSTO, -1, cv2.LINE_AA)

        # Pose e ângulos
        if results.pose_landmarks:
            lms = results.pose_landmarks.landmark
            _desenhar_esqueleto(img_bgr, lms, self.mp_holistic.POSE_CONNECTIONS, w, h)
            if img_ir_color is not None:
                _desenhar_esqueleto(img_ir_color, lms, self.mp_holistic.POSE_CONNECTIONS, w, h)
            meio_x = (lms[23].x + lms[24].x) / 2 * w     # centro do quadril: etiqueta vai "para fora"
            self._lm_frame = {}

            for nome in self.articulacoes_ativas:
                if nome not in self.MAPA_ARTICULACOES: continue
                eA, eB, eC = self.MAPA_ARTICULACOES[nome]
                iA, iB, iC = eA.value, eB.value, eC.value
                lm_a = self._lm_efetivo(iA, lms[iA])
                lm_b = self._lm_efetivo(iB, lms[iB])
                lm_c = self._lm_efetivo(iC, lms[iC])
                if lm_a is None or lm_b is None or lm_c is None:
                    continue
                if img_depth is not None:
                    angulo = calcular_angulo_3d(
                        extrair_coordenada_3d(lm_a, w, h, img_depth),
                        extrair_coordenada_3d(lm_b, w, h, img_depth),
                        extrair_coordenada_3d(lm_c, w, h, img_depth))
                else:
                    angulo = calcular_angulo_2d(lm_a, lm_b, lm_c, w, h)

                if angulo > 0:
                    self.suavizador[nome].append(angulo)
                    suave = sum(self.suavizador[nome]) / len(self.suavizador[nome])
                    pa, pb, pc = _px(lm_a, w, h), _px(lm_b, w, h), _px(lm_c, w, h)
                    cor = hex_bgr(info_artic(nome)[2])
                    cv2.line(img_bgr, pa, pb, cor, 3, cv2.LINE_AA)
                    cv2.line(img_bgr, pb, pc, cor, 3, cv2.LINE_AA)
                    _arco(img_bgr, pb, pa, pc, cor)
                    cv2.circle(img_bgr, pb, 6, cor, -1, cv2.LINE_AA)
                    cv2.circle(img_bgr, pb, 6, (255, 255, 255), 1, cv2.LINE_AA)
                    fora = pb[0] >= meio_x
                    for alvo in (img_bgr, img_ir_color):
                        if alvo is not None:
                            _pill(alvo, pb[0] + (16 if fora else -16), pb[1], f"{suave:.0f}°", cor,
                                  alinhar_direita=not fora)
                    ang[nome] = round(suave, 1)

            # Anel âmbar no quadril quando a posição está sendo interpolada (tracking perdido)
            for _idx in (23, 24):
                if self._frames_perdido.get(_idx, 0) > 0 and self._ultima_pos[_idx]:
                    p = (int(self._ultima_pos[_idx][0] * w), int(self._ultima_pos[_idx][1] * h))
                    cv2.circle(img_bgr, p, 11, hex_bgr(WARNING), 2, cv2.LINE_AA)

            # Análise 3D do ombro (abdução, flexão, rotação)
            if getattr(results, "pose_world_landmarks", None):
                self._calcular_ombros_3d(results.pose_world_landmarks.landmark, lms,
                                         w, h, img_bgr, img_ir_color, ang, meio_x)

        if inc is not None:
            cor_inc = SUCCESS if abs(inc) < 10 else WARNING if abs(inc) < 20 else DANGER
            _pill(img_bgr, 12, 24, f"Cabeça {inc:+.1f}°", hex_bgr(cor_inc))

        return img_bgr, img_ir_color, ang

    def run(self):
        while self.rodando:
            if self._camera_pedida is not None:
                self._aplicar_troca_camera()
            frame_rgb = None
            frame_3d  = np.zeros((480,640,3), dtype=np.uint8)
            frame_ir  = np.zeros((480,640,3), dtype=np.uint8)
            texto_crono = ""
            ang = {k: 0.0 for k in self.MAPA_ARTICULACOES}
            ang['inclinacao_cabeca'] = 0.0

            if self.kinect_ativo:
                img_rgb   = np.frombuffer(self.color_stream.read_frame().get_buffer_as_uint8(),  dtype=np.uint8 ).reshape(480,640,3)
                img_depth = np.frombuffer(self.depth_stream.read_frame().get_buffer_as_uint16(), dtype=np.uint16).reshape(480,640)
                img_bgr   = cv2.flip(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), 1)
                img_depth = cv2.flip(img_depth, 1)
                img_ir    = cv2.applyColorMap(cv2.convertScaleAbs(img_depth, alpha=255.0/4500.0), cv2.COLORMAP_JET)

                img_bgr, img_ir, ang = self.processar_e_desenhar(img_bgr, img_ir, img_depth)
                frame_rgb = img_bgr
                frame_ir  = img_ir

                z = img_depth[::self.PASSO, ::self.PASSO].flatten() / 1000.0
                x, y = self.x_grid * z, self.y_grid * z
                validos = (z > 0.1) & (z < 3.0)
                xv, yv, zv = x[validos], y[validos], z[validos]
                cores = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)[::self.PASSO, ::self.PASSO].reshape(-1,3)[validos]
                cxr,sxr = math.cos(self.angulo_rotacao_x), math.sin(self.angulo_rotacao_x)
                cyr,syr = math.cos(self.angulo_rotacao_y), math.sin(self.angulo_rotacao_y)
                czr,szr = math.cos(self.angulo_rotacao_z), math.sin(self.angulo_rotacao_z)
                y1=yv*cxr-zv*sxr; z1=yv*sxr+zv*cxr; x1=xv
                x2=x1*cyr-z1*syr; z2=x1*syr+z1*cyr; y2=y1
                xr=x2*czr-y2*szr; yr=x2*szr+y2*czr; zr=z2+2.0
                pxc=((xr/zr)*500+320).astype(int); pyc=((yr/zr)*500+240).astype(int)
                lim=(pxc>=0)&(pxc<640)&(pyc>=0)&(pyc<480)
                frame_3d[pyc[lim], pxc[lim]] = cores[lim][:,::-1]

            elif self.webcam_ativa:
                suc, frame = self.webcam.read()
                if suc:
                    img_bgr = cv2.flip(frame, 1)
                    img_bgr, _, ang = self.processar_e_desenhar(img_bgr, None, None)
                    frame_rgb = img_bgr

            # FPS real do loop (média móvel) — usado no FPS do vídeo gravado
            agora = time.time()
            if self._t_ultimo_loop is not None and frame_rgb is not None:
                dt = agora - self._t_ultimo_loop
                if dt > 0: self.fps_medido = 0.9 * self.fps_medido + 0.1 * (1.0 / dt)
            if frame_rgb is not None: self._t_ultimo_loop = agora

            with self._lock_gravacao:
                if self.gravando and self.escritor_csv and frame_rgb is not None:
                    t = round(time.time() - self.tempo_inicio_gravacao, 2)
                    seg = int(t); mm = seg // 60; ss = seg % 60
                    texto_crono = f"{mm:02d}:{ss:02d}"
                    linha = [t]
                    for key, _ in COLUNAS_CSV:
                        v = ang.get(key, 0.0)
                        linha.append(v if v != 0.0 else '')
                    self.escritor_csv.writerow(linha)
                    if self.video_writer: self.video_writer.write(frame_rgb)

            if frame_rgb is not None:
                self.sinal_frames_prontos.emit(frame_rgb, frame_3d, frame_ir, texto_crono, ang)

    def stop(self):
        self.rodando = False
        self.parar_gravacao(assincrono=False)
        self.wait()
        self.holistic.close()
        if self.kinect_ativo:
            self.depth_stream.stop(); self.color_stream.stop(); openni2.unload()
        if self.webcam_ativa:
            self.webcam.release()


# ── Componentes de interface ────────────────────────────────────────────────────
class Toggle(QCheckBox):
    """Interruptor (switch) — texto à esquerda, chave à direita."""
    def __init__(self, texto, parent=None):
        super().__init__(texto, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMinimumHeight(34)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 60, 34)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        ativo = self.isEnabled(); on = self.isChecked()
        p.setPen(QColor(TEXT if ativo else TEXT3)); p.setFont(self.font())
        p.drawText(r.adjusted(0, 0, -48, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        w, h = 34.0, 18.0
        x = r.right() - w - 1; y = r.center().y() - h / 2 + 1
        trilho = QColor(PRIMARY if on else BORDER2)
        if not ativo: trilho.setAlpha(90)
        p.setPen(Qt.NoPen); p.setBrush(trilho)
        p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
        d = h - 6
        kx = x + w - d - 3 if on else x + 3
        p.setBrush(QColor("#FFFFFF" if on else TEXT2) if ativo else QColor(TEXT3))
        p.drawEllipse(QRectF(kx, y + 3, d, d))
        p.end()


class Chip(QFrame):
    """Pílula de status (topo): ● texto"""
    def __init__(self, texto, cor=None, glifo=None):
        super().__init__()
        self.setObjectName("chip")
        self.setFixedHeight(28)
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 0, 12, 0); lay.setSpacing(7)
        self.ico = QLabel()
        if glifo: self.ico.setPixmap(icone_pixmap(glifo, TEXT2, 14))
        self.ico.setVisible(bool(glifo)); lay.addWidget(self.ico)
        self.dot = QLabel(); self.dot.setFixedSize(8, 8); lay.addWidget(self.dot)
        self.lbl = QLabel(texto); self.lbl.setObjectName("chipTexto"); lay.addWidget(self.lbl)
        self.set_cor(cor)

    def set_cor(self, cor):
        self.dot.setVisible(cor is not None)
        if cor: self.dot.setStyleSheet(f"background:{cor}; border-radius:4px;")

    def set_texto(self, t):
        self.lbl.setText(t)


class PainelVideo(QFrame):
    def __init__(self, titulo, subtitulo, cor, vazio="Aguardando câmera…"):
        super().__init__()
        self.setObjectName("cardVideo")
        lay = QVBoxLayout(self); lay.setContentsMargins(1, 1, 1, 1); lay.setSpacing(0)
        barra = QFrame(); barra.setObjectName("barraVideo"); barra.setFixedHeight(40)
        bl = QHBoxLayout(barra); bl.setContentsMargins(14, 0, 12, 0); bl.setSpacing(8)
        dot = QLabel(); dot.setFixedSize(8, 8); dot.setStyleSheet(f"background:{cor}; border-radius:4px;")
        t = QLabel(titulo); t.setObjectName("titulo")
        st = QLabel(subtitulo); st.setObjectName("sutil")
        bl.addWidget(dot); bl.addWidget(t); bl.addSpacing(2); bl.addWidget(st); bl.addStretch()
        self.badge = QLabel("● REC  00:00"); self.badge.setObjectName("rec"); self.badge.hide()
        bl.addWidget(self.badge)
        self.info = QLabel(""); self.info.setObjectName("sutil"); bl.addWidget(self.info)
        lay.addWidget(barra)
        self.tela = QLabel(vazio); self.tela.setObjectName("tela")
        self.tela.setAlignment(Qt.AlignCenter)
        self.tela.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        lay.addWidget(self.tela, 1)

    def set_gravando(self, on):
        self.setProperty("gravando", on); repolir(self)
        self.badge.setVisible(on)


class CardAngulo(QFrame):
    """Card de ângulo ao vivo: barra de cor · nome · E/D · mín/máx · valor grande."""
    def __init__(self, nome, lado, cor):
        super().__init__()
        self.setObjectName("jcard")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 14, 0); lay.setSpacing(12)
        barra = QFrame(); barra.setFixedWidth(4)
        barra.setStyleSheet(f"background:{cor}; border:none; border-top-left-radius:9px; "
                            f"border-bottom-left-radius:9px;")
        lay.addWidget(barra)
        col = QVBoxLayout(); col.setContentsMargins(0, 10, 0, 10); col.setSpacing(3)
        linha = QHBoxLayout(); linha.setSpacing(6)
        n = QLabel(nome); n.setObjectName("jnome"); linha.addWidget(n)
        if lado:
            tag = QLabel(lado); tag.setObjectName("tag")
            tag.setToolTip("Esquerdo" if lado == "E" else "Direito"); linha.addWidget(tag)
        linha.addStretch(); col.addLayout(linha)
        self.lbl_mm = QLabel(""); self.lbl_mm.setObjectName("sutil"); col.addWidget(self.lbl_mm)
        lay.addLayout(col, 1)
        self.lbl_valor = QLabel("—"); self.lbl_valor.setFont(fonte_display(26))
        self.lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_valor.setMinimumWidth(72)
        lay.addWidget(self.lbl_valor)
        self._cor_valor = None
        self.set_cor_valor(TEXT3)
        self.com_minmax = True
        self.reset()

    def set_cor_valor(self, cor):
        if cor != self._cor_valor:
            self._cor_valor = cor
            self.lbl_valor.setStyleSheet(f"color:{cor};")

    def reset(self):
        self.vmin = self.vmax = None
        self.lbl_mm.setText("mín —   máx —")

    def atualizar(self, v, cor=None):
        if not v:
            self.lbl_valor.setText("—"); self.set_cor_valor(TEXT3); return
        self.lbl_valor.setText(f"{v:.0f}°" if self.com_minmax else f"{v:.1f}°")
        self.set_cor_valor(cor or TEXT)
        if not self.com_minmax: return
        self.vmin = v if self.vmin is None else min(self.vmin, v)
        self.vmax = v if self.vmax is None else max(self.vmax, v)
        self.lbl_mm.setText(f"mín {self.vmin:.0f}°   máx {self.vmax:.0f}°")


class Toast(QFrame):
    """Mensagem flutuante temporária sobre a área de vídeo."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        lay = QHBoxLayout(self); lay.setContentsMargins(14, 10, 18, 10); lay.setSpacing(10)
        self.ico = QLabel(); lay.addWidget(self.ico)
        self.txt = QLabel(""); self.txt.setObjectName("toastTexto"); lay.addWidget(self.txt)
        self.efeito = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self.efeito)
        self.anim = QPropertyAnimation(self.efeito, b"opacity", self)
        self.anim.setDuration(260); self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.finished.connect(self._fim_anim)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self._sumir)
        self.hide()

    def mostrar(self, texto, tipo="ok", duracao=2800):
        cor, glifo = {"ok": (SUCCESS, ICO['ok']), "alerta": (WARNING, ICO['alerta']),
                      "info": (INFO, ICO['info'])}[tipo]
        self.ico.setPixmap(icone_pixmap(glifo, cor, 18))
        self.txt.setText(texto)
        self.adjustSize(); self._posicionar()
        self.show(); self.raise_()
        self.anim.stop(); self.anim.setStartValue(self.efeito.opacity() if self.isVisible() else 0.0)
        self.anim.setEndValue(1.0); self.anim.start()
        self.timer.start(duracao)

    def _posicionar(self):
        p = self.parentWidget()
        if p: self.move((p.width() - self.width()) // 2, p.height() - self.height() - 28)

    def _sumir(self):
        self.anim.stop(); self.anim.setStartValue(1.0); self.anim.setEndValue(0.0); self.anim.start()

    def _fim_anim(self):
        if self.anim.endValue() == 0.0: self.hide()


class Splash(QSplashScreen):
    def __init__(self):
        dpr = _dpr(); W, H = 520, 300
        pm = QPixmap(int(W * dpr), int(H * dpr)); pm.setDevicePixelRatio(dpr); pm.fill(QColor(SURFACE))
        p = QPainter(pm); p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        p.setPen(QPen(QColor(BORDER2), 1)); p.setBrush(Qt.NoBrush); p.drawRect(QRectF(0.5, 0.5, W - 1, H - 1))
        p.drawPixmap(44, 70, desenhar_logo(56))
        p.setPen(QColor(TEXT)); p.setFont(fonte_display(34, QFont.Bold))
        p.drawText(QRectF(116, 66, 380, 44), Qt.AlignLeft | Qt.AlignVCenter, "BioMotion")
        f = QFont(FONTE_UI); f.setPixelSize(14); p.setFont(f); p.setPen(QColor(TEXT2))
        p.drawText(QRectF(118, 106, 380, 24), Qt.AlignLeft | Qt.AlignVCenter, "Análise biomecânica de movimento")
        g = QLinearGradient(44, 0, W - 44, 0); g.setColorAt(0, QColor(PRIMARY)); g.setColorAt(1, QColor("#3B82F6"))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(QRectF(44, 176, W - 88, 3), 1.5, 1.5)
        p.end()
        super().__init__(pm)
        self._msg = "Iniciando…"

    def mensagem(self, texto):
        self._msg = texto; self.repaint(); QApplication.processEvents()

    def drawContents(self, p):
        f = QFont(FONTE_UI); f.setPixelSize(12); p.setFont(f); p.setPen(QColor(TEXT3))
        p.drawText(QRectF(44, 200, 432, 22), Qt.AlignLeft | Qt.AlignVCenter, self._msg)
        p.drawText(QRectF(44, 250, 432, 22), Qt.AlignLeft | Qt.AlignVCenter, "v2.2")


# ── Janela principal ────────────────────────────────────────────────────────────
ORDEM_CARDS = [f"{t}_{l}" for _, tipos in GRUPOS_ARTIC for t in tipos for l in ("esquerdo", "direito")]
TODAS_ARTIC = INFERIORES + SUPERIORES + OMBRO_3D
JANELA_GRAFICO_S = 10.0

class JanelaBioMotion(QMainWindow):
    def __init__(self, splash=None):
        super().__init__()
        configurar_aparencia(QApplication.instance())
        self.setWindowTitle("BioMotion — Análise Biomecânica")
        self.setWindowIcon(QIcon(desenhar_logo(64)))
        self.setMinimumSize(1200, 720)
        self.resize(1560, 940)

        # Motor (usa a última câmera escolhida, se ainda existir)
        if splash: splash.mensagem("Detectando câmeras e carregando o modelo de IA…")
        self.settings = QSettings("BioMotion", "BioMotion")
        cam_salva = self.settings.value("camera_indice", None)
        try: cam_salva = int(cam_salva) if cam_salva is not None else None
        except (TypeError, ValueError): cam_salva = None
        self.motor = MotorBiomecanico(camera_preferida=cam_salva)
        if splash: splash.mensagem("Montando a interface…")

        raiz = QFrame(); raiz.setObjectName("app")
        raiz.setFocusPolicy(Qt.ClickFocus)          # clicar fora tira o foco do campo de nome
        self.setCentralWidget(raiz)
        lr = QVBoxLayout(raiz); lr.setContentsMargins(0, 0, 0, 0); lr.setSpacing(0)
        lr.addWidget(self._criar_topo())
        corpo = QHBoxLayout(); corpo.setContentsMargins(0, 0, 0, 0); corpo.setSpacing(0)
        corpo.addWidget(self._criar_sidebar())
        corpo.addWidget(self._criar_palco(), 1)
        corpo.addWidget(self._criar_painel_angulos())
        lr.addLayout(corpo, 1)
        self._criar_status_bar()
        self._criar_atalhos()

        self._blink = True
        self._timer_blink = QTimer(self); self._timer_blink.timeout.connect(self._piscar_rec)
        self._fps_frames = 0; self._fps_last = time.time()
        self._t0 = time.time()

        self._restaurar_articulacoes()
        self._atualizar_status_vistas()
        self._atualizar_contexto()

        self.motor.sinal_frames_prontos.connect(self.desenhar_telas)
        self.motor.start()

    # ── Topo ────────────────────────────────────────────────────────────────────
    def _criar_topo(self):
        topo = QFrame(); topo.setObjectName("topbar"); topo.setFixedHeight(60)
        lay = QHBoxLayout(topo); lay.setContentsMargins(20, 0, 16, 0); lay.setSpacing(12)
        logo = QLabel(); logo.setPixmap(desenhar_logo(30)); lay.addWidget(logo)
        col = QVBoxLayout(); col.setSpacing(0); col.setContentsMargins(0, 0, 0, 0)
        marca = QLabel("BioMotion"); marca.setObjectName("marca")
        sub = QLabel("Análise biomecânica"); sub.setObjectName("sutil")
        col.addStretch(); col.addWidget(marca); col.addWidget(sub); col.addStretch()
        lay.addLayout(col)
        lay.addSpacing(14)
        div = QFrame(); div.setObjectName("divisor"); div.setFixedSize(1, 28); lay.addWidget(div)
        lay.addSpacing(14)
        ico = QLabel(); ico.setPixmap(icone_pixmap(ICO['atleta'], TEXT2, 16)); lay.addWidget(ico)
        self.lbl_ctx_atleta = QLabel(""); self.lbl_ctx_atleta.setObjectName("titulo")
        lay.addWidget(self.lbl_ctx_atleta)
        self.chip_ctx_vista = Chip("", PRIMARY); lay.addWidget(self.chip_ctx_vista)
        lay.addStretch()
        k = self.motor.kinect_ativo
        self.chip_kinect = Chip("Kinect" if k else "Kinect ausente", SUCCESS if k else TEXT3)
        self.chip_kinect.setToolTip("Sensor de profundidade: ângulos em 3D" if k
                                    else "Sem Kinect: ângulos calculados em 2D pela webcam")
        cam = self.motor.camera_indice
        self.chip_webcam = Chip(f"Câmera {cam}" if self.motor.webcam_ativa else "Sem câmera",
                                SUCCESS if self.motor.webcam_ativa else DANGER)
        self.chip_modo = Chip("Ângulos 3D" if k else "Ângulos 2D", None, ICO['ver'])
        self.chip_fps = Chip("-- fps", None, ICO['video'])
        self.lbl_fps = self.chip_fps.lbl
        for c in (self.chip_kinect, self.chip_webcam, self.chip_modo, self.chip_fps):
            lay.addWidget(c)
        return topo

    # ── Barra lateral (fluxo: atleta → vista → gravar) ─────────────────────────
    def _criar_sidebar(self):
        moldura = QFrame(); moldura.setObjectName("sidebar"); moldura.setFixedWidth(348)
        ml = QVBoxLayout(moldura); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        conteudo = QWidget()
        lay = QVBoxLayout(conteudo); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(14)
        lay.addWidget(self._card_atleta())
        lay.addWidget(self._card_gravacao())
        lay.addWidget(self._linha_elenco())
        lay.addSpacing(4)
        lay.addWidget(self._abas_config())
        lay.addStretch()
        scroll.setWidget(conteudo)
        ml.addWidget(scroll, 1)
        ml.addWidget(self._rodape_atalhos())
        return moldura

    def _cabecalho_card(self, glifo, titulo, extra=None):
        h = QHBoxLayout(); h.setSpacing(8); h.setContentsMargins(0, 0, 0, 0)
        ico = QLabel(); ico.setPixmap(icone_pixmap(glifo, PRIMARY, 16)); h.addWidget(ico)
        t = QLabel(titulo); t.setObjectName("titulo"); h.addWidget(t); h.addStretch()
        if extra is not None: h.addWidget(extra)
        return h

    def _card_atleta(self):
        card = QFrame(); card.setObjectName("card")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 14, 16, 16); lay.setSpacing(10)
        lay.addLayout(self._cabecalho_card(ICO['atleta'], "Atleta"))
        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Nome do atleta")
        self.input_nome.addAction(icone(ICO['atleta'], TEXT3, 14), QLineEdit.LeadingPosition)
        self.input_nome.setClearButtonEnabled(True)
        self.input_nome.textChanged.connect(self._atualizar_status_vistas)
        self.input_nome.textChanged.connect(self._atualizar_contexto)
        self.input_nome.returnPressed.connect(lambda: self.centralWidget().setFocus())
        lay.addWidget(self.input_nome)

        lay.addSpacing(2)
        lay.addWidget(secao("Vista da gravação"))
        lv = QHBoxLayout(); lv.setSpacing(6)
        self.grupo_vistas = QButtonGroup(self); self.grupo_vistas.setExclusive(True)
        self.btns_vista = {}
        for i, vista in enumerate(VISTAS):
            b = QPushButton(vista); b.setCheckable(True); b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor); b.setProperty("variant", "vista")
            b.setMinimumWidth(10); b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setToolTip(f"Vista {vista.lower()}  ·  atalho: {i + 1}")
            self.grupo_vistas.addButton(b, i); self.btns_vista[vista] = b; lv.addWidget(b)
        self.btns_vista[VISTAS[0]].setChecked(True)
        self.grupo_vistas.buttonToggled.connect(lambda *_: self._atualizar_contexto())
        lay.addLayout(lv)

        self.barra_progresso = QProgressBar(); self.barra_progresso.setRange(0, len(VISTAS))
        self.barra_progresso.setTextVisible(False); self.barra_progresso.setFixedHeight(4)
        lay.addWidget(self.barra_progresso)
        self.lbl_progresso = QLabel(""); self.lbl_progresso.setObjectName("sutil")
        lay.addWidget(self.lbl_progresso)
        return card

    def _card_gravacao(self):
        card = QFrame(); card.setObjectName("card")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(10)
        self.btn_gravar = QPushButton(); self.btn_gravar.setCheckable(True)
        self.btn_gravar.setFocusPolicy(Qt.NoFocus); self.btn_gravar.setCursor(Qt.PointingHandCursor)
        self.btn_gravar.setFixedHeight(52); self.btn_gravar.setIconSize(QSize(18, 18))
        self.btn_gravar.setToolTip("Iniciar / parar gravação  ·  atalho: Espaço")
        self.btn_gravar.clicked.connect(self.alternar_gravacao)
        self._estilo_botao_gravar(False)
        lay.addWidget(self.btn_gravar)
        self.lbl_destino = QLabel(""); self.lbl_destino.setObjectName("sutil")
        self.lbl_destino.setWordWrap(True)
        lay.addWidget(self.lbl_destino)
        la = QHBoxLayout(); la.setSpacing(8)
        self.btn_abrir_pasta = QPushButton("Pasta"); self.btn_abrir_pasta.setProperty("variant", "secondary")
        self.btn_abrir_pasta.setIcon(icone(ICO['pasta'], TEXT2, 16))
        self.btn_abrir_pasta.setToolTip("Abrir a pasta do atleta no Explorer  ·  Ctrl+O")
        self.btn_abrir_pasta.clicked.connect(self._abrir_pasta_atleta)
        self.btn_proximo = QPushButton("Próximo atleta"); self.btn_proximo.setProperty("variant", "secondary")
        self.btn_proximo.setIcon(icone(ICO['proximo'], TEXT2, 16))
        self.btn_proximo.setToolTip("Limpar o nome e começar o próximo atleta  ·  atalho: N")
        self.btn_proximo.clicked.connect(self._proximo_atleta)
        for b in (self.btn_abrir_pasta, self.btn_proximo):
            b.setFocusPolicy(Qt.NoFocus); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(38)
        la.addWidget(self.btn_abrir_pasta, 2); la.addWidget(self.btn_proximo, 3)
        lay.addLayout(la)
        return card

    def _linha_elenco(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(4, 0, 4, 0); h.setSpacing(8)
        ico = QLabel(); ico.setPixmap(icone_pixmap(ICO['elenco'], TEXT3, 15)); h.addWidget(ico)
        self.lbl_atletas = QLabel(""); self.lbl_atletas.setObjectName("muted"); h.addWidget(self.lbl_atletas)
        h.addStretch()
        return w

    def _abas_config(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        seg = QFrame(); seg.setObjectName("segmentado")
        sl = QHBoxLayout(seg); sl.setContentsMargins(3, 3, 3, 3); sl.setSpacing(2)
        self.pilha = QStackedWidget()
        grupo = QButtonGroup(self); grupo.setExclusive(True)
        paginas = [("Articulações", self._pagina_articulacoes()),
                   ("Exibição", self._pagina_exibicao()),
                   ("Espacial 3D", self._pagina_3d())]
        for i, (nome, pag) in enumerate(paginas):
            b = QPushButton(nome); b.setCheckable(True); b.setProperty("variant", "seg")
            b.setFocusPolicy(Qt.NoFocus); b.setCursor(Qt.PointingHandCursor)
            grupo.addButton(b, i); sl.addWidget(b)
            self.pilha.addWidget(pag)
            if i == 0: b.setChecked(True)
        grupo.buttonClicked[int].connect(self.pilha.setCurrentIndex)
        lay.addWidget(seg); lay.addWidget(self.pilha)
        return w

    def _pagina_articulacoes(self):
        pag = QWidget(); lay = QVBoxLayout(pag); lay.setContentsMargins(2, 0, 2, 0); lay.setSpacing(8)
        pre = QHBoxLayout(); pre.setSpacing(2)
        for rotulo, tipos in (("Inferiores", INFERIORES), ("Superiores", SUPERIORES),
                              ("Todas", TODAS_ARTIC), ("Limpar", [])):
            b = QPushButton(rotulo); b.setProperty("variant", "ghost")
            b.setFocusPolicy(Qt.NoFocus); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, t=tipos: self._aplicar_preset(t))
            pre.addWidget(b)
        pre.addStretch(); lay.addLayout(pre)

        self._chk_map = {}
        for titulo, tipos in GRUPOS_ARTIC:
            lay.addSpacing(4); lay.addWidget(secao(titulo))
            grid = QGridLayout(); grid.setSpacing(6)
            for r, tipo in enumerate(tipos):
                for c, lado in enumerate(("esquerdo", "direito")):
                    chave = f"{tipo}_{lado}"
                    cor = CORES_ARTIC[tipo]
                    b = QPushButton(f"{NOMES_ARTIC[tipo]} {'Esq' if c == 0 else 'Dir'}")
                    b.setCheckable(True); b.setFocusPolicy(Qt.NoFocus); b.setCursor(Qt.PointingHandCursor)
                    ic = QIcon(); ic.addPixmap(icone_ponto(cor), QIcon.Normal, QIcon.On)
                    ic.addPixmap(icone_ponto(BORDER2), QIcon.Normal, QIcon.Off)
                    b.setIcon(ic); b.setIconSize(QSize(10, 10))
                    b.setStyleSheet(
                        f"QPushButton {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; "
                        f"padding:8px 10px; color:{TEXT2}; text-align:left; font-size:12px; font-weight:600; }}"
                        f"QPushButton:hover {{ border-color:{BORDER2}; color:{TEXT}; }}"
                        f"QPushButton:checked {{ background:{rgba(cor, 0.12)}; border:1px solid {rgba(cor, 0.55)}; "
                        f"color:{TEXT}; }}")
                    b.toggled.connect(self.atualizar_motor)
                    self._chk_map[chave] = b
                    grid.addWidget(b, r, c)
            lay.addLayout(grid)
        return pag

    def _pagina_exibicao(self):
        pag = QWidget(); lay = QVBoxLayout(pag); lay.setContentsMargins(2, 0, 2, 0); lay.setSpacing(4)
        lay.addWidget(secao("Fonte de vídeo"))
        lay.addSpacing(2)
        self.combo_camera = QComboBox()
        self.combo_camera.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_camera.setMinimumContentsLength(12)
        self.combo_camera.view().setMinimumWidth(280)
        self.combo_camera.setCursor(Qt.PointingHandCursor)
        for cam in self.motor.cameras:
            res = f"{cam['largura']}×{cam['altura']}" if cam['largura'] else "?"
            sinal = "" if cam['com_sinal'] else "  ·  sem imagem (virtual?)"
            self.combo_camera.addItem(icone(ICO['camera'], TEXT2 if cam['com_sinal'] else TEXT3, 14),
                                      f"Câmera {cam['indice']}  ·  {res}{sinal}", cam['indice'])
        if not self.motor.cameras:
            self.combo_camera.addItem("Nenhuma câmera encontrada", None)
            self.combo_camera.setEnabled(False)
        pos = self.combo_camera.findData(self.motor.camera_indice)
        if pos >= 0: self.combo_camera.setCurrentIndex(pos)
        if self.motor.kinect_ativo:
            self.combo_camera.setEnabled(False)
            self.combo_camera.setToolTip("Kinect ativo: a webcam não é usada")
        self.combo_camera.currentIndexChanged.connect(self._trocar_camera)
        lay.addWidget(self.combo_camera)

        lay.addSpacing(12); lay.addWidget(secao("Janelas"))
        self.chk_view_rgb = Toggle("Câmera RGB")
        self.chk_view_3d = Toggle("Reconstrução 3D")
        self.chk_view_ir = Toggle("Profundidade (IR)")
        self.chk_view_grafico = Toggle("Gráfico de cinemática")
        for t in (self.chk_view_rgb, self.chk_view_3d, self.chk_view_ir, self.chk_view_grafico):
            t.setChecked(True); lay.addWidget(t)
        if not self.motor.kinect_ativo:
            for t in (self.chk_view_3d, self.chk_view_ir):
                t.setChecked(False); t.setEnabled(False); t.setToolTip("Requer o sensor Kinect")

        lay.addSpacing(12); lay.addWidget(secao("Camadas de IA no vídeo"))
        self.chk_view_rosto = Toggle("Contorno do rosto"); self.chk_view_rosto.setChecked(True)
        self.chk_view_maos = Toggle("Rastreio das mãos"); self.chk_view_maos.setChecked(True)
        lay.addWidget(self.chk_view_rosto); lay.addWidget(self.chk_view_maos)
        self.chk_view_rosto.toggled.connect(self.atualizar_visualizacao_ia)
        self.chk_view_maos.toggled.connect(self.atualizar_visualizacao_ia)
        return pag

    def _pagina_3d(self):
        pag = QWidget(); lay = QVBoxLayout(pag); lay.setContentsMargins(2, 0, 2, 0); lay.setSpacing(8)
        if not self.motor.kinect_ativo:
            aviso = QFrame(); aviso.setObjectName("card")
            al = QHBoxLayout(aviso); al.setContentsMargins(12, 10, 12, 10); al.setSpacing(10)
            ic = QLabel(); ic.setPixmap(icone_pixmap(ICO['info'], INFO, 16)); al.addWidget(ic, 0, Qt.AlignTop)
            t = QLabel("A reconstrução 3D precisa do sensor Kinect. Conecte-o e reinicie o BioMotion.")
            t.setObjectName("muted"); t.setWordWrap(True); al.addWidget(t, 1)
            lay.addWidget(aviso); lay.addSpacing(4)

        def linha_slider(rotulo, attr):
            topo = QHBoxLayout()
            l = QLabel(rotulo); l.setObjectName("muted")
            v = QLabel("0°"); v.setObjectName("titulo"); v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            topo.addWidget(l); topo.addStretch(); topo.addWidget(v)
            sl = QSlider(Qt.Horizontal); sl.setRange(-100, 100); sl.setCursor(Qt.PointingHandCursor)
            sl.valueChanged.connect(self.atualizar_rotacao)
            sl.valueChanged.connect(lambda val, lb=v: lb.setText(f"{int(val * 1.8)}°"))
            sl.setEnabled(self.motor.kinect_ativo)
            lay.addLayout(topo); lay.addWidget(sl); lay.addSpacing(6)
            setattr(self, attr, sl)

        linha_slider("Giro horizontal (Y)", "slider_y")
        linha_slider("Inclinação vertical (X)", "slider_x")
        linha_slider("Tombo lateral (Z)", "slider_z")
        self.btn_reset_3d = QPushButton("Resetar visão 3D"); self.btn_reset_3d.setProperty("variant", "secondary")
        self.btn_reset_3d.setIcon(icone(ICO['reset'], TEXT2, 14)); self.btn_reset_3d.setFocusPolicy(Qt.NoFocus)
        self.btn_reset_3d.clicked.connect(self.resetar_rotacao); self.btn_reset_3d.setEnabled(self.motor.kinect_ativo)
        lay.addWidget(self.btn_reset_3d)
        return pag

    def _rodape_atalhos(self):
        rod = QFrame(); rod.setObjectName("rodape")
        rod.setStyleSheet(f"QFrame#rodape {{ border-top:1px solid {BORDER}; }}")
        lay = QHBoxLayout(rod); lay.setContentsMargins(16, 10, 16, 10); lay.setSpacing(5)
        for tecla, desc in (("Espaço", "gravar"), ("1–3", "vista"), ("N", "próximo")):
            k = QLabel(tecla); k.setObjectName("kbd")
            d = QLabel(desc); d.setObjectName("sutil")
            lay.addWidget(k); lay.addWidget(d); lay.addSpacing(6)
        lay.addStretch()
        return rod

    # ── Palco central (vídeo + gráfico) ─────────────────────────────────────────
    def _criar_palco(self):
        self.palco = QWidget()
        lay = QVBoxLayout(self.palco); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(0)
        split_v = QSplitter(Qt.Vertical); split_v.setChildrenCollapsible(False); split_v.setHandleWidth(14)
        split_h = QSplitter(Qt.Horizontal); split_h.setChildrenCollapsible(False); split_h.setHandleWidth(14)
        self.splitter_videos = split_h

        vazio = "Aguardando câmera…" if (self.motor.webcam_ativa or self.motor.kinect_ativo) \
            else "Nenhuma câmera encontrada.\nConecte uma webcam e reinicie o BioMotion."
        self.painel_rgb = PainelVideo("Câmera", "RGB · espelhado", SUCCESS, vazio)
        self.painel_3d = PainelVideo("Reconstrução 3D", "Nuvem de pontos", INFO)
        self.painel_ir = PainelVideo("Profundidade", "Sensor Kinect", WARNING)
        self.tela_rgb, self.tela_3d, self.tela_ir = self.painel_rgb.tela, self.painel_3d.tela, self.painel_ir.tela
        for p in (self.painel_rgb, self.painel_3d, self.painel_ir): split_h.addWidget(p)

        # Gráfico
        card_g = QFrame(); card_g.setObjectName("card")
        gl = QVBoxLayout(card_g); gl.setContentsMargins(16, 12, 12, 6); gl.setSpacing(4)
        sub = QLabel(f"Ângulo (°) · últimos {int(JANELA_GRAFICO_S)} s"); sub.setObjectName("sutil")
        gl.addLayout(self._cabecalho_card(ICO['grafico'], "Cinemática articular", sub))
        pg.setConfigOptions(antialias=True, background=CARD, foreground=TEXT3)
        self.grafico = pg.PlotWidget()
        self.grafico.setStyleSheet("border:none; background:transparent;")
        pi = self.grafico.getPlotItem(); pi.hideButtons(); pi.setMenuEnabled(False)
        self.grafico.setMouseEnabled(x=False, y=False)
        f_ticks = QFont(FONTE_UI); f_ticks.setPixelSize(11)
        for nome_eixo in ('left', 'bottom'):
            ax = self.grafico.getAxis(nome_eixo)
            ax.setPen(pg.mkPen(BORDER2)); ax.setTextPen(pg.mkPen(TEXT3)); ax.setTickFont(f_ticks)
            ax.setStyle(tickLength=-4)
        self.grafico.getAxis('left').setTicks([[(v, f"{v}°") for v in range(0, 181, 45)]])
        self.grafico.getAxis('left').setWidth(44)
        self.grafico.showGrid(x=False, y=True, alpha=0.10)
        self.grafico.setYRange(0, 180, padding=0.04)
        gl.addWidget(self.grafico, 1)
        self.card_grafico = card_g

        split_v.addWidget(split_h); split_v.addWidget(card_g)
        split_v.setStretchFactor(0, 3); split_v.setStretchFactor(1, 1)
        split_v.setSizes([600, 250])
        lay.addWidget(split_v)

        self.toast = Toast(self.palco)

        # Buffers do gráfico
        self.buffer_size = 400
        self.eixo_x_tempo = deque(maxlen=self.buffer_size)
        self.eixo_y_dados = {k: deque(maxlen=self.buffer_size) for k in ORDEM_CARDS}
        self.curvas_plot = {}
        for k in ORDEM_CARDS:
            tipo, lado, cor, _ = info_artic(k)
            self.curvas_plot[k] = self.grafico.plot(
                pen=pg.mkPen(cor, width=2, style=Qt.SolidLine if lado == 'E' else Qt.DashLine))

        self.chk_view_rgb.toggled.connect(self.painel_rgb.setVisible)
        self.chk_view_3d.toggled.connect(self.painel_3d.setVisible)
        self.chk_view_ir.toggled.connect(self.painel_ir.setVisible)
        self.chk_view_grafico.toggled.connect(self.card_grafico.setVisible)
        self.painel_3d.setVisible(self.chk_view_3d.isChecked())
        self.painel_ir.setVisible(self.chk_view_ir.isChecked())
        return self.palco

    # ── Painel direito: ângulos ao vivo ─────────────────────────────────────────
    def _criar_painel_angulos(self):
        moldura = QFrame(); moldura.setObjectName("painelDireito"); moldura.setFixedWidth(292)
        ml = QVBoxLayout(moldura); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)
        cab = QWidget(); cl = QVBoxLayout(cab); cl.setContentsMargins(18, 18, 18, 8); cl.setSpacing(2)
        linha = QHBoxLayout()
        t = QLabel("Ângulos em tempo real"); t.setObjectName("tituloPainel"); linha.addWidget(t)
        linha.addStretch()
        self.btn_zerar = QPushButton("Zerar"); self.btn_zerar.setProperty("variant", "ghost")
        self.btn_zerar.setIcon(icone(ICO['reset'], TEXT2, 13)); self.btn_zerar.setFocusPolicy(Qt.NoFocus)
        self.btn_zerar.setToolTip("Zerar os valores mínimo e máximo")
        self.btn_zerar.clicked.connect(self._zerar_minmax); linha.addWidget(self.btn_zerar)
        cl.addLayout(linha)
        s = QLabel("Média móvel de 5 quadros · " + ("3D (Kinect)" if self.motor.kinect_ativo else "2D (webcam)"))
        s.setObjectName("sutil"); cl.addWidget(s)
        ml.addWidget(cab)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cont = QWidget(); lay = QVBoxLayout(cont); lay.setContentsMargins(16, 8, 16, 16); lay.setSpacing(8)

        self.card_cabeca = CardAngulo("Inclinação da cabeça", None, "#94A3B8")
        self.card_cabeca.com_minmax = False
        self.card_cabeca.lbl_mm.setText("Neutra até ±10°")
        lay.addWidget(self.card_cabeca)
        lay.addSpacing(6)

        self.cards_angulo = {}
        self._lbl_grupos = []      # (rótulo da seção, tipos do grupo)
        for titulo, tipos in GRUPOS_ARTIC:
            lbl = secao(titulo.split(" ·")[0]); lay.addWidget(lbl)
            self._lbl_grupos.append((lbl, tipos))
            for t in tipos:
                for lado_ in ("esquerdo", "direito"):
                    chave = f"{t}_{lado_}"
                    tipo, lado, cor, nome = info_artic(chave)
                    if tipo in OMBRO_3D: nome = f"{nome} do ombro"
                    c = CardAngulo(nome, lado, cor); c.hide()
                    self.cards_angulo[chave] = c; lay.addWidget(c)

        self.vazio_angulos = QFrame(); self.vazio_angulos.setObjectName("vazio")
        vl = QVBoxLayout(self.vazio_angulos); vl.setContentsMargins(18, 22, 18, 18); vl.setSpacing(8)
        ic = QLabel(); ic.setPixmap(icone_pixmap(ICO['ver'], TEXT3, 26)); ic.setAlignment(Qt.AlignCenter)
        t1 = QLabel("Nenhuma articulação selecionada"); t1.setObjectName("titulo"); t1.setAlignment(Qt.AlignCenter)
        t2 = QLabel("Escolha as articulações na aba Articulações, à esquerda.")
        t2.setObjectName("sutil"); t2.setWordWrap(True); t2.setAlignment(Qt.AlignCenter)
        b = QPushButton("Selecionar membros inferiores"); b.setProperty("variant", "secondary")
        b.setFocusPolicy(Qt.NoFocus); b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self._aplicar_preset(INFERIORES))
        for wdg in (ic, t1, t2): vl.addWidget(wdg)
        vl.addSpacing(4); vl.addWidget(b)
        lay.addWidget(self.vazio_angulos)
        lay.addStretch()
        scroll.setWidget(cont)
        ml.addWidget(scroll, 1)
        return moldura

    # ── Status bar e atalhos ────────────────────────────────────────────────────
    def _criar_status_bar(self):
        sb = self.statusBar(); sb.setSizeGripEnabled(False)
        sb.showMessage("  Pronto. Digite o nome do atleta para começar.")
        self.lbl_pasta_raiz = QLabel(f"Sessões em  {pasta_atletas()}")
        sb.addPermanentWidget(self.lbl_pasta_raiz)

    def _criar_atalhos(self):
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._atalho_gravar)
        for i, vista in enumerate(VISTAS):
            QShortcut(QKeySequence(str(i + 1)), self, activated=lambda v=vista: self._atalho_vista(v))
        QShortcut(QKeySequence("N"), self, activated=self._proximo_atleta)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._abrir_pasta_atleta)

    def _atalho_gravar(self):
        if self.btn_gravar.isEnabled(): self.btn_gravar.click()

    def _atalho_vista(self, vista):
        b = self.btns_vista[vista]
        if b.isEnabled(): b.setChecked(True)

    # ── Atletas / vistas ────────────────────────────────────────────────────────
    def _vista_atual(self):
        return VISTAS[max(0, self.grupo_vistas.checkedId())]

    def _estilo_botao_gravar(self, gravando, crono="00:00"):
        if gravando:
            set_variant(self.btn_gravar, "danger")
            self.btn_gravar.setIcon(icone(ICO['parar'], "#FFFFFF", 18))
            self.btn_gravar.setText(f"  Parar gravação   {crono}")
        else:
            set_variant(self.btn_gravar, "primary")
            self.btn_gravar.setIcon(icone(ICO['gravar'], ON_PRIMARY, 18))
            vista = self._vista_atual() if hasattr(self, "grupo_vistas") else VISTAS[0]
            self.btn_gravar.setText(f"  Gravar vista {vista.lower()}")

    def _atualizar_contexto(self):
        nome = self.input_nome.text().strip()
        self.lbl_ctx_atleta.setText(nome if nome else "Nenhum atleta")
        self.lbl_ctx_atleta.setStyleSheet("" if nome else f"color:{TEXT3}; font-weight:500;")
        self.chip_ctx_vista.set_texto(self._vista_atual())
        if not self.btn_gravar.isChecked(): self._estilo_botao_gravar(False)
        if nome_para_pasta(nome):
            self.lbl_destino.setText(f"Salvará em  Atletas / {nome_para_pasta(nome)}")
        else:
            self.lbl_destino.setText("Digite o nome do atleta para habilitar a gravação.")

    def _atualizar_status_vistas(self):
        nome = self.input_nome.text()
        cont = vistas_gravadas(nome)
        for vista, b in self.btns_vista.items():
            n = cont[vista]
            b.setText(vista + (f" ×{n}" if n > 1 else ""))
            b.setIcon(icone(ICO['check'], SUCCESS, 13) if n else QIcon())
        feitas = sum(1 for n in cont.values() if n > 0)
        self.barra_progresso.setValue(feitas)
        if nome_para_pasta(nome):
            completo = feitas == len(VISTAS)
            self.lbl_progresso.setText("Atleta completo — 3 de 3 vistas gravadas" if completo
                                       else f"{feitas} de {len(VISTAS)} vistas gravadas")
            self.lbl_progresso.setStyleSheet(f"color:{SUCCESS};" if completo else "")
        else:
            self.lbl_progresso.setText("Nenhuma vista gravada")
            self.lbl_progresso.setStyleSheet("")
        total, completos = contar_atletas()
        self.lbl_atletas.setText(f"Elenco: {total} atleta{'s' if total != 1 else ''}  ·  "
                                 f"{completos} completo{'s' if completos != 1 else ''}")
        tem_nome = bool(nome_para_pasta(nome))
        self.btn_abrir_pasta.setEnabled(True)
        self.btn_abrir_pasta.setToolTip(("Abrir a pasta do atleta" if tem_nome else "Abrir a pasta de atletas")
                                        + "  ·  Ctrl+O")

    def _selecionar_proxima_vista_pendente(self):
        cont = vistas_gravadas(self.input_nome.text())
        for vista in VISTAS:
            if cont[vista] == 0:
                self.btns_vista[vista].setChecked(True)
                return

    def _abrir_pasta_atleta(self):
        nome = self.input_nome.text()
        pasta = pasta_atleta(nome) if nome_para_pasta(nome) else pasta_atletas()
        os.makedirs(pasta, exist_ok=True)
        os.startfile(pasta)

    def _proximo_atleta(self):
        if self.btn_gravar.isChecked(): return
        self.input_nome.clear()
        self.btns_vista[VISTAS[0]].setChecked(True)
        self._zerar_minmax()
        self.input_nome.setFocus()
        self.statusBar().showMessage("  Pronto para o próximo atleta")

    # ── Articulações ────────────────────────────────────────────────────────────
    def _aplicar_preset(self, tipos):
        for chave, b in self._chk_map.items():
            b.blockSignals(True); b.setChecked(tipo_artic(chave) in tipos); b.blockSignals(False)
        self.atualizar_motor()

    def _restaurar_articulacoes(self):
        salvas = self.settings.value("articulacoes", None)
        if isinstance(salvas, str): salvas = [salvas] if salvas else []
        if salvas is None:
            self._aplicar_preset(INFERIORES)          # padrão: futebol → membros inferiores
        else:
            for chave, b in self._chk_map.items():
                b.blockSignals(True); b.setChecked(chave in salvas); b.blockSignals(False)
            self.atualizar_motor()

    def atualizar_motor(self, *_):
        ativos = [k for k in ORDEM_CARDS if self._chk_map[k].isChecked()]
        anteriores = set(self.motor.articulacoes_ativas)
        self.motor.articulacoes_ativas = ativos
        for k, card in self.cards_angulo.items():
            on = k in ativos
            if on and k not in anteriores: card.reset()
            card.setVisible(on)
        for lbl, tipos in self._lbl_grupos:
            lbl.setVisible(any(tipo_artic(k) in tipos for k in ativos))
        self.vazio_angulos.setVisible(not ativos)
        for k, curva in self.curvas_plot.items():
            curva.setVisible(k in ativos)
        self.settings.setValue("articulacoes", ativos)

    def _zerar_minmax(self):
        for c in self.cards_angulo.values(): c.reset()

    # ── Slots ───────────────────────────────────────────────────────────────────
    def _trocar_camera(self, _pos):
        indice = self.combo_camera.currentData()
        if indice is None: return
        self.motor.trocar_camera(indice)
        self.settings.setValue("camera_indice", indice)
        self.chip_webcam.set_texto(f"Câmera {indice}")
        self.toast.mostrar(f"Câmera {indice} selecionada", "info", 1800)

    def atualizar_visualizacao_ia(self):
        self.motor.desenhar_rosto = self.chk_view_rosto.isChecked()
        self.motor.desenhar_maos = self.chk_view_maos.isChecked()

    def alternar_gravacao(self, checked):
        if checked:
            nome = self.input_nome.text()
            if not nome_para_pasta(nome):
                self.btn_gravar.setChecked(False)
                self.input_nome.setFocus()
                self.toast.mostrar("Digite o nome do atleta antes de gravar", "alerta")
                self.statusBar().showMessage("  Digite o nome do atleta antes de gravar")
                return
            vista = self._vista_atual()
            self._vista_gravando = vista
            self.input_nome.setEnabled(False)
            for b in self.btns_vista.values(): b.setEnabled(False)
            self.btn_proximo.setEnabled(False)
            self._combo_camera_ativo = self.combo_camera.isEnabled()
            self.combo_camera.setEnabled(False)
            self._estilo_botao_gravar(True)
            pasta = self.motor.iniciar_gravacao(nome, vista)
            self.eixo_x_tempo.clear()
            for k in self.eixo_y_dados: self.eixo_y_dados[k].clear()
            self._zerar_minmax()
            self.painel_rgb.set_gravando(True)
            self.painel_rgb.badge.setText("● REC  00:00")
            self._timer_blink.start(600)
            self.statusBar().showMessage(f"  Gravando vista {vista.lower()}  ·  {pasta}")
        else:
            self._timer_blink.stop()
            self.motor.parar_gravacao()
            self.painel_rgb.set_gravando(False)
            self.input_nome.setEnabled(True)
            for b in self.btns_vista.values(): b.setEnabled(True)
            self.btn_proximo.setEnabled(True)
            self.combo_camera.setEnabled(getattr(self, "_combo_camera_ativo", True))
            vista = getattr(self, "_vista_gravando", "")
            nome = self.input_nome.text().strip()
            self._atualizar_status_vistas()
            self._selecionar_proxima_vista_pendente()
            self._estilo_botao_gravar(False)
            if all(n > 0 for n in vistas_gravadas(nome).values()):
                self.toast.mostrar(f"{nome} completo — 3 vistas gravadas. Tecle N para o próximo.", "ok", 4000)
            else:
                self.toast.mostrar(f"Vista {vista.lower()} salva  ·  {nome}", "ok")
            self.statusBar().showMessage(f"  Vista {vista.lower()} salva em {pasta_atleta(nome)}")

    def _piscar_rec(self):
        self._blink = not self._blink
        cor = DANGER if self._blink else rgba(DANGER, 0.35)
        self.painel_rgb.badge.setStyleSheet(f"color:{cor};")

    def atualizar_rotacao(self):
        self.motor.angulo_rotacao_x = (self.slider_x.value() / 100.0) * math.pi
        self.motor.angulo_rotacao_y = (self.slider_y.value() / 100.0) * math.pi
        self.motor.angulo_rotacao_z = (self.slider_z.value() / 100.0) * math.pi

    def resetar_rotacao(self):
        self.slider_x.setValue(0); self.slider_y.setValue(0); self.slider_z.setValue(0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toast") and self.toast.isVisible(): self.toast._posicionar()

    def desenhar_telas(self, f_rgb, f_3d, f_ir, texto_crono, ang_dict):
        if texto_crono and self.btn_gravar.isChecked():
            self.btn_gravar.setText(f"  Parar gravação   {texto_crono}")
            self.painel_rgb.badge.setText(f"● REC  {texto_crono}")

        inc = ang_dict.get('inclinacao_cabeca', 0.0)
        cor_inc = SUCCESS if abs(inc) < 10 else WARNING if abs(inc) < 20 else DANGER
        self.card_cabeca.atualizar(inc, cor_inc)

        dpr = self.devicePixelRatioF()
        def atualizar(label, frame):
            if not label.isVisible() or not label.window().isVisible(): return
            f = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = f.shape
            img_qt = QImage(f.data, w, h, ch * w, QImage.Format_RGB888)
            pm = QPixmap.fromImage(img_qt).scaled(int(label.width() * dpr), int(label.height() * dpr),
                                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            label.setPixmap(pm)

        atualizar(self.tela_rgb, f_rgb)
        if self.motor.kinect_ativo:
            atualizar(self.tela_3d, f_3d)
            atualizar(self.tela_ir, f_ir)
        if not self.painel_rgb.info.text():
            self.painel_rgb.info.setText(f"{f_rgb.shape[1]}×{f_rgb.shape[0]}")

        for k in self.motor.articulacoes_ativas:
            self.cards_angulo[k].atualizar(ang_dict.get(k, 0.0))

        # FPS
        self._fps_frames += 1
        agora = time.time()
        if agora - self._fps_last >= 1.0:
            self.lbl_fps.setText(f"{self._fps_frames} fps")
            self._fps_frames = 0; self._fps_last = agora

        if self.card_grafico.isVisible():
            t = agora - self._t0
            self.eixo_x_tempo.append(t)
            x = np.fromiter(self.eixo_x_tempo, dtype=float)
            for art, dados in self.eixo_y_dados.items():
                val = ang_dict.get(art, 0.0)
                dados.append(val if val > 0 else (dados[-1] if dados else np.nan))
                if art in self.motor.articulacoes_ativas:
                    self.curvas_plot[art].setData(x, np.fromiter(dados, dtype=float), connect="finite")
            self.grafico.setXRange(max(0.0, t - JANELA_GRAFICO_S), max(JANELA_GRAFICO_S, t), padding=0)

    def closeEvent(self, event):
        self.motor.stop()
        event.accept()


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    configurar_aparencia(app)
    splash = Splash(); splash.show(); app.processEvents()
    janela = JanelaBioMotion(splash)
    janela.showMaximized()
    splash.finish(janela)
    sys.exit(app.exec_())
