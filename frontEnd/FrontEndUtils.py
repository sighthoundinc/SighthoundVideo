#! /usr/local/bin/python

#*****************************************************************************
#
# FrontEndUtils.py
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

import os
import wx
import cPickle
import sys

from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kPrefsFile
from appCommon.CommonStrings import kRuleDir, kRuleExt, kQueryExt
from backEnd.BackEndPrefs import BackEndPrefs
from launch.Launch import Launch
from launch.Launch import serviceAvailable
from launch.Launch import kConfigKeyAutoStart
from launch.Launch import kConfigKeyBackend
from launch.Launch import kConfigValueTrue
from launch.Launch import kConfigValueFalse
from vitaToolbox.path.VolumeUtils import isRemotePath
from vitaToolbox.path.PathUtils import normalizePath


# The global data directory of the user, when running via a service.
_kDataDir = None

if wx.Platform == '__WXMAC__':
    editTxt = {'edit':' or attached'}
else:
    editTxt = {'edit':''}

_kTitleTextAutostart = "Configuration Error"
_kHeaderTextAutostart = \
    "Autostart incompatible with network%(edit)s storage" % editTxt
_kBodyTextAutostart = \
    "The autostart feature cannot be used in conjunction with "             \
    "network%(edit)s storage drives which you currently have as the "       \
    "target of your video storage or a rule response. To enable "           \
    "launching Arden AI at system startup first change these to "   \
    "local drives." % editTxt

_kTitleTextNetPath = 'Network%(edit)s drive selected' % editTxt
_kHeaderTextNetPath = \
    'Network%(edit)s drive use requires disabling autostart '               \
    'functionality' % editTxt
_kBodyTextNetPath = \
    'To use network%(edit)s drives as a storage target support for both '   \
    'autostart and running after user logout '                              \
    'must be disabled. Selecting "Yes" below will disable '                 \
    'these features and close the application. After restarting the '       \
    'application you will be able to configure network%(edit)s drives. '    \
    'Support for these features will be automatically restored '            \
    'in the future if the application detects that no network%(edit)s '     \
    'drives are in use.\n\n'                                                \
    'Would you like to disable autostart functionality?' % editTxt

if wx.Platform == '__WXMAC__':
    _kTitleTextAutostart = _kHeaderTextAutostart
    _kTitleTextNetPath = _kHeaderTextNetPath
else:
    _kBodyTextAutostart = _kHeaderTextAutostart + "\n\n" + _kBodyTextAutostart
    _kBodyTextNetPath = _kHeaderTextNetPath + "\n\n" + _kBodyTextNetPath


###############################################################################
def getUserLocalDataDir():
    """ Determines the user data directory. If we run as a service (OSX, Win32)
    the data directory gets told by the service - if it's not running then the
    caller must a) be prepared for that and b) probably go away because the
    system's not functioning, i.e. it can be used as service check if needed.

    @return The user data directory. None if it cannot be determined.
    """
    global _kDataDir
    if serviceAvailable():
        if _kDataDir is None:
            launch = Launch()
            if launch.open():
                try:
                    dataDir = launch.dataDir()
                    _kDataDir = None if not dataDir else dataDir
                finally:
                    try:
                        launch.close()
                    except:
                        pass
        return _kDataDir
    dataDir = wx.StandardPaths.Get().GetUserLocalDataDir()
    return os.path.join(os.path.dirname(dataDir), kAppName)


###############################################################################
def getServiceStartsBackend():
    """ Checks whether the service is the one starting the backend or not. Used
    to make an alternative launch by the frontend, hence it also depends if the
    service is generally available or not.

    @return  True if the service does the backend launching.
    """
    if not serviceAvailable():
        return False
    localDataDir = getUserLocalDataDir()
    launchConfig = Launch().getConfigOrDefaults(localDataDir)
    return kConfigValueTrue == launchConfig[kConfigKeyBackend]


