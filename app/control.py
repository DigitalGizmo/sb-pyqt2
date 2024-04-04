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
    # Most of this module is analogous to svelte Panel

    # These signals are internal to control.py
    startPressed = qtc.pyqtSignal()
    plugEventDetected = qtc.pyqtSignal()
    plugInToHandle = qtc.pyqtSignal(int)
    unPlugToHandle = qtc.pyqtSignal(int)
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

        # # Large text
        # self.label.setFont(QFont('Arial',30))
        # self.setGeometry(20,80,1200,400)

        # Small text for debug
        self.label.setFont(QFont('Arial',16))
        self.setGeometry(15,80,600,250)

        self.setCentralWidget(self.label)
        self.model = Model()

        # --- timers --- 
        self.bounceTimer=qtc.QTimer()
        self.bounceTimer.timeout.connect(self.continueCheckPin)
        self.bounceTimer.setSingleShot(True)
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
        self.plugEventDetected.connect(lambda: self.bounceTimer.start(300))
        self.plugInToHandle.connect(self.model.handlePlugIn)
        self.unPlugToHandle.connect(self.model.handleUnPlug)

        # Eventst from model.py
        self.model.displayTextSignal.connect(self.displayText)
        self.model.setLEDSignal.connect(self.setLED)
        # self.model.pinInEvent.connect(self.setPinsIn)
        self.model.blinkerStart.connect(self.startBlinker)
        self.model.blinkerStop.connect(self.stopBlinker)
        # self.model.checkPinsInEvent.connect(self.checkPinsIn)
        self.model.displayCaptionSignal.connect(self.displayCaptions)
        self.model.stopCaptionSignal.connect(self.stopCaptions)
        self.areCaptionsContinuing = True

        # Initialize the I2C bus:
        i2c = busio.I2C(board.SCL, board.SDA)
        self.mcp = MCP23017(i2c) # default address-0x20
        # self.mcpRing = MCP23017(i2c, address=0x22)
        self.mcpLed = MCP23017(i2c, address=0x21)

        # -- Make a list of pins for each bonnet, set input/output --
        # Plug tip, which will trigger interrupts
        self.pins = []
        for pinIndex in range(0, 16):
            self.pins.append(self.mcp.get_pin(pinIndex))
        # Will be initiallized to pull.up in reset()

        # LEDs 
        # Tried to put these in the Model/logic module -- but seems all gpio
        # needs to be in this base/main module
        self.pinsLed = []
        for pinIndex in range(0, 12):
            self.pinsLed.append(self.mcpLed.get_pin(pinIndex))
        # Set to output in reset()

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
                print(f"* Interrupt - pin number: {pin_flag} changed to: {self.pins[pin_flag].value}")

                # Test for phone jack vs start and stop buttons
                if (pin_flag < 12):
                    # Don't restart this interrupt checking if we're still
                    # in the pause part of bounce checking
                    if (not self.just_checked):
                        self.pinFlag = pin_flag

                        # print(f"pin {pin_flag} from model = {self.model.getPinsIn(pin_flag)}")
                        if (not self.awaitingRestart):

                            # Disabling wiggle check
                            # # If this pin is in, delay before checking
                            # # to protect against inadvertent wiggle
                            if (self.model.getIsPinIn(pin_flag) == True):

                                # print(f" ** pin {pin_flag} is already in - so wiggle wait")
                                # This will trigger a pause
                                self.wiggleDetected.emit()

                            else: # pin is not in, new event

                                # elif (not self.awaitingRestart):

                                # do standard check
                                self.just_checked = True
                                # The following signal starts a timer that will continue
                                # the check. This provides bounce protection
                                # This signal is separate from the main python event loop
                                # This emit will start bounc_timer with 300
                                self.plugEventDetected.emit()

                        else: # awaiting restart
                            print(" ** pin activity while awaiting restart")
                            self.just_checked = False

                else:
                    print("got to interupt 12 or greater")
                    if (pin_flag == 13 and self.pins[13].value == False):
                        # if (self.pins[13].value == False):
                        self.startPressed.emit()
                    # self.pinsLed[0].value = True
        # As of 2024-03-23 bounctime had been 100, changed to 150
        GPIO.add_event_detect(interrupt, GPIO.BOTH, callback=checkPin, bouncetime=50)

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

        # self.setLED(10, True)          
        # self.setLED(11, True)          

    def continueCheckPin(self):
        # Not able to send param through timer, so pinFlag has been set globaly
        print(f" * In continue, pinFlag = {str(self.pinFlag)} " 
              f"  * value: {str(self.pins[self.pinFlag].value)}")

        if (self.pins[self.pinFlag].value == False): # grounded by tip
            """
            False/grouded, then this event is a plug-in
            """
            # Send pin index to model.py as an int 
            # Model uses signals for LED, text and pinsIn to set here
            self.plugInToHandle.emit(self.pinFlag)
        else: # pin flag True, still, or again, high
            # Resume here - how do we get here??

            # print(f"  ** got to pin disconnected in continueCheckPin")


            # was this a legit unplug?
            # if (self.pinsIn[self.pinFlag]): # was plugged in

            # if (self.model.getPinsIn(self.pinFlag)):
            if (self.model.getIsPinIn(self.pinFlag)):
                # print(f"Pin {self.pinFlag} has been disconnected \n")

                # pinsIn : instead of True/False make it hold line index
                print(f" * pin {self.pinFlag} was in - handleUnPlug")

                # On unplug we can't tell which line electonicaly 
                # (diff in shaft is gone), so rely on pinsIn info
                self.unPlugToHandle.emit(self.pinFlag) # , self.whichLinePlugging
                # Model handleUnPlug will set pinsIn false for this on

            else:
                print(" ** got to pin true (changed to high), but not pin in")
        
        # Delay setting just_check to false in case the plug is wiggled
        # qtc.QTimer.singleShot(300, self.delayedFinishCheck)
        # qtc.QTimer.singleShot(70, self.delayedFinishCheck)
        qtc.QTimer.singleShot(150, self.delayedFinishCheck)


    def delayedFinishCheck(self):
        # This just delay resetting just_checked
        print(" * delayed finished check \n")
        self.just_checked = False

        # Experimental
        self.mcp.clear_ints()  # This seems to keep things fresh


    def checkWiggle(self):
        print(" * got to checkWiggle")
        # self.wiggleTimer.stop() -- now singleShot
        # Check whether the pin still grounded
        # if no longer grounded, proceed with event detection
        if (not self.pins[self.pinFlag].value == False):
            # The pin is no longer in
            self.just_checked = True
            self.plugEventDetected.emit()
        # else: still grounded -- do nothing
            # pin has been removed during pause

    def displayText(self, msg):
        self.label.setText(msg)        

    def setLED(self, flagIdx, onOrOff):
        self.pinsLed[flagIdx].value = onOrOff     

    def blinker(self):
        self.pinsLed[self.pinToBlink].value = not self.pinsLed[self.pinToBlink].value
        # print("blinking value: " + str(self.pinsLed[self.pinToBlink].value))
        
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

    def stopCaptions(self):
        self.areCaptionsContinuing = False

    # Mostly from ChatGPT
    def displayCaptions(self, fileType, file_name):
        with open('captions/' + fileType + '/' + file_name + '.srt', 'r') as f:
            captions = f.read().split('\n\n')
        self.areCaptionsContinuing = True
        self.caption_index = 0

        def time_str_to_ms(time_str):
            hours, minutes, seconds_ms = time_str.split(':')
            seconds, milliseconds = seconds_ms.split(',')
            return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(milliseconds)

        def display_next_caption():
            # print('got to display_next_caption')
            nonlocal self
            if self.caption_index < len(captions):
                caption = captions[self.caption_index]
                # print(f'full entry: {caption}')
                if '-->' in caption:
                    number, time, text = caption.split('\n', 2)
                    # print(f'time: {time}, text: {text}')
                    # self.caption_label.setText(text)

                    # Stop if unplugged
                    if (self.areCaptionsContinuing):
                        self.displayText(text)

                    # Proccess time
                    times = time.split(' --> ')
                    # print(f'times[0]: {times[0]}')
                    start_time_ms = time_str_to_ms(times[0])
                    end_time_ms = time_str_to_ms(times[1])
                    duration_ms = end_time_ms - start_time_ms

                    if (self.areCaptionsContinuing):
                        qtc.QTimer.singleShot(duration_ms, display_next_caption)
                self.caption_index += 1

        display_next_caption()

app = qtw.QApplication([])

win = MainWindow()
win.show()

sys.exit(app.exec_())