#*****************************************************************************
#
# IftttClient.py
#   IFTTT API Client
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

from appCommon.CommonStrings import kIftttPathTrigger
from appCommon.CommonStrings import kIftttPathState
from appCommon.CommonStrings import kIftttHost
from appCommon.hostedServices.ServicesClient import ServicesClient


##############################################################################
class IftttClient(ServicesClient):
    """ Client send IFTTT messages to. Although using the same mechanics the
    data goes to a different server, at this moment it's the push notification
    infrastructure.
    """

    ###########################################################
    def __init__(self, logger, token):
        """ Constructor.

        @param  logger      Logger instance, mostly for error messages.
        @param  token       API access token.
        @param  updatePath  Update path override, None for production/default.
        @param  secure      True to use HTTPS, False to do HTTP (for testing).
        @param  port        Port override. Optional, None defaults to 443.
        @param  host        Host override. Optional, None for default.
        @return             True if the request succeeded.
        """
        super(IftttClient, self).__init__(logger, token, host=kIftttHost)


    ###########################################################
    def trigger(self, camLoc, ruleName, time):
        """ Triggers an IFTTT channel.

        @param  camLoc    Camera location.
        @param  ruleName  Name of the rule causing the detection.
        @param  time      Timestamp, seconds since epoch.
        @return           True if the gateway accepted the data.
        """
        params = {'camera': camLoc, 'rule': ruleName, 'time': time}
        self._logger.info("sending IFTTT trigger: " + str(params))
        rsp = self.request("POST", kIftttPathTrigger, params)
        return rsp is not None


    ###########################################################
    def sendState(self, cameras, rules):
        """ Sends state information.

        @param  cameras  List of camera names.
        @param  rules    List of rule names.
        @return          True if the gateway accepted the data.
        """
        params = {'cameras': cameras, 'rules': rules }
        self._logger.info("sending IFTTT state: " + str(params))
        rsp = self.request("POST", kIftttPathState, params)
        return rsp is not None

