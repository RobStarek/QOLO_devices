from pyAndorSDK3 import AndorSDK3, andor_sdk3_exceptions, utils
from time import sleep
#utils.add_library_path(r'C:\Program Files\Andor SDK3')
sdk3 = AndorSDK3()

print("Andor cooling stopping...")
with sdk3.GetCamera(0) as cam:
    cam.TemperatureControl = '0.0'
    cam.SensorCooling = False
    sleep(1)
    for i in range(5):
        temp_string = f'Temp. status: {cam.TemperatureStatus:s} | {cam.SensorTemperature:.1f} C'
        print(temp_string)
        sleep(1)
sleep(4)

 
