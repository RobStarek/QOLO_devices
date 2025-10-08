import sys
import json
import toml
from time import time, strftime
import numpy as np
import h5py
import matplotlib.pyplot as plt
from PyQt5 import QtCore, QtGui, QtWidgets
#from scientificspin import ScientificDoubleSpinBox
import pyqtgraph as pg
pg.setConfigOptions(useOpenGL=True,antialias=False)
try:
    pg.setConfigOptions(useNumba=True)
except KeyError:
    pass
#from GrabThread_rnd import GrabThread
from GrabThread import GrabThread

pg.setConfigOptions(imageAxisOrder='row-major')

class ScanWindow(QtWidgets.QGroupBox):
    PX_SIZE = 6.3e-6
    MAGNIFICATION = 111
    SCALE_BAR_UM = 1

    def __init__(self, parent):
        super(ScanWindow, self).__init__(parent)  
        self.parent = parent      
        self.mouse_pos = None
        self.X_to_percent = 1
        self.Y_to_percent = 1
        self.X_offset = 50
        self.Y_offset = 50
        self.frames = 0
        self.fps_sample = (0, time())
        self.my_first_frame = True
        self.settings = {}
        self.fps_timer = QtCore.QTimer(self)
        self.fps_timer.timeout.connect(self.calc_fps)
        self.save_timer = QtCore.QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_settings)
        self.init_ui()              
        
        self.fps_timer.start(10000)   
        self.autoscale_timer = QtCore.QTimer(self)
        self.autoscale_timer.timeout.connect(self.img.autoLevels)
        self.view.sigStateChanged.connect(self.trigger_save_timer)
        #self.histo.sigLevelChangeFinished.connect(self.trigger_save_timer)
        self.param_widget.signal_autoscale.connect(self.on_autoscale)
        self.crosshair.sigPositionChangeFinished.connect(self.trigger_save_timer)

        #self.load_last_state()

    def init_ui(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.img = pg.ImageView()        
        #hist = self.img.getHistogramWidget()
        #self.img.getHistogramWidget().setRange(0,1024)     
        self.param_widget = CameraParamsWidget()        
        self.layout.addWidget(self.param_widget)
        self.setTitle("Andor Viewer")
        self.layout.addWidget(self.img)                
        

        self.view = self.img.getView()
        self.histo = self.img.getHistogramWidget()    
        self.histo.fillHistogram(False) #better performance?
        
        self.statusbar = QtWidgets.QStatusBar()
        self.statusbar.label = QtWidgets.QLabel("temp")
        self.statusbar.addWidget(self.statusbar.label)
        self.layout.addWidget(self.statusbar)
        
        self.setLayout(self.layout)
        
        #self.statusbar.setText('temperature')

        #self.view.getViewWidget().sigSceneMouseMoved.connect(self.click)
        self.scn = self.img.scene
        #self.scn.sigMouseClicked.connect(self.click)
        self.scn.sigMouseMoved.connect(self.mouse_moved)

        brush = QtGui.QBrush()
        pen = QtGui.QPen()
        pen.setColor(QtCore.Qt.red)
        brush.setColor(QtCore.Qt.red)
        brush.setStyle(QtCore.Qt.SolidPattern)        

        self.crosshair = pg.TargetItem(pos = (0,0), size=30, symbol='crosshair', pen = pen,brush=None)
        
        scale_bar_um = int(1e-6*self.SCALE_BAR_UM*self.MAGNIFICATION/self.PX_SIZE)        
        self.scalebar = pg.ScaleBar(scale_bar_um, 5, brush, pen)
        self.scalebar.setParentItem(self.view)
        self.scalebar.anchor(itemPos=(0.9,0.1), parentPos=(0.9,0.1), offset=(-10,10))
        self.scalebar.text.setText(f'{self.SCALE_BAR_UM:.0f} um')

        self.view.addItem(self.crosshair)
        
        self.img.keyPressEvent = self.any_key        
    
    def any_key(self,event):        
        if event.key()==QtCore.Qt.Key.Key_M:
            x, y= self.mouse_pos.x(), self.mouse_pos.y()
            mapped = self.view.mapSceneToView(self.mouse_pos)
            self.crosshair.setPos(mapped.x(), mapped.y())
        
    def mouse_moved(self, ev):
        self.mouse_pos = ev

    def calc_fps(self):
        dt = time() - self.fps_sample[1]
        df = self.frames - self.fps_sample[0]
        fps = df/dt
        print(f'frames: {self.frames}, df: {df}, dt: {dt}, fps: {fps:.1f}')
        self.fps_sample = (self.frames, time())

    def trigger_save_timer(self, ev):        
        self.save_timer.stop()                 
        self.save_timer.start(10000)

    def save_settings(self):
        print("Settings saved.")
        with open('last_view.json', 'w') as state_file:
            json.dump(self.get_current_state(), state_file)

    def on_autoscale(self, state):
        print(f"Toggled: {state}")
        if state:
            try:
                self.img.autoLevels()
            except ValueError as e:
                pass
            self.autoscale_timer.start(1000)
        else:
            self.autoscale_timer.stop()  
        self.trigger_save_timer(None)          

    def get_current_state(self):
        
        
        print("Autoscale:", self.param_widget.autoscale_button.isChecked())
        state = {
            'autoscale_button' : self.param_widget.autoscale_button.isChecked(),
            'exposure_value' : self.param_widget.spinbox.value(),
            'crosshair_xy' : (self.crosshair.pos().x(), self.crosshair.pos().y()),
            'view_state' : self.view.getState(),
            'levels' : self.img.getHistogramWidget().getLevels()
        }
        return state
    
    def load_last_state(self):
        settings = toml.load('cam_default.toml')
        self.settings = settings
        if settings.get('save_transform', False):
            try:
                with open('last_view.json', 'r') as state_file:
                    state = json.load(state_file)            
                    print("loaded:", state)
                    self.my_first_frame = False
                    self.param_widget.autoscale_button.setChecked(state.get('autoscale_button', False))
                    self.param_widget.spinbox.setValue(state.get('exposure_value', 50e-3))
                    cx, cy = state.get('crosshair_xy', (0,0))
                    self.crosshair.setPos((cx, cy))
                    self.img.setLevels(min= state.get('levels')[0], max= state.get('levels')[1])
                    view_state = state.get('view_state', None)
                    if view_state is not None:
                        print('applying view transform')
                        self.view.setState(view_state)
            except:
                pass        


    #def scan_callback(self, value):
    def handle_frame(self):
        if self.my_first_frame:
            #self.img.setImage(frame, autoRange=False, autoLevels=False, autoHistogramRange = False)
            self.img.setImage(self.parent.Worker.data, autoRange=True, autoLevels=True, autoHistogramRange = True)
            #self.img.setLevels([0,1024], True)                     
            self.img.updateImage(False)            
            self.my_first_frame = False
            self.frames = 1
        else:                        
            self.img.setImage(self.parent.Worker.data, autoRange=False, autoLevels=False, autoHistogramRange = False)
            self.frames += 1
            #self.img.setLevels([np.min(value),np.max(value)])         
            #self.img.updateImage(False)
            #self.img2.s
            
    def handle_temp_info(self, msg):
        self.statusbar.label.setText(msg)
        
class TestWin(QtWidgets.QMainWindow):
    
    #Main window containing main widget
    def __init__(self, parent = None):
        super(TestWin, self).__init__(parent)
        self.Worker = GrabThread()
        self.init_ui()

        self.SW.param_widget.spinbox.setValue(self.Worker.exp)        
        self.SW.param_widget.signal_save_image.connect(self.save_image)
    
        self.Worker.signal_frame_ready.connect(self.SW.handle_frame)
        self.Worker.signal_temp_ready.connect(self.SW.handle_temp_info)
        self.SW.param_widget.signal_set_exposure.connect(self.Worker.set_exposure)
        self.Worker.finished.connect(self.Worker.deleteLater)
        self.frames = 0
        self.lastt = time()

        self.Worker.start()
        self.SW.load_last_state()
        
        

    def init_ui(self):        
        self.SW = ScanWindow(self)
        self.setCentralWidget(self.SW)
        self.setWindowTitle("Andor Viewer")
        self.setGeometry(100,100,600,300)

    def save_image(self, *args):
        image = np.copy(self.Worker.data)
        metadata = self.Worker.get_metadata()
        timestamp1 = strftime("%d/%m/%Y %H:%M:%S")
        timestamp2 = strftime("%Y-%m-%d-%H-%M-%S")
        filename = f'img_{timestamp2}.h5'
        t0 = time()
        

        file = self.saveFileDialog(filename)
        if file:
            with h5py.File(file,'w') as h5f:
                dset_img = h5f.create_dataset('frame', data = image)
                for key, value in metadata.items():
                    dset_img.attrs[key] = value
                dset_img.attrs['timestamp'] = timestamp1
                dset_img.attrs['time'] = t0
                dset_img.attrs['magnification'] = self.SW.MAGNIFICATION
                dset_img.attrs['crosshair_position'] = (self.SW.crosshair.pos().x(), self.SW.crosshair.pos().y())
                
            self.SW.img.export(file.replace('.h5','_as_shown_.png'))
            self.SW.img.updateImage()
        
    def saveFileDialog(self, filename_hint=None):        
        options = QtWidgets.QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save image as h5...",
            filename_hint,
            "All Files (*);;Text Files (*.h5)",
            options=options)
        if fileName:
            return fileName
            

    def closeEvent(self, event):
        # do stuff
        self.Worker.go = False
        event.accept() # let the window close        

