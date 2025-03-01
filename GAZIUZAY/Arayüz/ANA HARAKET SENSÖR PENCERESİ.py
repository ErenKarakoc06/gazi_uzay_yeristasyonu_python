from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtCore import  QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPen, QTransform, QPixmap
from pymavlink import mavutil
import sys


class haraketpenceresi1(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(400,300)

        self.image_width = 2000
        self.image_height = 6608

        # Görseli yükle
        self.image_item = QGraphicsPixmapItem(QPixmap("Horizon_GroundSky5.bmp"))
        self.scene.addItem(self.image_item)

        # Görseli pencerenin ortasına yerleştir
        self.image_item.setPos(0,0
            #(self.width() - self.image_width) / 2,  # X koordinatı
            #(self.height() - self.image_height) / 2  # Y koordinatı
        )

        # Ortadaki artı işareti
        self.cross_horizontal = self.scene.addLine(-20, 0, 20, 0, pen=QPen(QColor("red"), 2))
        self.cross_vertical = self.scene.addLine(0, -20, 0, 20, pen=QPen(QColor("red"), 2))

        # Artıyı görselin tam ortasına yerleştir
        self.cross_horizontal.setPos(self.width() / 2, self.height() / 2)
        self.cross_vertical.setPos(self.width() / 2, self.height() / 2)

    def yatayguncelleme(self, pitch, roll):
        """
        Görseli günceller ve artıyı merkez noktasında sabit tutar.
        """
        # Görselin merkezini hesapla (800 x 2304 boyutlarını dikkate alarak)
        center_x = self.image_width / 2
        center_y = self.image_height / 2

        # Dönme ve hareket transformu uygula
        transform = QTransform()
        transform.translate(center_x, center_y)  # Görselin merkezine git
        transform.rotate(-roll)  # Roll açısına göre döndür
        transform.translate(-center_x, -center_y)  # Merkez dönüşü geri al
        self.image_item.setTransform(transform)

        # Pitch değerine göre görseli dikey eksende hareket ettir
        self.image_item.setPos(
            (self.width() - self.image_width) / 2,  # X pozisyonu değişmez
            (self.height() - self.image_height) / 2 + pitch*12.8  # Pitch'e göre Y pozisyonu
        )


class PixhawkThread(QThread):
    # Pitch ve roll değerlerini arayüze göndermek için sinyal
    update_horizon = pyqtSignal(float, float)

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
                msg = master.recv_match(type='ATTITUDE', blocking=True)  # 'ATTITUDE' mesajlarını dinle
                if msg:
                    pitch = msg.pitch * 60  # Pitch açısı
                    roll = msg.roll * 60  # Roll açısı
                    self.update_horizon.emit(pitch, roll)  # Sinyal gönder
        except Exception as e:
            print(f"Pixhawk bağlantı hatası: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class haraketpenceresi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hareket Penceresi")
        self.setGeometry(100, 100, 400,300)
        self.setFixedSize(400,300)

        # Horizon göstergesi
        self.horizon = haraketpenceresi1()
        self.setCentralWidget(self.horizon)

        # Durum bilgileri
        self.status_label = QLabel(self)
        self.status_label.setGeometry(10, 10, 300, 50)
        self.status_label.setText("Pixhawk bağlantısı bekleniyor...")

        # Pixhawk thread
        self.pixhawk_thread = PixhawkThread(port='COM5', baud=115200)
        self.pixhawk_thread.update_horizon.connect(self.update_horizon)
        self.pixhawk_thread.start()




    def update_horizon(self, pitch, roll):
        # Horizon'u güncelle
        self.horizon.yatayguncelleme(pitch, roll)

        # Durum etiketini güncelle
        self.status_label.setText(f"Pitch: {pitch:.2f}°, Roll: {roll:.2f}°")

    def closeEvent(self, event):
        # Pencere kapanırken Pixhawk thread'ini durdur
        self.pixhawk_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = haraketpenceresi()
    window.show()
    sys.exit(app.exec_())
