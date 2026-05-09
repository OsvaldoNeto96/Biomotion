import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

# --- 1. O TRABALHADOR DOS BASTIDORES (QThread) ---
# Esta classe roda em paralelo, processando o vídeo sem travar os botões da tela.
class VideoThread(QThread):
    # Criamos um "Sinal" que vai transportar a imagem pronta (matriz do numpy) para a interface
    sinal_frame_pronto = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.rodando = True # Chave de controle para ligar/desligar o loop

    def run(self):
        # Este método run() é o coração da Thread. Tudo aqui roda isolado.
        cap = cv2.VideoCapture(0)
        
        while self.rodando:
            sucesso, frame = cap.read()
            if sucesso:
                frame = cv2.flip(frame, 1) # Efeito espelho
                # Emite o frame para a interface principal através do sinal
                self.sinal_frame_pronto.emit(frame)
                
        cap.release()

    def stop(self):
        # Função para parar o loop quando fecharmos o programa
        self.rodando = False
        self.wait()

# --- 2. A JANELA PRINCIPAL (Interface Gráfica) ---
class JanelaBioMotion(QMainWindow):
    def __init__(self):
        super().__init__()

        # Configurações básicas da janela
        self.setWindowTitle("BioMotion - Análise Biomecânica")
        self.setGeometry(100, 100, 1000, 700) # Posição X, Posição Y, Largura, Altura

        # Widget central (O "chão" onde vamos colocar os botões e os vídeos)
        widget_central = QWidget(self)
        self.setCentralWidget(widget_central)

        # O Layout principal divide a tela horizontalmente (Esquerda: Controles, Direita: Vídeo)
        layout_principal = QHBoxLayout(widget_central)

        # --- PAINEL ESQUERDO: CONTROLES ---
        # QGroupBox cria uma caixinha com um título
        painel_controles = QGroupBox("Articulações Ativas")
        # Layout vertical para empilhar os botões um em cima do outro
        layout_controles = QVBoxLayout()
        
        # Criamos as caixas de seleção (Checkboxes)
        self.chk_cotovelo_esq = QCheckBox("Cotovelo Esquerdo")
        self.chk_cotovelo_dir = QCheckBox("Cotovelo Direito")
        self.chk_joelho_esq = QCheckBox("Joelho Esquerdo")
        
        # Adicionamos as caixas ao layout de controles
        layout_controles.addWidget(self.chk_cotovelo_esq)
        layout_controles.addWidget(self.chk_cotovelo_dir)
        layout_controles.addWidget(self.chk_joelho_esq)
        layout_controles.addStretch() # Empurra os botões para cima, preenchendo o espaço vazio
        
        painel_controles.setLayout(layout_controles)
        # Fixamos a largura do painel lateral
        painel_controles.setFixedWidth(250) 

        # --- PAINEL DIREITO: VÍDEO ---
        # QLabel é usado para exibir textos ou, no nosso caso, imagens (frames)
        self.tela_video = QLabel("Iniciando Câmera...")
        self.tela_video.setAlignment(Qt.AlignCenter) # Centraliza o vídeo
        self.tela_video.setStyleSheet("background-color: black; color: white; font-size: 20px;")

        # Adicionamos os dois painéis ao layout principal
        layout_principal.addWidget(painel_controles)
        layout_principal.addWidget(self.tela_video)

        # --- INICIANDO O TRABALHADOR (Thread) ---
        self.thread_video = VideoThread()
        # Conectamos o sinal que sai da Thread à função que atualiza a tela na Interface
        self.thread_video.sinal_frame_pronto.connect(self.atualizar_imagem)
        self.thread_video.start() # Dá a ordem de partida para o loop do OpenCV

    # --- 3. ATUALIZAÇÃO DA TELA ---
    def atualizar_imagem(self, frame_cv):
        """ Esta função recebe a matriz do OpenCV e converte para o formato que o PyQt5 entende """
        # Converte de BGR (OpenCV) para RGB (PyQt)
        frame_rgb = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_por_linha = ch * w
        
        # Cria a imagem do PyQt
        imagem_qt = QImage(frame_rgb.data, w, h, bytes_por_linha, QImage.Format_RGB888)
        
        # Coloca a imagem no QLabel, ajustando o tamanho se necessário
        self.tela_video.setPixmap(QPixmap.fromImage(imagem_qt).scaled(
            self.tela_video.width(), self.tela_video.height(), Qt.KeepAspectRatio))

    def closeEvent(self, event):
        # Garante que a câmera seja liberada corretamente quando clicamos no X da janela
        self.thread_video.stop()
        event.accept()

# --- 4. EXECUÇÃO DO APLICATIVO ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Aplica um estilo moderno e escuro básico à interface
    app.setStyle("Fusion") 
    janela = JanelaBioMotion()
    janela.show()
    sys.exit(app.exec_())