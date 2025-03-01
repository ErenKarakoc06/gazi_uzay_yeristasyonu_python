from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QTransform
from pymavlink import mavutil
import sys


class VerticalSpeedIndicator(QGraphicsView):
    update_speed = pyqtSignal(float)  # Dikey hız değerini almak için sinyal

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(250, 250)

        # Arka planı yükle ve yerleştir
        self.background = QGraphicsPixmapItem(QPixmap(
            "VerticalSpeedIndicator_Background.PNG"))
        self.scene.addItem(self.background)
        self.background.setPos(0, 0)

        # Hız göstergesi ibresini yükle ve yerleştir
        self.mark_icon = QGraphicsPixmapItem(QPixmap("VerticalSpeedNeedle.PNG"))
        self.scene.addItem(self.mark_icon)
        bg_width = self.background.pixmap().width()
        bg_height = self.background.pixmap().height()
        ac_width = self.mark_icon.pixmap().width()
        ac_height = self.mark_icon.pixmap().height()
        self.mark_icon.setPos((bg_width - ac_width) / 2, ((bg_height - ac_height) / 2) - 30)

        # Hız sinyalini update_display fonksiyonuna bağla
        self.update_speed.connect(self.update_display)

    def update_display(self, speed):
        """
        Dikey Hız göstergesi ibresini güncelle.
        """
        center_x = 12
        center_y = 96

        # Hız için dönme transformu uygula
        transform = QTransform()
        transform.translate(center_x, center_y)  # Görselin merkezine git
        transform.rotate(270 + speed * 25)  # Hız açısına göre döndür
        transform.translate(-center_x, -center_y)  # Merkez dönüşü geri al
        self.mark_icon.setTransform(transform)


class PixhawkThread(QThread):
    # Dikey hız değerlerini arayüze göndermek için sinyal
    update_speed = pyqtSignal(float)

    def __init__(self, port='/dev/ttyACM0', baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True

    def run(self):
        # Pixhawk bağlantısı
        try:
            master = mavutil.mavlink_connection(self.port, baud=self.baud)
            master.wait_heartbeat()
            print("Pixhawk bağlantısı kuruldu!")

            master.mav.param_set_send(
                master.target_system,
                master.target_component,
                b"ATTITUDE_RATE",
                50.0,  # 50 Hz gibi bir değer
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )

            while self.running:
                msg = master.recv_match(type='VFR_HUD', blocking=True)  # 'VFR_HUD' mesajlarını dinle
                if msg:
                    vertical_speed = msg.climb  # Dikey hız (m/s)
                    self.update_speed.emit(vertical_speed)  # Sinyal gönder

        except Exception as e:
            print(f"Pixhawk bağlantı hatası: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vertical Speed Indicator Display")
        self.setGeometry(100, 100, 230, 300)  # Yüksekliği artırdım
        self.view = VerticalSpeedIndicator()

        # Dikey hız değerini gösteren etiket
        self.speed_label = QLabel("Dikey Hız: 0.0", self)
        self.speed_label.setAlignment(Qt.AlignCenter)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addWidget(self.speed_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Pixhawk thread
        self.pixhawk_thread = PixhawkThread(port='COM9', baud=115200)
        self.pixhawk_thread.update_speed.connect(self.update_speed_label)
        self.pixhawk_thread.update_speed.connect(self.view.update_speed)
        self.pixhawk_thread.start()

    def update_speed_label(self, speed):
        self.speed_label.setText(f"Dikey Hız: {speed:.2f} m/s")

    def closeEvent(self, event):
        # Pencere kapanırken Pixhawk thread'ini durdur
        self.pixhawk_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