class CameraParamsWidget(QtWidgets.QWidget):
    signal_set_exposure = QtCore.pyqtSignal(float)
    signal_save_image = QtCore.pyqtSignal()
    signal_autoscale = QtCore.pyqtSignal(bool)
    

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Create a vertical layout to arrange the text box and button
        layout = QtWidgets.QHBoxLayout()

        # Create a text box (QLineEdit)
        #self.spinbox = ScientificDoubleSpinBox(self)
        self.spinbox = pg.SpinBox(self)
        self.spinbox.setMaximum(100)
        self.spinbox.setMinimum(10e-6)
        self.spinbox.setDecimals(3)
        options = {
            'step' : 1,
            'dec' : True,
            'siPrefix' : True,
            'suffix' : 's'
        }
        self.spinbox.setOpts(**options)
        self.spinbox.setValue(50)
        layout.addWidget(self.spinbox)

        # Create a button (QPushButton)
        self.button = QtWidgets.QPushButton("Set exposure", self)
        layout.addWidget(self.button)
        
        self.save_button = QtWidgets.QPushButton("Save to H5", self)        
        layout.addWidget(self.save_button)

        self.autoscale_button = QtWidgets.QPushButton("Autoscale", self)
        self.autoscale_button.setCheckable(True)
        layout.addWidget(self.autoscale_button)
        
        # Connect the button click event to a slot (function)
        self.button.clicked.connect(self.emit_set_exposure)
        self.save_button.clicked.connect(self.signal_save_image.emit)
        self.autoscale_button.toggled.connect(self.signal_autoscale.emit)
        # Set the layout for the widget
        self.setLayout(layout)                

    def emit_set_exposure(self):        
        str_value = self.spinbox.value()
        float_value = float(str_value)
        print(f"Exposure: {float_value}")        
        self.signal_set_exposure.emit(float_value)  # Emit
        print("Update cam_last.toml...")
        last_toml = toml.load('cam_last.toml')
        last_toml['exposure_s'] = round(float_value,5)
        with open("cam_last.toml", "w") as config_file:
            toml.dump(last_toml, config_file)
        print("Done.")

        


def dummy(x,y,z):
    pass

def dummy2():
    pass
    
if __name__ == "__main__":    
    QtApp = QtWidgets.QApplication(sys.argv)
    MainWindow = TestWin()    
    MainWindow.show()
    QtApp.exec_()
    MainWindow.Worker.go = False
    
    QtApp.quit()
    
