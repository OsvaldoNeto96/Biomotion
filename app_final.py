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
from datetime import datetime
import re
import cv2
import numpy as np
import mediapipe as mp
import math
from openni import openni2
from collections import deque
import pyqtgraph as pg
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
                             QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
                             QSlider, QPushButton, QSplitter, QSizePolicy,
                             QLineEdit, QScrollArea, QGridLayout, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap

# ── Paleta ─────────────────────────────────────────────────────────────────────
C_BG       = "#0d1117"
C_PANEL    = "#161b22"
C_PANEL2   = "#1c2128"
C_BORDER   = "#30363d"
C_TEAL     = "#00d4aa"
C_BLUE     = "#58a6ff"
C_TEXT     = "#e6edf3"
C_TEXT2    = "#8b949e"
C_GREEN    = "#3fb950"
C_RED      = "#f85149"
C_AMBER    = "#d29922"
C_PURPLE   = "#bc8cff"
C_ORANGE   = "#ff7b72"

ESTILO_GLOBAL = f"""
QMainWindow, QDialog {{
    background: {C_BG};
}}
QWidget {{
    background: {C_BG};
    color: {C_TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}
/* ── Grupos ── */
QGroupBox {{
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    margin-top: 16px;
    padding: 14px 10px 10px 10px;
    background: {C_PANEL};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 3px 10px;
    left: 14px;
    color: {C_BLUE};
    font-weight: 700;
    font-size: 11px;
    background: {C_PANEL};
    border-radius: 4px;
}}
/* ── CheckBoxes ── */
QCheckBox {{
    spacing: 10px;
    color: #c9d1d9;
    padding: 5px 6px;
    border-radius: 6px;
}}
QCheckBox:hover {{
    background: rgba(88,166,255,0.07);
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 2px solid {C_BORDER};
    background: {C_BG};
}}
QCheckBox::indicator:checked {{
    background: {C_TEAL};
    border-color: {C_TEAL};
    image: none;
}}
QCheckBox::indicator:hover {{
    border-color: {C_BLUE};
}}
/* ── Sliders ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {C_BORDER};
    border-radius: 2px;
    margin: 0 4px;
}}
QSlider::sub-page:horizontal {{
    background: {C_TEAL};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C_TEAL};
    border: 2px solid {C_BG};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #00b894;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}}
/* ── LineEdit ── */
QLineEdit {{
    background: {C_BG};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 10px 14px;
    color: {C_TEXT};
    selection-background-color: {C_BLUE};
}}
QLineEdit:focus {{
    border-color: {C_BLUE};
}}
QLineEdit:disabled {{
    color: {C_TEXT2};
    border-color: #21262d;
    background: {C_PANEL};
}}
/* ── ScrollArea ── */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {C_PANEL};
    width: 5px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: #484f58; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
/* ── Splitter ── */
QSplitter::handle:horizontal {{ background: {C_BORDER}; width: 1px; }}
QSplitter::handle:vertical   {{ background: {C_BORDER}; height: 1px; }}
/* ── Status Bar ── */
QStatusBar {{
    background: {C_PANEL};
    border-top: 1px solid {C_BORDER};
    color: {C_TEXT2};
    font-size: 11px;
    padding: 4px 10px;
}}
QStatusBar::item {{ border: none; }}
"""

# ── Helpers de estilo ───────────────────────────────────────────────────────────
def btn_style(bg, hover, text="#ffffff"):
    return (f"QPushButton {{ background:{bg}; color:{text}; border:none; "
            f"border-radius:8px; padding:12px 20px; font-weight:700; font-size:13px; }}"
            f"QPushButton:hover {{ background:{hover}; }}"
            f"QPushButton:pressed {{ background:{bg}; opacity:0.8; }}")

def btn_outline(color):
    return (f"QPushButton {{ background:transparent; color:{color}; "
            f"border:1px solid {color}; border-radius:8px; padding:8px 14px; "
            f"font-weight:600; font-size:12px; }}"
            f"QPushButton:hover {{ background:rgba(0,0,0,0.15); }}")

def sep_label(texto):
    lbl = QLabel(texto.upper())
    lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:10px; font-weight:700; "
                      f"padding:10px 0 4px 0; letter-spacing:1px;")
    return lbl

def criar_separador():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color:{C_BORDER}; background:{C_BORDER}; max-height:1px;")
    return line


# ── Funções biomecânicas ────────────────────────────────────────────────────────
THRESHOLD_VISIBILIDADE = 0.5
JANELA_SUAVIZACAO = 5

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


