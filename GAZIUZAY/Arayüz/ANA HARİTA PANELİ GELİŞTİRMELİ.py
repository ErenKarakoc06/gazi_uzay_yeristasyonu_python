from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QMainWindow, QWidget, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
from pymavlink import mavutil
import threading
import os
from folium import CustomIcon


class HaritaPenceresi(QMainWindow):
    update_signal = QtCore.pyqtSignal(float, float, float)  # Haritayı güncellemek için sinyal

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Harita Uygulaması")
        self.setGeometry(100, 100, 800, 600)

        # Harita widget'ı
        self.webView = QWebEngineView()
        self.map_path = os.path.abspath("Map1.html")
        self.path = []  # Yol çizgisi için koordinat listesi
        self.initialize_map(0, 0)  # Varsayılan başlangıç konumu
        self.webView.setUrl(QtCore.QUrl.fromLocalFile(self.map_path))

        # GPS verileri için etiket
        self.gps_label = QLabel("GPS Verileri Bekleniyor...", self)
        self.gps_label.setAlignment(QtCore.Qt.AlignCenter)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.webView)
        layout.addWidget(self.gps_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # GPS log dosyasını aç
        self.gps_log = open("gps_log.txt", "w")  # GPS verilerini kaydetmek için dosya

        # Signal bağlantısı
        self.update_signal.connect(self.update_map)

        # MAVLink verilerini Pixhawk'tan almak için bir iş parçacığı başlat
        self.thread = threading.Thread(target=self.mavlink_reader, daemon=True)
        self.thread.start()

    def initialize_map(self, latitude, longitude):
        """Harita dosyasını oluşturur ve başlangıç konumunu işaretler."""
        # Eğer harita daha önce oluşturulmadıysa, sadece başlat
        if not hasattr(self, 'map'):
            self.map = folium.Map(location=[latitude, longitude], zoom_start=20)

            # Geçmiş yol çizgisi varsa, haritaya ekleyin
            if self.path:
                folium.PolyLine(self.path, color="blue", weight=2.5, opacity=0.8).add_to(self.map)

            # Uçak simgesini oluştur
            airplane_icon = CustomIcon('plane.png', icon_size=(40, 40))

            # Mevcut konumu uçak simgesiyle işaretle
            folium.Marker(
                location=[latitude, longitude],
                popup="Mevcut İHA Konumu",
                icon=airplane_icon
            ).add_to(self.map)

            # Haritayı kaydet
            self.map.save(self.map_path)
        else:
            # Harita zaten varsa, sadece konum ekleyin
            airplane_icon = CustomIcon('plane.png', icon_size=(40, 40))
            folium.Marker(
                location=[latitude, longitude],
                popup="Mevcut İHA Konumu",
                icon=airplane_icon
            ).add_to(self.map)

        # Haritayı kaydet
        self.map.save(self.map_path)

    def update_map(self, latitude, longitude, altitude):
        """Harita üzerindeki konumu günceller."""
        self.path.append((latitude, longitude))  # Yol çizgisine yeni konumu ekle
        self.initialize_map(latitude, longitude)  # Haritayı güncelle

        # WebEngineView'i yeniden yükle
        self.webView.setUrl(QtCore.QUrl.fromLocalFile(self.map_path))

        # GPS verisini ekranda güncelle
        self.gps_label.setText(f"Latitude: {latitude}, Longitude: {longitude}, Altitude: {altitude} m")

    def mavlink_reader(self):
        """Pixhawk'tan GPS verilerini MAVLink protokolüyle okur."""
        try:
            # Pixhawk'a bağlan (seri portu ve baudrate'i kendi sisteminize göre ayarlayın)
            connection = mavutil.mavlink_connection('COM9', baud=115200)  # Doğru COM portunu kullanın
            connection.wait_heartbeat()  # Pixhawk ile bağlantıyı doğrula
            print("Pixhawk ile bağlantı kuruldu!")

            connection.mav.request_data_stream_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                2,  # Frekans (Hz)
                1  # Başlat (1) veya durdur (0)
            )

            while True:
                # GPS_RAW_INT mesajını al
                msg = connection.recv_match(type='GPS_RAW_INT', blocking=True)
                if msg:
                    # GPS verilerini çöz
                    latitude = msg.lat / 1e7  # Enlem
                    longitude = msg.lon / 1e7  # Boylam
                    altitude = msg.alt / 1000  # Yükseklik (metre)

                    # Sinyali tetikle
                    self.update_signal.emit(latitude, longitude, altitude)
                    print(f"Latitude: {latitude}, Longitude: {longitude}, Altitude: {altitude}")
                    self.gps_log.write(f"{latitude}, {longitude}, {altitude}\n")
                    self.gps_log.flush()


        except Exception as e:
            print(f"MAVLink Error: {e}")
            self.gps_label.setText(f"GPS Bağlantı Hatası: {e}")

    def __del__(self):
        """Kapanışta dosyayı kapat."""
        if hasattr(self, 'gps_log'):
            self.gps_log.close()


if __name__ == "__main__":
    app = QApplication([])
    pencere = HaritaPenceresi()
    pencere.show()
    app.exec_()
