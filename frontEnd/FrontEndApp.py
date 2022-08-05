#!/usr/bin/env python

#*****************************************************************************
#
# FrontEndApp.py
#
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
# https://github.url/thing
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
import re
import shutil
from subprocess import Popen, PIPE
import sys
import tempfile
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.mvc.AbstractModel import AbstractModel
from vitaToolbox.windows.winUtils import registerForForcedQuitEvents
from vitaToolbox.wx.DelayedProgressDialog import DelayedProgressDialog
from vitaToolbox.wx.LookForOtherInstances import lookForOtherInstances
from vitaToolbox.sysUtils.FileUtils import safeRemove


# Local imports...
from BackEndClient import BackEndClient
from DbCorruptedDialog import DbCorruptedDialog

from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kFrontEndLogName
from appCommon.CommonStrings import kMaxRecordSize, kMatchSourceSize
from appCommon.CommonStrings import kBackendMarkerArg
from appCommon.CommonStrings import kReservedMarkerArg
from appCommon.CommonStrings import kMemStoreBackendReady
from appCommon.CommonStrings import kDefaultRecordSize
from appCommon.LicenseUtils import hasPaidEdition
from appCommon.DbRecovery import getCorruptDatabaseStatus
from appCommon.DbRecovery import setCorruptDatabaseStatus
from appCommon.DbRecovery import kStatusRecover
from appCommon.DbRecovery import kStatusReset

from BugReportDialog import BugReportDialog
from GetLaunchParameters import getLaunchParameters

from FrontEndFrame import FrontEndFrame
from FrontEndPrefs import getFrontEndPref, setFrontEndPref
from FrontEndUtils import getUserLocalDataDir
from FrontEndUtils import getServiceStartsBackend
from FrontEndUtils import getRemotePathsFromSettings
from FrontEndUtils import setServiceStartsBackend, setServiceAutoStart

from LicensingHelpers import getLicense

from launch.Launch import serviceAvailable
from launch.Launch import Launch
from launch.Launch import launchCheckMac
from launch.Launch import launchCheckWin
from launch.Launch import launchLog


# Constants...

# ...we'll wait this many seconds before showing the "please wait" dialog...
_kStartDialogWait = 5.0

# ...we'll wait this many seconds to connect to the backend after starting it...
_kConnectTimeout = 90

# ...we'll wait this many seconds for to backend to be operationally ready...
_kReadyTimeout = 15

# ...when we're testing for an already running backend, we'll wait this long...
_kTestConnectTimeout = 1

# We wait this many seconds for a normal quit to take effect...
_kQuitTimeout = 15

# We wait this many seconds for a force quit to take effect...
_kForceQuitTimeout = 3

# Used to describe the build # of the app...
_kBuildTemplateStr    = "Build %s"

# The file that build info is stored in.
_kBuildFile = "build.txt"

# Number of seconds to wait before giving up on license data to get loaded.
_kLicenseLoadTimeout=30


# Offer to move data...
_kMoveDataOffer = (
'''Would you like to import your existing data into Sighthound Video?'''
'''\n\n'''
'''This data will no longer be accessible by Vitamin D Video. Please '''
'''first ensure that no Vitamin D Video processes are running before '''
'''continuing, and make a backup of your existing data.'''
)
_kMoveDataOfferTitle = "Vitamin D Video installation detected"

_kMoveFailedText = (
'''Couldn't move existing data.'''
'''\n\n'''
'''This might be because a file is open in another application.'''
'''Hit OK to try again, or Cancel to exit the application.\n\n'''
'''Message: %s'''
)
_kMoveFailedTitle = "Couldn't move"

_kVideoMoveFailedText = (
'''Couldn't move existing video files.'''
'''\n\n'''
'''Sighthound Video could not migrate the existing video files. Hit OK '''
'''to continue launching the application and begin from scratch, or Cancel '''
'''to exit and attempt to manually back up existing video files. They may '''
'''be located at "%s" or "%s".\n\n'''
'''Message: %s'''
)
_kVideoMoveFailedTitle = "Couldn't move"

