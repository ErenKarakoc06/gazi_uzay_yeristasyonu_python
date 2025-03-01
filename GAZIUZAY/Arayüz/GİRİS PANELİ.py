import sys
import sqlite3
from PyQt5 import QtWidgets,QtGui,QtCore


class Pencere(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.baglanti_olusturur()
        self.init_ui()


    def baglanti_olusturur(self):
        baglanti = sqlite3.connect("database.db")

        self.cursor = baglanti.cursor()

        self.cursor.execute("Create Table If not exists üyeler (kullanıcı_adı TEXT,şifre TEXT)")

        baglanti.commit()

    def init_ui(self):

        #RESİM BOYUTLANDIRMA MERKEZLENDİRME VE YERLEŞTİRME
        self.resim = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap("logo.png")
        scaled_pixmap = pixmap.scaled(200,200,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
        self.resim.setPixmap(scaled_pixmap)

        #KULLANICI ADI YAZISI
        self.yazi1= QtWidgets.QLabel("Kullanıcı Adı")
        self.yazi1.setAlignment(QtCore.Qt.AlignCenter)

        #KULLANICI ADI BÖLÜMÜ
        self.kullaniciadi = QtWidgets.QLineEdit()
        self.kullaniciadi.setFixedWidth(200)

        #Parola YAZISI
        self.yazi2 = QtWidgets.QLabel("Parola")
        self.yazi2.setAlignment(QtCore.Qt.AlignCenter)
        #self.yazi2.setFont(0,QFont("Arial",12))

        #ŞİFRE KISMI
        self.sifre = QtWidgets.QLineEdit()
        self.sifre.setFixedWidth(200)
        self.sifre.setEchoMode(QtWidgets.QLineEdit.Password)
        self.giris = QtWidgets.QPushButton("Giriş Yap")

        #BİLGİ YAZISI
        self.yazi3 = QtWidgets.QLabel("")


        #YERLEŞTİRMELER
        v_box = QtWidgets.QVBoxLayout()
        v_box.addStretch()
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


        h_box = QtWidgets.QHBoxLayout()
        h_box.addStretch()
        h_box.addLayout(v_box)
        h_box.addStretch()

        self.setLayout(h_box)
        self.giris.clicked.connect(self.login)
        self.setFixedSize(300,400)  #PENCERE ŞEKİLLENDİRME

        self.show()

    def login(self):
        adi = self.kullaniciadi.text()
        par = self.sifre.text()

        self.cursor.execute("Select * From üyeler where kullanıcı_adı = ? and şifre = ?",(adi,par))

        data = self.cursor.fetchall()

        if len(data) == 0:

            self.yazi3.setText("Kullanıcı bulunamadı\nLütfen tekrar deneyiniz...")

        else:
            self.yazi3.setText("Sistem Başlatılıyor...")


app = QtWidgets.QApplication(sys.argv)

pencere= Pencere()

sys.exit(app.exec_())

