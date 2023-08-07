#!/usr/bin/env python

#*****************************************************************************
#
# WebhookResponse.py
#    Response: execute a webhook
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


import time

from vitaToolbox.sysUtils.TimeUtils import formatTime

# Local imports...
from BaseResponse import BaseResponse

from backEnd import MessageIds


# Constants...
_kObjTimeoutMs = 10000 # after 10 seconds we will forget about an object

###############################################################
class WebhookResponse(BaseResponse):
    """Class for email responses."""
    ###########################################################
    def __init__(self, ruleName, camLoc,
                 responseRunnerQueue, configDict={}):
        """Empty initializer for EmailResponse class

        @param  ruleName             The name of the rule containing this
                                     response.
        @param  camLoc               The camera location.
        @param  responseRunnerQueue  A queue that the response runner proc is
                                     listening to.
        @param  configDict           A dictionary of user-configuration for
                                     the response.
        """
        super(WebhookResponse, self).__init__()

        # Save parameters...
        self._ruleName = ruleName
        self._camLoc = camLoc
        self._responseRunnerQueue = responseRunnerQueue

        self._url = configDict.get('webhookUri', '')
        self._contentType = configDict.get('webhookContentType', '')
        self._content = configDict.get('webhookContent', '')

        self._content = self._content.replace("{SvRuleName}",  "'" + self._ruleName + "'" )
        self._content = self._content.replace("{SvCameraName}", "'" + self._camLoc + "'" )

        # A set of object IDs that we've already sent the email for (at least
        # for the first pending range).
        self._objIdsProcessed = {}


    ###########################################################
    def _getNewActiveObjects(self, rangeDict):
        """ Get a list of newly appearing active objects (and update the times for existing ones)
        """
        webhookTriggers = []

        for objId in rangeDict:
            objRanges = rangeDict[objId]
            if not objId in self._objIdsProcessed:
                # only send notification if it is the first about this object
                firstMs = objRanges[0][0][1]
                webhookTriggers.append((objId, firstMs))
            # update our list of when the object was last seen
            lastMs = objRanges[len(objRanges)-1][1][1]
            self._objIdsProcessed[objId] = lastMs
        return webhookTriggers


    ###########################################################
    def _activeObjectsGC(self):
        """ Garbage-collect object IDs that had timed out, to prevent an ever-growing list
        """
        activeObjects = self._objIdsProcessed.keys()
        currentTime = int(time.time()*1000)
        for objId in activeObjects:
            if currentTime - self._objIdsProcessed[objId] > _kObjTimeoutMs:
                del self._objIdsProcessed[objId]


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        @param  ms         The most recent time in milliseconds that has been
                           processed.
        @param  rangeDict  A dictionary of response ranges.  Key = objId,
                           value = list of ((firstFrame, firstTime),
                                            (lastFrame, lastTime))
        """

        newNotifications = self._getNewActiveObjects(rangeDict)
        self._activeObjectsGC()
        if len(newNotifications) > 0:
            self._requestWebhookAction(newNotifications)


    ###########################################################
    def _requestWebhookAction(self, objList):
        """Request the sending of an email.

        @param  objList      List of (object ID, time) tuples to highlight.
        """


        for obj in objList:
            eventTime = obj[1]
            content = self._content.replace("{SvEventTime}", formatTime('%Y-%m-%d %H:%M:%S', time.localtime(eventTime/1000.0)) )
            # Now let the response runner know to trigger the webhook
            self._responseRunnerQueue.put([MessageIds.msgIdSendWebhook,
                                        self._camLoc, self._ruleName, self._url, eventTime, self._contentType, content, obj])


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        return

