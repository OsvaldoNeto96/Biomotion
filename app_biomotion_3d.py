import numpy as np
import cv2
import mediapipe as mp
import math
from openni import openni2

# --- 1. FUNÇÕES BIOMECÂNICAS BASE ---
def extrair_coordenada_3d(landmark, w, h, depth_img):
    px, py = int(landmark.x * w), int(landmark.y * h)
    if px < 0 or px >= w or py < 0 or py >= h: return None
    z_mm = depth_img[py, px]
    if z_mm == 0: return None
    fx, fy, cx, cy = 594.21, 591.04, 320.0, 240.0
    x_mm = (px - cx) * z_mm / fx
    y_mm = (py - cy) * z_mm / fy
    return [x_mm, y_mm, z_mm]

def calcular_angulo_3d(ponto_a, ponto_b, ponto_c):
    if ponto_a is None or ponto_b is None or ponto_c is None: return 0.0
    a, b, c = np.array(ponto_a), np.array(ponto_b), np.array(ponto_c)
    vetor_ba, vetor_bc = a - b, c - b
    tamanho_ba, tamanho_bc = np.linalg.norm(vetor_ba), np.linalg.norm(vetor_bc)
    if tamanho_ba == 0 or tamanho_bc == 0: return 0.0
    cosseno_angulo = np.clip(np.dot(vetor_ba, vetor_bc) / (tamanho_ba * tamanho_bc), -1.0, 1.0)
    return math.degrees(math.acos(cosseno_angulo))

angulo_rotacao_y = 0.0  
def controle_mouse_3d(event, x, y, flags, param):
    global angulo_rotacao_y
    if flags == cv2.EVENT_FLAG_LBUTTON:
        angulo_rotacao_y = ((x - 400) / 400.0) * math.pi

# --- 2. GERENCIADOR DE HARDWARE (LOGICA INFALÍVEL V2) ---
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

MAPA_ARTICULACOES = {
    'cotovelo_esquerdo': (mp_pose.PoseLandmark.LEFT_SHOULDER,  mp_pose.PoseLandmark.LEFT_ELBOW,  mp_pose.PoseLandmark.LEFT_WRIST),
    'cotovelo_direito':  (mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_WRIST)
}
articulacoes_ativas = ['cotovelo_esquerdo', 'cotovelo_direito']

print("--- INICIANDO DIAGNÓSTICO DE HARDWARE ---")

# A. Tentativa de iniciar a Webcam Comum
webcam = cv2.VideoCapture(0)
tem_webcam = webcam.isOpened()
if tem_webcam:
    print("[+] Webcam Comum detectada com sucesso.")
else:
    print("[-] Nenhuma Webcam Comum encontrada.")

# B. Tentativa de iniciar os Kinects
lista_kinects = []
try:
    openni2.initialize(r"C:\Program Files\OpenNI2\Redist")
    
    uris_disponiveis = []
    try:
        uris_disponiveis = openni2.Device.enumerate_uris()
    except Exception as e:
        print(f"[*] Aviso na listagem: {e}")

    if len(uris_disponiveis) > 0:
        print(f"[*] Encontrados {len(uris_disponiveis)} dispositivos OpenNI.")
        for i, uri in enumerate(uris_disponiveis):
            try:
                # Tenta abrir o dispositivo contornando as variações da biblioteca
                try:
                    dev = openni2.Device.open_file(uri)
                except AttributeError:
                    try:
                        dev = openni2.Device(uri)
                    except TypeError:
                        raise Exception("Sintaxe URI não suportada.")
                
                d_stream = dev.create_depth_stream()
                c_stream = dev.create_color_stream()
                try: dev.set_image_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)
                except: pass
                
                d_stream.start()
                c_stream.start()
                
                lista_kinects.append({
                    'id': i + 1, 'device': dev, 'depth_stream': d_stream, 'color_stream': c_stream,
                    'offset_x': i * 2.0, 'offset_z': 0.0
                })
                print(f"[+] Kinect {i+1} conectado via URI.")
            except Exception as e:
                print(f"[-] Falha ao abrir URI: {e}")

    # AQUI ESTÁ A CORREÇÃO: O Fallback de Força Bruta roda SEMPRE que a lista continuar vazia
    if len(lista_kinects) == 0:
        print("[*] Acionando Fallback de Força Bruta (open_any)...")
        try:
            dev = openni2.Device.open_any()
            
            d_stream = dev.create_depth_stream()
            c_stream = dev.create_color_stream()
            try: dev.set_image_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)
            except: pass
            
            d_stream.start()
            c_stream.start()
            
            lista_kinects.append({
                'id': 1, 'device': dev, 'depth_stream': d_stream, 'color_stream': c_stream,
                'offset_x': 0.0, 'offset_z': 0.0
            })
            print("[+] Kinect 1 conectado com sucesso via força bruta!")
        except Exception as e:
            print(f"[-] Conexão de força bruta falhou: {e}")

except Exception as e:
    print(f"[-] Falha estrutural no Motor OpenNI2: {e}")

print("-----------------------------------------")

if not tem_webcam and len(lista_kinects) == 0:
    print("ERRO FATAL: Nenhuma câmara (Kinect ou Webcam) foi detectada. Encerrando.")
    exit()

# --- 3. PREPARAÇÃO DA MATRIZ MATEMÁTICA 3D ---
PASSO = 4
fx, fy, cx, cy = 594.21, 591.04, 320.0, 240.0
u, v = np.meshgrid(np.arange(0, 640, PASSO), np.arange(0, 480, PASSO))
u, v = u.flatten(), v.flatten()
x_grid = (u - cx) / fx
y_grid = (v - cy) / fy

