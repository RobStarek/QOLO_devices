from serial import Serial
from time import sleep, time


class TTiMinimal():
    """
    Minimal class for TTi1906 multimeter
    Example use:    
    S = TTiMinimal("COM6")    
    x = S()
    """
    dt = 1  # sleep tiem

    def __init__(self, port, mode=b"ADC"):
        self.port = Serial(port, baudrate=9600, timeout=2)
        # mde measurement, default is DC current in mA
        self.port.write(mode+b"\n")
        sleep(0.1)
        self.port.write(b"SLOW\n")  # high precision
        self.port.write(b"Filter 4\n")  # average 8 values
        sleep(1)
        obsolete = self.port.read(self.port.inWaiting())

    def read(self):
        """
        Read value.
        """
        obsolete = self.port.read(self.port.inWaiting())
        self.port.write(b"READ?\n")
        sleep(self.dt)
        data = self.port.read(18)
        data = data.decode()
        try:
            number = float(data[0:11])
            unit = data[11:16]
        except:
            print("TTi1906:Error:could not parse", data)
            raise
        return number

    def close(self):
        self.port.close()

    def __del__(self):
        self.close()

    def __call__(self):
        return self.read()

