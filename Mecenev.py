import sys
import socket
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QInputDialog, QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import pyqtSignal, QObject

class Communicate(QObject):
    change_image_signal = pyqtSignal()

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.comm = Communicate()
        self.comm.change_image_signal.connect(self.change_image)
        self.initUI()

    def initUI(self):
        # Allow the user to choose a role
        self.choose_role()
        if self.role == 'sender':
            self.initSenderUI()
            self.wait_for_receiver()
        else:
            self.initReceiverUI()
            self.connect_to_sender()

    def choose_role(self):
        # Request the role from the user
        role, ok = QInputDialog.getItem(self, 'Choose Role', 'Select a role:', ['Sender', 'Receiver'], editable=False)
        if ok:
            if role == 'Sender':
                self.role = 'sender'
            else:
                self.role = 'receiver'
        else:
            # If the user cancels, close the application
            self.close()

    def initSenderUI(self):
        self.setWindowTitle('Sender')
        self.button = QPushButton('Send Message', self)
        self.button.clicked.connect(self.send_message)
        self.button.setEnabled(False)  # Button is disabled until the receiver connects
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)
        self.show()
        # Display the sender's IP address
        self.show_ip_address()

    def show_ip_address(self):
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        QMessageBox.information(self, 'Sender IP Address', f'Sender IP Address: {ip_address}')

    def wait_for_receiver(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind(('', 5000))
            self.server_socket.listen(1)
            threading.Thread(target=self.accept_connection, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to start server on port 5000: {e}')
            self.close()

    def accept_connection(self):
        try:
            self.conn, addr = self.server_socket.accept()
            print('Receiver connected from address', addr)
            self.button.setEnabled(True)  # Enable the button after connection
        except Exception as e:
            print('Error during connection:', e)

    def send_message(self):
        try:
            if hasattr(self, 'conn'):
                self.conn.sendall(b'change_image')
            else:
                QMessageBox.warning(self, 'No Connection', 'Receiver is not connected yet.')
        except Exception as e:
            print('Error sending message:', e)
            QMessageBox.critical(self, 'Error', f'Error sending message: {e}')

    def initReceiverUI(self):
        self.setWindowTitle('Receiver')
        self.label = QLabel(self)
        self.pixmap1 = QPixmap('image1.jpg')
        self.pixmap2 = QPixmap('image2.jpg')
        self.label.setPixmap(self.pixmap1)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.show()

    def connect_to_sender(self):
        # Request the sender's IP address
        sender_ip, ok = QInputDialog.getText(self, 'Sender IP Address', 'Enter the sender\'s IP address:')
        if ok:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.client_socket.connect((sender_ip, 5000))
                threading.Thread(target=self.receive_messages, daemon=True).start()
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to connect to sender: {e}')
                self.close()
        else:
            self.close()

    def receive_messages(self):
        while True:
            try:
                data = self.client_socket.recv(1024)
                if data:
                    message = data.decode()
                    if message == 'change_image':
                        self.comm.change_image_signal.emit()
            except Exception as e:
                print('Error receiving message:', e)
                break

    def change_image(self):
        current_pixmap = self.label.pixmap()
        if current_pixmap.cacheKey() == self.pixmap1.cacheKey():
            self.label.setPixmap(self.pixmap2)
        else:
            self.label.setPixmap(self.pixmap1)

    def closeEvent(self, event):
        try:
            if self.role == 'sender':
                if hasattr(self, 'conn'):
                    self.conn.close()
                if hasattr(self, 'server_socket'):
                    self.server_socket.close()
            elif self.role == 'receiver':
                if hasattr(self, 'client_socket'):
                    self.client_socket.close()
        except:
            pass
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())