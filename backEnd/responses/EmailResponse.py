#!/usr/bin/env python

#*****************************************************************************
#
# EmailResponse.py
#     Response: sending an email
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
from email.utils import make_msgid
import time
# Common 3rd-party imports...

# Toolbox imports...

# Local imports...
from BaseResponse import BaseResponse

from backEnd import MessageIds


# Constants...

# If an object disappears for this many ms, we'll assume it's gone.
_kMaxObjectVanishTimeMs = 3000

# We'll always send out an email before this amount of time.
_kMaxLatency = (1000 * 30)


# Do not email sooner than this since object's first appearance
_kMinTimeSinceStart = 2000

# If the object is hanging around that long, email about it again
_kMinRepeatTime = 10000

# If we haven't seen object for that long, forget about it
_kObjectTimeout = 30000

# Minimum overlap ratio we will consider to merge email notification for two objects
_kMinObjectOverlapRatio = 0.7

###############################################################
class EmailResponse(BaseResponse):
    """Class for email responses."""
    ###########################################################
    def __init__(self, ruleName, camLoc, emailSettings,
                 msgQueue, responseRunnerQueue, configDict={}):
        """Empty initializer for EmailResponse class

        @param  ruleName             The name of the rule containing this
                                     response.
        @param  emailSettings        A dictionary of email settings; see
                                     BackEndPrefs.  This object keeps a pointer
                                     to this dict--it may be updated by the
                                     caller periodically.
        @param  msgQueue             A queue for sending messages to the
                                     back end.
        @param  responseRunnerQueue  A queue that the response runner proc is
                                     listening to.
        @param  camLoc               The camera location.
        @param  configDict           A dictionary of user-configuration for
                                     the response.
        """
        super(EmailResponse, self).__init__()

        # Save parameters...
        self._ruleName = ruleName
        self._emailSettings = emailSettings
        self._msgQueue = msgQueue
        self._responseRunnerQueue = responseRunnerQueue
        self._camLoc = camLoc
        self._configDict = configDict

        self._wantLimiting = configDict.get('wantLimit', False)
        self._limitMs = configDict.get('limitSeconds', 60)*1000
        self._lastEmailTime = 0

        # A dict of ranges that are pending...
        #   key: objectId
        #   value: [
        #       ((firstFrame, firstMs), (lastFrame, lastMs)),
        #       ...
        #   ]
        self._pendingRanges = {}

        # A set of object IDs that we've already sent the email for (at least
        # for the first pending range).
        self._alreadyEmailed = set()

        self._activeObjects = {} # objId : (firstTime, lastTime, lastEmailRequest)


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        @param  ms         The most recent time in milliseconds that has been
                           processed.
        @param  rangeDict  A dictionary of response ranges.  Key = objId,
                           value = list of ((firstFrame, firstTime),
                                            (lastFrame, lastTime))
        """

        # Iterage on the new ranges, and add them to the existing one if new object,
        # or update the lastMs, if existing one
        for objId in rangeDict:
            objEntry = rangeDict[objId]
            firstMs  = objEntry[0][0][1]
            lastMs   = objEntry[-1][1][1]
            objIdPrev = self._activeObjects.get(objId, (firstMs, lastMs, 0))
            self._activeObjects[objId] = (objIdPrev[0], lastMs, objIdPrev[2])

        # Iterate on active objects, and see if we should (re)email notifications
        # about each one of them, OR whether we should forget about it
        toEmailList = []
        for objId in list(self._activeObjects):
            firstMs, lastMs, emailTime = self._activeObjects[objId]
            shouldEmail = ms - firstMs > _kMinTimeSinceStart and \
                          lastMs - emailTime > _kMinRepeatTime
            shouldRemove = ms - lastMs > _kObjectTimeout and \
                           emailTime > 0
            if shouldEmail:
                # print "Going to email %d" % objId
                toEmailList.append( (objId, firstMs if emailTime is 0 else emailTime, lastMs) )
            else:
                # print "Not emailing %d - diff=%d, lastEmail at %d" % (objId, ms-firstMs, emailTime)
                pass
            if shouldRemove:
                del self._activeObjects[objId]
            else:
                updatedTime = ms if shouldEmail else emailTime
                self._activeObjects[objId] = ( firstMs, lastMs, updatedTime )

        # Iterate on notifications we are about to send, and compress the list by merging the items
        alreadyEmailed = set()
        for objId, firstMs, lastMs in toEmailList:
            if objId in alreadyEmailed:
                continue

            # This one is going out!
            objSet = set([objId])
            alreadyEmailed.add(objId)
            print "Requesting notification for %d, delay=%d, rtDelay=%d" % (objId, ms-firstMs, int(time.time()*1000)-ms)

            for objId2, firstMs2, lastMs2 in toEmailList:
                if objId2 in alreadyEmailed:
                    continue
                if (firstMs2 <= lastMs) and (lastMs2 >= firstMs):
                    # the two ranges overlap, but do they overlap enough?
                    lenSum = (lastMs-firstMs) + (lastMs2-firstMs2)
                    overlapFirstMs = max(firstMs, firstMs2)
                    overlapLastMs = min(lastMs, lastMs2)
                    overlapLen = overlapLastMs - overlapFirstMs
                    overlapRatio = overlapLen*2/lenSum
                    if overlapRatio > _kMinObjectOverlapRatio:
                        print "Merging notifications for %d and %d" % (objId, objId2)
                        alreadyEmailed.add(objId2)
                        objSet.add(objId2)
                        firstMs = overlapFirstMs
                        lastMs = overlapLastMs

            self._requestEmail(len(objSet), sorted(objSet), firstMs, lastMs)



    ###########################################################
    def _requestEmail(self, numTriggers, objList, firstMs, lastMs):
        """Request the sending of an email.

        @param  numTriggers  The number of times the rule was triggered.
        @param  objList      List of object IDs to highlight.
        @param  firstMs      The first ms of relevant video.
        @param  lastMs       The last ms of relevant video.
        """
        if self._wantLimiting \
                and ((firstMs-self._lastEmailTime) < self._limitMs):
            return

        # Flush the video so that the response runner has a chance to read it...
        self._msgQueue.put([MessageIds.msgIdFlushVideo, self._camLoc])

        # Now let the response runner know to send the email...
        self._responseRunnerQueue.put([MessageIds.msgIdSendEmail,
                                       self._ruleName, self._camLoc,
                                       self._emailSettings, self._configDict,
                                       numTriggers, objList, firstMs, lastMs,
                                       make_msgid("SighthoundEmailResponse")])

        self._lastEmailTime = firstMs


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        return

