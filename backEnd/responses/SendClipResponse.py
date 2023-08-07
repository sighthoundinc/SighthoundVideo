#!/usr/bin/env python

#*****************************************************************************
#
# SendClipResponse.py
#     Response: send clip to folder, FTP, etc
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
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
from collections import defaultdict
import operator
#import time

# Common 3rd-party imports...

# Toolbox imports...

# Local imports...
from BaseResponse import BaseResponse

from backEnd import MessageIds

from appCommon.SearchUtils import makeResultsFromRanges
from appCommon.SearchUtils import extendPendingRanges
from appCommon.SearchUtils import pullOutDoneClips
from appCommon.SearchUtils import SearchConfig

def OB_ASID(a): return a

# Constants...




###############################################################
class SendClipResponse(BaseResponse):
    """Class for responses assoicated with sending a clip to a server.

    This is used for both FTP and for cloud clips.
    """
    ###########################################################
    def __init__(self, logger, protocol, ruleName, camLoc, responseDb, #PYCHECKER too many arguments OK
                 msgQueue, responseRunnerQueue, configDict,
                 playOffset, clipLengthOffsets, shouldCombineClips,
                 preservePlayOffset):
        """Initializer for SendClipResponse class

        @param  logger               An instance of a VitaLogger to use.
        @param  protocol             The protocol to use for sending, like
                                     kFtpProtocol.
        @param  ruleName             The name of the rule containing this
                                     response.
        @param  responseDb           The response DB.
        @param  msgQueue             A queue for sending messages to the
                                     back end.
        @param  responseRunnerQueue  A queue that the response runner proc is
                                     listening to.
        @param  camLoc               The camera location.
        @param  configDict           A dictionary of user-configuration for
                                     the response.
        @param  playOffset           Offset (in ms) to start playing at.
        @param  clipLengthOffsets    Offsets (in ms) to apply to start and stop
                                     of clip.  A tuple: (startOffset,stopOffset)
        @param  shouldCombineClips   True if clips should be combined; False
                                     otherwise.
        @param  preservePlayOffset  If True attempt to treat playOffset as part
                                    of the clip, not as padding.
        """
        super(SendClipResponse, self).__init__()

        # Save parameters...
        self._responseDb = responseDb
        self._logger = logger
        self._protocol = protocol
        self._ruleName = ruleName
        self._msgQueue = msgQueue
        self._responseRunnerQueue = responseRunnerQueue
        self._camLoc = camLoc
        self._configDict = configDict

        self._playOffset = playOffset
        self._startOffset, self._stopOffset = clipLengthOffsets
        self._shouldCombineClips = shouldCombineClips
        self._preservePlayOffset = preservePlayOffset

        # A list of pending ranges...  [
        #    (objId, ((firstMs, firstFrame),
        #             (lastMs, lastFrame))),
        #    ...,
        #    ...
        #  ]
        self._pendingRanges = []

        # If we're combining clips, we'll make sure that start time is
        # always >= the previous stop time...
        self._prevStopTime = 0


    ###########################################################
    def flush(self):
        """Flush out any pending data.

        Nothing more will be given.
        """
        self.addRanges(None, {})

        # TODO: Somehow indicate to the ResponseRunner not to wait too long
        # for video to flush because it's likely we won't have all the video
        # we actually want (since the camera just got turned off).


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        @param  ms         The most recent time in milliseconds that has been
                           processed; may be None for flushing.
        @param  rangeDict  A dictionary of response ranges.  Key = objId,
                           value = list of ((firstFrame, firstTime),
                                            (lastFrame, lastTime))
        """
        # Update self._pendingRanges with the new info from rangeDict...
        extendPendingRanges(self._pendingRanges, rangeDict,
                            self._shouldCombineClips)


        # aggressive merge should only be used for UI
        searchConfig = SearchConfig()
        searchConfig.disableClipMerging()

        # Try to make results, just like we do in search view...  This will
        # keep track of which 'source item indices' (indices into
        # self._pendingRanges) were used to make each result.
        curResults = makeResultsFromRanges(
            self._pendingRanges, self._playOffset, self._startOffset,
            self._stopOffset, self._shouldCombineClips, self._preservePlayOffset,
            searchConfig, None )

        # Pull out done clips, deleting things from self._pendingRanges...
        self._prevStopTime, doneClips = pullOutDoneClips(
            curResults, self._pendingRanges, ms, self._startOffset,
            self._stopOffset, self._shouldCombineClips, self._prevStopTime
        )

        # Send all the clips that are done...
        for clipInfo in doneClips:
            self._sendOutClip(clipInfo)


    ###########################################################
    def _sendOutClip(self, clipInfo):
        """Send out a clip.

        @param  clipInfo     Information about the clip to send.
        """
        # Log that we're queuing this up for sending.
        #timeStruct = time.localtime(clipInfo.startTime/1000.)
        #startTimeStr = time.strftime('%I:%M:%S %p', timeStruct).swapcase()
        #if startTimeStr[0] == '0':
        #    startTimeStr = startTimeStr[1:]
        #timeStruct = time.localtime(clipInfo.stopTime/1000.)
        #stopTimeStr = time.strftime('%I:%M:%S %p', timeStruct).swapcase()
        #if stopTimeStr[0] == '0':
        #    stopTimeStr = stopTimeStr[1:]
        #self._logger.info(
        #    "Queuing up clip to send for \"%s\": %s - %s" % (
        #        self._ruleName, startTimeStr, stopTimeStr
        #    )
        #)

        # Now let the response runner know to send the email...
        self._responseDb.addClipToSend(
            self._protocol, self._camLoc, self._ruleName,
            clipInfo.startTime, clipInfo.stopTime,
            clipInfo.playStart, clipInfo.previewMs,
            clipInfo.objList, clipInfo.startList
        )

        # Just put something on the queue to wake up the response runner...
        self._responseRunnerQueue.put([MessageIds.msgIdSendClip])


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        return