###############################################################################
def setServiceStartsBackend(flag):
    """ Sets whether the service is the one starting the backend or not.

    @param  flag  True to let the service take care about backend launching.
    @return       True if storing the start flag succeeded.
    """
    localDataDir = getUserLocalDataDir()
    cfg = Launch().getConfigOrDefaults(localDataDir)
    cfg[kConfigKeyBackend] = kConfigValueTrue if flag else kConfigValueFalse
    return Launch().setConfig(cfg, localDataDir)


###############################################################################
def getServiceAutoStart():
    """ Checks whether the service starting the backend at system launch time.
    This will only happen if the service is responsible for starting the
    backend in general.

    @return  True if the service does autostart.
    """
    localDataDir = getUserLocalDataDir()
    launchConfig = Launch().getConfigOrDefaults(localDataDir)
    return kConfigValueTrue == launchConfig[kConfigKeyAutoStart]


###############################################################################
def setServiceAutoStart(flag):
    """ Sets whether the service should do autostart on system launch.

    @param  flag  True to autostart.
    @return       True if storing the start flag succeeded.
    """
    localDataDir = getUserLocalDataDir()
    cfg = Launch().getConfigOrDefaults(localDataDir)
    cfg[kConfigKeyAutoStart] = kConfigValueTrue if flag else kConfigValueFalse
    return Launch().setConfig(cfg, localDataDir)


###############################################################################
def getRemotePathsFromSettings():
    """Checks and returns a list of paths in the settings that resolve to remote
    paths.

    @return  remotePaths  List of remote paths found in the user settings.
    """

    # Initialize list where we keep track of remote paths found so far...
    remotePaths = []

    # Get the data directory...
    dataDir = getUserLocalDataDir()

    # Get the backend preferences...
    prefs = BackEndPrefs(os.path.join(dataDir, kPrefsFile))

    # Get the video storage location...
    videoStorageLocation = prefs.getPref('videoDir')

    # Check if the video storage path is a network path...
    if videoStorageLocation and isRemotePath(videoStorageLocation):
        remotePaths.append(("Video storage location", videoStorageLocation))

    # Get the rules/query directory...
    ruleDir = os.path.join(dataDir, kRuleDir)
    if os.path.isdir(ruleDir):
        fileNames = os.listdir(ruleDir)
    else:
        fileNames = []

    # Now loop through every rule, and check if the sound and export paths
    # are on any network paths...
    for fileName in fileNames:
        fileName = normalizePath(fileName)
        _, ext = os.path.splitext(fileName)
        if ext == kRuleExt:
            try:
                # Load the rule
                ruleFilePath = os.path.join(ruleDir, fileName)
                ruleFile = file(ruleFilePath, 'r')
                rule = cPickle.load(ruleFile)
                ruleFile.close()

                # Load it's associated query
                queryFileName = rule.getQueryName()+kQueryExt
                queryFilePath = os.path.join(ruleDir, queryFileName)
                queryFile = file(queryFilePath, 'r')
                queryModel = cPickle.load(queryFile)
                queryFile.close()

                responses = queryModel.getResponses()

                # Check if the sound path is a network path...
                _, soundResponseConfig = responses[2]
                soundPath = soundResponseConfig.get('soundPath', '')
                if soundPath and isRemotePath(soundPath):
                    remotePaths.append((
                        "Sound path in " + queryFileName, soundPath
                    ))

                # Check if the export path for clips is a network path...
                _, localExportResponseConfig = responses[5]
                exportPath = localExportResponseConfig.get('exportPath', '')
                if exportPath and isRemotePath(exportPath):
                    remotePaths.append((
                        "Export path in " + queryFileName, exportPath
                    ))

            except:
                # A rule failed to load. Do nothing, since there's nothing
                # we can do about here.  It will be logged by the backend
                # anyway if it runs into the same issue when loading rules.
                pass

    # Return the list of remote paths that we found...
    return remotePaths


