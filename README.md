# QOLO_devices
Collection of modules for controlling our laboratory devices.

## SMC100CC
Controller module for Newport SMC100CC motor driver (https://www.newport.com/p/SMC100CC). It is used to control motion of linear and rotational Newport motors via serial communication.
It's purpose is to provide a short and readable way to control the motors.

### Content:
* smc100py3.py - base module for individual controllers
* smcStack.py - extension module for easier management of multiple controllers
* example.py - example how to use smcStack.py.

## MDADC2
A control module for QOLO custom ADC box v2 (from Michal Dudka).
(todo)
