"""
This snippet serves to speedup writing new classes for 
device that are controlled via serial port.
"""
import toml
import serial
from serial.tools.list_ports import comports

def detect_comport(pid, vid, sn=None):    
    if sn is None:
        sn = True
    for entry in comports():
        sn_cond = (sn == entry.serial_number) if sn is not None else True
        if pid == entry.pid and vid == entry.vid and sn_cond:
            return entry


class DeviceTemplate():    
    def __init__(self, pid, vid, sn=None):
        self.com_address = detect_comport(pid, vid, sn)
        self.port = serial.Serial(
            baudrate = 115200
        )
        self.port.port = self.com_address

    def __enter__(self):
        if self.port.isOpen():
            return None
        self.port.open()
        
    def __exit__(self):
        self.close()       

    def close(self):
        if not self.port.isOpen():
            return None
        self.port.close()    

    def sample_method(self, value):
        msg = f'sample_cmd {value:.3f}'.encode('ascii')
        self.port.write(msg)
        response = self.port.read(3)
        return response
