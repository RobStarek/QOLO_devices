"""
Michal Dudka ADC v2 python 3 class. Single-shot-based module.
Type: AD7734
Tested on Python 3.7.1.
"""

import serial
from time import sleep, time

class MD_ADC_v2():
    def __init__(self, port=None, settings=None):
        self.channels = [1, 2, 3, 4, 5, 6, 7, 8]
        self.settings = {
            i: {"chop": False, "cont": False, "time": 127, "range": 0}
            for i in self.channels
        }
        # time formula A, B, min, max
        self.time_table = [
            [128, 248, 2, 127],
            [128, 249, 2, 127],
            [64,  206, 3, 127],
            [64,  207, 3, 127]
        ]
        self.voltage_table = [
            [20, 2**24, -10],
            [10, 2**24, 0],
            [10, 2**24, -5],
            [5, 2**24, 0]
        ]
        self.delay = 0.025  # sec
        self.clk = 2.5  # MHz
        try:
            self.port = serial.Serial(
                port, baudrate=921600, bytesize=8, parity='N', xonxoff=False,  timeout=1)
        except:
            self.port = None
            raise Exception(f'MD_ADC_v2:: Connection to: {port} failed.')
            # raise

        if not(settings is None):
            msgs, check = self.apply_settings(settings, reset=True)
            if not check:
                print(
                    "MD_ADC_v2:: Settings application failed. Check setting dictionary.")
                for msg in msgs:
                    print(msg)

    def __del__(self):
        self.close()

    def __call__(self, arg=None):
        """
        Read voltage.
        Args:
            arg: list of channels to be read (integers 1 to 8)
        Returns:
            dicionary of voltages with channel numbers (int) as keys
        """
        return self.read_singles(arg)

    def close(self):
        """
        Close port.
        """
        if self.port.isOpen():
            self.port.close()
        
    def get_ID(self):
        """
        Get ID string of the device.        
        """
        self.port.write(b'id\n')
        sleep(self.delay)
        msg = self.port.read(self.port.inWaiting())
        msg2 = str(msg, encoding='ascii')
        msg2 = msg2.replace("\r\n", "")
        return msg2

    def validate(self, msg):
        """
        Validate answer message.
        Args:
            msg: bytes of message
        Returns:
            True if msg is OK
            False if msg is ??
            None if unknown
        """
        msg2 = str(msg, encoding='ascii')
        valid = ("\r\n" in msg2) and ("OK" in msg2)
        invalid = ("\r\n" in msg2) and ("??" in msg2)
        if valid:
            return True
        elif invalid:
            return False
        else:
            return None

    def reset(self):
        """
        Restart MCU of the device.
        """
        self.port.write(b"rst\n")
        sleep(10*self.delay)
        old = self.port.read(self.port.inWaiting()) #discard what remains

    def conversion_time_calc(self, ch, t):
        """
        Convert set time from arb unit to actual microseconds.
        Args:
            ch: integer of channel (1 to 8)
            t:  conversion time setting (2,3,-127)
        Return:
            conversion time in microseconds (int)
        """
        if not(ch in self.settings.keys()):
            raise Exception(
                f'MD_ADC_v2: Channel {ch} not in {self.settings.keys()}')

        cont = self.settings[ch]['cont']
        chop = self.settings[ch]['chop']
        tt_idx = cont*2 + chop
        A, B, t_min, t_max = self.time_table[tt_idx]
        if t > t_max:
            t = t_max
        elif t < t_min:
            t = t_min
        time_us = (A*t + B)/self.clk
        return int(time_us)+1

    def voltage_calc(self, ch, val):
        """
        Convert ADC value to voltage based on range.
        Formula is A*(val*1.0/B) + C and A,B,C are saved in voltage_table
        Args:
            ch: integer with channel number (from 1 to 8)
            val: ADC value (from 0 to 2**24)
        Return:
            Float voltage
        """
        try:
            A, B, C = self.voltage_table[self.settings[ch]['range']]
        except:
            raise Exception(
                f'MD_ADC_v2: Channel {ch} not in {self.settings.keys()} or does not have range value.')
        return A*(val*1.0/B) + C

    def get_conversion_times(self):
        """
        Get conversion time in microseconds for each channel.
        Returns:
            Dictionary with keys as channel.
        """
        return {ch: self.conversion_time_calc(ch, self.settings[ch]['time']) for ch in self.channels}

    def apply_settings(self, setting=None, reset=True):
        """
        Apply setting dictionary to the device.
        Args:
            setting: setting dictionary, if none, than the current dict is applied
            reset: if True, the chip se restarted prior the application
        Returns:
            msgs: list of responses
            check: boolean whether application was correct
        """
        if not(setting is None):
            self.settings = setting
        if reset:
            self.reset()
        commands = []
        for key in self.channels:
            msg_chop = bytes(
                f"{'on' if self.settings[key]['chop'] else 'off'}_chop{key}\n", encoding='ascii')
            msg_time = bytes(
                f"time{key}={int(self.settings[key]['time']):d}\n", encoding='ascii')
            msg_range = bytes(
                f"range{key}={int(self.settings[key]['range']):d}\n", encoding='ascii')
            msg_cont = bytes(
                f"{'on' if self.settings[key]['cont'] else 'off'}_cont{key}\n", encoding='ascii')
            commands = commands + [msg_chop, msg_time, msg_range, msg_cont]

        msgs = b''
        for cmd in commands:
            self.port.write(cmd)
            sleep(self.delay)
            msg = self.port.read(self.port.inWaiting())
            msgs = msgs + msg

        check = (str(msgs, encoding='ascii').count("OK") == len(commands))
        return msgs, check

    def read_singles(self, channels=None):
        """
        Single read of ADC voltage.
        Args:
            channels: list of channels to be read (integers from 1 to 8)
        Returns:
            results: dictionary with channels as keys
        """
        if channels is None:
            channels = self.channels
        cmds = [bytes(f"single{ch}\n", encoding='ascii') for ch in channels]
        msgs = b''
        results = {}
        for cmd in cmds:
            self.port.write(cmd)
            sleep(self.delay)
            msg = self.port.read(self.port.inWaiting())
            msgs = msgs+msg
        msgs = str(msgs, encoding='ascii')
        for msg in msgs.split("\r\n"):
            if len(msg) > 0:
                try:
                    a, b = msg.split(',')
                    ch = int(a)
                    val = int(b)
                    V = self.voltage_calc(ch, val)
                    results[int(a)] = V
                except:
                    print(f"MD_ADC_v2: Parsing {msg} as single count failed.")
                    pass
        return results


## Example use
##DefaulSettings = {
##    i: {"chop": False, "cont": False, "time": 127, "range": 0}
##    for i in range(1, 9)
##}
##X = MD_ADC_v2('COM10', settings=DefaulSettings)