_kStartError = \
"The application could not be started.\nPlease wait a minute and try again."

_kServiceMissingWin32 = \
"""The service is not running.\nPlease check the Sighthound Video Launch """
"""entry in the 'Services' section of """
"""the Control Panel, or reinstall the application."""

_kRunningFromContainer = \
"%s cannot run from a container, or any external storage" % kAppName

_kServiceMissingMac = \
"""The service is not running.\nPlease reinstall the application."""

_kCrashTitle = "Error Report"
_kLaunchError = ('''It appears that %s previously had trouble starting. '''
'''Would you like to submit the error for analysis?''' % kAppName)
_kCrashError = ('''It appears that %s experienced a crash. Would you like '''
'''to submit the error for analysis?''' % kAppName)


_kDbReset = "Resetting databases ..."
_kDbRecovery = "Recovering databases ..."
_kDbRecoveryProgress = "Recovering databases (%d%%) ..."
_kDbRecoveryPollSecs = .5

_kDefaultStartDialogMessage = "Just a moment..."

# How long to wait for the service to get ready after activation steps.
_kLaunchCheckTimeout = 10

##############################################################################
class FrontEndApp(wx.App):
    """The main application class for the front end gui."""
    ###########################################################
    def __init__(self, logger):
        """FrontEndApp constructor.

        @param  logger  Our logger.
        """
        self._logger = logger

        # Call the superclass constructor.  This will call OnInit().
        wx.App.__init__(self, redirect=False)

        self._debugModeModel = _DebugModeModel()

    ###########################################################
    def OnInit(self):
        """Init the application for wx.App to function correctly.

        This is called by our superclass's constructor, and is generally
        considered the place to create the main window (called a Frame) for
        the app.  However, we do not create the Frame here.  There are many
        checks that take place before the Frame is created.  Some of those
        checks involve showing message boxes/dialogs to the user.  If a popup
        is shown to the user during OnInit, wx.App will forcefully close it
        because it hasn't finished initializing. So we just set the app's name
        and register the callback function for forced quit events here. After
        initialization, we must manually call PostInit where warnings and info
        popups can be shown to the user, and where the Frame may be created and
        shown.

        @return success  True if the init was successful. If False is returned,
                         wx.App will close the python interpreter.
        """
        # Set our app name before doing anything else, so that our wx paths
        # get set properly...
        self.SetAppName(kAppName)

        self.__callbackFunc = registerForForcedQuitEvents()

        self._closingApp = False
        self._closedWins = []

        return True


    ###########################################################
    def PostInit(self):
        """Init the rest of the application.

        This must be called manually directly _after_ this class has been
        instantiated. This is where warning and info popups can be shown to the
        user, and where the Frame is created and shown.

        @return success  True if the post-init was successful
        """
        isOSX = sys.platform == "darwin"

        if isOSX and \
           (sys.argv[0].startswith("/Volumes/") or sys.argv[0].startswith("/private/")):
            wx.MessageBox(_kRunningFromContainer, "Error",
                          wx.ICON_ERROR | wx.OK, None)
            return False

        if serviceAvailable():
            try:
                if isOSX:
                    buildStr = wx.GetApp().getAppBuildStr()
                    m = re.search('[0-9]+', buildStr)
                    if not m:
                        launchLog("no build number found in '%s'" % buildStr)
                        return False
                    build = "r%s" % m.group()
                    legacyDataDir = wx.StandardPaths.Get().GetUserLocalDataDir()
                    legacyDataDir = os.path.join(os.path.dirname(legacyDataDir),
                                                 kAppName)
                    checked = False
                    try:
                        checked = launchCheckMac(build, legacyDataDir,
                                                 _kLaunchCheckTimeout)
                    except:
                        pass
                    if not checked:
                        wx.MessageBox(_kServiceMissingMac, "Error",
                                      wx.ICON_ERROR | wx.OK, None)
                        return False
                else:
                    if not launchCheckWin():
                        wx.MessageBox(_kServiceMissingWin32, "Error",
                                      wx.ICON_ERROR | wx.OK, None)
                        return False
            except:
                launchLog("UNCAUGHT LAUNCH CHECK ERROR (%s)" %
                          sys.exc_info()[1])
                return False

        if isOSX:
            # We once used a hack to enable Retina support on the older wx we
            # were using. Not necessary anymore, but we want to make sure to
            # clean up our old stuff to avoid any possible trouble.
            #
            # TODO: remove eventually ...
            #
            try:
                retinaPatch = os.path.join(os.path.expanduser("~"), "Library",
                    "Preferences", "com.sighthound.sighthoundvideo.plist")
                if os.path.exists(retinaPatch):
                    os.remove(retinaPatch)
            except:
                pass

        # Check for other instances, on Windows. Mac inherently
        # prevents multiple instances of an app from running.
        if (wx.Platform == "__WXMSW__"):
            self._singleInstanceChecker = lookForOtherInstances()
            if self._singleInstanceChecker is None:
                return True

        self._startDlg = DelayedProgressDialog(_kStartDialogWait,
                                    "Starting %s..." % (kAppName),
                                    _kDefaultStartDialogMessage,
                                    parent=None, style=wx.PD_APP_MODAL)

        ready = False
        try:
            # Quit any old copies of the backend that are running
            isRightVersionRunning = self._handleOldBackends()

            # Offer to move the user's data directory if they are upgrading
            # from VDV to Sighthound Video. Must happen after setting app name
            # but before we do anything with the data directory...
            if not self._offerMoveDataDir():
                return False

            # Ensure we have the correct build file for the running app.
            self._copyBuildFile()

            # Now that we have an app name, we can find our data dir and point
            # our logger there.
            userLocalDataDir = getUserLocalDataDir()
            logDir = os.path.join(userLocalDataDir, "logs")
            self._logger.setLogDirectory(logDir)
            self._logger.enableDiskLogging()

            # If the database got corrupted we ask the user for consent first.
            databaseResetOnly = False
            dbCorrupted = getCorruptDatabaseStatus(userLocalDataDir)
            if dbCorrupted is not None:
                self._logger.info("DB corruption status %s" % str(dbCorrupted))
                dlg = DbCorruptedDialog(None)
                try:
                    result = dlg.ShowModal()
                finally:
                    dlg.Destroy()
                if wx.YES == result:
                    self._logger.info("DB recovery selected")
                    setCorruptDatabaseStatus([kStatusRecover], userLocalDataDir)
                if wx.NO == result:
                    self._logger.info("DB reset selected")
                    setCorruptDatabaseStatus([kStatusReset], userLocalDataDir)
                    databaseResetOnly = True
                if wx.CANCEL == result:
                    self._logger.info("DB manual recovery selected")
                    return False

            self._logger.info("Starting %s..." % kAppName)

            # On Mac built app, redirect stdout/stderr from C modules to
            # /dev/null so that they don't pollute the console.  This matches
            # Windows and seems like the best we can come up with for now.
            # See bug #503.
            frozen = hasattr(sys, "frozen")
            if frozen and (wx.Platform == "__WXMAC__"):
                self._cStdStreams = open("/dev/null", "a")
                os.dup2(self._cStdStreams.fileno(), 1)
                os.dup2(self._cStdStreams.fileno(), 2)

            def showStartError():
                wx.MessageBox(_kStartError, "Error", wx.ICON_ERROR|wx.OK, None)

            # For now, service on Windows is unable to reach any network paths
            # (whether it is by UNC or letter drive), so if any of the settings
            # contain network paths, we MUST _NOT_ allow the service to start
            # the backend. If the settings do not contain any network paths,
            # then we explicitly set the configuration file to allow service to
            # start the backend.
            serviceStartsBackend = getServiceStartsBackend()
            if frozen:
                netPathsUsed = getRemotePathsFromSettings()
                isSetSVCConfig = setServiceStartsBackend(not netPathsUsed)

                if netPathsUsed:
                    serviceStartsBackend = False

                # Disable autostart if service will not start the backend on
                # this run...
                if not serviceStartsBackend:
                    setServiceAutoStart(False)

                self._logger.info(
                    "Service %s launch the backend, because network paths %s "
                    "found in the settings: %s",
                    "should" if (not netPathsUsed) else "should NOT",
                    "were" if netPathsUsed else "were NOT",
                    netPathsUsed
                )

                if isSetSVCConfig:
                    self._logger.info("Service config file was set successfully...")
                else:
                    self._logger.error("Service config file could not be set!!!")

            if not isRightVersionRunning:

                # To run from source we still need to support the 'old' way of
                # launching the back-end, through forking for OSX that is ...
                if not serviceStartsBackend and wx.Platform == '__WXMAC__':
                    self._logger.info("About to fork back-end ...")
                    pid = os.fork()
                else:
                    pid = 0

                # If the backend runs as a service we just signal it to
                # (re)start everything ...
                if serviceStartsBackend:
                    self._logger.info("signaling service...")
                    launch = Launch()
                    if not launch.open():
                        self._logger.error("cannot connect to launch service")
                        showStartError()
                        return False
                    launchResult = launch.do(killFirst=True)
                    launch.close()
                    if launchResult is None:
                        self._logger.error("launch via service failed")
                        showStartError()
                        return False
                    else:
                        self._logger.info("launch initiated (x%08x, x%08x)" %
                                          launchResult)
                # If src/win or the forking child on src/mac...
                elif pid == 0:
                    self._logger.info("launching backend...")
                    openParams = getLaunchParameters()
                    openParams.extend(["--backEnd",
                                       userLocalDataDir.encode('utf-8'),
                    # mark the backend progress via an argument which is not
                    # used directly but picked up through process enumeration
                    # where we examine the command lines ...
                                       kBackendMarkerArg,
                    # this parameter is a placeholder, as a matter of fact it
                    # actually vanishes when we spawn a web server, as if there
                    # is a bug always dropping the last command line argument;
                    # thus it guarantees that the actual backend marker will
                    # make it and can then be replaced by nginx to the other
                    # marker value (kNginxMarkerArg) ...
                                       kReservedMarkerArg])

                    # I'm not sure if all of the closing of FDs is all that
                    # important on Mac now that we're running from a fork, but
                    # I don't think it hurts...
                    self._logger.disableDiskLogging()
                    subProc = Popen(openParams, stdin=PIPE, stdout=PIPE,
                                    stderr=PIPE,
                                    close_fds=(wx.Platform == "__WXMAC__"))
                    self._logger.enableDiskLogging()
                    subProc.stdin.close()
                    subProc.stdout.close()
                    subProc.stderr.close()

                    # On Mac, if we're the forking child, we've done our duty
                    # now that we've opened our subprocess.  Exit.  Use the
                    # special os._exit (not os.exit)
                    if wx.Platform == '__WXMAC__':
                        os._exit(0)
                else:
                    # Wait for our forked process to exit (Mac only)...
                    os.waitpid(pid, 0)

            # If database recovery is going we need to report it.
            self._logger.info("Checking DB status...")
            while True:
                status = getCorruptDatabaseStatus(userLocalDataDir)
                if status is None:
                    msg = _kDefaultStartDialogMessage
                else:
                    time.sleep(_kDbRecoveryPollSecs)
                    if status and "progress" == status[0]:
                        if databaseResetOnly:
                            msg = _kDbReset
                        else:
                            msg = _kDbRecoveryProgress % int(status[1])
                    else:
                        msg = _kDbRecovery
                self._startDlg.Pulse(msg)
                if status is None:
                    break

            # Wait until we can connect to the NMS.
            self._logger.info("Waiting for backend connection ...")

            backEndClient = BackEndClient()
            for _ in xrange(_kConnectTimeout * 10):
                if backEndClient.connect():
                    break
                time.sleep(.1)
                self._startDlg.Pulse()

            if backEndClient.isConnected():
                self._logger.info("Waiting for backend readiness ...")
                try:
                    for _ in xrange(_kReadyTimeout * 10):
                        item = backEndClient.memstoreGet(kMemStoreBackendReady,
                                                         .1, -1)
                        if item and item[0]:
                            ready = True
                            break
                        else:
                            self._startDlg.Pulse()
                except Exception, e:
                    self._logger.error(
                        "Waiting for backend readiness failed: " + str(e))

        finally:
            self._startDlg.Destroy()
            self._startDlg = None

        if not ready and not backEndClient.isConnected():
            showStartError()
            return False

        # Assure that we have a good license.  If not, we'll bail right now.
        # NOTE: If upgrading from beta (AKA: downgrading num cameras allowed),
        # there all cameras will continue recording while this dialog is up.
        # TODO: OK?
        lic = getLicense(backEndClient, None, _kLicenseLoadTimeout)
        if not lic:
            backEndClient.quit(_kQuitTimeout)
            backEndClient.forceQuit(_kForceQuitTimeout)
            return True

        # Check for any previous crashes and prompt user to send any
        # available logs.
        self._checkForCrashReports(backEndClient)



        # Get and cache whether the backend was launched by service or not. The
        # reason why we do this is so that all UI components of the entire app
        # can call wx.App.Get().isBackendLaunchedByService() without needing to
        # have a reference to the backend client. This value makes sense to
        # cache here because this property of the backend will not change during
        # the lifetime of the frontend.
        self._isBackendLaunchedByService = backEndClient.launchedByService()

        frame = FrontEndFrame(kAppName, backEndClient)
        self.SetTopWindow(frame)

        frame.Show(True)

        setFrontEndPref('launchFailures', 0)

        return True


    ############################################################
    def isBackendLaunchedByService(self,loop):
        """Gets whether or not the backend was launched by service.

        @return  bool  True if the backend was launched by service, and False
                       otherwise.
        """
        return self._isBackendLaunchedByService


    ############################################################
    def OnEventLoopEnter(self, loop):
        #loop = wx.EventLoopBase.GetActive()
        #print("loop=%s" % (loop,))
        if self._closingApp:
            self._CloseAppManually()


    ############################################################
    def OnEventLoopExit(self, loop):
        #loop = wx.EventLoopBase.GetActive()
        #print("loop=%s" % (loop,))
        pass


    ############################################################
    def IsAppClosingAutomatically(self):
        return self._closingApp


    ############################################################
    def CloseAppManually(self):
        if not self._closingApp:
            self._logger.info("Begin closing the app automatically...")
            self._closingApp = True
            self._CloseAppManually()


    ############################################################
    def _CloseAppManually(self):
        topWins = list(wx.GetTopLevelWindows())
        currLoop = wx.EventLoopBase.GetActive()

        if not currLoop:
            return

        # print(
        #     "currLoop=%s, numTopWins=%s, topWins=%s"
        #     % (currLoop, len(topWins), topWins)
        # )

        while len(topWins) > 0:
            topWin = topWins.pop()
            if topWin not in self._closedWins:
                self._closedWins.append(topWin)
                topWin.Close(True)
                #print("Ran close for frame or dialog...")
                break
            # else:
            #     print("IsBeingDeleted: %s" % (topWin.IsBeingDeleted(),))

        if currLoop and currLoop.IsMain():
            self._closedWins = []


    ############################################################
    def MacReopenApp(self):
        """Called when the dock icon is clicked, and ???

        I'm not sure if we actually need this. It seems to work OK without
        on 10.10 at least, but wary to remove. Fixed behavior to restore
        proper window.
        """
        # Saw self.GetTopWindow() be None in case 12035.
        focusControl = None
        if self.GetTopWindow():
            focusControl = self.GetTopWindow().FindFocus()

        # Raise the app to the foreground, attempting to ensure that our
        # highest level windowremains on top.
        windows = wx.GetTopLevelWindows()
        for win in windows:
            if focusControl and win == focusControl.GetTopLevelParent():
                win.Raise()
                return

        # If nothing had focus (common) or we can't find the focus owner
        # (not sure what would cause that)
        if windows:
            windows[len(windows)-1].Raise()


    ###########################################################
    def _offerMoveDataDir(self):
        """Offer to move the user's data directory if they've upgraded.

        @returns  shouldRun  False if the app should abort launching.
        """
        if getFrontEndPref("vdvImportOffered"):
            return True

        dataDir = getUserLocalDataDir()

        # Look for old data in "Vitamin D Video" and offer to move it...
        oldAppDir = os.path.join(os.path.split(dataDir)[0], "Vitamin D Video" + os.sep)
        if os.path.isdir(oldAppDir):
            choice = wx.MessageBox(_kMoveDataOffer, _kMoveDataOfferTitle,
                                   wx.YES_NO | wx.YES_DEFAULT, None)
            if choice == wx.YES:
                while True:
                    try:
                        os.rename(oldAppDir, dataDir)
                        setFrontEndPref("vdvImportOffered", True)
                    except Exception, e:
                        # If we can't just rename, give an error message.
                        choice = wx.MessageBox(_kMoveFailedText % str(e),
                                               _kMoveFailedTitle,
                                               wx.ICON_ERROR |
                                               wx.OK | wx.CANCEL, None)
                        if choice == wx.CANCEL:
                            return False
                    else:
                        # Video storage directories are stored as absolute
                        # paths in the prefs file. If they pointed to somewhere
                        # within the old data directory we need to update them.

                        # Guess at likely options in case of extreme failure.
                        oldVideoDir = os.path.join(oldAppDir, "videos")
                        newVideoDir = os.path.join(dataDir, "videos")
                        try:
                            from backEnd.BackEndPrefs import BackEndPrefs
                            from appCommon.CommonStrings import kPrefsFile
                            prefs = BackEndPrefs(os.path.join(dataDir, kPrefsFile))

                            oldVideoDir = prefs.getPref('videoDir')
                            if type(oldVideoDir) == str:
                                oldVideoDir = oldVideoDir.decode('utf-8')
                            if oldVideoDir is not None:
                                prefix = os.path.commonprefix([oldVideoDir, oldAppDir])
                                if prefix == oldAppDir:
                                    newVideoDir = os.path.join(dataDir, oldVideoDir[len(prefix):])
                                    prefs.setPref('videoDir', newVideoDir)

                            storageDir = prefs.getPref('dataDir')
                            if storageDir is not None:
                                prefix = os.path.commonprefix([storageDir, oldAppDir])
                                if prefix == oldAppDir:
                                    prefs.setPref('dataDir',
                                            os.path.join(dataDir, storageDir[len(prefix):]))

                        except Exception, e:
                            choice = wx.MessageBox(_kVideoMoveFailedText %
                                                   (oldVideoDir, newVideoDir, str(e)),
                                                   _kVideoMoveFailedTitle,
                                                   wx.ICON_ERROR |
                                                   wx.OK | wx.CANCEL, None)
                            if choice == wx.CANCEL:
                                return False
                        break

        setFrontEndPref("vdvImportOffered", True)
        return True


    ###########################################################
    def _copyBuildFile(self):
        dataDir = getUserLocalDataDir()
        buildFilePath = os.path.join(dataDir, _kBuildFile)

        # Copy the build file for next time...
        if os.path.exists(_kBuildFile):
            if not os.path.isdir(dataDir):
                os.makedirs(dataDir)
            shutil.copy(_kBuildFile, buildFilePath)


    ###########################################################
    def _handleOldBackends(self):
        """Find / kill old backends.

        As a side effect, this will also detect whether the right version of
        the backend is already running...

        @return isRightVersionRunning  True if the right version of the backend
                                       is already running.
        """
        client = BackEndClient()
        for _ in xrange(_kTestConnectTimeout * 10):
            didConnect = client.connect()
            if didConnect:
                break
            time.sleep(.1)
            self._startDlg.Pulse()

        if not didConnect:
            # Nothing wants to talk to us.  Do a force quit anyway in case
            # the back end crashed but other processes are still running.
            client.forceQuit(_kForceQuitTimeout, self._startDlg.Pulse)
            return False

        frozen = hasattr(sys, "frozen")
        if client.isConnected(frozen):
            # The right version is already there...
            return True

        # Wrong version is there...
        # ...quit it
        didQuit = client.quit(_kQuitTimeout, self._startDlg.Pulse)
        if not didQuit:
            client.forceQuit(_kForceQuitTimeout, self._startDlg.Pulse)

        return False


    ###########################################################
    def getDebugModeModel(self):
        """Return the data model for debug mode.

        @return debugModeModel  The data model for debug mode.
        """
        return self._debugModeModel


    ###########################################################
    def getAppBuildStr(self, lookInDir='.'):
        """Return a string describing the build of app.

        @param  lookInDir  The dir to look in for 'build.txt'.  The CWD by default.
        @return appVerStr  The app version string.
        """
        buildFilePath = os.path.join(lookInDir, _kBuildFile)

        try:
            buildStr = file(buildFilePath).read().split()[-1].strip()
        except Exception:
            buildStr = "unknown"
        return _kBuildTemplateStr % (buildStr)


    ############################################################
    def _checkForCrashReports(self, backEndClient):
        """If any hard crashes or failed launches, prompt the user to submit."""
        lastCheck = getFrontEndPref('lastCrashCheck')
        if lastCheck == 0:
            # Go back 6 hours by default if we've never checked before.
            lastCheck = time.time()-6*60*60

        launchFailures = getFrontEndPref('launchFailures')

        # Try to avoid any clock oddities.
        now = int(max(time.time(), lastCheck))

        try:
            prompt = _kLaunchError
            crashes = []
            logsToSend = []

            # OSX and WIN can check for failed launch files.
            tmpDir = tempfile.gettempdir()
            launchLogs = os.listdir(tmpDir)
            launchLogs = [os.path.join(tmpDir, log) for log in launchLogs
                    if log.startswith('sighthound')]

            # OSX can check for hard crashes.
            if wx.Platform == "__WXMAC__":
                # TODO: After OSX service, check global dir too?
                osDir = os.path.expanduser("~/Library/Logs/DiagnosticReports")
                crashes = os.listdir(osDir)
                crashes = [os.path.join(osDir, crash) for crash in crashes if
                    crash.startswith('Sighthound')]

                if len(crashes):
                    prompt = _kCrashError

            # The first time we see we've failed to launch we'll allow a retry.
            # If it occurs again we'll force the display dialog even if we have
            # no crash/launch failure files to attach. Something is still wrong
            # and we want to get them in contact with support without them
            # needing to look up contact or forum info.
            forcePrompt = False
            if launchFailures > 1:
                forcePrompt = True
                prompt = _kLaunchError
            else:
                # Increment the launch failure count. It'll be reset to 0 if we
                # continue and open.
                setFrontEndPref('launchFailures', launchFailures+1)

            # Include up to 3 recent logs from each category. Err on the side
            # of including info that might have been seen before rather than
            # missing it for "launch" files.
            launchLogs.sort(key = lambda x: os.path.getmtime(x))
            crashes = \
                [log for log in crashes if os.path.getmtime(log) >= lastCheck]
            logsToSend += launchLogs[-3:]
            logsToSend += crashes[-3:]

            if len(crashes) or forcePrompt:
                # Reset the count, as we'll want a little buffer before
                # re-prompting again.
                setFrontEndPref('launchFailures', 0)

                # We have logs we'd like to submit ask the user and then send.
                submit = wx.MessageBox(prompt, _kCrashTitle,
                        wx.ICON_ERROR | wx.YES_NO)
                if wx.YES == submit:
                    dlg = BugReportDialog(None, self._logger, backEndClient, logsToSend)
                    try:
                        dlg.ShowModal()
                    finally:
                        dlg.Destroy()

                # Should we try to remove files we submitted?
                # Until then, need to set lastCheck to max(lastCheck, maxmtime)
                # in case anyone had their clock in the future and got a crash.
                for log in crashes:
                    now = max(now, os.path.getmtime(log))


        except Exception, e:
            self._logger.error("Error checking for crash reports - " + str(e))

        # Update the 'last checked' time.
        setFrontEndPref('lastCrashCheck', now)





