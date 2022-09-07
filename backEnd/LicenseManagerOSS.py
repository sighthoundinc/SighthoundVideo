#! /usr/local/bin/python

#*****************************************************************************
#
# LicenseManagerOSS.py
#     License validation and provisioning stub
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

"""
## @file
Contains the license manager and utilities.
"""

import os, sys, copy, time
import StringIO

from vitaToolbox.strUtils import Obfuscate
from vitaToolbox.sysUtils.FileUtils import writeStringToFile
from appCommon.CommonStrings import kReportLevelError
from appCommon.CommonStrings import kReportLevelInfo
from appCommon.CommonStrings import kLicenseFileName
from appCommon.CommonStrings import kMemStoreLicenseLoginStatus
from appCommon.CommonStrings import kMemStoreLicenseList
from appCommon.CommonStrings import kMemStoreLicenseData
from appCommon.CommonStrings import kLoginStatusAccountId
from appCommon.CommonStrings import kLoginStatusFailed
from appCommon.CommonStrings import kLoginStatusLastUser
from appCommon.CommonStrings import kLoginStatusMachineId
from appCommon.CommonStrings import kLoginStatusToken
from MessageIds import msgIdNeedRelogin
from MessageIds import msgIdLicenseChanged
from MessageIds import msgIdLicenseSupportExpired


###############################################################################


##############################################################################
class LicenseManager(object):
    """ A stub to implement licensing functionality for those who desire it.
    """

    ###########################################################
    def __init__(self, settings, machineId, workDir, logger):
        """ Constructor.

        @param settings   Settings stored by a former instance.
        @param machineId  The machine identifier to use.
        @param workDir    The common work directory to store the license and
                          the authentication token as files.
        @param logger     The logging instance to use.
        """
        super(LicenseManager, self).__init__()
        self._logger = logger
        self._settings = settings
        self._nmsClient = _DelayingNmsClient()
        self._machineId = machineId
        self._accountId = 1 # Normally this information would come from the license
        self._authToken = "" # Normally this will be provided by the login operation at the start of backEnd execution
        # {
        #   u'Cameras': u'-1',
        #   u'Name': u'Sight Hound',
        #   u'Timestamp': u'1658859560',
        #   u'Expires': u'1690481960',
        #   u'Support Expires': u'1653224309',
        #   u'Edition': u'Pro Edition',
        #   u'Serial Number': u'XXXX-XXX-XXXXXXX',
        #   u'Signature': u'ZvnYru/TM2yxqQiamCFazGiNnf6FI/zVv+qkkNJZUuSeJXOrAYSl2ow9G0T5O7MkFJCZ02vv7puvKTkYvrC6A8USSynjqwhHZsXFq5+edyV+/oXTxV6ZLqBgIUgq3ke5JHmwUUhzrDovLOybXgpz8oam9Y3vbRP3HkGfUgBI5+M=',
        #   u'Signature': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx=',
        #   u'Machine ID': u'xxxxxxxxxxxxxxxxxxxx',
        #   u'Email': u'user@sight.hound'
        # }
        now = int(time.time())
        in5years = now + 60*60*24*365*5
        self._licenseData = {
            "Cameras" : -1,
            "Timestamp" : now,
            "Expires" : in5years,
            "Support Expires" : in5years,
            "Edition" : "Pro Edition",
            "Serial Number": "XXXX-XXX-XXXXXXX",
            "Signature" : "",
            "Machine ID" : self._machineId,
            "Email" : "user@sight.hound"
        }


    ###########################################################
    def setNmsClient(self, nmsClient):
        """ Sets the NMS client. Delayed calls made to the NMS since the
        beginning will be invoked on the real client, in the original order.

        @param nmsClient  XML/RPC client instance to talk to the network message
                          server, to access the memstore and to post
                          license-change messages.
        """
        self._nmsClient.commit(nmsClient)
        self._nmsClient = nmsClient


    ###########################################################
    def licenseData(self):
        """ Gives access to the license data directly. Useful if the instance
        is in the same process, where going over the memstore would be overkill.

        @return  The license data dictionary. Copy of to be precise, so the
                 caller can do whatever it wants with it.
        """
        return copy.deepcopy(self._licenseData)


    ###########################################################
    def userLogin(self, opid, user, password):
        """ Run a login attempt. If successful the token will be saved. The
            login status will be updated, so the caller can check what happened.
            The former auth token will be discarded.

        @param user      User name.
        @param password  Password.
        """
        pass # In current implementation it is a no-op


    ###########################################################
    def userLogout(self):
        """Dissociate from the current user account and revert to starter."""
        pass # In current implementation it is a no-op

    ###########################################################
    def listRefresh(self, opid, matchLicense=True):
        """ Loads the latest list of licenses. If successful the memstore will
        be updated with this data. On failure the last error field instead.

        @param matchLicense  True to check if the current license (based on the
                             serial number) is different than the one in the
                             list. If so the license will be acquired again.
        @param opid          Operation identifier.
        """
        pass

    ###########################################################
    def acquire(self, opid=None, serialNumber=None):
        """ Executes an acquisition attempt for a different license. On success
        the new license data will be put into the memstore and the actual
        document be saved to a local file.

        @param   opid          Operation identifier. Optional, can be None.
        @param   serialNumber  Optional serial number of the license to acquire.
        @return                True if a license got acquired successfully or
                               if we reset to starter.
        """
        return True


    ###########################################################
    def unlink(self, opid):
        """ Unlinks the current machine from any license associated with it.

        @param opid   Operation identifier.
        @return       True if the unlink operation was successful.
        """
        return True


    ###########################################################
    def run(self):
        """ To run schedules amongst other things. Should be called by the
        owner on a regular basis. Can be as often as possible, the overhead,
        when nothing happens, is very small.
        """
        pass


    ###########################################################
    def getAccountId(self):
        """ Return the current account ID

        @return accountID  The current account ID
        """
        return self._accountId

    ###########################################################
    def getAuthToken(self):
        """Return the current auth token.

        @return authToken  The current auth token.
        """
        return self._authToken


###############################################################################
class _DelayingNmsClient:
    """ Proxy class to delay calls to the NMS made by the license server. It
    mimics all of the necessary methods of the actual NMS client.
    """
    def __init__(self):
        """ Constructor. """
        self._calls = []

    def memstorePut(self, key, data, ttl=-1):
        self._calls.append(["memstorePut", key, data, ttl])
        return -1

    def setLicenseSettings(self, settings):
        self._calls.append(["setLicenseSettings", settings])

    def addMessage(self, message):
        self._calls.append(["addMessage", message])

    def commit(self, nmsClient):
        """ Commit the methods, meaning calling them on the real client in the
        order they got recorded.

        @param nmsClient  The (real) NMS client whose methods get called.
        @return Number of method calls made.
        """
        for call in self._calls:
            method = call[0]
            if "memstorePut" == method:
                nmsClient.memstorePut(call[1], call[2], call[3])
            elif "setLicenseSettings" == method:
                nmsClient.setLicenseSettings(call[1])
            elif "addMessage" == method:
                nmsClient.addMessage(call[1])
        result = len(self._calls)
        self._calls = []
        return result
