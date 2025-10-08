from PyQt5 import QtCore
import toml
from collections import deque
import enum
import numpy as np
from time import sleep, time
from pyAndorSDK3 import AndorSDK3, andor_sdk3_exceptions
from pyAndorSDK3 import utils
#utils.add_library_path(r'C:\Program Files\Andor SDK3')
sdk3 = AndorSDK3()


class Commands(enum.IntEnum):
    SET_EXP = 1


class GrabThread(QtCore.QThread):
    # signal_frame_ready = QtCore.pyqtSignal(np.ndarray, name="frame")
    signal_frame_ready = QtCore.pyqtSignal(name="frame")
    signal_temp_ready = QtCore.pyqtSignal(str, name="temperature")
    
    def __init__(self):
        super(GrabThread, self).__init__()
        settings = toml.load('cam_default.toml')
        if settings.get('setup', False) == "last":
            last_settings = toml.load("cam_last.toml")
            for key, item in last_settings.items():
                settings[key] = item
        
        self.go = True
        self.data = np.zeros((1024, 1024))
        self.exp = settings.get('exposure_s', 0.05)
        self.cam = sdk3.GetCamera(0)
        

        self.cam.AOIHeight = int(settings.get('roi_height', 2046))
        self.cam.AOIWidth = int(settings.get('roi_width', 2046))
        self.cam.AOILeft = int(settings.get('roi_left', 0))
        self.cam.AOITop = int(settings.get('roi_top', 0))
        
        self.cam.AOIHbin = 1
        self.cam.AOIVbin = 1   
        self.cam.FrameCount = 1
        # print(self.cam.min_AOIHeight, self.cam.max_AOIHeight)
        # print(self.cam.min_AOIWidth, self.cam.max_AOIWidth)
        # print(self.cam.min_AOILeft, self.cam.max_AOILeft)
        # print(self.cam.min_AOITop, self.cam.max_AOITop)        
        
        self.cam.CycleMode = 'Continuous'
        self.cam.TriggerMode = "Internal"
        self.cam.ExposureTime = self.exp
        self.cam.GainMode = settings.get('gain_mode', '12-bit (low noise)')
        
        #self.cam.TemperatureControl = settings.get('temperature', '0.0')
        #self.cam.SensorCooling = settings.get('cooling', False)
                

        self.rate = self.calc_framerate()        
        self.cam.FrameRate = self.rate       
        # print(self.cam.max_FrameRate)
        # print(self.cam.MaxInterfaceTransferRate)
        sleep(1)
        self.commands = deque()
        self.fps_limit = 35
        self.fps_period = 1/self.rate 
        print(f"Exp: {self.exp} Rate: {self.rate}, FPS period: {self.fps_period}")
        
        #self.cam.set_roi(hstart = center_x-w_x//2, hend = center_x+w_x//2, vstart = center_y-w_y//2, vend = center_y+w_y//2,hbin=bins,vbin=bins)
        # self.cam.set_exposure(self.exp)

    def calc_framerate(self):
        max_fps = self.cam.max_FrameRate
        max_rate = self.cam.MaxInterfaceTransferRate
        rate = min(max_rate, max_fps)*0.8
        if rate > 30:
            return 30        
        return rate

    def get_metadata(self):
        meta = {
            'exposure_s' : self.exp,
            'camera' : self.cam.CameraModel,
            'gain_mode' : self.cam.GainMode,
            'px_size' : self.cam.PixelWidth,
            'aoi_left' : self.cam.AOILeft,
            'aoi_top' : self.cam.AOITop,
            'aoi_width' : self.cam.AOIWidth,
            'aoi_height' : self.cam.AOIHeight,
            'bin_y' : self.cam.AOIHbin,
            'bin_x' : self.cam.AOIVbin,
            'sw_version' : 1.5,
            'sensor_temperature' : self.cam.SensorTemperature
        }        
        return meta
        
    def run(self):
        print("Scanner Thread unleashed!")
        w8 = 0.1
        t00 = time()
        buff_wait = int(1000/self.rate)+1000

        t_last_send = time()
        allow_new_frame = True
        
        imgsize = self.cam.ImageSizeBytes
        print(imgsize)
        buf = np.empty((imgsize,), dtype='B')
        last_temp_t = 0
        temp_string = "?|?"
        
        self.cam.queue(buf, imgsize)
        self.cam.AcquisitionStart()
        t00 = time()        
        t_last_send = time() - 5
        _img = np.copy(self.data)

        while self.go:
            # print('tick')
            while self.commands:
                command, arg = self.commands.popleft()
                if command == Commands.SET_EXP:
                    self.exp = arg
                    # self.cam.AcquisitionStop()
                    self.cam.ExposureTime = self.exp
                    sleep(0.02)
                    self.rate = self.calc_framerate()
                    
                    print(f"new fps: {self.rate}, new exp: {self.exp}")
                    self.cam.FrameRate = self.rate
                    self.fps_period = 1/self.rate 
                    buff_wait = int(1000/self.rate)+2000
                    # self.cam.AcquisitionStart()
        
            if (time()-last_temp_t) > 1:
                temp_string = f'Temp. status: {self.cam.TemperatureStatus:s} | {self.cam.SensorTemperature:.1f} C'
                #print(temp_string)
                last_temp_t = time()
                self.signal_temp_ready.emit(temp_string)
            
            # wild loop
            # print(f'Loading... t={time()-t00:.2f}')
            #grab image once in a while
            if (time()-t_last_send) > self.fps_period:
                t_last_send = time()        
                self.data = np.copy(_img)
                self.signal_frame_ready.emit()
                # print(f'Emitted... t={time()-t00:.2f}')
                acq = self.cam.wait_buffer(buff_wait)
                _img = acq.image
            else:
                self.msleep(1)
            #queue in every tick                                                          
            self.cam.queue(buf, imgsize)                 

        self.cam.AcquisitionStop()
        self.cam.flush()
        print("Closing camera.")
        self.cam.close()
        print("Worker thread ended.")

    def set_exposure(self, value):
        self.exp = value
        self.commands.append([Commands.SET_EXP, self.exp])
