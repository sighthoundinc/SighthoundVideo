#!/usr/bin/env python

#*****************************************************************************
#
# BackEndPrefs.py
#   Preferences for the backEnd
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
Contains the BackEndPrefs class.
"""

import cPickle
import wx

from vitaToolbox.networking.SimpleEmail import kDefaultEncryption
from vitaToolbox.networking.SimpleEmail import kDefaultPort

kLiveMaxBitrate = "liveMaxBitrate"
kLiveMaxBitrateDefault = -1
kClipQualityProfile = "clipVideoQualityProfile"
kClipQualityProfileDefault = 0 # svvpOriginal -- remux if we can
kLiveEnableTimestamp = "liveEnableTimestamp"
kLiveEnableTimestampDefault = False
kLiveEnableFastStart = "liveEnableFastStart"
kLiveEnableFastStartDefault = True
kLiveMaxResolution = "liveMaxResolution"
kClipMergeThreshold = "clipMergeThreshold"
kClipMergeThresholdDefault = 10
kFpsLimit = "fpsLimit"
kRecordInMemory = "recordInMemory"
kRecordInMemoryDefault = False
kLiveMaxResolutionDefault = -1
kClipResolution = "clipStreamResolution"
kClipResolutionDefault = 480
kGenThumbnailResolution = "genThumbnailRes"
kGenThumbnailResolutionDefault = 240
kHardwareAccelerationDevice = "hardwareDevice"
kHardwareAccelerationDeviceDefault = "none" if wx.Platform == '__WXMAC__' else "auto"



_kDefaultPrefs = {
    'maxStorageSize' : 100,

    # Email-related settings...
    "emailSettings": {
        'fromAddr':   "",
        'toAddrs':    "",   # Obsolete--only used for old rules...
        'host':       "",
        'user':       "",
        'password':   "",
        'port':       kDefaultPort,
        'encryption': kDefaultEncryption,
    },

    'ftpSettings': {
        'host':         "",
        'port':         21,
        'isPassive':    True,
        'directory':    u"",
        'user':         u"",
        'password':     u"",
    },

    'notificationSettings': {
        'enabled':         False,
        'gatewayGUID':     "",
        'gatewayPassword': "",
        'gatewayUserName': ""
    },

    # We store arm settings on the back end (even though they are used
    # totally by the front end) because I assume we might eventually want
    # to expose arming / disarming to web site, iPhone app, ...
    'armSettings': {
        # A list of cameras that we _don't_ want to arm, since by default we
        # arm all cameras...
        'camerasNotToArm': [],

        # Number of minutes to delay arming...
        'armDelayMinutes': 1,

        # Whether we want the delay when arming...
        'wantArmDelay': True,
    },

    'cacheDuration' : 48,

    # Web server is initially turned off.
    'webPort': -1,

    # Initial authentication is empty, so we can ask the user to provide us.
    'webAuth': "",

    # Port opener should not run by default.
    'portOpenerEnabled': False,

    # License (manager) settings.
    'licenseSettings': {
        # The authentication token (to talk to the licensing server).
        'authToken': None,
    },

    'timePref12': True,
    'datePrefUS': True,

    'iftttIdle': True,

    kLiveMaxBitrate: kLiveMaxBitrateDefault,
    kClipQualityProfile: kClipQualityProfileDefault,
    kLiveEnableTimestamp: kLiveEnableTimestampDefault,
    kLiveEnableFastStart: kLiveEnableFastStartDefault,
    kLiveMaxResolution: kLiveMaxResolutionDefault,
    kClipResolution: kClipResolutionDefault,
    kGenThumbnailResolution: kGenThumbnailResolutionDefault,
    kRecordInMemory: kRecordInMemoryDefault,
    kClipMergeThreshold: kClipMergeThresholdDefault,
    kHardwareAccelerationDevice: kHardwareAccelerationDeviceDefault,

    'clipTimestamps': False,
    'clipBoundingBoxes': True,
}

class BackEndPrefs(object):
    """Implements a class for persisting app preferences."""
    ###########################################################
    def __init__(self, prefsPath):
        """The initializer for BackEndPrefs.

        @param  prefsPath  The path to the prefs file.
        """
        # Call the base class initializer
        super(BackEndPrefs, self).__init__()

        self._prefsPath = prefsPath

        self._prefs = None

        try:
            f = open(self._prefsPath, "r")
            self._prefs = cPickle.load(f)
            f.close()
        except Exception:
            pass

        if not isinstance(self._prefs, type(_kDefaultPrefs)):
            self._prefs = _kDefaultPrefs


    ###########################################################
    def getPref(self, prefName):
        """Retrieve a preference value

        NOTE: This function is thread safe. Ensure any changes preserve that.

        @param  prefName  The name of the preference to retrieve
        @return prefVal   The value of the preference, or None
        """
        if wx.Platform == '__WXMAC__' and prefName == kHardwareAccelerationDevice:
            return "none"
        return self._prefs.get(prefName, _kDefaultPrefs.get(prefName, None))


    ###########################################################
    def setPref(self, prefName, prefVal, save=True):
        """Set a preference

        @param  prefName  The name of the preference to set
        @param  prefVal   The new value of the preference
        @param  save       If True, will attempt to save all preferences
        """
        self._prefs[prefName] = prefVal

        if not save:
            return

        try:
            f = open(self._prefsPath, "w")
            cPickle.dump(self._prefs, f)
            f.close()
        except Exception:
            return
