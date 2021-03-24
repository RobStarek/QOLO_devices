from serial import Serial
from time import sleep, time


class EncWheel():
    """
    Minimal class for arduino encoder wheel
    """
    dt = 1  # sleep tiem

    def __init__(self, port):
        self.port = Serial(port, baudrate=9600, timeout=2)                
        sleep(1)
        obsolete = self.port.read(self.port.inWaiting())

    def send_val(self, i):
        mybyte = 0b1010 << 4
        mybyte = mybyte + (i & 0b1111)
        self.port.write(mybyte.to_bytes(mybyte, 'little'))

    def request_id(self, i):
        self.port.write(b'\x5f')
        sleep(0.1)
        return self.port.read(self.port.inWaiting())
        

    def close(self):
        self.port.close()

    def __del__(self):
        self.close()

    def __call__(self, i=0):
        return self.send_val(i)

class EncWheelD():
    """
    Minimal class for arduino encoder wheel
    """
    dt = 1  # sleep tiem

    def __init__(self, port):
        self.port = Serial(port, baudrate=9600, timeout=2)                
        sleep(1)
        obsolete = self.port.read(self.port.inWaiting())

    def send_val(self, i): 
        """
        i = 0 ... 255
        """       
        mybyte = i.to_bytes(1, 'little')
        print(mybyte)
        self.port.write(mybyte)
        sleep(0.05)
        obs = self.port.read(self.port.inWaiting())
        print(obs)

    def close(self):
        self.port.close()

    def __del__(self):
        self.close()

    def __call__(self, i=0):
        return self.send_val(i)        

D = EncWheelD('COM6')

for i in range(26,210):
    print(i)
    D(i)
    sleep(0.5)

D.close()