###############################################################################
def promptUserIfRemotePath(path):
    """Asks the user if they would like to disable service from starting the
    backend if the given path is remote, we are running from frozen, the backend
    was launched from service, and we are running on Windows OS.

    Note:  When run on Mac, this function simply returns its argument.

    @param  path  A path as a string.

    @return  path  The path from the argument if the user was never prompted.
                   Otherwise, it will be an empty string.
    """
    if hasattr(sys, "frozen") and isRemotePath(path) and \
       wx.App.Get().isBackendLaunchedByService():

        dlg = wx.MessageDialog(
            wx.App.Get().GetTopWindow(),
            _kBodyTextNetPath,
            _kTitleTextNetPath,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION | wx.CENTER,
        )

        try:
            result = dlg.ShowModal()
            if result == wx.ID_YES:
                setServiceStartsBackend(False)
                wx.App.Get().CloseAppManually()
        finally:
            dlg.Destroy()

        return ''

    return path


###############################################################################
def promptUserIfRemotePathEvtHandler(evt):
    """Gets the string value stored in the event and pass it to
    promptUserIfRemotePath and if the string passed is not an acceptable path,
    the event's string value will be changed to the empty string.

    Note:  When run on Mac, this function behaves as a no-op.

    @param  evt  Text change event emitted by wx.TextEntry objects.
    """
    if not evt:
        return

    evtObj = evt.GetEventObject()

    if not isinstance(evtObj, wx.TextEntry):
        return

    if not promptUserIfRemotePath(evtObj.GetValue()):
        evtObj.ChangeValue('')


###############################################################################
def promptUserIfAutoStartEvtHandler(evt):
    """Unchecks the checkbox given by the event, and prompts the user why we
    will not allow them to check the box.

    Note 1: This event handler was designed to be used by the "_launchOnStartup"
            (for the "Auto start" feature) checkbox control in OptionsDialog.py.
            This function is placed here to contain all of the
            disabling/enabling of service handling in ONE place. In the future,
            if/when we decide to change or remove this function (and/or the
            other functions related to this one) it will be easier for future
            developers to find all of the logic pertaining to the
            disabling/enabling of service.

    Note 2: When run on Mac, this function behaves as a no-op.

    @param  evt  A wx.EVT_CHECKBOX event.
    """
    if (evt and (hasattr(sys, "frozen")) and
            (getRemotePathsFromSettings()) and
            (isinstance(evt.GetEventObject(), wx.CheckBox)) and
            (evt.GetEventObject().GetValue()) ):

        # First, uncheck the checkbox...
        evt.GetEventObject().SetValue(False)

        # Tell the user why we will not let them check the checkbox...
        dlg = wx.MessageDialog(
            wx.App.Get().GetTopWindow(),
            _kBodyTextAutostart,
            _kTitleTextAutostart,
            wx.OK | wx.ICON_INFORMATION | wx.CENTER,
        )

        try:
            _ = dlg.ShowModal()
        finally:
            dlg.Destroy()


###############################################################################
def determineGridViewCameras(cameras, order):
    """ Determines the cameras to be shown in the grid view. Tries to match
    reality with what the user has configured before regarding order.

    @param  cameras  The actual list of camera locations.
    @param  order    Order preference as formerly configured by the user.
    @return          List of cameras to finally show.
    """

    # Sort the camera list if there are no preferences yet.
    if not len(order):
        cameras = sorted(cameras)

    # Whatever was preferred should be honored, unless it doesn't exist anymore.
    result = []
    for camera in order:
        if camera in cameras:
            result.append(camera)

    # If there are new cameras which haven't been around during the last round
    # of preference editing we just add them to the end, but also sorted.
    newCameras = []
    for camera in cameras:
        if not camera in result:
            newCameras.append(camera)
    newCameras = sorted(newCameras)
    result.extend(newCameras)

    return result
