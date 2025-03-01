from PyQt5.QtWidgets import QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QAction, QVBoxLayout, QWidget, QTextEdit
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QTransform, QImage, QPen, QColor
from pymavlink import mavutil
import sys
import cv2

class MDIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MDI Window")
        self.setGeometry(0, 0, 1920, 1080)  # Ana pencere boyutlarını 1920 x 1080 olarak ayarla

        # MDI Area oluştur
        self.mdi = QMdiArea()
        self.setCentralWidget(self.mdi)

        # Menü çubuğu oluştur
        self.menu = self.menuBar()
        self.window_menu = self.menu.addMenu("Window")

        # Yeni alt pencere açma eylemi (örnek olarak)
        new_action = QAction("New Text Window", self)
        new_action.triggered.connect(self.new_text_window)
        self.window_menu.addAction(new_action)

        # Pencere ekleme eylemleri (sizin pencere kodlarınızı ekleyin)
        add_horizon_action = QAction("Add Horizon Display", self)
        add_horizon_action.triggered.connect(self.add_horizon_display)
        self.window_menu.addAction(add_horizon_action)

    def new_text_window(self):
        # Yeni alt pencere oluştur (örnek olarak)
        sub = QMdiSubWindow()
        sub.setWidget(QTextEdit())
        sub.setWindowTitle("Sub Text Window")
        self.mdi.addSubWindow(sub)
        sub.show()

    def add_horizon_display(self):
        sub = QMdiSubWindow()
        horizon_display = HorizonDisplay()
        sub.setWidget(horizon_display)
        sub.setWindowTitle("Horizon Display")
        self.mdi.addSubWindow(sub)
        sub.show()

class HorizonDisplay(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(250, 250)

        self.image_item = QGraphicsPixmapItem()
        self.scene.addItem(self.image_item)

        # Döndürülebilir PNG göstergesi
        self.horizon_indicator = QGraphicsPixmapItem(QPixmap("Dedector.PNG"))
        self.horizon_indicator.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.horizon_indicator)

        # Artı işareti (Kamera görüntüsünün merkezinde sabit)
        self.cross_horizontal = self.scene.addLine(-20, 0, 20, 0, pen=QPen(QColor("red"), 2))
        self.cross_vertical = self.scene.addLine(0, -20, 0, 20, pen=QPen(QColor("red"), 2))
        self.cross_horizontal.setPos(self.width() / 2, self.height() / 2)
        self.cross_vertical.setPos(self.width() / 2, self.height() / 2)

        # Göstergenin başlangıç konumu (Tam ortada)
        self.horizon_indicator.setPos((self.width() - 200) / 2, (self.height() - 200) / 2)

    def update_image(self, qimg):
        """ Kamera görüntüsünü günceller """
        self.image_item.setPixmap(QPixmap.fromImage(qimg))

    def update_horizon(self, pitch, roll):
        """ PNG göstergesini roll ile döndürür, pitch ile yukarı-aşağı hareket ettirir """
        transform = QTransform()
        transform.translate(100, 100)  # PNG'nin merkezine git
        transform.rotate(-roll)  # Roll açısına göre döndür
        transform.translate(-100, -100)  # Merkez dönüşü geri al
        self.horizon_indicator.setTransform(transform)

        # Pitch değerine göre yukarı-aşağı hareket ettir
        self.horizon_indicator.setPos((self.width() - 200) / 2, (self.height() - 200) / 2 + pitch * 5)

class CameraThread(QThread):
    frame_ready = pyqtSignal(QImage)

    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.running = True
        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(3, 400)  # Genişlik
        self.cap.set(4, 300)  # Yükseklik

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                qimg = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
                self.frame_ready.emit(qimg)

    def stop(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()
        self.quit()
        self.wait()

class PixhawkThread(QThread):
    update_horizon = pyqtSignal(float, float)

    def __init__(self, port='COM9', baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True

    def run(self):
        try:
            master = mavutil.mavlink_connection(self.port, baud=self.baud)
            master.wait_heartbeat()
            print("Pixhawk bağlantısı kuruldu!")

            while self.running:
                msg = master.recv_match(type='ATTITUDE', blocking=True, timeout=1)
                if msg:
                    pitch = msg.pitch * 60
                    roll = msg.roll * 60
                    self.update_horizon.emit(pitch, roll)
        except Exception as e:
            print(f"Pixhawk bağlantı hatası: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MDIWindow()
    window.show()
    sys.exit(app.exec_())
