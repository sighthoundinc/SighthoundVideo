#!/usr/bin/env python

#*****************************************************************************
#
# PushResponse.py
#     Response: push event to mobile client(s)
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
# https://github.url/thing
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

# Local imports...
from appCommon.SearchUtils import kFrameTolerance
from backEnd import MessageIds
from BaseResponse import BaseResponse

# Arbitrary, but must be negative value. The first frame we get could be any
# positive number, and we must guarantee it isn't flagged as a continuation.
_kStopFrameDefault = -20


###############################################################
class PushResponse(BaseResponse):
    """A class for push notification responses."""
    ###########################################################
    def __init__(self, cameraLocation, ruleName, combine, startOffset,
            stopOffset, messageQueue):
        """Initialize for PushResponse class

        @param  cameraLocation The camera location triggering this response.
        @param  ruleName       The rule name triggering this response.
        @param  combine        True if overlapping objects items should only be
                               notified once.
        @param  startOffset    Query value indicating the start padding length.
        @param  stopOffset     Query value indicating the end padding length.
        @param  messageQueue   A queue the response runner proc is listening to.
        """
        super(BaseResponse, self).__init__()

        self._cam = cameraLocation
        self._rule = ruleName
        self._combine = combine
        self._queue = messageQueue

        self._stopFrame = _kStopFrameDefault

        # For region rules we need to track when the last time a given object
        # triggered the rule. In the app recurring triggers within the possible
        # padding (startOffset+stopOffset) are combined, we want to mimic this.
        self._padding = startOffset + stopOffset

        # key = objId, value = (firstFrame, firstTime, lastFrame, lastTime)
        self._objLookup = {}


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        General algorithm:
          non-overlap (instantaneous rules) -
            * always fire, though combining if multiple objects trigger at the
              same moment.
          overlap (anything other than line crossing or door) -
            * Create list of unique range spans, ignoring object ids
            * If the first range is not a continuation of the last, trigger
              a push. Trigger a push for each additional disconnected range.

        @param  ms         The most recent time in milliseconds that has been
                           processed.
        @param  rangeDict  A dictionary of response ranges.  Key = objId,
                           value = list of ((firstFrame, firstTime),
                                            (lastFrame, lastTime)).
        """
        rawList = []

        for objId in rangeDict:
            for ((firstFrame, firstTime), (lastFrame, lastTime)) in rangeDict[objId]:
                if not self._combine:
                    rawList.append((firstFrame, firstTime))
                else:
                    # If combining clips and we saw an object within our
                    # padding tolerance we want to combine these clips. Pretend
                    # the object has been triggering the whole time.
                    if objId in self._objLookup and \
                            self._objLookup[objId][3] > (firstTime-self._padding):
                        prevFirstFrame, prevFirstTime, _, _ = self._objLookup[objId]
                        rawList.append((prevFirstFrame, prevFirstTime, lastFrame))
                        self._objLookup[objId] = (prevFirstFrame, prevFirstTime,
                                lastFrame, lastTime)
                    else:
                        rawList.append((firstFrame, firstTime, lastFrame))
                        self._objLookup[objId] = (firstFrame, firstTime, lastFrame, lastTime)

        # If we got no ranges, return
        if not len(rawList):
            return

        if not self._combine:
            rawList = list(set(rawList))
            rawList.sort()
            for _, ms in rawList:
                self._queuePushNotification(ms)
            return


        # Combine overlapping ranges
        rawList.sort()
        spanList = [rawList[0]]
        for i in xrange(1, len(rawList)):
            prevStart, prevMs, prevStop = spanList[len(spanList)-1]
            start, ms, stop = rawList[i]

            if (start-prevStop) <= kFrameTolerance:
                spanList[len(spanList)-1] = (prevStart, prevMs, max(prevStop, stop))
            else:
                spanList.append((start, ms, stop))

        # Check if the first entry extends previous notification. If so, ingore.
        start, _, stop = spanList[0]
        if (start-self._stopFrame) <= kFrameTolerance:
            self._stopFrame = stop
            spanList.pop(0)

        # Every entry in the spanList now needs to trigger a push notification.
        for (start, ms, stop) in spanList:
            self._queuePushNotification(ms)
            self._stopFrame = stop

        # If an object hasn't been seen in > self._padding, remove it.
        for objId in self._objLookup.keys():
            if self._objLookup[objId][3] < (ms-self._padding):
                del self._objLookup[objId]


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        self._stopFrame = _kStopFrameDefault


    ###########################################################
    def _queuePushNotification(self, ms):
        """Request a push notification be sent.

        @param ms  The ms to include in the notification.
        """
        self._queue.put([MessageIds.msgIdSendPush, self._cam, self._rule, ms])
