# import sys
import json
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtGui as qtg
from PyQt5 import QtCore as qtc
import vlc

conversationsJsonFile = open('conversations.json')
conversations = json.load(conversationsJsonFile)
personsJsonFile = open('persons.json')
persons = json.load(personsJsonFile)

class Model(qtc.QObject):
    """Main logic patterned after software proto
    """
    # The following signals are connected in/ called from control.py
    displayTextSignal = qtc.pyqtSignal(str)
    setLEDSignal = qtc.pyqtSignal(int, bool)
    # pinInEvent = qtc.pyqtSignal(int, bool)
    blinkerStart = qtc.pyqtSignal(int)
    blinkerStop = qtc.pyqtSignal()
    displayCaptionSignal = qtc.pyqtSignal(str)
    stopCaptionSignal = qtc.pyqtSignal()
    # Doesn't seem to be used
    checkPinsInEvent = qtc.pyqtSignal() 
    
    # The following signals are local
    # Need to avoid thread conflicts
    setTimeToNextSignal = qtc.pyqtSignal(int)
    playRequestCorrectSignal = qtc.pyqtSignal()

    buzzInstace = vlc.Instance()
    buzzPlayer = buzzInstace.media_player_new()
    buzzPlayer.set_media(buzzInstace.media_new_path("/home/piswitch/Apps/sb-audio/buzzer.mp3"))

    toneInstace = vlc.Instance()
    tonePlayer = toneInstace.media_player_new()
    toneEvents = tonePlayer.event_manager()
    toneMedia = toneInstace.media_new_path("/home/piswitch/Apps/sb-audio/outgoing-ring.mp3")
    tonePlayer.set_media(toneMedia)

    # vlcInstances = [vlc.Instance(), vlc.Instance()]
    # vlcPlayers = [vlcInstances[0].media_player_new(), vlcInstances[1].media_player_new()]
    # vlcEvents = [vlcPlayers[0].event_manager(), vlcPlayers[1].event_manager()]

    vlcInstance = vlc.Instance()
    vlcPlayer = vlcInstance.media_player_new()
    vlcEvent = vlcPlayer.event_manager()

    def __init__(self):
        super().__init__()
        self.callInitTimer = qtc.QTimer()
        self.callInitTimer.setSingleShot(True)
        self.callInitTimer.timeout.connect(self.initiateCall)

        self.reconnectTimer = qtc.QTimer()
        self.reconnectTimer.setSingleShot(True)
        self.reconnectTimer.timeout.connect(self.reCall)
        # reconnectTimer = undefined
        # audioCaption = " "

        self.silencedCalTimer = qtc.QTimer()
        self.silencedCalTimer.setSingleShot(True)
        self.silencedCalTimer.timeout.connect(self.silencedCallEnded)

        self.playRequestCorrectSignal.connect(self.playRequestCorrect)
        self.setTimeToNextSignal.connect(self.setTimeToNext)

        self.reset()

    def reset(self):
        self.stopAllAudio()
        self.stopTimers()

        # Put pinsIn here in model where it's used more often
        # rather than in control which would require a lot of signaling.
        self.pinsIn = [False,False,False,False,False,False,False,False,False,False,False,False,False,False]
        # self.pinsInLine = [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]
        
        self.currConvo = 0
        self.currCallerIndex = 0
        self.currCalleeIndex = 0
        # self.whichLineInUse = -1
        # self.prevLineInUse = -1

        self.incrementJustCalled = False
        # self.reCallLine = 0 # Workaround timer not having params
        self.silencedCallLine = 0 # Workaround timer not having params
        # self.requestCorrectLine = 0 # Workaround timer not having params
        # self.interruptingCallInHasBeenInitiated = False

        self.NO_UNPLUG_STATUS = 0
        self.WRONG_NUM_IN_PROGRESS = 1
        # self.AWAITING_INTERRUPT = 1
        # self.DURING_INTERRUPT_SILENCE = 2
        self.REPLUG_IN_PROGRESS = 3
        self.CALLER_UNPLUGGED = 5

        self.phoneLine = {
                "isEngaged": False,
                "unPlugStatus": self.NO_UNPLUG_STATUS,
                "caller": {"index": 99, "isPlugged": False},
                "callee": {"index": 99, "isPlugged": False}
                # "audioTrack": vlc.MediaPlayer("/home/piswitch/Apps/sb-audio/1-Charlie_Operator.mp3")
            }

        self.displayTextSignal.emit("Keep your ears open for incoming calls!")

    def stopTimers(self):
        if self.callInitTimer.isActive():
            self.callInitTimer.stop()
        if self.reconnectTimer.isActive():
            self.reconnectTimer.stop()
        if self.silencedCalTimer.isActive():
            self.silencedCalTimer.stop()


    def stopAllAudio(self):
        # if self.callInitTimer.isActive():
        #     self.callInitTimer.stop()

        self.buzzPlayer.stop()
        self.tonePlayer.stop()
        # self.vlcPlayers[0].stop()
        self.vlcPlayer.stop()
    # remove
    # def setPinInLine(self, pinIdx, lineIdx):
    #     self.pinsInLine[pinIdx] = lineIdx

    def setPinIn(self, pinIdx, value):
        self.pinsIn[pinIdx] = value

    # Remove
    # def getPinInLine(self, pinIdx):
    #     return self.pinsInLine[pinIdx]
    
    # Used by wiggle detect in control
    def getIsPinIn(self, pinIdx):
        return self.pinsIn[pinIdx]

    def initiateCall(self):
        self.incrementJustCalled = False

        if (self.currConvo < 9):
            print(f'Setting currCallerIndex to {conversations[self.currConvo]["caller"]["index"]}'
                  f' currConvo: {self.currConvo}')
            self.currCallerIndex =  conversations[self.currConvo]["caller"]["index"]
            # Set "target", person being called
            self.currCalleeIndex = conversations[self.currConvo]["callee"]["index"]
            # This just rings the buzzer. Next action will
            # be when user plugs in a plug - in Panel.svelte drag end: handlePlugIn
            # buzzTrack.volume = .6   
            self.buzzPlayer.play()
            self.blinkerStart.emit(conversations[self.currConvo]["caller"]["index"])
            self.displayTextSignal.emit("Incoming call..")
            
            print(f'- New convo {self.currConvo} being initiated by: ' 
                    f'{persons[conversations[self.currConvo]["caller"]["index"]]["name"]}')
        else:
            # Play congratulations
            print("Congratulations - done!")
            self.playFinished()

    def playHello(self, _currConvo): # , lineIndex
        # print(" -- got to playHello")
        media = self.vlcInstance.media_new_path("/home/piswitch/Apps/sb-audio/" + 
            conversations[_currConvo]["helloFile"] + ".mp3")
        self.vlcPlayer.set_media(media)
        # For convo idxs 3 and 7 there is no full convo, so end after hello.
        # Attach event before playing
        if (_currConvo == 3 or  _currConvo == 7):
            print(f"** got to currConv = 3 or 7 **")
            self.vlcEvent.event_attach(vlc.EventType.MediaPlayerEndReached, 
                self.endOperatorOnlyHello) #  _currConvo, ,lineIndex
        # Proceed with playing -- event may or may not be attached            
        self.vlcPlayer.play()
        # Send msg to screen
        self.displayTextSignal.emit(conversations[_currConvo]["helloText"])

    def endOperatorOnlyHello(self, event): # , lineIndex
            print("  - About to detach vlcEvent in endOperatorOnlyHello")
            self.vlcEvent.event_detach(vlc.EventType.MediaPlayerEndReached) 
            #  supress further callbacks self.supressCallback
            # Don't know what this did in software proto
            # setHelloOnlyCompleted(lineIndex)
            self.clearTheLine() # lineIndex
            print(f" ** Hello-only ended.  Bump currConvo from {self.currConvo}")
            self.currConvo += 1
            # Timers can't be started from another thread
            self.setTimeToNextSignal.emit(1000)

    def playConvo(self, currConvo): # , lineIndex
        """
        This just plays the outgoing tone and then starts the full convo
        """
        print(f" -- got to play convo, currConvo: {currConvo}")
        # Long VLC way of creating callback
        self.toneEvents.event_attach(vlc.EventType.MediaPlayerEndReached, 
            self.playFullConvo, currConvo) # playFullConvo(currConvo, lineIndex)
        self.tonePlayer.set_media(self.toneMedia)
        self.tonePlayer.play()

    # def playFullConvoFromEvent(self, event, _currConvo, lineIndex):
    #     """ This allows playing fullConvo without sending the event param.
    #     This happens when the caller is unplugged
    #     """
    #     print("inf playFullConvoFromEvent trying to relay to fullConvo")
    #     self.playFullConvo(self, _currConvo, lineIndex)

    def playFullConvo(self, event, _currConvo):
        # print(f"fullconvo, convo: {_currConvo}, linedx: {lineIndex}, dummy: {dummy}")
        # self.outgoingTone.stop()

        # Stop tone events from calling more times
        print("  - About to detach toneEvent playFullConvo")
        
        self.toneEvents.event_detach(vlc.EventType.MediaPlayerEndReached) # self.vlcEventdetached     

        print(f" -- PlayFullConvo {_currConvo}")
        # Set callback for convo track finish
        self.vlcEvent.event_attach(vlc.EventType.MediaPlayerEndReached, 
            self.setCallCompleted) #  _currConvo, 
        media = self.vlcInstance.media_new_path("/home/piswitch/Apps/sb-audio/" + 
            conversations[_currConvo]["convoFile"] + ".mp3")
        self.vlcPlayer.set_media(media)
        self.vlcPlayer.play()
        # self.displayTextSignal.emit(conversations[_currConvo]["convoText"])

        # self.display_captions('captions/2-Charlie_Calls_Olive.srt')
        self.displayCaptionSignal.emit(conversations[_currConvo]["convoFile"])

        # self.displayTextSignal.emit(conversations[_currConvo]["helloText"])

    # Called after caller unplugs. Redundant - workaround doe to not needing to 
    # stop  calling event. -- must be a better way!
    def playFullConvoNoEvent(self, _currConvo): # , lineIndex
        # print(f"fullconvo, convo: {_currConvo}, linedx: {lineIndex}, dummy: {dummy}")
        # self.outgoingTone.stop()

        #  no tone event to stop
        self.displayTextSignal.emit(conversations[_currConvo]["convoText"])

        print(f"-- PlayFullConvoNoEvent {_currConvo}")
        # Set callback for convo track finish
        self.vlcEvent.event_attach(vlc.EventType.MediaPlayerEndReached, 
            self.setCallCompleted) #  _currConvo, 
        media = self.vlcInstance.media_new_path("/home/piswitch/Apps/sb-audio/" + 
            conversations[_currConvo]["convoFile"] + ".mp3")
        self.vlcPlayer.set_media(media)
        self.vlcPlayer.play()
        # needs to be dynamic
        self.displayCaptionSignal.emit(conversations[_currConvo]["convoFile"])


    def playWrongNum(self, pluggedPersonIdx): # , lineIndex
        print(f"got to play wrong number, currConvo: {self.currConvo}")
        # Long VLC way of creating callback
        self.toneEvents.event_attach(vlc.EventType.MediaPlayerEndReached, 
            self.playFullWrongNum, pluggedPersonIdx) # playFullConvo(currConvo, lineIndex)
        self.tonePlayer.set_media(self.toneMedia)
        self.tonePlayer.play()

    def playFullWrongNum(self, event, pluggedPersonIdx): # , lineIndex
        # wrongNumFile = persons[pluggedPersonIdx]["wrongNumFile"]
        # disable event
        print("  - About to detacth toneEventin playFullWrongNum")

        self.toneEvents.event_detach(vlc.EventType.MediaPlayerEndReached) 

        self.displayTextSignal.emit(persons[pluggedPersonIdx]["wrongNumText"])

        print(f"-- PlayWrongNun person {pluggedPersonIdx}")
        # Set callback for wrongNUm track finish

        self.vlcEvent.event_attach(vlc.EventType.MediaPlayerEndReached, 
            self.startPlayRequestCorrect) #  _currConvo, 
        
        media = self.vlcInstance.media_new_path("/home/piswitch/Apps/sb-audio/" + 
            persons[pluggedPersonIdx]["wrongNumFile"] + ".mp3")
        self.vlcPlayer.set_media(media)
        self.vlcPlayer.play()


    def startPlayRequestCorrect(self, event): # , lineIndex
        print("  - About to detach vlcEvent in startPlayRequestCorrect")

        self.vlcEvent.event_detach(vlc.EventType.MediaPlayerEndReached)

        # self.requestCorrectLine = lineIndex
        self.playRequestCorrectSignal.emit()
        # self.requestCorrectTimer.start(1000)

    # def startRequestCorrectTimer(self):
    #     self.requestCorrectTimer.start(500)

    # Reply from caller saying who caller really wants
    def playRequestCorrect(self):
        print(f"got to playRequestCorrect, currConvo: {self.currConvo}")
        # Transcript for correction
        self.displayTextSignal.emit(conversations[self.currConvo]["retryAfterWrongText"])

        print("  - About to detach vlcEvent in PlayRequestCorrect")
        self.vlcEvent.event_detach(vlc.EventType.MediaPlayerEndReached) 


        media = self.vlcInstance.media_new_path("/home/piswitch/Apps/sb-audio/" + 
            conversations[self.currConvo]["retryAfterWrongFile"] + ".mp3")
        
        self.vlcPlayer.set_media(media)
        self.vlcPlayer.play()
        # At this point we hope user unplugs wrong number
        # Will be handled by "unPlug"

    def playFinished(self):
        self.toneEvents.event_detach(vlc.EventType.MediaPlayerEndReached)         

        self.displayTextSignal.emit("Congratulations -- you finished your first shift as a switchboard operator!")
        # print(f"-- PlayFullConvo {_currConvo}, lineIndex: {lineIndex}")

        media = self.vlcInstance.media_new_path("/home/piswitch/Apps/sb-audio/" + 
            "FinishedActivity.mp3")
        self.vlcPlayer.set_media(media)
        self.vlcPlayer.play()

    # def supressCallback(self, event):
    #     print("     supress video end callback")

    # def vlcEventdetached(self, event):
    #     print(f"     event detached: {event}")

    def setTimeToNext(self, timeToWait):
        self.callInitTimer.start(timeToWait)        

    def setTimeReCall(self, _currConvo): # , lineIdx
        print("got to setTimeReCall")
        # Hack: set reCallLine globally bcz I can't send params thru timer
        # self.reCallLine = lineIdx
        # currConvo is already global
        self.reconnectTimer.start(1000)
        # recconectTimer will call reCall

    def reCall(self):
        print("got to reCall")
        # Hack: receives reCallLine globally 
        self.playHello(self.currConvo) #, self.reCallLine
        # calling playHello direclty with callback would send event param
        # self.vlcPlayers[lineIdx].stop()
        # self.setTimeToNextSignal.emit(1000)
        # self.playHello(_currConvo, lineIdx)

    # def handlePlugIn(self, pluggedIdxInfo):
    def handlePlugIn(self, personIdx):
        """triggered by control.py
        """
        # personIdx = pluggedIdxInfo['personIdx']
        # lineIdx = pluggedIdxInfo['lineIdx']
        lineIdx = 0

        # ********
        # Fresh plug-in -- aka caller not plugged
        # *******/
        # Is this new use of this line -- caller has not been plugged in.

        print(f' - Start handlePlugIn, personIdx: {personIdx}'
              f' is caller plugged: {self.phoneLine["caller"]["isPlugged"]}')
        if (not self.phoneLine["caller"]["isPlugged"]): # New line - Caller not plugged
            # Did user plug into the actual caller?
            if personIdx == self.currCallerIndex: # Correct caller
                # Turn this LED on
                self.setLEDSignal.emit(personIdx, True)
                # Set this person's jack to plugged
                # self.setPinInLine(personIdx, lineIdx)
                self.setPinIn(personIdx, True)

                # Set this line as having caller plugged
                self.phoneLine["caller"]["isPlugged"] = True
                # Set identity of caller on this line
                self.phoneLine["caller"]["index"] = personIdx;				
                # print(f' - Just set caller {self.phoneLine["caller"]["index"]} to True')
                # Set this line in use only we have gotten this success
                # self.whichLineInUse = lineIdx
                # See software app for extended debug message here
                # Stop Buzzer. 
                self.buzzPlayer.stop()
                # Blinker handdled in control.py
                self.blinkerStop.emit()

                # print(f" ++ New plugin- prev line in use: {self.prevLineInUse}")

                #  Handle case where caller was unplugged
                if (self.phoneLine["unPlugStatus"] == self.CALLER_UNPLUGGED):
                    print(f"  - Caller was unplugged")
                    """ more logic here  
                    """
                    if (self.phoneLine["callee"]["isPlugged"] < 90):
                        # if (correct callee??)
                        # Stop Hello/Request
                        print(f"  - trying to stop audio ")
                        # silence request	

                        self.vlcPlayer.stop()
                        # set line engaged
                        self.phoneLine["unPlugStatus"] = self.NO_UNPLUG_STATUS
                        self.phoneLine["Engaged"] = True
                        self.phoneLine["caller"]["isPlugged"] = True
                        # Start conversation without the ring
                        # For now anyway can't play full convo without sending event so
                        self.playFullConvoNoEvent(self.currConvo) # ,	lineIdx

                        # # If this is redo of call to be interrupted then restar timer
                        # # Disabling call interruption
                        # if (self.currConvo == 0 or self.currConvo == 4):
                        #     print('    (starting timer for call that will interrupt)')
                        #     # Move que to next call
                        #     self.currConvo += 1
                        #     # Handle to stop double increment
                        #     # self.interruptingCallInHasBeenInitiated = True
                        #     # Set awaitingInterrupt = true;
                        #     self.phoneLines[lineIdx]["unPlugStatus"] = self.AWAITING_INTERRUPT
                        #     # clearTimeout(callInitTimer)
                        #     self.setTimeToNext(11000); # less than reg 15 secs bcz no ring
                    else:
                        print('   We should not get here');
                # # Disabling multi-call
                # elif (self.prevLineInUse >= 0): # Silence other conversation, if there is one
                #     print(f'  - silencing call on line: {self.prevLineInUse}')
                #     # Set unplug status so that unplugging this silenced call will
                #     # handled correctly by..
                #     self.phoneLines[self.prevLineInUse]["unPlugStatus"] = self.DURING_INTERRUPT_SILENCE

                #     self.vlcPlayers[self.prevLineInUse].stop()
                #     # self.vlcPlayers[self.prevLineInUse].audio_set_volume(10)
                #     # Can't set volume on one instance withoug affect all
                #     # Work-around using timer
                #     # Set hacked global param. 
                #     # Fix if I figure out how to send params through timver
                #     self.silencedCallLine = self.prevLineInUse
                #     self.silencedCalTimer.start(4000)


                #     self.playHello(self.currConvo, lineIdx)
                else: # Regular, just play incoming Hello/Request
                    self.playHello(self.currConvo) # , lineIdx
                
                # Set prev for use in next call. Here??
                # print(f"setting prev line in use from {p}")
                # self.prevLineInUse = self.whichLineInUse
            else:
                print("wrong jack -- or wrong line")
                self.displayTextSignal.emit("That's not the jack for the person who is asking you to connect!")

        else: # caller is plugged
			#********
		    # Other end of the line -- caller is plugged, so this must be the other plug
			#********/
			# But first, make sure this is the line in use
            # print(f"Which line in use: {lineIdx}")
            # if (lineIdx == self.whichLineInUse): # This is the line in use
            # Whether or not this is correct callee -- turn LED on.
            self.setLEDSignal.emit(personIdx, True)
            # Set pinsIn True
            # self.setPinInLine(personIdx, lineIdx)
            self.setPinIn(personIdx, True)
            # Stop the hello operator track,  whether this is the correct
            # callee or not
            self.vlcPlayer.stop() # vlcPlayers[lineIdx]
            # Set callee -- used by unPlug even if it's the wrong number
            self.phoneLine["callee"]["index"] = personIdx
            if (personIdx == self.currCalleeIndex): # Correct callee
                print(f" - Plugged into correct callee, idx: {personIdx}")
                # Set this line as engaged
                self.phoneLine["isEngaged"] = True
                # Also set line callee plugged
                self.phoneLine["callee"]["isPlugged"] = True
                # # Silence incoming Hello/Request, if necessary
                # self.vlcPlayers[lineIdx].stop()
                self.playConvo(self.currConvo)

                # # Disableing mult-calls
                # # Set timer for next call
                # # Hard-wire to interrupt two calls
                # if (self.currConvo == 0 or self.currConvo == 4):
                #     print('    (starting timer for call that will interrupt)')
                #     # Move que to next call
                #     self.currConvo += 1
                #     # Handle to stop double increment
                #     # self.interruptingCallInHasBeenInitiated = True
                #     # Set awaitingInterrupt = true;
                #     self.phoneLines[lineIdx]["unPlugStatus"] = self.AWAITING_INTERRUPT
                #     self.setTimeToNext(15000)

                # # if (personIdx == 11 and (self.currConvo == 1)):
                # #     print("unsetting interruptingCallInHasBeenInitiated")
                # #     self.interruptingCallInHasBeenInitiated = False

            else: # Wrong number
                print("wrong number")
                self.phoneLine["unPlugStatus"] = self.WRONG_NUM_IN_PROGRESS

                self.playWrongNum(personIdx) # , lineIdx
        

    def handleUnPlug(self, personIdx): # , lineIdx
        """ triggered by control.py
        Need lineIdx!!
        """
        print( f" - Index {personIdx} Unplugged with line status of: {self.phoneLine['unPlugStatus']}\n"
               f"     while line isEngaged = {self.phoneLine['isEngaged']}"
            )
        # if not during restart!

        # If conversation is in progress -- engaged (implies correct callee)
        if (self.phoneLine["isEngaged"]):
            print(f'  - Unplugging a call in progress person id: {persons[personIdx]["name"]} ' )
            # Stop the audio
            self.vlcPlayer.stop()
            # Stop subtitles
            self.stopCaptionSignal.emit()
            # Clear Transcript 
            self.displayTextSignal.emit("Call disconnected..")

            # callee just unplugged
            if (self.phoneLine["callee"]["index"] == personIdx):  
                print('   Unplugging callee')
                # Turn off callee LED
                self.setLEDSignal.emit(self.phoneLine["callee"]["index"], False)

                # Mark callee unplugged
                self.phoneLine["callee"]["isPlugged"] = False
                self.phoneLine["isEngaged"] = False
                self.vlcPlayer.stop()	
                # Leave caller plugged in, replay hello
                self.setTimeReCall(self.currConvo) 
            # caller unplugged
            elif (self.phoneLine["caller"]["index"] == personIdx): 
                print(" Caller just unplugged")
                self.phoneLine["caller"]["isPlugged"] = False
                self.phoneLine["isEngaged"] = False
                # Also
                self.phoneLine["unPlugStatus"] = self.CALLER_UNPLUGGED
                # Turn off caller LED
                self.setLEDSignal.emit(self.phoneLine["caller"]["index"], False)
                # In this case timer can be called directly (without signal)
                # Perhaps because no call is engaged at this point
                self.setTimeToNext(1000);							

            else: 
                print('    This should not happen')

        # Phone line is not engaged -- isEngaged == False

        # # # First, maybe this is an unplug of "old" call to free up the plugg
        # # # caller would be plugged
        # elif (self.phoneLines[lineIdx]["caller"]["isPlugged"] == True):
        #     print(f'  Unplug on wrong number, personIdx: {personIdx}')
        #     # Cover for before personidx defined
        #     if (personIdx < 99):
        #         self.ledEvent.emit(personIdx, False)
            
        # # With the above, are the following two conditions ever satisfied?
        # elif (self.phoneLines[lineIdx]["unPlugStatus"] == self.REPLUG_IN_PROGRESS):
        #     # Don't do anything about unplug if one end of the line
        #     # has already been unplugged.
        #     print('  Re-plug in progress - unplugging the other end ')
        #     # This is the remaining end unplugged, so clear the REPLUG
        #     self.phoneLines[lineIdx]["unPlugStatus"] = self.NO_UNPLUG_STATUS
            
        #     # Somewher in here condition for if CALLER_UNPLUGGED then
        #     # 		don't unplug the callee
        # elif (self.phoneLines[lineIdx]["unPlugStatus"] == self.CALLER_UNPLUGGED):
        #     # Also test for whether this unplug was an erroneous attempt
        #     # at re-plugging the caller??
        #     print('   Unplugg on the wrong jack during caller unplug')

        # Phone line is not engaged -- isEngaged == False
        else:   # Line was not fully engaged 
            print(f' - not engaged, callee index: {self.phoneLine["callee"]["index"]}'
                  f'    caller index: {self.phoneLine["caller"]["index"]}'
                  )
            # If wrong number, hmm need plug status for wrong number

            # # First, maybe this is an unplug of "old" call to free up the plugg
            # # caller would be plugged
            if (self.phoneLine["caller"]["isPlugged"] == True):
                # Caller has initiated a call

                # If this is the caller being unplugged (erroneously)
                # if incoming person index == caller for this convo
                if (personIdx == self.phoneLine["caller"]["index"]):
                    print("     caller unplugged")
                    self.vlcPlayer.stop() # vlcPlayers[lineIdx]
                    self.clearTheLine()

                    self.callInitTimer.start(1000)

                elif (self.phoneLine["unPlugStatus"] == self.WRONG_NUM_IN_PROGRESS):
                    # Unplugging wrong num
                    print(f'  Unplug on wrong number, personIdx: {personIdx}')
                    self.vlcPlayer.stop() # vlcPlayers[lineIdx]
                    # Cover for before personidx defined
                    if (personIdx < 99):
                        self.setLEDSignal.emit(personIdx, False)
                    # clear the unplug status
                    self.phoneLine["unPlugStatus"] = self.NO_UNPLUG_STATUS
                else: # Not unplugging wrong - do nothing
                    print(" just unplugging to free up a plug")

            else: # caller not plugged
                print(" * nothing going on, just unplugging ")

            # print(f' ++ not engaged, callee index: {self.phoneLines[lineIdx]["callee"]["index"]}')
            # if (self.phoneLines[lineIdx]["callee"]["index"] < 90): # callee jack was unplugged
            #     print('  ** Unplug on callee thats not engaged ')

            #     self.ledEvent.emit(self.phoneLines[lineIdx]["callee"]["index"], False)

            #     # Clear transcript?
            #     self.displayText.emit(" ")
            # else:
            #     # Wasn't callee that was unplugged (& line wasn't engaged),
            #     # so might have been wrong num that was unplugged
            #     # Need to turn off LED
            #     # print(f'  Unplug was prob on wrong number, personIdx: {personIdx}')
            #     # # Cover for before personidx defined
            #     # if (personIdx < 99):
            #     #     self.ledEvent.emit(personIdx, False)
            #     print("orphaned else in unplug")

            # self.vlcPlayers[lineIdx].stop()
        
            # #  and if was during isWrongNumInProgress
            # # then 
            #     # (just) turn off this led
            #     # which allows another plugin?



        # After all is said and done, this was unplugged, So, set pinIn False
        # self.setPinInLine(personIdx, -1)
        self.setPinIn(personIdx, False)
        print(f" - pin {personIdx} is now {self.pinsIn[personIdx]}")


    def setCallCompleted(self, event): #, _currConvo, lineIndex
        # Disable callback
        self.vlcEvent.event_detach(vlc.EventType.MediaPlayerEndReached)
                
        # otherLineIdx = 1 if (lineIndex == 0) else 0
        # print(f" ** setCallCompleted. Convo: {self.currConvo},  line:  {lineIndex} stopping. Other line has" 
        #       f"unplug stat of {self.phoneLines[otherLineIdx]['unPlugStatus']}")
        print(f" ** setCallCompleted. Convo: {self.currConvo}")
        # Stop call
        self.stopCall()

        # # Disable multi-call

        # else: 

        # Regular ending
        # # print("other line has neither caller nor callee plugged")
        # if (self.phoneLines[otherLineIdx]["unPlugStatus"] == self.REPLUG_IN_PROGRESS):
        #     # Handle case where this is a silenced call ending automatically
        #     # while the interrupting call has been unplugged
        #     # Here "other line" is the interrupting call that was unplugged
        #     print('   we think this is auto end of silenced call during 2nd call unplug');
        #     # Reset the unplug status
        #     self.phoneLines[otherLineIdx]["unPlugStatus"] = self.NO_UNPLUG_STATUS
        # # Trying to handle interrupting call that isn't answered as an interrupt
        # # This solution doen't work
        # # elif (self.currConvo == 1 or self.currConvo == 5): 
        # #     # if this is interrupting call it shouldn't do the incriment
        # # #     print("- Ignoring end of convo 1 or 5")
        # else:

    
        # Workaround to stop double calling
        if not self.incrementJustCalled:
            self.incrementJustCalled = True
            print(f' -  increment from {self.currConvo} and start regular timer for next call.')
            # Uptick currConvo here, when call is comlete
            self.currConvo += 1
            # Use signal rather than calling callInitTimer bcz threads
            self.setTimeToNextSignal.emit(1000)

        # When call 0 ends, do nothing. But how do I kmow this is is 0 ending since
        # currConvo has already been incremented to 1. When 1 ends I do want to increment.    
        
        # if (self.interruptingCallInHasBeenInitiated):
        #     print("-- Interrupting call has been initiated -- and is ending, do nothing.")    

        # # Trying to handle interrupting call that isn't answered as an interrupt
        # else:
        #     # Workaround to stop double calling
        #     if not self.incrementJustCalled:
        #         self.incrementJustCalled = True
        #         print(f'  increment from {self.currConvo} and start regular timer for next call.')
        #         self.currConvo += 1
        #         # Use signal rather than calling callInitTimer bcz threads
        #         # Uptick currConvo here, when call is comlete
        #         self.setTimeToNextSignal.emit(1000)


    def stopCall(self): # , lineIndex
        self.clearTheLine()
        # Reset volume -- in this line was silenced by interrupting call
        # self.vlcPlayers[self.prevLineInUse].audio_set_volume(100)

    def silencedCallEnded(self):
        print("-- Silenced call ended")
        self.stopSilentCall(self.silencedCallLine)

    def stopSilentCall(self, lineIndex):
        print(f'  Trying to stop silent call on line: {lineIndex}')
        self.phoneLines[lineIndex]["unPlugStatus"] = self.NO_UNPLUG_STATUS
        # Clear the line settings
        self.clearTheLine()


    def clearTheLine(self):
        # Clear the line settings
        self.phoneLine["caller"]["isPlugged"] = False
        self.phoneLine["callee"]["isPlugged"] = False
        self.phoneLine["isEngaged"] = False
        self.phoneLine["unPlugStatus"] = self.NO_UNPLUG_STATUS
        # self.prevLineInUse = -1
        # Turn off the LEDs
        # persons[phoneLines[lineIdx].caller.index].ledState = LED_OFF;
        # self.ledEvent.emit(personIdx, False)
        self.setLEDSignal.emit(self.phoneLine["caller"]["index"], False)
        # Can't turn off callee led if callee index hasn't been defined
        # print(f'About to try to turn off .callee.index: {self.phoneLines[lineIdx]["callee"]["index"]}')
        if (self.phoneLine["callee"]["index"] < 90):
            # console.log('got into callee index not null');
            self.setLEDSignal.emit(self.phoneLine["callee"]["index"], False)

    def handleStart(self):
        """Just for startup
        """
        # hasSoftPinsIn = False
        # for pinVal in self.pinsInLine:
        #     # print(f"pinVal: {pinVal}")
        #     if pinVal >= 0:
        #         hasSoftPinsIn = True

        # self.checkPinsInEvent.emit()


        # if hasSoftPinsIn:
        #     self.stopAllAudio()
        #     self.displayText.emit("pins still in, remove and press Start again")
        #     # print("pins still in, remove and press Start again")

        # else:
        print("got to model.handleStart")
        self.reset()
        # self.initiateCall()
        self.callInitTimer.start(2000)

