from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel, \
    QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QTransform
from pymavlink import mavutil
import sys


class TurnCoordinator(QGraphicsView):
    update_horizon = pyqtSignal(float, float)  # Roll ve ball değerlerini almak için sinyal

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(250, 250)

        # Load and place background
        self.background = QGraphicsPixmapItem(QPixmap("TurnCoordinator_Background2.png"))
        self.scene.addItem(self.background)
        self.background.setPos(0, 0)

        # Load and place aircraft icon in the center of the background
        self.aircraft_icon = QGraphicsPixmapItem(QPixmap("DJV JUL 2357-12.png"))
        self.scene.addItem(self.aircraft_icon)
        bg_width = self.background.pixmap().width()
        bg_height = self.background.pixmap().height()
        ac_width = self.aircraft_icon.pixmap().width()
        ac_height = self.aircraft_icon.pixmap().height()
        self.aircraft_icon.setPos((bg_width - ac_width) / 2, ((bg_height - ac_height) / 2) - 15)

        # Load and place turn marks
        self.mark_icon = QGraphicsPixmapItem(QPixmap("TurnCoordinatorMarks.png"))
        self.scene.addItem(self.mark_icon)
        self.mark_icon.setPos(96, 158)  # Slightly above the aircraft icon

        # Load and place ball indicator
        self.ball_indicator = QGraphicsPixmapItem(QPixmap("TurnCoordinatorBall,png.PNG"))
        self.scene.addItem(self.ball_indicator)
        self.ball_indicator.setPos(98, 158)  # Below aircraft icon

        # Connect the update_horizon signal to the update_roll method
        self.update_horizon.connect(self.update_display)

    def update_display(self, roll, ball_position):
        """
        Update the roll of the aircraft icon and the position of the ball indicator.
        """
        center_x = self.aircraft_icon.boundingRect().center().x()
        center_y = self.aircraft_icon.boundingRect().center().y()

        # Apply rotation transform for roll
        transform = QTransform()
        transform.translate(center_x, center_y)  # Move to the center of the image
        transform.rotate(roll/1.587)  # Rotate by the roll angle
        transform.translate(-center_x, -center_y)  # Move back to the original position
        self.aircraft_icon.setTransform(transform)

        center_x = 99  # Ball'ın merkez noktası (orta çizgi)
        y_base = 159  # Ball'ın Y eksenindeki sabit referans noktası
        k = -1.84  # Roll için X ekseni ölçekleme katsayısı
        a = -0.00198  # Parabol eğriliği (a'yı küçülterek daha düzgün hale getirebiliriz)

        # Roll'a bağlı olarak ball'ın X pozisyonu
        ball_x = center_x + (k * roll)

        # Yükseklik parabol formülü (concave up)
        ball_y = y_base + a * (ball_x - center_x) ** 2

        # Ball'ın yeni pozisyonunu ayarla
        self.ball_indicator.setPos(ball_x, ball_y)


class PixhawkThread(QThread):
    # Roll ve ball değerlerini arayüze göndermek için sinyal
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
                    roll = msg.roll * 60  # Roll açısı
                    ball_position = msg.roll * 30  # Ball position (örnek olarak roll ile aynı değeri kullanıyoruz)
                    self.update_horizon.emit(roll, ball_position)  # Sinyal gönder
        except Exception as e:
            print(f"Pixhawk bağlantı hatası: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Turn Coordinator Display")
        self.setGeometry(100, 100, 230, 300)  # Yüksekliği artırdım
        self.view = TurnCoordinator()

        # Roll derecesini gösteren etiket
        self.roll_label = QLabel("Roll: 0.0°", self)
        self.roll_label.setAlignment(Qt.AlignCenter)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addWidget(self.roll_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Pixhawk thread
        self.pixhawk_thread = PixhawkThread(port='COM9', baud=115200)
        self.pixhawk_thread.update_horizon.connect(self.update_roll_label)
        self.pixhawk_thread.update_horizon.connect(self.view.update_horizon)
        self.pixhawk_thread.start()

    def update_roll_label(self, roll, ball_position):
        self.roll_label.setText(f"Roll: {roll:.2f}°")

    def closeEvent(self, event):
        # Pencere kapanırken Pixhawk thread'ini durdur
        self.pixhawk_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())