if len(lista_kinects) > 0:
    cv2.namedWindow("BioMotion - Scanner 3D Virtual")
    cv2.setMouseCallback("BioMotion - Scanner 3D Virtual", controle_mouse_3d)

# --- 4. LOOP PRINCIPAL ---
while True:
    
    # BLOCO DA WEBCAM
    if tem_webcam:
        sucesso, frame_webcam = webcam.read()
        if sucesso and frame_webcam is not None:
            frame_webcam = cv2.flip(frame_webcam, 1)
            frame_rgb = cv2.cvtColor(frame_webcam, cv2.COLOR_BGR2RGB)
            frame_rgb.flags.writeable = False
            results_webcam = pose.process(frame_rgb)
            frame_rgb.flags.writeable = True

            if results_webcam.pose_landmarks:
                mp_drawing.draw_landmarks(frame_webcam, results_webcam.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
            cv2.imshow("BioMotion - Webcam Apoio", frame_webcam)

    # BLOCO DOS KINECTS
    pontos_3d_acumulados = []
    cores_acumuladas = []

    for kinect_info in lista_kinects:
        k_id = kinect_info['id']
        c_stream = kinect_info['color_stream']
        d_stream = kinect_info['depth_stream']
        offset_x = kinect_info['offset_x']

        color_frame = c_stream.read_frame()
        img_rgb = np.frombuffer(color_frame.get_buffer_as_uint8(), dtype=np.uint8).reshape(480, 640, 3)
        depth_frame = d_stream.read_frame()
        img_depth = np.frombuffer(depth_frame.get_buffer_as_uint16(), dtype=np.uint16).reshape(480, 640)

        img_bgr_espelhada = cv2.flip(cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB), 1)
        img_depth_espelhada = cv2.flip(img_depth, 1)

        img_bgr_espelhada.flags.writeable = False
        results_k = pose.process(cv2.cvtColor(img_bgr_espelhada, cv2.COLOR_BGR2RGB))
        img_bgr_espelhada.flags.writeable = True

        if results_k.pose_landmarks:
            mp_drawing.draw_landmarks(img_bgr_espelhada, results_k.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            lms = results_k.pose_landmarks.landmark
            for nome_art in articulacoes_ativas:
                pt_A_idx, pt_B_idx, pt_C_idx = MAPA_ARTICULACOES[nome_art]
                pos_A = extrair_coordenada_3d(lms[pt_A_idx.value], 640, 480, img_depth_espelhada)
                pos_B = extrair_coordenada_3d(lms[pt_B_idx.value], 640, 480, img_depth_espelhada)
                pos_C = extrair_coordenada_3d(lms[pt_C_idx.value], 640, 480, img_depth_espelhada)

                angulo = calcular_angulo_3d(pos_A, pos_B, pos_C)
                if angulo > 0:
                    cx_p, cy_p = int(lms[pt_B_idx.value].x * 640), int(lms[pt_B_idx.value].y * 480)
                    cv2.putText(img_bgr_espelhada, f"{int(angulo)}", (cx_p + 15, cy_p), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow(f"BioMotion - Kinect {k_id} RGB", img_bgr_espelhada)

        z = img_depth_espelhada[::PASSO, ::PASSO].flatten() / 1000.0
        x = x_grid * z
        y = y_grid * z

        validos = (z > 0.1) & (z < 3.0)
        x_val = x[validos] + offset_x
        y_val = y[validos]
        z_val = z[validos]

        cores = cv2.cvtColor(img_bgr_espelhada, cv2.COLOR_BGR2RGB)[::PASSO, ::PASSO].reshape(-1, 3)[validos]

        pontos_3d_acumulados.append((x_val, y_val, z_val))
        cores_acumuladas.append(cores)

    # BLOCO RENDERIZAÇÃO 3D UNIFICADO
    if len(lista_kinects) > 0 and len(pontos_3d_acumulados) > 0:
        
        x_total = np.concatenate([p[0] for p in pontos_3d_acumulados])
        y_total = np.concatenate([p[1] for p in pontos_3d_acumulados])
        z_total = np.concatenate([p[2] for p in pontos_3d_acumulados])
        cores_totais = np.concatenate(cores_acumuladas)

        cos_t = math.cos(angulo_rotacao_y)
        sin_t = math.sin(angulo_rotacao_y)
        x_rot = x_total * cos_t - z_total * sin_t
        z_rot = x_total * sin_t + z_total * cos_t

        foco_virtual = 500.0
        centro_canvas_x, centro_canvas_y = 400, 300
        z_camera = z_rot + 2.0 

        px_canvas = ((x_rot / z_camera) * foco_virtual + centro_canvas_x).astype(int)
        py_canvas = ((y_total / z_camera) * foco_virtual + centro_canvas_y).astype(int)

        canvas = np.zeros((600, 800, 3), dtype=np.uint8)
        limites = (px_canvas >= 0) & (px_canvas < 800) & (py_canvas >= 0) & (py_canvas < 600)
        
        canvas[py_canvas[limites], px_canvas[limites]] = cores_totais[limites][:, ::-1]

        cv2.putText(canvas, f"Rotacao: {int(math.degrees(angulo_rotacao_y))} graus", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        cv2.imshow("BioMotion - Scanner 3D Virtual", canvas)

    if cv2.waitKey(1) & 0xFF == 27:
        break

# --- 5. ENCERRAMENTO LIMPO ---
if tem_webcam:
    webcam.release()

for kinect_info in lista_kinects:
    kinect_info['depth_stream'].stop()
    kinect_info['color_stream'].stop()

if len(lista_kinects) > 0:
    openni2.unload()

cv2.destroyAllWindows()