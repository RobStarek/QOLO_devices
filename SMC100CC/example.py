from smcStack import SMCStack

#Construction dictionary
#Motors are assigned to given keys, its addresses, labels and correction are assigned with tuple
#For example, under key 1, there is a motor with address 1, automatic label and correction 47.5 degrees.
ConstructionDict = {
    1 : (1, None, 47.5),
    2 : (2, None, 0),
    3 : (3, "My motor", 0)
}

#Initialize SMC stack object
Ms = SMCStack('COM3', ConstructionDict, 1) #init stack
Mov1 = {1: 20, 2:30} #define movement dictionary, with keys corresponding to motors and values to absolute positions
Ms(Mov1) #perform collective movement

#Control individual motors
Ms[2](45) #move motor with key 2 to 45 degrees
#...
Ms.Close() #close port at the end
