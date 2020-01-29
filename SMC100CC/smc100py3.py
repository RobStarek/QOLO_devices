import serial
from time import sleep, localtime, strftime

"""
Motor controller class for Newport SMC100cc
v. 2
last edit:

This class should make motor SR50 (Newport) controlling via SMC100CC/PP easier.
It has a some most useful commands, other commands is possible to send via
send_command() method.
1 instance = 1 motor

Examples use:
M = SMC100CC('COM3', 1) #construct object, init serial communication
M(45) #move to 45 deg
"""


class SMC100CC:
    port = None
    address = None
    label = None
    DEBUG = False
    pos = None
    state = None
    correction = 0.0
    state_code_table = {"0A": "0A Not referenced from reset",
                        "0B": "0B Not referenced from homing",
                        "0C": "0C not referenced from config",
                        "0D": "0D Not referenced from disable",
                        "0E": "0E Not referenced from ready",
                        "0F": "0F Not referenced from moving",
                        "10": "10 Not referenced fromESP stage error",
                        "11": "11 Not refferenced from jogging",
                        "14": "14 Configuration",
                        "1E": "1E Homing commanded from RS-232-C",
                        "1F": "1F Homing commanded from RC",
                        "28": "28 Moving",
                        "32": "32 Ready from homing",
                        "33": "33 Ready from moving",
                        "34": "34 Ready from disable",
                        "35": "35 Ready from jogging",
                        "3C": "3C Disable from ready",
                        "3D": "3D Disable from moving",
                        "3E": "3E Disable from jogging",
                        "46": "46 Jogging from ready",
                        "47": "47 Jogging from disable",
                        "": "Unknown"}

    # *** Methods *** (aka functions)
    # **Special methods**

    def __init__(self, port, address=1, label=None, correction=0.0):
        # Takes name of port or already created ports
        # If input parameter is string, use it as port address.
        # If given parameter is instance of pyserial.serial (port), assign it as motor port.
        if isinstance(port, str):
            # Create connection
            self.port = serial.Serial(port, 57600, xonxoff=True, timeout=0)
            # baudrate = 57 600 bit/s, data bits - 8, parity = none, stopbits = 1, term = cr+lf
        else:
            self.port = port  # assign reference
        # Set address.
        self.address = f"{address:02d}"
        self.label = f"Motor{address:02d}" if label == None else label

        try:
            self.get_state()

        except:
            self.state = "0A Not referenced from reset"

        self.correction = correction
        try:
            self.get_pos()
        except:
            pass

    # On instance destruction
    def __del__(self):
        if self.DEBUG:
            print("Closing port.")
        self.port.close()  # Close port

    def __call__(self, pos):
        """
        Send motor to given position plus its offset (degrees).
        Returns True is command succeeded.
        """
        if not (self.pos == pos):
            self.move_abs_noblock(pos+self.correction)
            self.pos = pos
        return True

    def __str__(self):
        """
        Get readable string with motor info.
        """
        try:
            output = f"{self.label:s}: {self.get_state()[1]:s} @ {self.get_pos():.3f}"
        except:
            output = f"{self.label:s}: Unknown state. Unknown pos"
            raise
        return output

    # **Support methods** (not neccesary, but useful to make code more simple).
    # Send command without waiting for response.
    def send_command(self, command, value):
        """
        Send command to motor. Terminators are already included.
        command and value are strings.
        """
        cmd = f"{self.address:s}{command:s}{value:s}\r\n"
        if self.DEBUG:
            print(self.label, "SC:", cmd)
        self.port.write(bytes(cmd, encoding='ascii'))
        return cmd

    # Send command to port and wait a while (time), the return response
    def send_command_listen(self, command, value, time):
        """
        Send command to motor and wait (time) for response, which
        is returned with command in a list.
        """
        cmd = self.send_command(command, value)
        sleep(time)
        #response = str(self.port.read(20), encoding='ascii')
        response = str(self.port.read(self.port.inWaiting()), encoding='ascii')
        if self.DEBUG:
            print(self.label, "SCL:", response)
        return [response, cmd]

    # **Main methods**
    # Get position of motor.

    def get_pos(self):
        """Get position of motor."""
        x = (self.send_command_listen("TP", "", 0.1))
        if len(str(self.address)) == 1:
            x = float(x[0][3:-2])
        if len(str(self.address)) == 2:
            x = float(x[0][4:-2])
        self.pos = x - self.correction
        return x

    # Get relative move time estimation.
    def get_mr_time(self, x):
        """"
        Get relative movement time for distance x in seconds.
        Returns:
            x ... float, seconds to finish movement
        """
        if abs(x)<0.1:
            return 0.1

        x = (self.send_command_listen("PT", str(x), 0.1))
        if len(str(self.address)) == 1:
            x = float(x[0][3:-2])
        if len(str(self.address)) == 2:
            x = float(x[0][4:-2])
        return x

    # Get state code and state name
    def get_state(self):
        """
        Ask about controllers state.
        """
        result = (self.send_command_listen("TS", "", 0.05))[0]
        if len(str(self.address)) == 1:
            state_code = result[7:-2]  # two last chars of string
        if len(str(self.address)) == 2:
            state_code = result[8:-2]  # two last chars of string
        # state_code = "" #test
        state_descr = self.state_code_table[state_code]
        self.state = state_descr
        return [state_code, state_descr]

    def reset(self):
        """
        Reset the controller. Afterwards, homing is required.
        """
        self.send_command("RS", "")
        sleep(1)
        return (self.get_state())[1]

    def disable(self):
        """
        Disable controller.
        """
        self.send_command("MM", "0")
        sleep(0.1)
        return (self.get_state())[1]

    def enable(self):
        """
        Enable controller.
        """
        self.send_command("MM", "1")
        sleep(0.1)
        return (self.get_state())[1]

    def home(self, time=None):
        """
        Execute home search and wait at least time seconds to finish.
        If time==None, block program until done.
        Returns current state of the controller.
        """
        self.send_command("OR", "")
        if time == None:
            self.get_state()
            while self.state == "1E Homing commanded from RS-232-C":
                self.get_state()
                sleep(0.3)
        else:
            time = time+0.1
            sleep(time)

        self.pos = 0 - self.correction
        return (self.get_state())[1]

    # Stop motion of motor.
    def stop(self):
        """
        Stop motors, even when moving.
        """
        self.send_command("ST", "")
        sleep(0.1)
        self.pos = self.get_pos()-self.correction
        return (self.get_state())[1]

    def move_abs_noblock(self, x):
        """
        Execute absolute movement to position x (degrees) but without blocking the program.
        """
        self.get_state()
        if not(self.state == "28 Moving"):
            if self.DEBUG == True:
                print("--- \n")
                print(strftime("%H:%M:%S", localtime()))
                print("Moving motor", self.label, " to position:", str(x))
                print("Without program freeze")
            self.send_command("PA", str(x))  # Position absolute
            sleep(0.017)
            self.get_state()
            return True
        else:
            print("Error ... moving")
            return False
