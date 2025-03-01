from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGridLayout,
                             QSpacerItem, QSizePolicy, QHBoxLayout)
from PyQt5.QtGui import QPixmap, QTransform, QColor, QPen, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView
from pymavlink import mavutil
import os
import sys
import folium
from folium import CustomIcon
import cv2
import sqlite3


# ---------------------- Harita Penceresi ----------------------
class HaritaPenceresi(QMainWindow):
    update_signal = QtCore.pyqtSignal(float, float, float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Harita Uygulaması")
        self.setGeometry(100, 100, 800, 600)
        self.webView = QWebEngineView()
        self.map_path = os.path.abspath("Map1.html")
        self.path = []
        self.initialize_map(0, 0)
        self.webView.setUrl(QtCore.QUrl.fromLocalFile(self.map_path))

        self.gps_label = QLabel("GPS Verileri Bekleniyor...", self)
        self.gps_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.webView)
        layout.addWidget(self.gps_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.update_signal.connect(self.update_map)

    def initialize_map(self, latitude, longitude):
        self.map = folium.Map(location=[latitude, longitude], zoom_start=20)
        if self.path:
            folium.PolyLine(self.path, color="blue", weight=2.5, opacity=0.8).add_to(self.map)
        airplane_icon = CustomIcon('plane.png', icon_size=(40, 40))
        folium.Marker(
            location=[latitude, longitude],
            popup="Mevcut İHA Konumu",
            icon=airplane_icon
        ).add_to(self.map)
        self.map.save(self.map_path)

    def update_map(self, latitude, longitude, altitude):
        self.path.append((latitude, longitude))
        self.initialize_map(latitude, longitude)
        self.webView.setUrl(QtCore.QUrl.fromLocalFile(self.map_path))
        self.gps_label.setText(f"Latitude: {latitude}, Longitude: {longitude}, Altitude: {altitude} m")


# ---------------------- Hareket Penceresi ----------------------
class HaraketPenceresi(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(400, 300)
        self.image_width = 2000
        self.image_height = 6608
        # Load image
        self.image_item = QGraphicsPixmapItem(QPixmap("Horizon_GroundSky5.bmp"))
        self.scene.addItem(self.image_item)
        # Cross lines in the center
        self.cross_horizontal = self.scene.addLine(-20, 0, 20, 0, pen=QPen(QColor("red"), 2))
        self.cross_vertical = self.scene.addLine(0, -20, 0, 20, pen=QPen(QColor("red"), 2))
        # Place the cross in the image center
        self.cross_horizontal.setPos(self.width() / 2, self.height() / 2)
        self.cross_vertical.setPos(self.width() / 2, self.height() / 2)

    def yatay_guncelleme(self, pitch, roll):
        center_x = self.image_width / 2
        center_y = self.image_height / 2
        transform = QTransform()
        transform.translate(center_x, center_y)
        transform.rotate(-roll)
        transform.translate(-center_x, -center_y)
        self.image_item.setTransform(transform)
        self.image_item.setPos(
            (self.width() - self.image_width) / 2,
            (self.height() - self.image_height) / 2 + pitch * 12.8
        )


# ---------------------- Pixhawk Thread ----------------------
class PixhawkThread(QThread):
    update_gps = pyqtSignal(float, float, float)
    update_horizon = pyqtSignal(float, float)
    update_speed = pyqtSignal(float)
    update_vertical_speed = pyqtSignal(float)

    def __init__(self, port='COM5', baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True

    def validate_gps_data(self, latitude, longitude, altitude):
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and altitude >= -500):
            raise ValueError("Invalid GPS data")

    def run(self):
        try:
            master = mavutil.mavlink_connection(self.port, baud=self.baud)
            master.wait_heartbeat()
            print("Pixhawk bağlantısı kuruldu!")
            while self.running:
                msg = master.recv_match(blocking=True)
                if msg:
                    if msg.get_type() == 'GPS_RAW_INT':
                        latitude = msg.lat / 1e7
                        longitude = msg.lon / 1e7
                        altitude = msg.alt / 1000
                        try:
                            self.validate_gps_data(latitude, longitude, altitude)
                            self.update_gps.emit(latitude, longitude, altitude)
                        except ValueError as e:
                            print(f"Invalid GPS data: {e}")
                    elif msg.get_type() == 'ATTITUDE':
                        pitch = msg.pitch * 60
                        roll = msg.roll * 60
                        self.update_horizon.emit(pitch, roll)
                    elif msg.get_type() == 'VFR_HUD':
                        speed = msg.groundspeed
                        vertical_speed = msg.climb
                        self.update_speed.emit(speed)
                        self.update_vertical_speed.emit(vertical_speed)
        except Exception as e:
            print(f"Pixhawk bağlantı hatası: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


# ---------------------- Kamera Thread ----------------------
class CameraThread(QThread):
    frame_ready = pyqtSignal(QImage)

    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.running = True
        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(3, 400)  # Width
        self.cap.set(4, 300)  # Height

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


# ---------------------- Kamera Görüntüleme ----------------------
class CameraDisplay(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(400, 300)
        self.image_item = QGraphicsPixmapItem()
        self.scene.addItem(self.image_item)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_image(self, qimg):
        self.image_item.setPixmap(QPixmap.fromImage(qimg))


# ---------------------- Air Speed Indicator ----------------------
class AirSpeedIndicator(QGraphicsView):
    update_speed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(250, 250)
        self.background = QGraphicsPixmapItem(QPixmap("AirSpeedIndicator_Background.PNG"))
        self.scene.addItem(self.background)
        self.background.setPos(0, 0)
        self.mark_icon = QGraphicsPixmapItem(QPixmap("AirSpeedNeedle.PNG"))
        self.scene.addItem(self.mark_icon)
        bg_width = self.background.pixmap().width()
        bg_height = self.background.pixmap().height()
        ac_width = self.mark_icon.pixmap().width()
        ac_height = self.mark_icon.pixmap().height()
        self.mark_icon.setPos((bg_width - ac_width) / 2, ((bg_height - ac_height) / 2) - 30)
        self.update_speed.connect(self.update_display)

    def update_display(self, speed):
        center_x = 12
        center_y = 96
        transform = QTransform()
        transform.translate(center_x, center_y)
        transform.rotate(180 + speed * 7.2)
        transform.translate(-center_x, -center_y)
        self.mark_icon.setTransform(transform)


# ---------------------- Vertical Speed Indicator ----------------------
class VerticalSpeedIndicator(QGraphicsView):
    update_speed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(250, 250)
        self.background = QGraphicsPixmapItem(QPixmap("VerticalSpeedIndicator_Background.PNG"))
        self.scene.addItem(self.background)
        self.background.setPos(0, 0)
        self.mark_icon = QGraphicsPixmapItem(QPixmap("VerticalSpeedNeedle.PNG"))
        self.scene.addItem(self.mark_icon)
        bg_width = self.background.pixmap().width()
        bg_height = self.background.pixmap().height()
        ac_width = self.mark_icon.pixmap().width()
        ac_height = self.mark_icon.pixmap().height()
        self.mark_icon.setPos((bg_width - ac_width) / 2, ((bg_height - ac_height) / 2) - 30)
        self.update_speed.connect(self.update_display)

    def update_display(self, speed):
        center_x = 12
        center_y = 96
        transform = QTransform()
        transform.translate(center_x, center_y)
        transform.rotate(270 + speed * 25)
        transform.translate(-center_x, -center_y)
        self.mark_icon.setTransform(transform)


# ---------------------- Turn Coordinator ----------------------
class TurnCoordinator(QGraphicsView):
    update_horizon = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(250, 250)
        self.background = QGraphicsPixmapItem(QPixmap("TurnCoordinator_Background2.png"))
        self.scene.addItem(self.background)
        self.background.setPos(0, 0)
        self.aircraft_icon = QGraphicsPixmapItem(QPixmap("DJV JUL 2357-12.png"))
        self.scene.addItem(self.aircraft_icon)
        bg_width = self.background.pixmap().width()
        bg_height = self.background.pixmap().height()
        ac_width = self.aircraft_icon.pixmap().width()
        ac_height = self.aircraft_icon.pixmap().height()
        self.aircraft_icon.setPos((bg_width - ac_width) / 2, ((bg_height - ac_height) / 2) - 15)
        self.mark_icon = QGraphicsPixmapItem(QPixmap("TurnCoordinatorMarks.png"))
        self.scene.addItem(self.mark_icon)
        self.mark_icon.setPos(96, 158)
        self.ball_indicator = QGraphicsPixmapItem(QPixmap("TurnCoordinatorBall,png.PNG"))
        self.scene.addItem(self.ball_indicator)
        self.ball_indicator.setPos(98, 158)
        self.update_horizon.connect(self.update_display)

    def update_display(self, roll, ball_position):
        center_x = self.aircraft_icon.boundingRect().center().x()
        center_y = self.aircraft_icon.boundingRect().center().y()
        transform = QTransform()
        transform.translate(center_x, center_y)
        transform.rotate(roll / 1.587)
        transform.translate(-center_x, -center_y)
        self.aircraft_icon.setTransform(transform)
        center_x = 99
        y_base = 159
        k = -1.84
        a = -0.00198
        ball_x = center_x + (k * roll)
        ball_y = y_base + a * (ball_x - center_x) ** 2
        self.ball_indicator.setPos(ball_x, ball_y)


# ---------------------- Login Page ----------------------
class LoginPage(QWidget):
    def __init__(self):
        super().__init__()
        self.baglanti_olusturur()
        self.init_ui()

    def baglanti_olusturur(self):
        baglanti = sqlite3.connect("database.db")
        self.cursor = baglanti.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS üyeler (kullanıcı_adı TEXT, şifre TEXT)")
        baglanti.commit()

    def init_ui(self):
        self.resim = QLabel()
        pixmap = QtGui.QPixmap("logo.png")
        scaled_pixmap = pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.resim.setPixmap(scaled_pixmap)
        self.yazi1 = QLabel("Kullanıcı Adı")
        self.yazi1.setAlignment(QtCore.Qt.AlignCenter)
        self.kullaniciadi = QtWidgets.QLineEdit()
        self.kullaniciadi.setFixedWidth(200)
        self.yazi2 = QLabel("Parola")
        self.yazi2.setAlignment(QtCore.Qt.AlignCenter)
        self.sifre = QtWidgets.QLineEdit()
        self.sifre.setFixedWidth(200)
        self.sifre.setEchoMode(QtWidgets.QLineEdit.Password)
        self.giris = QtWidgets.QPushButton("Giriş Yap")
        self.yazi3 = QLabel("")

        v_box = QVBoxLayout()
        v_box.addStretch()
        v_box.addWidget(self.resim)
        v_box.addStretch()
        v_box.addWidget(self.yazi1)
        v_box.addWidget(self.kullaniciadi)
        v_box.addWidget(self.yazi2)
        v_box.addWidget(self.sifre)
        v_box.addWidget(self.yazi3)
        v_box.addStretch()
        v_box.addWidget(self.giris)
        v_box.addStretch()

        h_box = QHBoxLayout()
        h_box.addStretch()
        h_box.addLayout(v_box)
        h_box.addStretch()

        self.setLayout(h_box)
        self.giris.clicked.connect(self.login)
        # Fixed size for the login page remains 300 x 400.
        self.setFixedSize(300, 400)

    def login(self):
        adi = self.kullaniciadi.text()
        par = self.sifre.text()
        self.cursor.execute("SELECT * FROM üyeler WHERE kullanıcı_adı = ? AND şifre = ?", (adi, par))
        data = self.cursor.fetchall()
        if len(data) == 0:
            self.yazi3.setText("Kullanıcı bulunamadı\nLütfen tekrar deneyiniz...")
        else:
            self.yazi3.setText("Sistem Başlatılıyor...")


# ---------------------- Main Window ----------------------
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ana Pencere")
        self.setGeometry(0, 0, 1400, 900)

        main_container = QWidget()
        self.setCentralWidget(main_container)
        layout = QGridLayout()
        main_container.setLayout(layout)

        # Map, Motion, and Camera windows
        self.map_window = HaritaPenceresi()
        self.map_window.setFixedSize(800, 600)
        self.motion_window = HaraketPenceresi()
        self.motion_window.setFixedSize(400, 300)
        self.camera_display = CameraDisplay()
        self.camera_display.setFixedSize(400, 300)

        # Create the instrument indicators vertical layout
        indicators_layout = QVBoxLayout()
        self.airspeed_indicator = AirSpeedIndicator()
        self.airspeed_indicator.setFixedSize(250, 250)
        self.vertical_speed_indicator = VerticalSpeedIndicator()
        self.vertical_speed_indicator.setFixedSize(250, 250)
        self.turn_coordinator = TurnCoordinator()
        self.turn_coordinator.setFixedSize(250, 250)
        indicators_layout.addWidget(self.airspeed_indicator)
        indicators_layout.addSpacerItem(QSpacerItem(0, 25, QSizePolicy.Minimum, QSizePolicy.Fixed))
        indicators_layout.addWidget(self.vertical_speed_indicator)
        indicators_layout.addSpacerItem(QSpacerItem(0, 25, QSizePolicy.Minimum, QSizePolicy.Fixed))
        indicators_layout.addWidget(self.turn_coordinator)

        indicators_widget = QWidget()
        indicators_widget.setLayout(indicators_layout)

        # Create a container that places the indicators and the login page side by side.
        instruments_and_login = QWidget()
        h_layout = QHBoxLayout()
        h_layout.addWidget(indicators_widget)
        h_layout.addSpacing(30)  # 30 pixels spacing
        self.login_page = LoginPage()
        h_layout.addWidget(self.login_page)
        # Align the login page at the top (instead of its default vertical center)
        h_layout.setAlignment(self.login_page, Qt.AlignTop)
        instruments_and_login.setLayout(h_layout)

        # Add widgets to the grid layout
        layout.addWidget(self.map_window, 0, 0, 2, 2, Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(self.motion_window, 2, 0, Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(self.camera_display, 2, 1, Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(instruments_and_login, 0, 2, 3, 1, Qt.AlignTop | Qt.AlignLeft)

        # Start Pixhawk thread and Camera thread.
        self.pixhawk_thread = PixhawkThread(port='COM5', baud=115200)
        self.pixhawk_thread.update_gps.connect(self.map_window.update_signal.emit)
        self.pixhawk_thread.update_horizon.connect(self.motion_window.yatay_guncelleme)
        self.pixhawk_thread.update_speed.connect(self.airspeed_indicator.update_speed)
        self.pixhawk_thread.update_vertical_speed.connect(self.vertical_speed_indicator.update_speed)
        self.pixhawk_thread.update_horizon.connect(self.turn_coordinator.update_horizon)
        self.pixhawk_thread.start()

        self.camera_thread = CameraThread()
        self.camera_thread.frame_ready.connect(self.camera_display.update_image)
        self.camera_thread.start()

    def closeEvent(self, event):
        self.pixhawk_thread.stop()
        self.camera_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())