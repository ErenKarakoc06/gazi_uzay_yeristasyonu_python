from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap
import sys
import cv2  # OpenCV kütüphanesi

class CameraThread(QThread):
    frame_ready = pyqtSignal(QImage)

    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.running = True
        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(3, 500)  # Genişlik
        self.cap.set(4, 500)  # Yükseklik

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


class CameraDisplay(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(500, 400)  # Kamera görüntüsü boyutu

        # Kamera görüntüsü için QGraphicsPixmapItem
        self.image_item = QGraphicsPixmapItem()
        self.scene.addItem(self.image_item)

        # Ekranı ortalamak için
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_image(self, qimg):
        """ Kamera görüntüsünü günceller """
        self.image_item.setPixmap(QPixmap.fromImage(qimg))


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kamera Görüntüsü")
        self.setGeometry(0, 0, 500, 400)  # Pencere boyutu
        self.setFixedSize(500, 400)

        # Ekranın tam ortasında başlasın
        screen_rect = self.frameGeometry()
        screen_center = QApplication.primaryScreen().availableGeometry().center()
        screen_rect.moveCenter(screen_center)
        self.move(screen_rect.topLeft())

        self.camera_display = CameraDisplay()
        self.setCentralWidget(self.camera_display)

        self.camera_thread = CameraThread()
        self.camera_thread.frame_ready.connect(self.camera_display.update_image)
        self.camera_thread.start()

    def closeEvent(self, event):
        """ Uygulama kapatılırken thread'leri güvenli şekilde durdurur """
        self.camera_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
