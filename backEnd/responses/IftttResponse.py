#!/usr/bin/env python

#*****************************************************************************
#
# IftttResponse.py
#     Response: initiating IFTTT action
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

# Local imports...
from backEnd import MessageIds
from PushResponse import PushResponse

###############################################################
class IftttResponse(PushResponse):
    """A class for IFTTT responses."""

    ###########################################################
    def _queuePushNotification(self, ms):
        """Request an IFTTT trigger be sent.

        @param ms  The ms of the trigger.
        """
        msg = [MessageIds.msgIdTriggerIfttt, self._cam, self._rule, ms/1000]
        self._queue.put(msg)

