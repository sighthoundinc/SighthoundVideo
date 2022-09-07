#!/usr/bin/env python

#*****************************************************************************
#
# SoundResponse.py
#     Response: play a local sound
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Sighthound, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Sighthound, Inc.
# by emailing opensource@sighthound.com
#
# This file is part of the Sighthound Video project which can be found at
# https://github.com/sighthoundinc/SighthoundVideo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; using version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
#
#
#*****************************************************************************


# Python imports...
import os
from subprocess import Popen, PIPE
import sys
import time
import wave

# Common 3rd-party imports...
import pyaudio

# Local imports...
from BaseResponse import BaseResponse

from frontEnd.GetLaunchParameters import getLaunchParameters

_kSoundPathLookup = "soundPath"


###############################################################
class SoundResponse(BaseResponse):
    """Sound response class."""
    ###########################################################
    def __init__(self, paramDict):
        """Initializer for SoundResponse class

        @param  paramDict      A dictionary of parameters for the response.
        """
        super(SoundResponse, self).__init__()

        assert _kSoundPathLookup in paramDict

        # This is a dict of object ids and the last frame number they were seen
        # in.  We won't alert a second time for an object until it begins
        # re-triggering after a break.
        self._itemDict = {}

        soundPath = paramDict.get(_kSoundPathLookup,'')

        # We should always be passing as unicode, but we weren't previously,
        # hence this test.
        if type(soundPath) == unicode:
            soundPath = soundPath.encode('utf-8')

        self._popenParamList = getLaunchParameters()
        self._popenParamList.extend(["--sound", soundPath])

        self._lastAlertTime = 0
        self._fileDuration = 0
        try:
            waveFile = wave.open(soundPath, 'rb')
            self._fileDuration = 1.0*waveFile.getnframes()/waveFile.getframerate()
        except Exception:
            pass


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        @param  ms         The most recent time in milliseconds that has been
                           processed.
        @param  rangeDict  A dictionary of response ranges.  Key = objId,
                           value = list of ((firstFrame, firstTime),
                                            (lastFrame, lastTime)).
        """
        _ = ms

        alert = False

        prevSeenObjs = self._itemDict.keys()
        curObjs = rangeDict.keys()

        for objId in curObjs:
            numRanges = len(rangeDict[objId])
            if not numRanges:
                assert False, "Must have entries in the range list"

            elif numRanges == 1:
                # There is only one range. We'll check to see if it is a
                # continuation of the previous triggered events.  If not we'll
                # send an alert.
                (firstFrame, _), (lastFrame, _) = rangeDict[objId][0]

                if (objId not in self._itemDict) or \
                   (firstFrame != self._itemDict[objId]+1):
                    alert = True

                self._itemDict[objId] = lastFrame
            else:
                # If there are multiple ranges here we know the object triggered
                # after taking a break so we'll send an alert.  If the object
                # hasn't been previously tracked, we'll also send an alert.
                alert = True
                for (_, _), (lastFrame, _) in rangeDict[objId]:
                    # Set the last frame seen to the last frame seen.
                    self._itemDict[objId] = max(self._itemDict.get(objId, 0),
                                                lastFrame)

        # Clean up objects that aren't around anymore.
        for objId in prevSeenObjs:
            if objId not in curObjs:
                del self._itemDict[objId]

        if alert:
            now = time.time()
            if now < self._lastAlertTime+self._fileDuration:
                # We only want to begin a new play if the previous has finished.
                return

            self._lastAlertTime = now

            # Launch a process to play the specified sound file.
            subProc = Popen(self._popenParamList, stdin=PIPE, stdout=PIPE,
                            stderr=PIPE, close_fds=(sys.platform=='darwin'))
            subProc.stdin.close()
            subProc.stdout.close()
            subProc.stderr.close()


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        return


#####################################################################
def playSound(soundPath, catchExceptions=True):
    """Play a wave file.

    @param  soundPath        The absolute path to the wave file to play.
    @param  catchExceptions  If True exceptions will be caught and ignored.
    """
    try:
        if type(soundPath) == str:
            soundPath = soundPath.decode('utf-8')

        pyAudioInst = pyaudio.PyAudio()
        waveFile = wave.open(soundPath, 'rb')

        channels, width, framerate, _, _, _ = waveFile.getparams()
        format = pyAudioInst.get_format_from_width(width)
        stream = pyAudioInst.open(rate=framerate, channels=channels, format=format,
                                  output=True)

        data = waveFile.readframes(4096)
        while data:
            stream.write(data)
            data = waveFile.readframes(4096)

        stream.close()
        pyAudioInst.terminate()
    except:
        if not catchExceptions:
            raise