##############################################################################
class _DebugModeModel(AbstractModel):
    """A simple data model for keeping track of debug mode.

    Always just does a broadcast update, since there's only one member.
    """

    ###########################################################
    def __init__(self):
        """_DebugModeModel constructor."""
        super(_DebugModeModel, self).__init__()
        self._debugMode = None

    ###########################################################
    def _debugFileLocation(self):
        userLocalDataDir = getUserLocalDataDir()
        return None if userLocalDataDir is None else os.path.join(userLocalDataDir, "debugMode")

    ###########################################################
    def isDebugMode(self):
        """Return whether we're in debug mode.

        @return isDebugMode  True if we're in debug mode; False otherwise.
        """
        if self._debugMode is None:
            debugFile = self._debugFileLocation()
            if debugFile is None:
                # we aren't in the state where we can query debug mode yet
                return False
            self._debugMode = os.path.isfile(debugFile)
        return self._debugMode

    ###########################################################
    def setDebugMode(self, wantDebugMode):
        """Set debug mode and update our listeners.

        @param  wantDebugMode  True if we want debug mode; False otherwise.
        """
        # Force to a True bool, just to be paranoid (since we compare with ==)
        wantDebugMode = bool(wantDebugMode)
        if self._debugMode != wantDebugMode:
            if wantDebugMode:
                with open(self._debugFileLocation(), "w") as f:
                    f.write("Debug mode is on!")
            else:
                safeRemove(self._debugFileLocation())
                if os.path.isfile(self._debugFileLocation()):
                    # we've failed to remove the file -- and disable debug mode
                    wantDebugMode = True
            self._debugMode = wantDebugMode
            self.update()

