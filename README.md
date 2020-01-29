# QOLO_devices
Collection of modules for controlling our laboratory devices.

## SMC100CC
Controller module for Newport SMC100CC motor driver (https://www.newport.com/p/SMC100CC). It is used to control motion of linear and rotational Newport motors via serial communication.
It's purpose is to provide a short and readable way to control the motors.

### Content
* smc100py3.py - base module for individual controllers
* smcStack.py - extension module for easier management of multiple controllers
* example.py - example how to use smcStack.py.

### Example
```python
#Define motors, their addresses, labels and correction offsets.
ConstructionDict = {
    1 : (1, None, 5.42),
    2 : (2, None, 4.5),
    3 : (3, "My motor", 3)
}
Ms = SMCStack('COM3', ConstructionDict, 1) #initialize stack
Mov1 = {1: 20, 2:30} #define movement dictionary
Ms(Mov1) #perform collective movement
#...
Ms[2](45) #move motor 2 individually
#...
Ms.Close() #close port, when it is not needed anymore
```    
***

## MDADC2
A control module for QOLO custom ADC box v2 (from Michal Dudka). This box has AD7734 ADC inside and it is controlled by STM microcontroller via virtual serial link over USB.

The provided module is used to read voltages from given channels.

### Example
```python
#Define settings
DefaulSettings = {
    i: {"chop": False, "cont": False, "time": 127, "range": 0}
    for i in range(1, 9)
}
#Create instance
ADC = MD_ADC_v2('COM3', settings=DefaulSettings)
#Read all channels
data = ADC()
#Read voltages from specified channels
data12 = ADC([1,2])
#...
#close port when done
ADC.close()
```
