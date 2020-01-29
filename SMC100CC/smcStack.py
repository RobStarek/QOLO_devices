import serial
from time import sleep, localtime, strftime, time
from smc100py3 import SMC100CC

"""
Controller class for stack of SMC100CC drivers.
It makes easier to handle multiple controllers.
Requires smc100py3.py module.

Example:
    ConstructionDict = {
        1 : (1, None, 0),
        2 : (2, None, 0),
        3 : (3, "My motor", 0)
    }
    Ms = SMCStack('COM3', ConstructionDict, 1) #init stack
    Mov1 = {1: 20, 2:30} #define movement
    Ms(Mov1) #perform collective movement
    #...
    Ms.Close() #close port at the end


"""


class SMCStack():
    dT = 0.02
    DEBUG = False

    def __init__(self, port, ConstructionDict, MasterKey=None):
        """
        Args:
            port - string path to used serial port
            ConstructionDict - dictionary with keys, addresses, labels and correction
            MasterKey - selected key to be the constructed first, if none, first from keys is selected
        """
        self.Motors = {}
        if not(MasterKey in ConstructionDict.keys()):
            MasterKey = sorted(ConstructionDict.keys())[0]

        # Init first motor
        self.Motors[MasterKey] = SMC100CC(port, *ConstructionDict[MasterKey])
        self.Motors[MasterKey].DEBUG = self.DEBUG
        self.port = self.Motors[MasterKey].port
        sleep(self.dT)

        # Init remaining motors
        for key in sorted([key for key in ConstructionDict if key != MasterKey]):
            addr, label, corr = ConstructionDict[key]
            self.Motors[key] = SMC100CC(self.port, addr, label, corr)
            self.Motors[key].DEBUG = self.DEBUG

    def __call__(self, PosDict):
        """
        Perform CollectiveMode().
        """
        self.CollectiveMove(PosDict)

    def __del__(self):
        self.port.close()

    def __getitem__(self, key):
        return self.Motors.get(key, None)

    def GetPos(self, keys=None):
        Position = {}
        if keys == None:
            keys = sorted(self.Motors.keys())

        for key in self.Motors:
            if key in self.Motors:
                Position[key] = self.Motors[key].get_pos()
                sleep(self.dT)

        return Position

    def Home(self, keys=None):
        """
        Untested collective home.
        """
        if keys == None:
            keys = self.Motors.keys()
        for key in keys:
            if key in self.Motors.keys():
                self.Motors[key].home()

    def WaitForMovement(self, keys):
        """
        Wait for selected motor to finish movement.
        Args:
            keys: list with keys to selected motor
        """

        is_moving = []
        t0 = time()
        for key in keys:
            sleep(self.dT)
            val = self.Motors[key].get_state()[0] == "28"
            is_moving.append(val)

        while any(is_moving) and time()-t0 < 100:
            sleep(self.dT)
            is_moving = []
            for key in keys:
                val = self.Motors[key].get_state()[0] == "28"
                sleep(self.dT)
                is_moving.append(val)

    def CollectiveMove(self, PosDict):
        """
        Efficient absolute move of multiplate motors.
        Wait only for one who is travelling the most.
        Start with the one with longest distance.
        Args:
            PosDict: dictionary of key: absolute position (deg)

        """
        Current = self.GetPos()
        target_keys = set(PosDict.keys())
        my_keys = set(self.Motors.keys())
        keys = target_keys.intersection(my_keys)
        distance = {key: abs(Current[key]-PosDict[key]) for key in keys}
        # sorted distance keys
        distance = sorted(distance, key=lambda x: distance[x])

        longest_dist = distance[-1]  # key of longest-travelling motor
        dist_value = abs(Current[longest_dist] - PosDict[longest_dist])
        time_estim = self.Motors[longest_dist].get_mr_time(dist_value)
        sleep(self.dT)

        t0 = time()
        for key in distance[::-1]:
            self.Motors[key](PosDict[key])
            sleep(self.dT)

        while time()-t0 < time_estim and time()-t0 < 100:  # upper limit for waiting
            sleep(2*self.dT)

        self.WaitForMovement(distance)

    def Close(self):
        self.port.close()