##############################################################################
def validateOSVersion(logger):
    """
    Check against known problematic OSX version.
    If failing to retrieve version, or in other unexpected scenarios, err
    on side of caution, and proceed with the attempt to start the software.
    """
    isOSX = sys.platform == "darwin"
    if not isOSX:
        return True

    import platform
    ver = platform.mac_ver()
    if ver is None:
        logger.error("Could not retrieve OSX version")
        return True

    release = ver[0]
    if release is None or len(release) == 0:
        logger.error("OSX version release string is empty")
        return True

    releaseArr = release.split(".")
    if len(releaseArr) < 2:
        logger.error("OSX version release string value is unexpected:" + release)
        return True

    major = int(releaseArr[0])
    minor = int(releaseArr[1])
    hasPatch = len(releaseArr) > 2
    patch = 0 if not hasPatch else int(releaseArr[2])

    errStr = None;
    if major < 10 or (major == 10 and minor < 10):
        errStr = "Unsupported macOS version. macOS 10.10 or greater is required"
    elif major == 10 and minor == 12 and patch < 4:
        errStr = """Unsupported macOS version %s. This macOS version has a known problem, """\
                 """which prevents Sighthound Video from functioning correctly. """\
                 """Please upgrade macOS to 10.12.4 or later version.""" % release

    if errStr is not None:
        dlg = wx.MessageDialog(None,
                        errStr,
                        "Cannot start Sighthound Video",
                        wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        return False
    return True

##############################################################################
def main():
    # Grab the standard streams before creating the app.  This seems to be
    # needed on Windows.  Note that we can't give a log directory yet because
    # we can't use getUserLocalDataDir() until after the app is created...
    logger = getLogger(kFrontEndLogName)
    logger.grabStdStreams()


    # If OnInit() returns false, the app will automatically exit.
    app = FrontEndApp(logger)

    try:
        if not validateOSVersion(logger):
            return
    except:
        import traceback
        traceback.print_exc()

    # Immediately call PostInit() so that we perform our checks before the
    # application is started. If True is returned, start the MainLoop to begin
    # processing GUI events.  If false, log as an error.
    if app.PostInit():
        app.MainLoop()
    else:
        # When OnInit() returns false, we get a similar message, so I copied
        # that, and applied it here for when PostInit returns false.
        logger.error("PostInit returned false, exiting...")
    logger.info("Front end application closed...")


if __name__ == '__main__':
    main()
