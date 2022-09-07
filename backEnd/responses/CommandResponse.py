#!/usr/bin/env python

#*****************************************************************************
#
# CommandResponse.py
#     Response: executing a local command.
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
import shlex
from subprocess import Popen, PIPE
import sys

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.path.PathUtils import existsInPath

# Local imports...
from BaseResponse import BaseResponse

from appCommon.CommonStrings import kCommandResponseLookup


###############################################################
class CommandResponse(BaseResponse):
    """A class for custom command responses."""
    ###########################################################
    def __init__(self, paramDict):
        """Empty initializer for CommandResponse class

        @param  paramDict      A dictionary of parameters for the response.
        """
        super(CommandResponse, self).__init__()

        assert kCommandResponseLookup in paramDict

        # This is a dict of object ids and the last frame number they were seen
        # in.  We won't alert a second time for an object until it begins
        # re-triggering after a break.
        self._itemDict = {}

        command = paramDict.get(kCommandResponseLookup, '')

        # We should always be passing as unicode.
        if type(command) == unicode:
            command = command.encode('utf-8')

        # Since shlex.split only supports POSIX parsing, we
        # recreate that function manually here, but setting the
        # posix parameter only if on Mac. Python 2.6 fixes this.
        lex = shlex.shlex(command, posix=(sys.platform=="darwin"))
        lex.whitespace_split = True
        lex.commenters = ''
        self._popenParamList = list(lex)


    ###########################################################
    def _executeCommand(self):
        """Execute the command response."""
        if not self._popenParamList:
            return

        # Since Popen on Python 2.5 or earlier leaks three pipes
        # each time it tries to execute a command that doesn't exist,
        # first test that the command exists. We need to search the
        # environment path as well.
        if not existsInPath(self._popenParamList[0], "file"):
            return

        # Execute the command
        try:
            p = Popen(self._popenParamList, stdin=PIPE, stdout=PIPE,
                      stderr=PIPE, close_fds=(sys.platform=='darwin'))
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()
        except Exception:
            return


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
            # Execute the requested command.
            self._executeCommand()


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        return

