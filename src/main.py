import cv2
import math
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget, QDesktopWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QRect

from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtGui import QPixmap, QImage, QMouseEvent, QWheelEvent
from PyQt5.QtCore import Qt, QRect


import time

from PyQt5 import QtCore, QtGui, QtWidgets
from user import Ui_MainWindow
import os


class VideoThread(QThread):
    change_pixmap = pyqtSignal(QImage)
    change_pixmapraw = pyqtSignal(QImage)

    def run(self):
        #cap = cv2.VideoCapture("http://192.168.55.42:5000/video_feed")
        cap = cv2.VideoCapture("file.mp4")
        capraw = cv2.VideoCapture("file.mp4")
        while True:
            retraw, frameraw = capraw.read()
            ret, frame = cap.read()
            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                laser_points = []
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    if cv2.contourArea(contour) > 100:
                        M = cv2.moments(contour)
                        if M['m00'] == 0:
                            continue
                        cx = int(M['m10'] / M['m00'])
                        cy = int(M['m01'] / M['m00'])
                        laser_points.append((cx, cy))
                if len(laser_points) < 2:
                    continue
                pixels_distance = np.sqrt(abs((laser_points[0][0] - laser_points[1][0])*2 + (laser_points[0][1] - laser_points[1][1])*2))
                
                if pixels_distance == 0:
                    continue
                
                pixel_size = 5 / pixels_distance
                
                if not np.isnan(pixel_size):

                    for i in range(10, frame.shape[0], int(10 / pixel_size)):
                            cv2.line(frame, (0, i), (frame.shape[1], i), (0, 255, 0), 1)
                    for i in range(10, frame.shape[1], int(10 / pixel_size)):
                            cv2.line(frame, (i, 0), (i, frame.shape[0]), (0, 255, 0), 1)

            # Emit the processed image (on need)
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.change_pixmap.emit(q_image)    

            rgb_imageraw = cv2.cvtColor(frameraw, cv2.COLOR_BGR2RGB)
            hr, wr, chr = rgb_imageraw.shape
            bytes_per_lineraw = chr * wr
            q_imageraw = QImage(rgb_imageraw.data, wr, hr, bytes_per_lineraw, QImage.Format_RGB888)
            self.change_pixmapraw.emit(q_imageraw) 


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.cap = cap
        self.recording = False
    
        # Add zoom factor
        self.zoom_factor = 4.0
        
        self.setupUi(self)
        
        
        self.zoom_effect.mouseMoveEvent = self.mouseMoveEvent
        self.zoom_effect.wheelEvent = self.wheelEvent
        
        self.setGeometry(QRect(0, 0, 600, 300))
        
        self.thread = VideoThread(self)
        self.thread.change_pixmap.connect(self.set_image)
        self.thread.change_pixmapraw.connect(self.set_imageraw)

        self.thread.start()

        self.grid.clicked.connect(self.gridToggle)
        self.img_save.clicked.connect(self.save_image)
        self.save_location.clicked.connect(self.choose_save_location)
        self.video_save.clicked.connect(self.start_stop_recording)

    def save_image(self):
        timestamp= time.strftime("%Y%m%d-%H%M%S")
        imgfilename = f"{self.save_location}/Images/{timestamp}.jpg"
        self.video_output.pixmap().save(imgfilename)
        QMessageBox.information(self, "Information", "Image saved.")
                
    
    def start_stop_recording(self):
        if not self.cap.isOpened():
            self.cap.open("file.mp4")
        
        if not hasattr(self, 'writer') or not self.writer.isOpened():
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


            timestamp= time.strftime("%Y%m%d-%H%M%S")
            vidfilename = f"{self.save_location}/Videos/{timestamp}.mp4"
       
            self.writer = cv2.VideoWriter(vidfilename, cv2.VideoWriter_fourcc(*'DIVX'), 20, (width, height))
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(1)
        else:
            self.timer.stop()
            self.writer.release()
            QMessageBox.information(self, "Information", "Video saved.")
         

    def update_frame(self):
        ret, frame = self.cap.read()
        self.writer.write(frame)
        #cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == 27:
            self.timer.stop()
            self.writer.release()
            self.cap.release()
            cv2.destroyAllWindows()


    def set_image(self, image):
        if self.grid.text() == 'Hide Grid':
            self.video_output.setPixmap(QPixmap.fromImage(image))

    def set_imageraw(self, image):
        if self.grid.text() == 'Show Grid':
            self.video_output.setPixmap(QPixmap.fromImage(image))
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.video_output.setGeometry(QRect(0, 0, self.width()//2, self.height()))
        self.zoom_effect.setGeometry(QRect(self.width()//2, 0, self.width()//2, self.height()))
        
    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.x()
        y = event.y()
        
        # Get the section of the image to be zoomed
        rect = QRect(int(x - 150/self.zoom_factor), int(y - 150/self.zoom_factor), int(300/self.zoom_factor), int(300/self.zoom_factor))
        image = self.video_output.pixmap().copy(rect).toImage()
        
        # Scale the image to be displayed in the zoomed label
        zoomed_image = image.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.zoom_effect.setPixmap(QPixmap.fromImage(zoomed_image))

    def wheelEvent(self, event: QWheelEvent):
        # Change zoom factor based on mouse wheel event
        if event.angleDelta().y() > 0:
            self.zoom_factor *= 1.1
        else:
            self.zoom_factor /= 1.1
        
        # Update zoomed image
        self.mouseMoveEvent(event)
        
    def gridToggle(self):
        if self.grid.text() == 'Show Grid':
            self.grid.setText('Hide Grid')
        else:
            self.grid.setText('Show Grid')

    def choose_save_location(self):
        options = QFileDialog.Options()
        self.save_location = QFileDialog.getExistingDirectory(self, "Choose Save Location", "", options=options)
        
        img_directory_name, vid_directory_name = f"{self.save_location}/Images/", f"{self.save_location}/Videos/"

        try:
            os.mkdir(img_directory_name)
        except FileExistsError:
            pass

        try:
            os.mkdir(vid_directory_name)
        except FileExistsError:
            pass


if __name__ == '__main__':
    app = QApplication([])
    cap = cv2.VideoCapture("file.mp4")
    window = MainWindow()
    window.show()
    app.exec_()

