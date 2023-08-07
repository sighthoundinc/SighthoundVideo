#!/usr/bin/env python

#*****************************************************************************
#
# FrontEndPrefs.py
#
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
import os
import cPickle as pickle
import sys
import getpass

# Common 3rd-party imports...
import wx

# Local imports...
from appCommon.CommonStrings import kAppName
from frontEnd.FrontEndUtils import getUserLocalDataDir

# These are stored in our app data directory...
_kPrefsFileFmt = "Gui Prefs%s.pkl"


# Default values for preferences...
_kDefaultPrefs = {
    # These all have to do with marking up video.  See VideoMarkupModel.
    "showBoxesAroundObjects": True,
    "showDifferentColorBoxes": True,
    "showRegionZones": False,

    # If true, we will show extra menu items for debugging.
    "showDebugMenuItems": False,

    # Used for the old "live import" dialog...
    "streamHistory" : [
    ],

    #Auto update prefs
    "skipVersion": 0, # version to skip notifing the user about
    "lastAutoUpdateTime" : 0, # time of last auto update
    "lastOffer": 0,   # last offer ID (integer)

    # VDV->Arden.ai prefs
    "vdvImportOffered": False,

    # If true, clips playback will continue down the results list once started.
    "wantContinuousPlayback": False,

    # When the app first starts up, it shouldn't be maximized. And
    # it should start with it's default position.
    "appWindowMaximized" : False,
    "prevAppWindowPosition" : wx.DefaultPosition,
    "prevAppWindowSize" : None,

    # Show the last view the app was closed in. "MonitorView" is the default
    # setting to preserve legacy behavior. "SearchView" is the only other
    # valid option for this setting.
    "openInMonitorOrSearchView": "MonitorView",

    # Store last path and other settings from export clip.
    "lastPathExportClip" : '',
    "lastTimestampOverlayExportClip": False,
    "lastBoundingBoxesExportClip": False,
    "lastFpsLimitExportClip": -1,
    "lastSizeLimitExportClip":-1,

    # Hide or show the daily timeline
    "showDailyTimeline" : True,

    # If True warn when the suport and upgrades contract is near expiration
    "supportRenewalWarning" : True,

    "lastLegacySigninSkip" : 0,
    "legacyPromptCount" : 0,

    "lastCrashCheck" : 0,
    "launchFailures" : 0,

    # Enable audio playback if available
    "playAudio" : 0,
    # Overlay timestamps whe
    "overlayTimestamp" : 0,
    # Remember the sort preference in the Search Results List in the Search View
    "isSortAscending": True,

    # Grid view layout
    "gridViewCols": 2,
    "gridViewRows": 2,
    "gridViewStart": 0,
    "gridViewOrder":  [
    ],
    "gridViewFps": 10,
    "gridViewShowInactive": 1,
    "hasConsentToSubmitVideo": False,
}


# Our global prefs, which is loaded the first time it's used.  We only
# contain values for things that the user overrides--for everthing else,
# we'll refer to the 'default' in the big table.
_prefs = None


##############################################################################
def getFrontEndPref(prefName):
    """Get the value of the preference for the given key.

    This will automatically load preferences from the preference file, if
    needed.  If the user hasn't entered a value for the given preference, this
    function will return the default.

    @param  prefName  The key of the preference to look up.
    @return value     The value of the preference, or None.
    """
    _loadPrefsIfNeeded()
    if prefName in _prefs:
        return _prefs[prefName]
    else:
        return _kDefaultPrefs.get(prefName, None)


##############################################################################
def setFrontEndPref(prefName, prefVal, save=True):
    """Set a preference

    @param  prefName  The name of the preference to set
    @param  prefVal   The new value of the preference
    @param  save       If True, will attempt to save all preferences
    """
    _loadPrefsIfNeeded()
    _prefs[prefName] = prefVal
    if save:
        _savePrefs()


##############################################################################
def _loadPrefsIfNeeded(wantForce=False):
    """Load the global _prefs variable, if needed.

    If prefs hasn't been loaded yet (or you want to force it), this will try
    to read the prefs from the pickle.  If any sort of error shows up, you'll
    get blank prefs.

    @param  wantForce  If True, we'll force load even if they're already loaded.
    """
    global _prefs
    if wantForce or _prefs is None:
        _prefs = {}
        userDataDir = getUserLocalDataDir()
        try:
            user = ' ' + getpass.getuser().encode("utf-8")
        except:
            user = None
        userNames = [""] if user is None else [user, ""]
        for userName in userNames:
            try:
                path = os.path.join(userDataDir, _kPrefsFileFmt % userName)
                f = open(path)
                _prefs = pickle.load(f)
                break
            except (IOError, EOFError):
                pass
            finally:
                try:
                    f.close()
                except:
                    pass


###########################################################
def _savePrefs():
    """Save the current _prefs global to its pickle.

    @return didFail  Returns true if we had some sort of IO error saving.
    """
    assert _prefs is not None, "Prefs must be loaded to be saved"

    try:
        userDataDir = getUserLocalDataDir()
        if not os.path.isdir(userDataDir):
            os.mkdir(userDataDir)
        try:
            user = ' ' + getpass.getuser().encode("utf-8")
        except:
            user = ""
        path = os.path.join(userDataDir, _kPrefsFileFmt % user)
        f = open(path, "w")
        pickle.dump(_prefs, f)

        return False
    except IOError:
        return True
    finally:
        try:
            f.close()
        except:
            pass


##############################################################################
def main():
    """OB_REDACT
       Our main code.  Allows setting/getting prefs from command line.
    """
    usage = "Usage: FrontEndPrefs.py [prefName [prefVal]]"

    # ...the name is critical so that prefs get stored in the right place.
    app = wx.App(False)
    app.SetAppName(kAppName)

    try:
        if len(sys.argv) == 1:
            # Just list all prefs...
            _loadPrefsIfNeeded()
            prefs = _kDefaultPrefs.copy()
            prefs.update(_prefs)
            print "\nAll prefs:"
            print "\n".join("* %s: %s" % item for item in prefs.iteritems())
        elif sys.argv[1] == '--help':
            # Print help
            print "\n" + usage + "\n"
        elif len(sys.argv) == 2:
            (prefName, ) = sys.argv[1:]
            print "\n* %s: %s" % (prefName, getFrontEndPref(prefName))
        else:
            # Get prefName and prefVal out of arugments...
            prefName, prefValStr = sys.argv[1:]

            # If the default value is not a string, assume we need an eval...
            if isinstance(_kDefaultPrefs[prefName], basestring):
                prefVal = prefValStr
            else:
                prefVal = eval(prefValStr)

            print "\nSetting %s to %s" % (prefName, str(prefVal))
            setFrontEndPref(prefName, prefVal)
    except Exception:
        print "\n" + usage + "\n"
        raise


##############################################################################
if __name__ == '__main__':
    main()
