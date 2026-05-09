import numpy as np
import cv2
import mediapipe as mp
import math
from openni import openni2

# --- 1. FUNÇÕES MATEMÁTICAS ---
# (Mantenha as funções extrair_coordenada_3d e calcular_angulo_3d exatamente iguais ao código anterior)
# ... [Suas funções aqui] ...

def extrair_coordenada_3d(landmark, w, h, depth_img):
    px = int(landmark.x * w)
    py = int(landmark.y * h)
    if px < 0 or px >= w or py < 0 or py >= h: return None
    z_mm = depth_img[py, px]
    if z_mm == 0: return None
    fx, fy = 594.21, 591.04
    cx, cy = 320.0, 240.0
    x_mm = (px - cx) * z_mm / fx
    y_mm = (py - cy) * z_mm / fy
    return [x_mm, y_mm, z_mm]

def calcular_angulo_3d(ponto_a, ponto_b, ponto_c):
    if ponto_a is None or ponto_b is None or ponto_c is None: return 0.0
    a, b, c = np.array(ponto_a), np.array(ponto_b), np.array(ponto_c)
    vetor_ba = a - b
    vetor_bc = c - b
    tamanho_ba = np.linalg.norm(vetor_ba)
    tamanho_bc = np.linalg.norm(vetor_bc)
    if tamanho_ba == 0 or tamanho_bc == 0: return 0.0
    produto_escalar = np.dot(vetor_ba, vetor_bc)
    cosseno_angulo = np.clip(produto_escalar / (tamanho_ba * tamanho_bc), -1.0, 1.0)
    return math.degrees(math.acos(cosseno_angulo))


# --- 2. CONFIGURAÇÃO DA INTERFACE (O "Cérebro" das Escolhas) ---

mp_pose = mp.solutions.pose # Referência rápida para facilitar a digitação

# Criamos um Dicionário. Ele funciona no esquema "Chave": "Valor".
# A Chave é o nome amigável da articulação. 
# O Valor é uma tupla (lista fixa) com os 3 pontos necessários: (Ponto A, Vértice B, Ponto C)
MAPA_ARTICULACOES = {
    'cotovelo_esquerdo': (mp_pose.PoseLandmark.LEFT_SHOULDER,  mp_pose.PoseLandmark.LEFT_ELBOW,  mp_pose.PoseLandmark.LEFT_WRIST),
    'cotovelo_direito':  (mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_WRIST),
    'joelho_esquerdo':   (mp_pose.PoseLandmark.LEFT_HIP,       mp_pose.PoseLandmark.LEFT_KNEE,   mp_pose.PoseLandmark.LEFT_ANKLE),
    'joelho_direito':    (mp_pose.PoseLandmark.RIGHT_HIP,      mp_pose.PoseLandmark.RIGHT_KNEE,  mp_pose.PoseLandmark.RIGHT_ANKLE),
    'quadril_esquerdo':  (mp_pose.PoseLandmark.LEFT_SHOULDER,  mp_pose.PoseLandmark.LEFT_HIP,    mp_pose.PoseLandmark.LEFT_KNEE),
    'quadril_direito':   (mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_HIP,   mp_pose.PoseLandmark.RIGHT_KNEE)
}

# Aqui simulamos os botões da sua futura interface!
# Tudo o que você escrever nesta lista, o programa vai calcular e desenhar na tela.
# Se quiser remover algo, basta apagar o nome da lista.
articulacoes_ativas = ['cotovelo_esquerdo', 'cotovelo_direito', 'joelho_direito']


# --- 3. INICIALIZAÇÃO DO SISTEMA ---
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

openni2.initialize(r"C:\Program Files\OpenNI2\Redist")
try: dev = openni2.Device.open_any()
except Exception as e: print(f"Erro: {e}"); exit()

depth_stream = dev.create_depth_stream()
color_stream = dev.create_color_stream()

try: dev.set_image_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)
except: pass

depth_stream.start()
color_stream.start()


# --- 4. LOOP PRINCIPAL ---
while True:
    # Leitura do Kinect (sem alterações, apenas compactado para leitura)
    color_frame = color_stream.read_frame()
    img_bgr = cv2.cvtColor(np.frombuffer(color_frame.get_buffer_as_uint8(), dtype=np.uint8).reshape(480, 640, 3), cv2.COLOR_RGB2BGR)
    
    depth_frame = depth_stream.read_frame()
    img_depth = np.frombuffer(depth_frame.get_buffer_as_uint16(), dtype=np.uint16).reshape(480, 640)
    
    depth_display = cv2.convertScaleAbs(img_depth, alpha=(255.0/4500.0))
    img_depth_color = cv2.applyColorMap(depth_display, cv2.COLORMAP_JET)

    # --- ESPELHAMENTO DE IMAGEM (Efeito Espelho) ---
    # Ao invés de o paciente se ver invertido, o eixo 1 vira a imagem horizontalmente.
    img_bgr = cv2.flip(img_bgr, 1)
    img_depth = cv2.flip(img_depth, 1) 
    img_depth_color = cv2.flip(img_depth_color, 1)

    # Inteligência Artificial
    img_bgr.flags.writeable = False
    # Como espelhamos a imagem BGR, temos que convertê-la temporariamente de volta para RGB para o MediaPipe ler direito
    results = pose.process(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    img_bgr.flags.writeable = True

    if results.pose_landmarks:
        # Desenha as linhas base nas duas janelas
        mp_drawing.draw_landmarks(img_bgr, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        mp_drawing.draw_landmarks(img_depth_color, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        lms = results.pose_landmarks.landmark
        h, w = img_depth.shape

        # --- O NOVO MOTOR DE PROCESSAMENTO DE ÂNGULOS ---
        # Este laço 'for' vai olhar APENAS para os nomes que você colocou na lista 'articulacoes_ativas'
        for nome_art in articulacoes_ativas:
            
            # 1. Pega no Dicionário os 3 pontos necessários (ex: ombro, cotovelo, pulso)
            pt_A_idx, pt_B_idx, pt_C_idx = MAPA_ARTICULACOES[nome_art]
            
            # 2. Pega as coordenadas 2D (da tela) que o MediaPipe gerou para esses 3 pontos
            landmark_A = lms[pt_A_idx.value]
            landmark_B = lms[pt_B_idx.value] # Este é sempre o vértice do ângulo
            landmark_C = lms[pt_C_idx.value]

            # 3. Converte os 3 pontos para coordenadas 3D reais (Milímetros) usando nossa função
            pos_A_3d = extrair_coordenada_3d(landmark_A, w, h, img_depth)
            pos_B_3d = extrair_coordenada_3d(landmark_B, w, h, img_depth)
            pos_C_3d = extrair_coordenada_3d(landmark_C, w, h, img_depth)

            # 4. Calcula o ângulo!
            angulo = calcular_angulo_3d(pos_A_3d, pos_B_3d, pos_C_3d)

            if angulo > 0:
                # Calcula onde desenhar o texto (exatamente em cima do vértice/ponto B)
                cx, cy = int(landmark_B.x * w), int(landmark_B.y * h)
                texto = f"{int(angulo)} graus"
                
                # Escreve o resultado nas duas imagens
                cv2.putText(img_bgr, texto, (cx + 15, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(img_depth_color, texto, (cx + 15, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("BioMotion - RGB Espelhado", img_bgr)
    cv2.imshow("BioMotion - Mapa Profundidade 3D", img_depth_color)

    if cv2.waitKey(1) & 0xFF == 27: break

depth_stream.stop(); color_stream.stop(); openni2.unload(); cv2.destroyAllWindows()