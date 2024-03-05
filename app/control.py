import sys
# import json
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5.QtGui import QFont

import vlc
import board
import busio
from digitalio import Direction, Pull
from RPi import GPIO
from adafruit_mcp230xx.mcp23017 import MCP23017

from model import Model

class MainWindow(qtw.QMainWindow): 
    # Almost all of this should be in separate module analogous to svelte Panel

    startPressed = qtc.pyqtSignal()
    plugEventDetected = qtc.pyqtSignal()
    plugInToHandle = qtc.pyqtSignal(dict)
    unPlugToHandle = qtc.pyqtSignal(int, int)
    wiggleDetected = qtc.pyqtSignal()

    def __init__(self):
        # self.pygame.init()
        super().__init__()

        # ------- pyqt window ----
        self.setWindowTitle("You Are the Operator")
        self.label = qtw.QLabel(self)
        self.label.setWordWrap(True)
        # self.label.setText("Keep your ears open for incoming calls! ")
        self.label.setAlignment(qtc.Qt.AlignTop)

        # self.label.setFont(QFont('Arial',30))
        # self.setGeometry(20,80,1200,400)
        self.label.setFont(QFont('Arial',16))
        self.setGeometry(15,80,600,250)

        self.setCentralWidget(self.label)

        self.model = Model()

        # ------ phone call logic------
        self.whichLinePlugging = -1

        # --- timers --- 
        self.bounceTimer=qtc.QTimer()
        self.bounceTimer.timeout.connect(self.continueCheckPin)
        self.blinkTimer=qtc.QTimer()
        self.blinkTimer.timeout.connect(self.blinker)
        # Supress interrupt when plug is just wiggled
        self.wiggleDetected.connect(lambda: self.wiggleTimer.start(80))
        self.wiggleTimer=qtc.QTimer()
        self.wiggleTimer.setSingleShot(True)
        self.wiggleTimer.timeout.connect(self.checkWiggle)

        # Self (control) for gpio related, self.model for audio
        self.startPressed.connect(self.startReset)
        # self.startPressed.connect(self.model.handleStart)

        # Bounce timer less than 200 cause failure to detect 2nd line
        # Tested with 100
        self.plugEventDetected.connect(lambda: self.bounceTimer.start(200))
        self.plugInToHandle.connect(self.model.handlePlugIn)
        self.unPlugToHandle.connect(self.model.handleUnPlug)

        # Eventst from model.py
        self.model.displayText.connect(self.setScreenLabel)
        self.model.ledEvent.connect(self.setLED)
        # self.model.pinInEvent.connect(self.setPinsIn)
        self.model.blinkerStart.connect(self.startBlinker)
        self.model.blinkerStop.connect(self.stopBlinker)
        # self.model.checkPinsInEvent.connect(self.checkPinsIn)



        # Initialize the I2C bus:
        i2c = busio.I2C(board.SCL, board.SDA)
        self.mcp = MCP23017(i2c) # default address-0x20
        self.mcpRing = MCP23017(i2c, address=0x22)
        self.mcpLed = MCP23017(i2c, address=0x21)

        # -- Make a list of pins for each bonnet, set input/output --
        # Plug tip, which will trigger interrupts
        self.pins = []
        for pinIndex in range(0, 16):
            self.pins.append(self.mcp.get_pin(pinIndex))
        # # Set to input - later will get intrrupt as well
        # for pinIndex in range(0, 16):
        #     self.pins[pinIndex].direction = Direction.INPUT
        #     self.pins[pinIndex].pull = Pull.UP

        # Stereo "ring" which will detect 1st vs 2nd line
        self.pinsRing = []
        for pinIndex in range(0, 12):
            self.pinsRing.append(self.mcpRing.get_pin(pinIndex))
        # # Set to input
        # for pinIndex in range(0, 12):
        #     self.pinsRing[pinIndex].direction = Direction.INPUT
        #     self.pinsRing[pinIndex].pull = Pull.UP

        # LEDs 
        # Tried to put these in the Model/logic module -- but seems all gpio
        # needs to be in this base/main module
        self.pinsLed = []
        for pinIndex in range(0, 12):
            self.pinsLed.append(self.mcpLed.get_pin(pinIndex))
        # In Reset
        # # Set to output
        # for pinIndex in range(0, 12):
        #    self.pinsLed[pinIndex].switch_to_output(value=False)

        # -- Set up Tip interrupt --
        self.mcp.interrupt_enable = 0xFFFF  # Enable Interrupts in all pins
        # self.mcp.interrupt_enable = 0xFFF  # Enable Interrupts first 12 pins
        # self.mcp.interrupt_enable = 0b0000111111111111  # Enable Interrupts in pins 0-11 aka 0xfff

        # If intcon is set to 0's we will get interrupts on both
        #  button presses and button releases
        self.mcp.interrupt_configuration = 0x0000  # interrupt on any change
        self.mcp.io_control = 0x44  # Interrupt as open drain and mirrored
        # put this in startup?

        self.mcp.clear_ints()  # Interrupts need to be cleared initially


        self.reset()

        # connect either interrupt pin to the Raspberry pi's pin 17.
        # They were previously configured as mirrored.
        GPIO.setmode(GPIO.BCM)
        interrupt = 17
        GPIO.setup(interrupt, GPIO.IN, GPIO.PUD_UP)  # Set up Pi's pin as input, pull up

        # -- code for detection --
        def checkPin(port):
            """Callback function to be called when an Interrupt occurs.
            The signal for pluginEventDetected calls a timer -- it can't send
            a parameter, so the work-around is to set pin_flag as a global.
            """
            for pin_flag in self.mcp.int_flag:
                # print("Interrupt connected to Pin: {}".format(port))
                print(f"Interrupt - pin number: {pin_flag} changed to: {self.pins[pin_flag].value}")

                # Test for phone jack vs start and stop buttons
                if (pin_flag < 12):
                    # Don't restart this interrupt checking if we're still
                    # in the pause part of bounce checking
                    if (not self.just_checked):
                        self.pinFlag = pin_flag

                        # print(f"pin {pin_flag} from model = {self.model.getPinsIn(pin_flag)}")
                        if (not self.awaitingRestart):

                            # If this pin is in, delay before checking
                            # to protect against inadvertent wiggle
                            # if (self.pinsIn[pin_flag]):
                            # if (self.model.getPinsIn(pin_flag)):
                            if (self.model.getPinInLine(pin_flag) >= 0):

                                print(f" ++ pin {pin_flag} is already in")
                                # This will trigger a pause
                                self.wiggleDetected.emit()

                            else: # pin is not in, new event


                            # elif (not self.awaitingRestart):
                                # do standard check
                                self.just_checked = True
                                # The following signal starts a timer that will continue
                                # the check. This provides bounce protection
                                # This signal is separate from the main python event loop
                                self.plugEventDetected.emit()

                        else: # awaiting restart
                            print("pin activity while awaiting restart")
                            self.just_checked = False

                else:
                    print("got to interupt 12 or greater")
                    if (pin_flag == 13 and self.pins[13].value == False):
                        # if (self.pins[13].value == False):
                        self.startPressed.emit()
                    # self.pinsLed[0].value = True

        GPIO.add_event_detect(interrupt, GPIO.BOTH, callback=checkPin, bouncetime=100)

    def reset(self):
        self.label.setText("Press the Start button to begin!")
        self.just_checked = False
        self.pinFlag = 15
        self.pinToBlink = 0
        self.awaitingRestart = False

        # Set to input - later will get intrrupt as well
        for pinIndex in range(0, 16):
            self.pins[pinIndex].direction = Direction.INPUT
            self.pins[pinIndex].pull = Pull.UP

        # Set to input
        for pinIndex in range(0, 12):
            self.pinsRing[pinIndex].direction = Direction.INPUT
            self.pinsRing[pinIndex].pull = Pull.UP

        # Set to output
        for pinIndex in range(0, 12):
           self.pinsLed[pinIndex].switch_to_output(value=False)

        self.mcp.clear_ints()  # Interrupts need to be cleared initially

        if self.bounceTimer.isActive():
            self.bounceTimer.stop()
        if self.blinkTimer.isActive():
            self.blinkTimer.stop()            
        if self.wiggleTimer.isActive():
            self.wiggleTimer.stop()            

    def continueCheckPin(self):
        # Not able to send param through timer, so pinFlag has been set globaly
        # print("In continue, pinFlag = " + str(self.pinFlag) + " val: " +
        #       str(self.pins[self.pinFlag].value))

        self.bounceTimer.stop()

        if (self.pins[self.pinFlag].value == False): # grounded by cable
            """False/grouded, then this event is a plug-in
            """
            # Determine which line
            self.whichLinePlugging = 0
            # print("Stereo (Ring) pin {} aledgedly now: {}".format(self.pinFlag, self.pinsRing[self.pinFlag].value))
            if (self.pinsRing[self.pinFlag].value == True):
                self.whichLinePlugging = 1
            print(f"Pin {self.pinFlag} connected on line {self.whichLinePlugging}")
            # Send plugin info to model.py as a dict 
            # Model uses signals for LED, text and pinsIn to set here
            self.plugInToHandle.emit({"personIdx": self.pinFlag, "lineIdx": self.whichLinePlugging})
        else: # pin flag True, still, or again, high
            # was this a legit unplug?
            # if (self.pinsIn[self.pinFlag]): # was plugged in

            # if (self.model.getPinsIn(self.pinFlag)):
            if (self.model.getPinInLine(self.pinFlag) >= 0):
                # print(f"Pin {self.pinFlag} has been disconnected \n")

                # Need to indirectly determine which line is being unpluged.
                # Cant't test directly bcz stereo ring is no longer in place
                # pinsIn : instead of True/False make it hold line index

                print(f" ++ pin {self.pinFlag} was in on line {self.model.getPinInLine(self.pinFlag)}")

                # On unplug we can't tell which line electonicaly 
                # (diff in shaft is gone), so rely on pinsIn info
                self.unPlugToHandle.emit(self.pinFlag, self.whichLinePlugging)
                # Model handleUnPlug will set pinsIn false for this on

            else:
                print("got to pin true (changed to high), but not pin in")
        
        # print("finished check \n")

        # self.mcp.clear_ints()
        # self.just_checked = False
        # Delay setting just_check to false in case the plug is wiggled
        qtc.QTimer.singleShot(300, self.delayedFinishCheck)


    def delayedFinishCheck(self):
        print("delayed finished check \n")
        self.just_checked = False

    def checkWiggle(self):
        print("got to checkWiggle")
        # self.wiggleTimer.stop() -- now singleShot
        # Check whether the pin still grounded
        # if no longer grounded, proceed with event detection
        if (not self.pins[self.pinFlag].value == False):
            # The pin is no longer in
            self.just_checked = True
            self.plugEventDetected.emit()
        # else: still grounded -- do nothing
            # pin has been removed during pause

    def setScreenLabel(self, msg):
        self.label.setText(msg)        

    def setLED(self, flagIdx, onOrOff):
        self.pinsLed[flagIdx].value = onOrOff     

    def blinker(self):
        # print("blinking")
        self.pinsLed[self.pinToBlink].value = not self.pinsLed[self.pinToBlink].value
        
    def startBlinker(self, personIdx):
        self.pinToBlink = personIdx
        self.blinkTimer.start(600)

    def stopBlinker(self):
        if self.blinkTimer.isActive():
            self.blinkTimer.stop()
    def getAnyPinsIn(self):
        anyPinsIn = False

        for pinIndex in range(0, 12):
            if self.pins[pinIndex].value == False:
                anyPinsIn = True
        return anyPinsIn

    def startReset(self):
        print("reseting, starting")
        self.awaitingRestart = True
        self.model.stopAllAudio()
        self.model.stopTimers()
        # _anyPinsIn = self.getAnyPinsIn()
        # print(f"in reset, anyPinsIn =  {_anyPinsIn}")
        # if (_anyPinsIn):
        if (self.getAnyPinsIn()):
            self.label.setText("Remove phone plugs and press Start again")
        else:
            self.reset()
            self.model.handleStart()

app = qtw.QApplication([])

win = MainWindow()
win.show()

sys.exit(app.exec_())