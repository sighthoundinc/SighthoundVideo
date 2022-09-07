#!/usr/bin/env python

#*****************************************************************************
#
# RecordResponse.py
#     Response: mark the time range for extended retention / saving
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



from BaseResponse import BaseResponse
from backEnd import MessageIds


###############################################################
class RecordResponse(BaseResponse):
    """A response that flags clips to be 'recorded'."""
    ###########################################################
    def __init__(self, paramDict):
        """Initializer for RecordResponse.

        @param  paramDict     A parameter dictionary containing
                msgList       A list to add messages to.
                camLoc        The camera location this response is monitoring.
                preRecord     The time in seconds to record before a trigger.
                postRecord    The time in seconds to record after a trigger.
        """
        super(RecordResponse, self).__init__()

        # Track the highest time we've marked for saving.  We don't ever need
        # to mark anything prior to this again.  This will save us a few
        # database hits near file boundaries.
        self._highestSavedTime = 0

        self._msgList = paramDict['msgList']
        self._camLoc = paramDict['camLoc']
        self._preRecord = paramDict['preRecord']*1000
        self._postRecord = paramDict['postRecord']*1000


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        @param  ms      The most recent time in milliseconds that has been
                        processed.
        @param  ranges  A dictionary of response ranges.  Key = objId, value =
                        list of ((firstFrame, firstTime), (lastFrame, lastTime))
        """
        _ = ms

        # We don't do anything if there is no new data...
        if not rangeDict:
            return

        # Build a list of times to mark as saved for all objects.
        prevHighestSave = self._highestSavedTime

        timeRanges = []
        for objId in rangeDict:
            # Adjust each time range for the pre and post record values and
            # append to the range list
            for (_, firstMs), (_, lastMs) in rangeDict[objId]:
                lastMsToSave = lastMs+self._postRecord
                timeRanges.append((max(firstMs-self._preRecord,
                                       prevHighestSave+1), lastMsToSave))
                self._highestSavedTime = max(self._highestSavedTime,
                                             lastMsToSave)

        timeRanges.sort()

        self._msgList.append([MessageIds.msgIdAddSavedTimes, self._camLoc,
                              timeRanges])


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        # If we toggle the camera quickly, the rule will still remember that we
        # requested a record into the future but the new camera stream will not.
        # Our first tags after a new session must contain the full tag request
        # range.
        self._highestSavedTime = 0