# ── Motor de bastidores ─────────────────────────────────────────────────────────
class MotorBiomecanico(QThread):
    sinal_frames_prontos = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, str, dict)

    def __init__(self):
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

        self.kinect_ativo = False
        self.webcam_ativa = False
        self.webcam = cv2.VideoCapture(0)
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

    def _resolucao_captura(self):
        if self.kinect_ativo: return (640, 480)
        if self.webcam_ativa:
            w = int(self.webcam.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.webcam.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (w if w > 0 else 640, h if h > 0 else 480)
        return (640, 480)

    def iniciar_gravacao(self, nome_paciente=""):
        pasta = os.path.join(_base_dir(), "Analises_Salvas")
        if not os.path.exists(pasta): os.makedirs(pasta)
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"Analise_{re.sub(r'[^a-zA-Z0-9]','_',nome_paciente.strip())}_{data_hora}" if nome_paciente.strip() else f"Analise_{data_hora}"

        self.arquivo_csv = open(os.path.join(pasta, base + ".csv"), 'w', newline='', encoding='utf-8')
        self.escritor_csv = csv.writer(self.arquivo_csv, delimiter=';')
        self.escritor_csv.writerow([
            'Tempo_Segundos',
            'Ombro_Esq','Ombro_Dir','Cotovelo_Esq','Cotovelo_Dir',
            'Punho_Esq','Punho_Dir','Quadril_Esq','Quadril_Dir',
            'Joelho_Esq','Joelho_Dir','Tornozelo_Esq','Tornozelo_Dir',
            'Inclinacao_Cabeca'
        ])
        larg, alt = self._resolucao_captura()
        self.video_writer = cv2.VideoWriter(
            os.path.join(pasta, base + ".avi"),
            cv2.VideoWriter_fourcc(*'XVID'), 25.0, (larg, alt))
        self.tempo_inicio_gravacao = time.time()
        self.gravando = True

    def parar_gravacao(self):
        self.gravando = False
        if self.arquivo_csv: self.arquivo_csv.close(); self.arquivo_csv = None
        if self.video_writer: self.video_writer.release(); self.video_writer = None

    def _inclinacao_cabeca(self, fl, w, h):
        e, d = fl.landmark[33], fl.landmark[263]
        return round(math.degrees(math.atan2((d.y - e.y) * h, (d.x - e.x) * w)), 1)

    def processar_e_desenhar(self, img_bgr, img_ir_color, img_depth):
        h, w = img_bgr.shape[:2]
        results = self.holistic.process(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        ang = {k: 0.0 for k in self.MAPA_ARTICULACOES}
        ang['inclinacao_cabeca'] = 0.0

        tem = (results.face_landmarks or results.pose_landmarks
               or results.left_hand_landmarks or results.right_hand_landmarks)
        if not tem:
            return img_bgr, img_ir_color, ang

        # Rosto por regiões
        if self.desenhar_rosto and results.face_landmarks:
            fl = results.face_landmarks
            draw = self.mp_drawing.draw_landmarks
            DS = self.mp_drawing.DrawingSpec
            draw(img_bgr, fl, self.mp_face_mesh.FACEMESH_FACE_OVAL,  None, DS(color=(0,212,170),  thickness=1))
            draw(img_bgr, fl, self.mp_face_mesh.FACEMESH_LEFT_EYE,   None, DS(color=(88,166,255),  thickness=1))
            draw(img_bgr, fl, self.mp_face_mesh.FACEMESH_RIGHT_EYE,  None, DS(color=(88,166,255),  thickness=1))
            draw(img_bgr, fl, self.mp_face_mesh.FACEMESH_LIPS,       None, DS(color=(188,140,255), thickness=1))
            inc = self._inclinacao_cabeca(fl, w, h)
            ang['inclinacao_cabeca'] = inc
            cor_inc = (0,212,170) if abs(inc)<10 else (0,165,255) if abs(inc)<20 else (80,80,245)
            cv2.putText(img_bgr, f"Cab: {inc:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, cor_inc, 2)

        # Mãos
        if self.desenhar_maos:
            draw = self.mp_drawing.draw_landmarks
            DS = self.mp_drawing.DrawingSpec
            if results.left_hand_landmarks:
                draw(img_bgr, results.left_hand_landmarks, self.mp_holistic.HAND_CONNECTIONS,
                     DS(color=(121,22,76),  thickness=2, circle_radius=3),
                     DS(color=(121,44,250), thickness=2))
            if results.right_hand_landmarks:
                draw(img_bgr, results.right_hand_landmarks, self.mp_holistic.HAND_CONNECTIONS,
                     DS(color=(245,117,66), thickness=2, circle_radius=3),
                     DS(color=(245,66,230), thickness=2))

        # Pose e ângulos
        if results.pose_landmarks:
            DS = self.mp_drawing.DrawingSpec
            self.mp_drawing.draw_landmarks(
                img_bgr, results.pose_landmarks, self.mp_holistic.POSE_CONNECTIONS,
                DS(color=(80,110,10), thickness=2, circle_radius=3),
                DS(color=(80,256,121), thickness=2))
            if img_ir_color is not None:
                self.mp_drawing.draw_landmarks(img_ir_color, results.pose_landmarks, self.mp_holistic.POSE_CONNECTIONS)

            lms = results.pose_landmarks.landmark
            for nome in self.articulacoes_ativas:
                if nome not in self.MAPA_ARTICULACOES: continue
                eA, eB, eC = self.MAPA_ARTICULACOES[nome]
                iA, iB, iC = eA.value, eB.value, eC.value
                if min(lms[iA].visibility, lms[iB].visibility, lms[iC].visibility) < THRESHOLD_VISIBILIDADE:
                    continue
                if img_depth is not None:
                    angulo = calcular_angulo_3d(
                        extrair_coordenada_3d(lms[iA], w, h, img_depth),
                        extrair_coordenada_3d(lms[iB], w, h, img_depth),
                        extrair_coordenada_3d(lms[iC], w, h, img_depth))
                else:
                    angulo = calcular_angulo_2d(lms[iA], lms[iB], lms[iC], w, h)

                if angulo > 0:
                    self.suavizador[nome].append(angulo)
                    suave = sum(self.suavizador[nome]) / len(self.suavizador[nome])
                    cx_pt = int(lms[iB].x * w); cy_pt = int(lms[iB].y * h)
                    cor = (0,255,0) if suave > 90 else (0,200,255) if suave > 45 else (0,0,255)
                    cv2.putText(img_bgr, f"{int(suave)}", (cx_pt+15, cy_pt),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
                    if img_ir_color is not None:
                        cv2.putText(img_ir_color, f"{int(suave)}", (cx_pt+15, cy_pt),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
                    ang[nome] = round(suave, 1)

        return img_bgr, img_ir_color, ang

    def run(self):
        while self.rodando:
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

            if self.gravando and self.escritor_csv and frame_rgb is not None:
                t = round(time.time() - self.tempo_inicio_gravacao, 2)
                seg = int(t); mm = seg // 60; ss = seg % 60
                texto_crono = f"⏺  {mm:02d}:{ss:02d}"
                linha = [t]
                for key in ['ombro_esquerdo','ombro_direito','cotovelo_esquerdo','cotovelo_direito',
                            'punho_esquerdo','punho_direito','quadril_esquerdo','quadril_direito',
                            'joelho_esquerdo','joelho_direito','tornozelo_esquerdo','tornozelo_direito',
                            'inclinacao_cabeca']:
                    v = ang.get(key, 0.0)
                    linha.append(v if v != 0.0 else '')
                self.escritor_csv.writerow(linha)
                if self.video_writer: self.video_writer.write(frame_rgb)

            if frame_rgb is not None:
                self.sinal_frames_prontos.emit(frame_rgb, frame_3d, frame_ir, texto_crono, ang)

    def stop(self):
        self.rodando = False
        self.parar_gravacao()
        self.wait()
        self.holistic.close()
        if self.kinect_ativo:
            self.depth_stream.stop(); self.color_stream.stop(); openni2.unload()
        if self.webcam_ativa:
            self.webcam.release()


# ── Interface Gráfica ──────────────────────────────────────────────────────────
class JanelaBioMotion(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BioMotion")
        self.resize(1520, 920)
        self.setStyleSheet(ESTILO_GLOBAL)

        # Motor
        self.motor = MotorBiomecanico()

        # Layout raiz: header + conteúdo principal
        raiz = QWidget()
        self.setCentralWidget(raiz)
        layout_raiz = QVBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        layout_raiz.addWidget(self._criar_header())

        # Divisor principal
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout_raiz.addWidget(splitter)

        splitter.addWidget(self._criar_sidebar())
        splitter.addWidget(self._criar_painel_direito())
        splitter.setSizes([310, 1210])
        splitter.setHandleWidth(1)

        # Status bar
        self._criar_status_bar()

        # Timer blink para gravação
        self._blink_estado = True
        self._timer_blink = QTimer(self)
        self._timer_blink.timeout.connect(self._blink_gravacao)

        # Frames para FPS
        self._fps_frames = 0
        self._fps_last = time.time()

        self.motor.sinal_frames_prontos.connect(self.desenhar_telas)
        self.motor.start()

    # ── Header ─────────────────────────────────────────────────────────────────
    def _criar_header(self):
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background:{C_PANEL}; border-bottom:1px solid {C_BORDER};")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0)

        # Logo + título
        logo = QLabel("●")
        logo.setStyleSheet(f"color:{C_TEAL}; font-size:22px; padding-right:4px;")
        titulo = QLabel("BioMotion")
        titulo.setStyleSheet(f"color:{C_TEXT}; font-size:18px; font-weight:700;")
        subtitulo = QLabel("Painel Clínico de Biomecânica")
        subtitulo.setStyleSheet(f"color:{C_TEXT2}; font-size:11px; padding-left:10px;")

        lay.addWidget(logo)
        lay.addWidget(titulo)
        lay.addWidget(subtitulo)
        lay.addStretch()

        # Indicadores de sensor
        lay.addWidget(self._indicador_sensor("Kinect",  self.motor.kinect_ativo))
        lay.addSpacing(16)
        lay.addWidget(self._indicador_sensor("Webcam",  self.motor.webcam_ativa))
        lay.addSpacing(24)

        versao = QLabel("v2.1")
        versao.setStyleSheet(f"color:{C_TEXT2}; font-size:11px;")
        lay.addWidget(versao)

        return header

    def _indicador_sensor(self, nome, ativo):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        w.setStyleSheet(f"background:rgba(255,255,255,0.04); border:1px solid {C_BORDER}; border-radius:20px;")

        led = QLabel("●")
        led.setStyleSheet(f"color:{C_GREEN if ativo else C_RED}; font-size:10px; background:transparent; border:none;")
        lbl = QLabel(nome)
        lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:11px; background:transparent; border:none;")
        lay.addWidget(led); lay.addWidget(lbl)
        return w

    # ── Sidebar ─────────────────────────────────────────────────────────────────
    def _criar_sidebar(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(310)
        scroll.setStyleSheet(f"background:{C_BG};")

        sidebar = QWidget()
        sidebar.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(12, 12, 12, 16)
        lay.setSpacing(10)

        lay.addWidget(self._grupo_sessao())
        lay.addWidget(self._grupo_visualizacao())
        lay.addWidget(self._grupo_articulacoes())
        lay.addWidget(self._grupo_3d())
        lay.addStretch()

        scroll.setWidget(sidebar)
        return scroll

    # ── Grupo: Sessão ───────────────────────────────────────────────────────────
    def _grupo_sessao(self):
        grp = QGroupBox("Controle de Sessão")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Nome do Paciente")
        lay.addWidget(self.input_nome)

        self.btn_gravar = QPushButton("⏺  INICIAR GRAVAÇÃO")
        self.btn_gravar.setCheckable(True)
        self.btn_gravar.setStyleSheet(btn_style(C_GREEN, "#2ea043"))
        self.btn_gravar.setFixedHeight(48)
        self.btn_gravar.clicked.connect(self.alternar_gravacao)
        lay.addWidget(self.btn_gravar)

        self.lbl_cronometro = QLabel("")
        self.lbl_cronometro.setAlignment(Qt.AlignCenter)
        self.lbl_cronometro.setFixedHeight(28)
        self.lbl_cronometro.setStyleSheet(
            f"color:{C_RED}; font-weight:700; font-size:16px; "
            f"background:rgba(248,81,73,0.08); border-radius:6px; padding:2px;")
        lay.addWidget(self.lbl_cronometro)

        return grp

    # ── Grupo: Visualização ─────────────────────────────────────────────────────
    def _grupo_visualizacao(self):
        grp = QGroupBox("Visualização")
        lay = QVBoxLayout(grp)
        lay.setSpacing(2)

        lay.addWidget(sep_label("Câmeras"))
        self.chk_view_rgb     = QCheckBox("Câmera RGB");               self.chk_view_rgb.setChecked(True)
        self.chk_view_3d      = QCheckBox("Reconstrução 3D");          self.chk_view_3d.setChecked(True)
        self.chk_view_ir      = QCheckBox("Sensor IR / Profundidade"); self.chk_view_ir.setChecked(True)
        self.chk_view_grafico = QCheckBox("Gráfico em Tempo Real");    self.chk_view_grafico.setChecked(True)

        lay.addWidget(self.chk_view_rgb)
        lay.addWidget(self.chk_view_3d)
        lay.addWidget(self.chk_view_ir)
        lay.addWidget(self.chk_view_grafico)

        lay.addWidget(criar_separador())
        lay.addWidget(sep_label("Malhas de IA"))

        self.chk_view_rosto = QCheckBox("Malha Facial (Face Mesh)"); self.chk_view_rosto.setChecked(True)
        self.chk_view_maos  = QCheckBox("Rastreio de Mãos");         self.chk_view_maos.setChecked(True)

        lay.addWidget(self.chk_view_rosto)
        lay.addWidget(self.chk_view_maos)

        self.chk_view_rosto.stateChanged.connect(self.atualizar_visualizacao_ia)
        self.chk_view_maos.stateChanged.connect(self.atualizar_visualizacao_ia)

        return grp

    # ── Grupo: Articulações ─────────────────────────────────────────────────────
    def _grupo_articulacoes(self):
        grp = QGroupBox("Análise Articular")
        lay = QVBoxLayout(grp)
        lay.setSpacing(6)

        # Card inclinação cabeça
        card_face = QWidget()
        card_face.setStyleSheet(f"background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;")
        card_lay = QHBoxLayout(card_face)
        card_lay.setContentsMargins(12, 8, 12, 8)
        ic_lbl = QLabel("↕")
        ic_lbl.setStyleSheet(f"color:{C_PURPLE}; font-size:18px; font-weight:700; border:none; background:transparent;")
        card_lay.addWidget(ic_lbl)
        txt_lbl = QLabel("Inclinação da Cabeça")
        txt_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:12px; border:none; background:transparent;")
        card_lay.addWidget(txt_lbl)
        card_lay.addStretch()
        self.lbl_inclinacao = QLabel("--°")
        self.lbl_inclinacao.setStyleSheet(f"color:{C_TEAL}; font-weight:700; font-size:14px; border:none; background:transparent;")
        card_lay.addWidget(self.lbl_inclinacao)
        lay.addWidget(card_face)

        # Grid de articulações 2 colunas
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 4, 0, 0)

        _GRUPOS = [
            ("Membro Superior", C_BLUE, [
                ("Ombro Esq",     "ombro_esquerdo"),
                ("Ombro Dir",     "ombro_direito"),
                ("Cotovelo Esq",  "cotovelo_esquerdo"),
                ("Cotovelo Dir",  "cotovelo_direito"),
                ("Punho Esq",     "punho_esquerdo"),
                ("Punho Dir",     "punho_direito"),
            ]),
            ("Membro Inferior", C_GREEN, [
                ("Quadril Esq",   "quadril_esquerdo"),
                ("Quadril Dir",   "quadril_direito"),
                ("Joelho Esq",    "joelho_esquerdo"),
                ("Joelho Dir",    "joelho_direito"),
                ("Tornozelo Esq", "tornozelo_esquerdo"),
                ("Tornozelo Dir", "tornozelo_direito"),
            ]),
        ]

        self._chk_map = {}
        row = 0
        for nome_grupo, cor_grupo, articulacoes in _GRUPOS:
            sep_w = QWidget()
            sep_w.setStyleSheet("background:transparent;")
            sep_h = QHBoxLayout(sep_w)
            sep_h.setContentsMargins(0, 4, 0, 0); sep_h.setSpacing(6)
            dot = QLabel("■")
            dot.setStyleSheet(f"color:{cor_grupo}; font-size:8px; background:transparent;")
            lbl_g = QLabel(nome_grupo.upper())
            lbl_g.setStyleSheet(f"color:{C_TEXT2}; font-size:10px; font-weight:700; background:transparent;")
            sep_h.addWidget(dot); sep_h.addWidget(lbl_g); sep_h.addStretch()
            grid.addWidget(sep_w, row, 0, 1, 2)
            row += 1

            for i in range(0, len(articulacoes), 2):
                for col, (label, key) in enumerate(articulacoes[i:i+2]):
                    chk = QCheckBox(label)
                    chk.stateChanged.connect(self.atualizar_motor)
                    self._chk_map[key] = chk
                    grid.addWidget(chk, row, col)
                row += 1

        lay.addLayout(grid)

        # Botão selecionar/desmarcar todos
        lay_btns = QHBoxLayout()
        btn_todos = QPushButton("Selecionar Todos")
        btn_todos.setStyleSheet(btn_outline(C_TEAL))
        btn_todos.clicked.connect(lambda: self._selecionar_todos(True))
        btn_nenhum = QPushButton("Limpar")
        btn_nenhum.setStyleSheet(btn_outline(C_TEXT2))
        btn_nenhum.clicked.connect(lambda: self._selecionar_todos(False))
        lay_btns.addWidget(btn_todos); lay_btns.addWidget(btn_nenhum)
        lay.addLayout(lay_btns)

        return grp

    def _selecionar_todos(self, estado):
        for chk in self._chk_map.values():
            chk.setChecked(estado)

    # ── Grupo: Controle 3D ──────────────────────────────────────────────────────
    def _grupo_3d(self):
        grp = QGroupBox("Controle Espacial 3D")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)

        def slider_row(label, attr):
            row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
            row_l = QHBoxLayout(row_w); row_l.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:12px; min-width:100px; background:transparent;")
            val_lbl = QLabel("0°")
            val_lbl.setStyleSheet(f"color:{C_TEAL}; font-weight:700; font-size:12px; min-width:32px; background:transparent;")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_l.addWidget(lbl); row_l.addWidget(val_lbl)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(-100, 100)
            sl.valueChanged.connect(self.atualizar_rotacao)
            sl.valueChanged.connect(lambda v, l=val_lbl: l.setText(f"{int(v*1.8)}°"))
            lay.addWidget(row_w); lay.addWidget(sl)
            setattr(self, attr, sl)

        slider_row("Giro Horizontal (Y)", "slider_y")
        slider_row("Inclinação Vertical (X)", "slider_x")
        slider_row("Tombo Lateral (Z)", "slider_z")

        self.btn_reset_3d = QPushButton("↺  Resetar Visão 3D")
        self.btn_reset_3d.setStyleSheet(btn_outline(C_TEXT2))
        self.btn_reset_3d.clicked.connect(self.resetar_rotacao)
        lay.addWidget(self.btn_reset_3d)

        return grp

    # ── Painel Direito ──────────────────────────────────────────────────────────
    def _criar_painel_direito(self):
        painel = QWidget()
        painel.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(painel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        splitter_v = QSplitter(Qt.Vertical)
        splitter_v.setChildrenCollapsible(False)
        splitter_v.setHandleWidth(1)

        # ── Vídeos ──────────────────────────────────────────────────────────────
        splitter_vids = QSplitter(Qt.Horizontal)
        splitter_vids.setHandleWidth(1)
        self.splitter_videos = splitter_vids

        def criar_tela(titulo, subtitulo, cor_dot):
            container = QWidget()
            container.setStyleSheet(f"background:#0a0e13; border:none;")
            cl = QVBoxLayout(container)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            # Barra do topo
            barra = QWidget()
            barra.setFixedHeight(30)
            barra.setStyleSheet(f"background:{C_PANEL}; border-bottom:1px solid {C_BORDER};")
            bl = QHBoxLayout(barra)
            bl.setContentsMargins(10, 0, 10, 0)
            dot_lbl = QLabel("●")
            dot_lbl.setStyleSheet(f"color:{cor_dot}; font-size:10px; background:transparent;")
            t_lbl = QLabel(titulo)
            t_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:11px; font-weight:600; background:transparent;")
            st_lbl = QLabel(subtitulo)
            st_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:10px; background:transparent;")
            bl.addWidget(dot_lbl); bl.addWidget(t_lbl); bl.addSpacing(6); bl.addWidget(st_lbl); bl.addStretch()
            cl.addWidget(barra)

            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background:#0a0e13; border:none;")
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            cl.addWidget(lbl)
            return container, lbl

        c_rgb, self.tela_rgb = criar_tela("RGB",          "Câmera Principal", C_GREEN)
        c_3d,  self.tela_3d  = criar_tela("3D",           "Nuvem de Pontos",  C_BLUE)
        c_ir,  self.tela_ir  = criar_tela("IR / Depth",   "Sensor Kinect",    C_AMBER)

        splitter_vids.addWidget(c_rgb)
        splitter_vids.addWidget(c_3d)
        splitter_vids.addWidget(c_ir)

        # ── Gráfico ─────────────────────────────────────────────────────────────
        pg.setConfigOptions(antialias=True, background=C_BG)
        self.grafico = pg.PlotWidget()
        self.grafico.setLabel('left',   'Ângulo (°)', color=C_TEXT2)
        self.grafico.setLabel('bottom', 'Frames',     color=C_TEXT2)
        self.grafico.showGrid(x=True, y=True, alpha=0.15)
        self.grafico.setYRange(0, 190)
        self.grafico.getAxis('left').setPen(pg.mkPen(C_BORDER))
        self.grafico.getAxis('bottom').setPen(pg.mkPen(C_BORDER))
        self.grafico.getAxis('left').setTextPen(pg.mkPen(C_TEXT2))
        self.grafico.getAxis('bottom').setTextPen(pg.mkPen(C_TEXT2))
        self.grafico.addLegend(offset=(10, 10), brush=pg.mkBrush(C_PANEL + "cc"))
        self.grafico.setTitle("Cinemática Articular — Ângulos em Tempo Real",
                              color=C_TEXT2, size="12pt")
        self.grafico.setStyleSheet(f"background:{C_BG}; border-top:1px solid {C_BORDER};")

        splitter_v.addWidget(splitter_vids)
        splitter_v.addWidget(self.grafico)
        splitter_v.setSizes([580, 240])

        lay.addWidget(splitter_v)

        # Buffers do gráfico
        self.buffer_size = 150
        self.eixo_x_tempo = deque(maxlen=self.buffer_size)
        _keys = list(self.motor.MAPA_ARTICULACOES.keys())
        self.eixo_y_dados = {k: deque(maxlen=self.buffer_size) for k in _keys}
        self.frame_count = 0

        _CORES_PLOT = {
            'ombro_esquerdo':     ('#FF6B35', Qt.SolidLine,   'Ombro Esq'),
            'ombro_direito':      ('#4ECDC4', Qt.SolidLine,   'Ombro Dir'),
            'cotovelo_esquerdo':  ('#f85149', Qt.SolidLine,   'Cotovelo Esq'),
            'cotovelo_direito':   ('#3fb950', Qt.SolidLine,   'Cotovelo Dir'),
            'punho_esquerdo':     ('#d29922', Qt.DashLine,    'Punho Esq'),
            'punho_direito':      ('#e6edf3', Qt.DashLine,    'Punho Dir'),
            'quadril_esquerdo':   ('#bc8cff', Qt.DotLine,     'Quadril Esq'),
            'quadril_direito':    ('#A8E6CF', Qt.DotLine,     'Quadril Dir'),
            'joelho_esquerdo':    ('#58a6ff', Qt.SolidLine,   'Joelho Esq'),
            'joelho_direito':     ('#00d4aa', Qt.SolidLine,   'Joelho Dir'),
            'tornozelo_esquerdo': ('#FF8B94', Qt.DashDotLine, 'Tornozelo Esq'),
            'tornozelo_direito':  ('#B4A7D6', Qt.DashDotLine, 'Tornozelo Dir'),
        }
        self.curvas_plot = {
            k: self.grafico.plot(pen=pg.mkPen(c, width=2, style=s), name=n)
            for k, (c, s, n) in _CORES_PLOT.items()
        }

        # Conecta visibilidade câmeras
        self.chk_view_rgb.toggled.connect(c_rgb.setVisible)
        self.chk_view_3d.toggled.connect(c_3d.setVisible)
        self.chk_view_ir.toggled.connect(c_ir.setVisible)
        self.chk_view_grafico.toggled.connect(self.grafico.setVisible)

        return painel

    # ── Status bar ──────────────────────────────────────────────────────────────
    def _criar_status_bar(self):
        sb = self.statusBar()
        sb.showMessage("  Sistema iniciado  ·  Aguardando sessão")
        sensor_txt = "Kinect: " + ("Conectado" if self.motor.kinect_ativo else "Não detectado") + \
                     "   Webcam: " + ("Ativa" if self.motor.webcam_ativa else "Não detectada")
        lbl_sensor = QLabel(sensor_txt + "   ")
        lbl_sensor.setStyleSheet(f"color:{C_TEXT2}; font-size:11px;")
        self.lbl_fps = QLabel("FPS: --   ")
        self.lbl_fps.setStyleSheet(f"color:{C_TEXT2}; font-size:11px;")
        sb.addPermanentWidget(lbl_sensor)
        sb.addPermanentWidget(self.lbl_fps)

    # ── Slots ───────────────────────────────────────────────────────────────────
    def atualizar_visualizacao_ia(self):
        self.motor.desenhar_rosto = self.chk_view_rosto.isChecked()
        self.motor.desenhar_maos  = self.chk_view_maos.isChecked()

    def alternar_gravacao(self, checked):
        if checked:
            self.input_nome.setEnabled(False)
            self.btn_gravar.setStyleSheet(btn_style(C_RED, "#da3633"))
            self.btn_gravar.setText("⏹  PARAR GRAVAÇÃO")
            self.motor.iniciar_gravacao(self.input_nome.text())
            self.eixo_x_tempo.clear()
            for k in self.eixo_y_dados: self.eixo_y_dados[k].clear()
            self._timer_blink.start(800)
            self.statusBar().showMessage("  ⏺  Gravação em andamento — CSV + AVI salvando em /Analises_Salvas")
        else:
            self._timer_blink.stop()
            self.lbl_cronometro.setVisible(True)
            self.input_nome.setEnabled(True)
            self.btn_gravar.setStyleSheet(btn_style(C_GREEN, "#2ea043"))
            self.btn_gravar.setText("⏺  INICIAR GRAVAÇÃO")
            self.motor.parar_gravacao()
            self.lbl_cronometro.setText("✔  Sessão salva")
            self.lbl_cronometro.setStyleSheet(
                f"color:{C_GREEN}; font-weight:700; font-size:14px; "
                f"background:rgba(63,185,80,0.1); border-radius:6px; padding:2px;")
            self.statusBar().showMessage("  Sessão finalizada e salva em /Analises_Salvas")

    def _blink_gravacao(self):
        self.lbl_cronometro.setVisible(self._blink_estado)
        self._blink_estado = not self._blink_estado

    def atualizar_motor(self):
        self.motor.articulacoes_ativas = [k for k, chk in self._chk_map.items() if chk.isChecked()]

    def atualizar_rotacao(self):
        self.motor.angulo_rotacao_x = (self.slider_x.value() / 100.0) * math.pi
        self.motor.angulo_rotacao_y = (self.slider_y.value() / 100.0) * math.pi
        self.motor.angulo_rotacao_z = (self.slider_z.value() / 100.0) * math.pi

    def resetar_rotacao(self):
        self.slider_x.setValue(0); self.slider_y.setValue(0); self.slider_z.setValue(0)

    def desenhar_telas(self, f_rgb, f_3d, f_ir, texto_crono, ang_dict):
        if texto_crono:
            self.lbl_cronometro.setText(texto_crono)
            self.lbl_cronometro.setStyleSheet(
                f"color:{C_RED}; font-weight:700; font-size:16px; "
                f"background:rgba(248,81,73,0.08); border-radius:6px; padding:2px;")

        inc = ang_dict.get('inclinacao_cabeca', 0.0)
        if inc != 0.0:
            self.lbl_inclinacao.setText(f"{inc:.1f}°")
            cor_inc = C_TEAL if abs(inc) < 10 else C_AMBER if abs(inc) < 20 else C_RED
            self.lbl_inclinacao.setStyleSheet(
                f"color:{cor_inc}; font-weight:700; font-size:14px; border:none; background:transparent;")

        def atualizar(label, frame):
            if not label.isVisible(): return
            f = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = f.shape
            img_qt = QImage(f.data, w, h, ch * w, QImage.Format_RGB888)
            label.setPixmap(QPixmap.fromImage(img_qt).scaled(
                label.width(), label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        atualizar(self.tela_rgb, f_rgb)
        atualizar(self.tela_3d,  f_3d)
        atualizar(self.tela_ir,  f_ir)

        # FPS
        self._fps_frames += 1
        agora = time.time()
        if agora - self._fps_last >= 1.0:
            self.lbl_fps.setText(f"FPS: {self._fps_frames}   ")
            self._fps_frames = 0
            self._fps_last = agora

        if self.grafico.isVisible():
            self.frame_count += 1
            self.eixo_x_tempo.append(self.frame_count)
            for art, dados in self.eixo_y_dados.items():
                val = ang_dict.get(art, 0.0)
                dados.append(val if val > 0 else (dados[-1] if dados else 0))
                ativo = art in self.motor.articulacoes_ativas
                self.curvas_plot[art].setData(list(self.eixo_x_tempo), list(dados)) if ativo else None
                self.curvas_plot[art].setVisible(ativo)

    def closeEvent(self, event):
        self.motor.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    janela = JanelaBioMotion()
    janela.show()
    sys.exit(app.exec_())
