#!/usr/bin/env python

#*****************************************************************************
#
# FrontEndFrame.py
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
import sys
import time
import urllib
import webbrowser

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.wx.CreateMenuFromData import createMenuFromData
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...
from appCommon.CommonStrings import kAppName, kDocumentationUrl, kForumsUrl
from appCommon.CommonStrings import kUpgradeFeaturesUrl
from appCommon.CommonStrings import kFrontEndLogName
from appCommon.CommonStrings import kLoginStatusLastUser
from appCommon.CommonStrings import kReleaseNotesUrl
from appCommon.CommonStrings import kRenewSupportUrl
from appCommon.CommonStrings import kVideoFolder
from appCommon.CommonStrings import kObjDbFile
from appCommon.CommonStrings import kClipDbFile
from appCommon.CommonStrings import kOpenSourceVersion
from appCommon.LicenseUtils import kEditionField, kExpiresField, kTrialEdition
from appCommon.LicenseUtils import kSerialField, kSupportField, kNoValueToken
from appCommon.LicenseUtils import isLegacyLicense
from appCommon.LicenseUtils import kStarterEdition

from AboutBox import ShowAboutBox

if not kOpenSourceVersion:
    from AppUpdateDialog import DoAutoUpdateCheck

from ArmCameras import handleArmRequest
from ArmCameras import handleDisarmRequest
if not kOpenSourceVersion:
    from BugReportDialog import BugReportDialog
from FrontEndPrefs import getFrontEndPref, setFrontEndPref
from FtpStatusDialog import FtpStatusDialog
from LicenseDialog import doShowLicenseDialog
from LicensingHelpers import SupportExpiredDialog
from LicensingHelpers import kSupportExpiredChoiceRenew
from LicensingHelpers import kSupportExpiredChoiceStarter
from LoginDialog import LoginDialog

# TODO: As back end evolves, will we continue importing it this way?
from backEnd.ClipManager import ClipManager
from backEnd.DataManager import DataManager
from backEnd.DebugLogManager import DebugLogManager
import backEnd.MessageIds as MessageIds

from MonitorView import MonitorView
from GridView import GridView
from OptionsDialog import OptionsDialog
from SearchView import SearchView, kCameraNameParam, kQueryNameParam
from LegacyBanner import LegacyBanner
from LegacyBanner import EVT_SHOW_LOGIN
from StarterBanner import StarterBanner
from TrialBanner import TrialBanner, EVT_DIRECT_PURCHASE
from UIPrefsDataModel import UIPrefsDataModel
from ViewToolbarControl import ViewToolbarControl, EVT_VIEW_CHANGED
from FrontEndUtils import getUserLocalDataDir

from vitaToolbox.wx.ToolbarBitmapTextButton import ToolbarBitmapTextButton

from videoLib2.python.VideoLibUtils import GetVideolibModulesList, GetVideoLibDebugConfigItems, GetVideoLibLogLevels

import MenuIds


def OB_ASID(a): return a
def OB_KEYARG(a): return a

# Constants...

_kMonitorViewNum = 0
_kGridViewNum = 1
_kSearchViewNum  = 2

_kIsWin = wx.Platform == "__WXMSW__"

if _kIsWin:
    # In Windows, the toolbar's size is taken into account.
    _kDefaultAppSize = (923, 781)

    # In Windows, "Options" is the name of the config UI.
    _kMenuOptions = "&Options"
else:
    _kDefaultAppSize = (921, 742)

    # By leaving the text label blank, wxPython will automatically add the
    # correct labelling and functionality of "Preferences".
    _kMenuOptions = ""

_kHideExitPrompt = 'hideExitPrompt'

_kProblemEncountered = 'The application has encountered a problem and must exit.'

_kQuitTimeout = 25
_kForceQuitTimeout = 3

_kBackEndPollMsecs = 4000

_kUpdateTimeMS = 24 *60*60 *1000

# TODO: Could try grabbing programmatically, but this is always 22 as far as
#       I can tell. Toolbar move hack will go away on wx upgrade as well.
_kOSXMenuBarHeight = 22

_kAuthRepromptDelaySeconds = 24*60*60

_kSecondsPerDay = 60*60*24
_kSupportWarnText = "Your support and upgrade subscription expires in %d days"
_kSupportWarnOneText = "Your support and upgrade subscription expires in %d day"
_kSupportWarnSoonText = "Your support and upgrade subscription expires in less than 24 hours"
_kSupportExpiredText = "Your support and upgrade subscription has expired"
_kSupportWarnBmpPath = "frontEnd/bmps/Renew_warn.png"
_kSupportExpiredBmpPath = "frontEnd/bmps/Renew_expired.png"
_kSupportWarnBmpDownPath = "frontEnd/bmps/Renew_warn_down.png"
_kSupportExpiredBmpDownPath = "frontEnd/bmps/Renew_expired_down.png"

# Reprompt legacy users who skip sign when they launch again after this period.
_kLoginRepromptInterval = _kSecondsPerDay*14
_kLoginMaxPrompts = 5


##############################################################################
class FrontEndFrame(wx.Frame):
    """The main frame for the front end gui."""
    def __init__(self, frameName, backEndClient):
        """FrontEndFrame constructor.

        @param  frameName      The name to display in the title bar.
        @param  backEndClient  A connection to the back end app.
        """
        # Load previous size and position of the app window.
        self._prevAppWindowPosition = getFrontEndPref("prevAppWindowPosition")
        self._prevAppWindowSize = getFrontEndPref("prevAppWindowSize")
        self._topLeftDisplayId = getFrontEndPref("prevAppTopLeftDisplay")
        self._bottomRightDisplayId = getFrontEndPref("prevAppBottomRightDisplay")


        # Load if the window was maximized when it was closed.
        self._appWindowMaximized = getFrontEndPref("appWindowMaximized")

        wx.Frame.__init__(self, None, -1, frameName, self._prevAppWindowPosition)

        # Keep track of our normal title
        self._frameName = frameName

        # We will call these to prepare for exiting, they do not have the
        # ability to cancel exit, though they can delay (a LITTLE BIT) if needed
        self._exitNotificationList = []

        # We will call these after initialization of the app so that child windows
        # can restore preferences that might get overridden by other initializations.
        self._prefsNotificationList = []

        # Tuples (fn,args) to be called (once) when the frame becomes active.
        self._activationCalls = []

        self._lastSupportExpiredMessage = None

        self._terminatedBackEnd = False

        self._debugModeModel = wx.GetApp().getDebugModeModel()
        self._debugModeModel.addListener(self._handleDebugModeChange)

        self._logger = getLogger(kFrontEndLogName)

        self._backEndClient = backEndClient

        self._uiPrefsDataModel = UIPrefsDataModel(backEndClient)

        dataDirectory = backEndClient.getStorageLocation()
        videoDirectory = os.path.join(backEndClient.getVideoLocation(),
                                      kVideoFolder)

        self._currentView = None
        self._clipManager = ClipManager(self._logger)
        self._clipManager.open(os.path.join(dataDirectory, kClipDbFile))
        self._dataManager = DataManager(self._logger, self._clipManager,
                                        videoDirectory)
        self._dataManager.open(os.path.join(dataDirectory, kObjDbFile))
        #self._currentPipelineName = "Default"

        # Prevent displaying an auth reprompt too frequently. Track the last
        # display in seconds.
        self._showingLoginDialog = False
        self._lastAuthPromptSeconds = 0

        # Any IDs that we need to be constant...
        self._armCamerasId = wx.NewId()
        self._allCamerasOffId = wx.NewId()

        # Initialize everything
        self._initMenus()
        self._initToolbar()
        self._initUiWidgets()

        # Set the app icons.  On Mac, the icon is set implicitly.
        if (wx.Platform == "__WXMSW__"):
            icons = wx.IconBundle()
            icons.AddIcon(os.path.join("icons", "SmartVideoApp.ico"), wx.BITMAP_TYPE_ICO)
            self.SetIcons(icons)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Start a periodic timer we'll use to poll the back end for messages.
        self._backEndTimer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnBackEndTimer, self._backEndTimer)
        self._backEndTimer.Start(_kBackEndPollMsecs)
        self._backEndErrorCount = 0

        # Check for updates and then every 24 hours
        # ...do a CallAfter to see if it fixes the build machine...

        self._autoupdateTimer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnAutoCheck, self._autoupdateTimer)

        diffInMS = int(1000*(time.time()-getFrontEndPref("lastAutoUpdateTime")))
        if (diffInMS>_kUpdateTimeMS) or (diffInMS < 0):
            diffInMS = 2*1000 # wait 2 seconds and do the update

        self._autoupdateTimer.Start(diffInMS, True)

        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)

        # Setting the window size from preferences.
        if self._prevAppWindowSize:
            self.SetSize(self._prevAppWindowSize)
            self.Layout()
        else:
            # If there is no previous size recorded, use the
            # default app size. This is not the minimum size
            # of the app; we just want it to be presented in
            # a nice way, and this is a good size to use.
            self.SetSize(_kDefaultAppSize)
            self.Layout()
        if self._appWindowMaximized:
            self.Maximize(True)
            self.Layout()

        # If the window size has changed, we need to give the other hidden
        # view a chance to resize before setting sash preferences. If the
        # sash preferences are set before the view has a chance to resize,
        # the gravity settings for the sash from the multiSplitterWindow
        # will distort the view, and overwrite the sash position preferences.
        passiveViews = [self._monitorView, self._searchView, self._gridView]
        passiveViews.remove(self._currentView)
        for passiveView in passiveViews:
            passiveView.SetSize(self._currentView.GetSize())
            passiveView.Layout()

        # Call functions in the preferences notification list
        # to give child windows the chance to restore their own preferences.
        # There are some preferences that, when restored, get overridden due
        # to the initialization process of the rest of the app.
        for callableFn in self._prefsNotificationList:
            callableFn()

        wx.CallAfter(self._showLoginDialog, False, True)

        self._uiPrefsDataModel.addListener(self._handleSupportWarningChange,
                key='supportWarning')
        self._uiPrefsDataModel.update('time')

        self._uiPrefsDataModel.addListener(self._handleGridViewChange,
                                           key="gridView")

        self.Bind(wx.EVT_DISPLAY_CHANGED, self.OnDisplayChange)

        wx.CallAfter(self._updateSupportRenewal)
        wx.CallAfter(self.OnDisplayChange, None)

        # Set up debug logging
        self._debugLogManager = DebugLogManager("UI", getUserLocalDataDir())
        self._handleDebugModeChange(self._debugModeModel)


    ###########################################################
    def OnDisplayChange(self, event):
        """Check to see if the display resolution has changed, or
        if the app is starting off-screen. If so, change our
        position and size appropriately.

        @param  event  The display-changed event object.

        Note: This function should be called in a wx.CallAfter(),
              because window size and position information finalizes
              after the frame's __init__ function.
        """

        changeInSizeNeeded = False

        topLeftDisp, bottomRightDisp = self._getCurrentDisplayIds()
        topRightDisp = wx.Display.GetFromPoint(self.GetPosition() + (self.GetSize().width, 0))
        if topLeftDisp != self._topLeftDisplayId or \
           bottomRightDisp != self._bottomRightDisplayId or \
           (topLeftDisp == wx.NOT_FOUND and topRightDisp == wx.NOT_FOUND):
            # one of the displays had changed, so we'll move the window to (0,0)
            # see if it'll fit at current size, or we'll need to resize it as well
            # self._logger.info("Moving the window: topLeftDisp=" + str(topLeftDisp) +
            #                         " prevTopLeftDisp=" + str(self._topLeftDisplayId) +
            #                         " bottomRightDisp=" + str(bottomRightDisp) +
            #                         " prevBottomRightDisp=" + str(self._bottomRightDisplayId) +
            #                         " topRightDisp=" + str(topRightDisp) +
            #                         " curPos=" + str(self.GetPosition()) +
            #                         " curSize=" + str(self.GetSize()) )
            screenPosX, screenPosY, screenWidth, screenHeight = wx.GetClientDisplayRect()
            curWidth, curHeight = self.GetSize()
            if curWidth > screenWidth:
                curWidth = screenWidth
                changeInSizeNeeded = True
            if curHeight > screenHeight:
                curHeight = screenHeight
                changeInSizeNeeded = True

            self.SetPosition( (0, 0) )
            if changeInSizeNeeded:
                self.SetSize( (curWidth, curHeight) )
            self.Layout()

            self._topLeftDisplayId, self._bottomRightDisplayId = self._getCurrentDisplayIds()



    ###########################################################
    def OnActivate(self, event):
        """Handle activate events.

        @param  event  The activate event.
        """

        if wx.Platform == '__WXMAC__':
            # If we're not active, do some housekeeping...
            if not event.GetActive():
                # Make sure that we release capture if we aren't active...
                if self.HasCapture():
                    self.ReleaseMouse()

        event.Skip()

        # Activation calls happen in a safe(r) zone.
        wx.CallAfter(self._doActivateCalls)


    ###########################################################
    def _activeCall(self, fn, *args):
        """ To make an arbitrary call. If the window is not active yet (e.g.
        able to properly pop a modal dialog) the all will be delayed until
        activation happens.

        @param  fn    The function to call.
        @param  args  Optional function parameters.
        """
        if self.IsActive():
            fn(*args)
        else:
            self._logger.info("delaying call for activation")
            self._activationCalls.append((fn, args))
            return


    ###########################################################
    def _doActivateCalls(self):
        """ Execute delayed calls, at activation point.
        """
        acs = self._activationCalls
        self._activationCalls = []
        for ac in acs:
            try:
                ac[0](*ac[1])
            except:
                self._logger.error("activation call failed (%s)" %
                                   sys.exc_info()[1])


    ###########################################################
    def _hasCameras(self):
        """Return true if cams are running or could possibly run.

        Check if any cameras are running or could possibly run without
        futher user intervention.

        @return hasCams  True if cams are running or could possibly run.
        """
        hasCameras = False
        try:
            camNames = self._backEndClient.getCameraLocations()
            for camName in camNames:
                _, _, enabled, extras = \
                            self._backEndClient.getCameraSettings(camName)
                frozen = extras.get('frozen', False)
                if enabled and not hasCameras and not frozen:
                    # If the camera is enabled either has rules with responses
                    # enabled return now so we don't stop the back end.
                    rules = \
                        self._backEndClient.getRuleInfoForLocation(camName)
                    for _, _, _, enabled, responses in rules:
                        if enabled and responses:
                            hasCameras = True
                            break
        except Exception:
            self._logger.error("Exception checking for running cameras.",
                               exc_info=True)

        return hasCameras

    ###########################################################
    def _getCurrentDisplayIds(self):
        pos = self.GetPosition()
        w, h = self.GetSize()
        topLeftDisplayId = wx.Display.GetFromPoint(pos)
        bottomRightDisplayId = wx.Display.GetFromPoint(pos+(w,h))
        return topLeftDisplayId, bottomRightDisplayId

    ###########################################################
    def OnClose(self, event):
        """Handle close events.

        @param  event  The close event.
        """
        self._logger.info("Front end requested to close")

        # Stop getting messages from the back end.
        # Note: if in the future we can't do this because we need to get
        # messages from the back end while it's quitting, we should set a
        # flag here so that OnBackEndTimer() will ignore exceptions thrown
        # by getMessage().  That will start failing when the back end quits.
        self._backEndTimer.Stop()

        # Make the current view go passive, especially so we don't touch the
        # backend anymore.
        self._currentView.prepareToClose()

        # If we haven't terminated the back end, we have to decide two things:
        # - did the user really want to exit?
        # - do we want to kill the back end?
        #
        # If the back end is already gone, there is no choice--we just exit.
        if not self._terminatedBackEnd:

            # Check if there is a good reason to keep the back end running
            # (we'll keep it running if there are still active cameras).
            hasCameras = self._hasCameras()

            # We might want to give the user a chance to cancel the close...
            if (event.CanVeto()                         and
                (not getFrontEndPref(_kHideExitPrompt)) and
                hasCameras                                 ):

                dlg = _exitInfoDialog(self)
                try:
                    response = dlg.ShowModal()
                    if response != wx.OK:
                        event.Veto()

                        # Restart the back end timer.
                        self._backEndTimer.Start(_kBackEndPollMsecs)

                        # Bail...
                        return
                finally:
                    dlg.Destroy()

            # If the app is being closed automatically, the backend is supposed
            # to be completely closed too.
            if not hasCameras or wx.App.Get().IsAppClosingAutomatically():
                self.forceBackendExit()

        # If they close the main frame, it means we want the app to exit now,
        # even if there are other windows open (because we are a one-main-window
        # application).  We will use sys.exit().  This will throw an exception
        # that should propagate all the way up and seems to stop wx OK (we
        # hope).  Other solutions we played with:
        # - If we just call event.Skip() here, we get into trouble if we have
        #   child windows.  We get weird crashes (don't remember if Mac, PC, or
        #   both).  ...and the app doesn't seem to quit on PC?
        # - If we try to close all windows, childmost to parentmost, we get
        #   into weird event-loop closing issues on Windows.  Maybe would be
        #   solvable by closing one window per idle event (?), but that wasn't
        #   tried.
        #
        # Before we call sys.exit(), call other people and let them know.  This
        # lets people who have threads clean them up (since sys.exit doesn't
        # play well with threads).  This is needed because it looks like
        # destructors aren't really getting called correctly when we use
        # sys.exit().
        for callableFn in self._exitNotificationList:
            callableFn()

        # Save position and size of the window, the current display resolution,
        # and whether the window was maximized (Windows OS only).
        topLeftDisp, bottomRightDisp = self._getCurrentDisplayIds()
        setFrontEndPref("prevAppWindowPosition", self.GetPosition())
        setFrontEndPref("prevAppWindowSize", self.GetSize())
        setFrontEndPref("appWindowMaximized", self.IsMaximized())
        setFrontEndPref("prevAppTopLeftDisplay", topLeftDisp)
        setFrontEndPref("prevAppBottomRightDisplay", bottomRightDisp)


        # Save the view we are closing in.
        openViewPref = "SearchView"
        if self._currentView == self._monitorView:
            openViewPref = "MonitorView"
        elif self._currentView == self._gridView:
            openViewPref = "GridView"
        setFrontEndPref("openInMonitorOrSearchView", openViewPref)

        """A workaround for a crash, where we'd segfault in child control
        destructor eventually calling a paint handler. (SV-88) We hide
        ourselves, to prevent any paint handlers from occurring during the
        teardown.
        """
        self._currentView.Hide()

        if wx.App.Get().IsAppClosingAutomatically():
            self.Unbind(wx.EVT_ACTIVATE)
            self.Destroy()
        else:
            sys.exit(0)


    ###########################################################
    def registerExitNotification(self, call):
        """Register the given callable to be called when we're exiting.

        The callable can't cancel the exit, but it will be told about it.  It
        can delay a little, if needed.

        TODO: If needed, add a way to unregister?

        @param  call  The callable to register.
        """
        self._exitNotificationList.append(call)


    ###########################################################
    def registerPrefsNotification(self, call):
        """Register the given callable to be called when we're restoring preferences.

        @param  call  The callable to register.
        """
        self._prefsNotificationList.append(call)


    ###########################################################
    def forceBackendExit(self):
        """Quit the back end."""
        self._backEndTimer.Stop()

        self._terminatedBackEnd = True

        # Exit the back end
        f = wx.Frame(None)
        progDlg = wx.ProgressDialog("Closing %s..." % kAppName,
                            "Just a moment...                             ",
                            parent=f, style=wx.PD_APP_MODAL)
        try:
            #self._logger.info("About to quit backend...")
            didQuit = self._backEndClient.quit(_kQuitTimeout, progDlg.Pulse)
            #self._logger.info("didQuit: %s" % didQuit)
            if not didQuit:
                self._logger.warn(
                    "Back end wasn't responsive to quit; forcing."
                )
                self._backEndClient.forceQuit(_kForceQuitTimeout,
                                              progDlg.Pulse)
        except Exception, e:
            self._logger.error("Quitting failed with exception %s" % str(e))
        finally:
            #self._logger.info("about to destroy progDlg...")
            progDlg.Destroy()
            f.Destroy()
            #self._logger.info("progDlg destroyed successfully...")


    ###########################################################
    def shouldAnimateChild(self, childWin):
        """Return True if the given child window should be animating.

        We won't animate a child window if one of the following is true:
        - The child isn't visible.
        - We've been minimized.
        - Any subwindows have been opened.
        - We're midway through closing.

        @return shouldAnimateChild  True if our children should animate.
        """

        topWindows = 1
        topWinList = wx.GetTopLevelWindows()
        if len(topWinList) > 1:
            for topWin in topWinList:
                try:
                    if (topWin != self) and \
                       (not hasattr(topWin, OB_ASID('_dontBlockAninmation'))):
                        topWindows+=1
                except Exception:
                    pass

        return ((childWin.IsShownOnScreen()) and
                (topWindows == 1)            and
                (not self.IsIconized())         )


    ###########################################################
    def OnNotImplemented(self, event):
        wx.MessageBox("Not implemented", parent=self)


    ###########################################################
    def _initMenus(self):
        """Init / bind to any menu commands..."""
        menuBar = wx.MenuBar()

        if wx.Platform == '__WXMAC__':
            # No file menu on Mac...
            fileMenuData = []

            # Throw "Exit" into the Tools menu, since we don't have a File
            # menu.  It doesn't matter where we put it (well, the Window menu
            # doesn't work, but otherwise it doesn't matter), since wx will
            # relocate it.  ...but we don't want to put it in the File menu
            # because when wx relocates it, we'll end up with a blank File
            # menu (we want no File menu at all)...
            # Note: MacOS will give it the command-Q shortcut.
            extraToolsData = (
                ("", "", wx.ID_EXIT, self.OnExit),
            )

            # Want Command-W to do a close of the app.  No File Menu on Mac, so
            # we put it in Window menu.  This matches System Preferences...
            # Note that it's purposely OnExit, not OnClose.  The OnClose()
            # will get called automatically by the exit code.
            windowMenuData = [
                ("&Window",
                    ("&Close\tCtrl+W", "", wx.ID_ANY, self.OnExit),
                ),
            ]
        else:
            # Windows file menu is standard...
            fileMenuData = [
                ("&File",
                    ("", "", wx.ID_EXIT, self.OnExit),
                ),
            ]

            # No extra tools data on Windows...
            extraToolsData = tuple()

            # No window menu...
            windowMenuData = []

        self._monitorViewMenuId = wx.NewId()
        self._searchViewMenuId = wx.NewId()
        self._gridViewMenuId = wx.NewId()

        # Data structure for the contents of the menus and menu items
        conditionalAny = wx.ID_NONE if kOpenSourceVersion else wx.ID_ANY

        menuData = \
            fileMenuData + \
            [
                (MenuIds.kViewMenuEx,
                    ("Monitor View\tCtrl-1", "", self._monitorViewMenuId, self.OnMenuChangeView),
                    ("Grid View\tCtrl-2", "", self._gridViewMenuId, self.OnMenuChangeView),
                    ("Search View\tCtrl-3", "", self._searchViewMenuId, self.OnMenuChangeView),
                    (None, None, None, None),
                    # The SearchView binds to these and manages them.
                    ("x Show &Boxes Around Objects", "", wx.ID_ANY, None),
                    ("x Show Different &Color Boxes", "", wx.ID_ANY, None),
                    ("x Show &Region Zones", "", wx.ID_ANY, None),
                    ("x Show &Daily Timeline", "", wx.ID_ANY, None),
                ),
                (MenuIds.kControlsMenuEx,
                    ("Play\tSpace", "", wx.ID_ANY, None),
                    (None, None, None, None),
                    ("Previous Clip\tUp", "", wx.ID_ANY, None),
                    ("Next Clip\tDown", "", wx.ID_ANY, None),
                    ("Top Clip in List\tShift+Up", "", wx.ID_ANY, None),
                    ("Bottom Clip in List\tShift+Down", "", wx.ID_ANY, None),
                    ("Previous Day\tCtrl+Up", "", wx.ID_ANY, None),
                    ("Next Day\tCtrl+Down", "", wx.ID_ANY, None),
                    (None, None, None, None),
                    ("Next Frame\tRight", "", wx.ID_ANY, None),
                    ("Previous Frame\tLeft", "", wx.ID_ANY, None),
                    ("Forward 2 Seconds\tShift+Right", "", wx.ID_ANY, None),
                    ("Backward 2 Seconds\tShift+Left", "", wx.ID_ANY, None),
                    ("Next Event in Clip\tCtrl+Right", "", wx.ID_ANY, None),
                    ("Previous Event in Clip\tCtrl+Left", "", wx.ID_ANY, None),
                    ("First Event in Clip\tEnter", "", wx.ID_ANY, None),
                    (None, None, None, None),
                    ("* 1/2 Speed\tAlt+0", "", wx.ID_ANY, None),
                    ("+ 1x Speed\tAlt+1", "", wx.ID_ANY, None),
                    ("* 2x Speed\tAlt+2", "", wx.ID_ANY, None),
                    ("* 4x Speed\tAlt+4", "", wx.ID_ANY, None),
                    ("* 16x Speed\tAlt+5", "", wx.ID_ANY, None),
                    (None, None, None, None),
                    ("x Continuous Playback\tc", "", wx.ID_ANY, None),
                    (None, None, None, None),
                    ("x &Mute Audio", "", wx.ID_ANY, None),
                 ),
                (MenuIds.kToolsMenuEx,
                    # The SearchResultsPlaybackPanel handles these and also
                    # manages showing / hiding as needed...
                    (MenuIds.kExportClipMenuEx, "", wx.ID_ANY, None),
                    (MenuIds.kExportClipForBugReportMenuEx, "", wx.ID_ANY, None),
                    (MenuIds.kExportFrame, "", wx.ID_ANY, None),
                    (MenuIds.kExportAllWithinTimeRangeMenu, "", wx.ID_ANY, None),
                    (MenuIds.kSubmitClipForAnalysis, "", conditionalAny, None),
                    (MenuIds.kSubmitClipForAnalysisWithNote, "", conditionalAny, None),

                    (MenuIds.kDeleteClipMenuEx, "", wx.ID_ANY, self.OnNotImplemented),
                    ("&Select All Clips\tCtrl-A", "", wx.ID_ANY, self.OnNotImplemented),
                    (None, None, None, None),

                    ("&Add Camera...\tCtrl-N", "", wx.ID_ANY, self.OnNotImplemented),
                    ("&Edit Camera...\tCtrl-E", "", wx.ID_ANY, self.OnNotImplemented),
                    ("Edit Camera &Location...", "", wx.ID_ANY, self.OnNotImplemented),
                    ("&Remove Camera...", "", wx.ID_ANY, self.OnNotImplemented),
                    ("Re&connect to Camera", "", wx.ID_ANY, self.OnNotImplemented),

                    (None, None, None, None),
                    ("Visit Camera &Web Page", "", wx.ID_ANY, self.OnNotImplemented),

                    (None, None, None, None),
                    ("Ar&m Cameras...", "", self._armCamerasId, self.OnArmCameras),
                    ("T&urn Off Cameras", "", self._allCamerasOffId, self.OnDisarmCameras),

                    (None, None, None, None),
                    ("&FTP Status", "", wx.ID_ANY, self.OnFtpStatus),
                    # (None, None, None, None), Separator auto-added on Win...
                    (_kMenuOptions, "", wx.ID_PREFERENCES, self.OnOptions),
                ) + extraToolsData,
                ("&Help",
                    ("&Reference Guide", "", wx.ID_HELP, self.OnHelp),
                    ("Support Forums", "", conditionalAny, self.OnForums),
                    ("Report a &Problem...", "", conditionalAny, self.OnReportAProblem),
                    (None, None, conditionalAny, None),
                    ("Learn About &Upgrade Features...", "", conditionalAny, self.OnLearnAboutUpgrades),
                    ("Show License Information", "", conditionalAny, self.OnShowLicenseInformation),
                    (None, None, None, None),
                    ("Check for Updates...", "", conditionalAny, self.OnUpdate),
                    ("Release Notes", "", conditionalAny, self.OnReleaseNotes),
                    # (None, None, None, None), Separator auto-added on Win...
                    ("&About %s" % kAppName, "", wx.ID_ABOUT, self.OnAbout),
                ),
            ] + \
            windowMenuData

        # Create each menu and its items
        for item in menuData:
            menuLabel = item[0]
            menuItems = item[1:]
            menu = createMenuFromData(menuItems, self)
            menuBar.Append(menu, menuLabel)

        self.SetMenuBar(menuBar)

        # Create the debug menu and store in a member...
        debugMenuData = [ ("x Overlay &Timestamp On Clips", "", wx.ID_ANY, None) ]
        for item in GetVideoLibDebugConfigItems():
            debugMenuData.append( ("x " + item, "", wx.ID_ANY, self.OnLoggingChange) )
        debugMenuData.append((None, None, None, None))
        self._debugMenu = createMenuFromData(debugMenuData, self)

        logLevelSubMenuData = []
        for item in GetVideoLibLogLevels():
            prefix = "+ " if item[1] else "* "
            logLevelSubMenuData.append( (prefix + item[0], "", wx.ID_ANY, self.OnLoggingChange) )
        self._debugMenu.AppendSubMenu(createMenuFromData(logLevelSubMenuData, self), "Log Level", "");

        modulesSubMenuData = []
        for item in GetVideolibModulesList():
            modulesSubMenuData.append( ("x " + item,   "", wx.ID_ANY, self.OnLoggingChange) )
        self._debugModulesSubmenu = self._debugMenu.AppendSubMenu(
                                                createMenuFromData(modulesSubMenuData, self),
                                                "Modules", "");


    ###########################################################
    def _initToolbar(self):
        """Init / bind the window's toolbar..."""
        toolbar = self.CreateToolBar()
        toolbar.SetWindowStyle(wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT)

        toolbar.SetToolBitmapSize((24, 24))

        if wx.Platform == '__WXMSW__' :
            # Stop the toolbar from flickering by setting to double buffered.
            # This happens in Windows only.
            toolbar.SetDoubleBuffered(True)
            # Setting the toolbar to doube buffered makes its background solid
            # black. To fix that, we just hijack its paint event, and clear the
            # paint DC. Technically, we can do whatever we want with it now; we
            # can draw our own themes and colours if we wanted to.
            def OnPaint(event):
                dc = wx.AutoBufferedPaintDCFactory(toolbar)
                dc.Clear()
            toolbar.Bind(wx.EVT_PAINT, OnPaint)

        bmpNames = [["View_Monitor_Unselected_MouseUp.png",
                     "View_Monitor_Unselected_MouseDown.png",
                     "View_Monitor_Selected_MouseUp.png",
                     "View_Monitor_Selected_MouseDown.png"],
                    ["View_Grid_Unselected_MouseUp.png",
                     "View_Grid_Unselected_MouseDown.png",
                     "View_Grid_Selected_MouseUp.png",
                     "View_Grid_Selected_MouseDown.png"],
                    ["View_Search_Unselected_MouseUp.png",
                     "View_Search_Unselected_MouseDown.png",
                     "View_Search_Selected_MouseUp.png",
                     "View_Search_Selected_MouseDown.png"]]
        bmps = []
        for bmpNamesForView in bmpNames:
            bmpsForView = [wx.Bitmap("frontEnd/bmps/" + bmpName)
                           for bmpName in bmpNamesForView]
            bmps.append(bmpsForView)

        self._viewControl = ViewToolbarControl(toolbar, bmps)
        self._viewControl.setSelection(_kSearchViewNum)
        self._viewControl.Bind(EVT_VIEW_CHANGED, self.OnViewChanged)

        toolbar.AddControl(self._viewControl)
        toolbar.Realize()

        self._renewButton = None
        self._renewSpacer = None
        self._renewTimer = None

        #self._numBaseTools = toolbar.GetToolsCount()


    ###########################################################
    def _updateBanner(self, lic=None):
        """Ensure the banner is in the correct state for the current license.

        @param  lic  The license to reference, None to query the back end.
        """
        if lic is None:
            lic = self._backEndClient.getLicenseData()

        if lic[kEditionField] == kTrialEdition:
            self._trialBanner.setExpiration(lic[kExpiresField])
            self._trialBanner.showBanner(True)
            self._legacyBanner.Hide()
            if self._starterBanner: self._starterBanner.Hide()
        else:
            self._trialBanner.showBanner(False)
            if isLegacyLicense(lic):
                if self._starterBanner: self._starterBanner.Hide()
                self._legacyBanner.Show()
                # Must come after show, may hide the banner.
                self._legacyBanner.updateBanner(lic)
            else:
                self._legacyBanner.Hide()

                if lic[kEditionField] == kStarterEdition:
                    # If we're not a legacy license and we're in starter then
                    # show the starter banner.
                    if not self._starterBanner:
                        self._starterBanner = StarterBanner(self,
                                self._backEndClient)
                        self._sizer.Insert(0, self._starterBanner, 0, wx.EXPAND)
                    self._starterBanner.Show()
                elif self._starterBanner:
                    self._starterBanner.Hide()

        # When the banners swap in and out, we need to update the min size and
        # current size.
        minWidth, minHeight = self._realBestSize

        if self._trialBanner.IsShown():
            minHeight += self._trialBanner.GetBestSize().GetHeight()
        elif self._legacyBanner.IsShown():
            minHeight += self._legacyBanner.GetBestSize().GetHeight()
        elif self._starterBanner and self._starterBanner.IsShown():
            minHeight += self._starterBanner.GetBestSize().GetHeight()

        _, screenHeight = wx.Display().GetClientArea().GetSize()
        width, height = self.GetSize()

        # Update the min size and current size
        self.SetMinSize((minWidth, minHeight))
        if wx.Platform == "__WXMSW__":
            if self.IsMaximized():
                self.Layout()
                return
        self.SetSize((width, min(screenHeight, max(height, minHeight))))
        self.Layout()


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""
        self._sizer = wx.BoxSizer(wx.VERTICAL)

        # Create the views
        self._trialBanner = TrialBanner(self, self._backEndClient)
        self._legacyBanner = LegacyBanner(self, self._backEndClient,
                self.OnShowLicenseInformation)
        self._starterBanner = None
        self._searchView = SearchView(self, self._dataManager,
                                      self._clipManager,
                                      self._backEndClient)
        self._searchView.Hide()
        self._monitorView = MonitorView(self, self._backEndClient,
                                        self._dataManager, self._doSearch,
                                        self._activateMonitorView)
        self._monitorView.Hide()
        self._gridView = GridView(self, self._backEndClient);
        self._gridView.Hide()
        viewSizer = wx.BoxSizer(wx.VERTICAL)
        viewSizer.Add(self._searchView, 1, wx.EXPAND)
        viewSizer.Add(self._monitorView, 1, wx.EXPAND)
        viewSizer.Add(self._gridView, 1, wx.EXPAND)
        self._sizer.Add(viewSizer, 1, wx.EXPAND)
        self.SetSizer(self._sizer)

        # Make the search view active, hide the others.
        self._realBestSize = None
        for view in [self._monitorView, self._gridView, self._searchView]:
            self._switchView(view)
            bestSize = self.GetBestSize()
            if self._realBestSize is None:
                self._realBestSize = bestSize
            # FIXME: works, but isn't ideal at all ... need a better strategy
            #        because initial views will size themselves way too high
            #        if there are many cameras present
            self._realBestSize[0] = max(self._realBestSize[0], bestSize[0])
            self._realBestSize[1] = max(self._realBestSize[1], bestSize[1])

        self.SetMinSize(self._realBestSize)
        self.SetSize(self._realBestSize)

        # Hide or show the banners.  Must be called after
        # SetMinSize and SetSize have been called.
        self._sizer.Insert(0, self._trialBanner, 0, wx.EXPAND)
        self._sizer.Insert(0, self._legacyBanner, 0, wx.EXPAND)
        self._updateBanner()

        self.Bind(EVT_DIRECT_PURCHASE, self.OnShowLicenseInformation)
        self.Bind(EVT_SHOW_LOGIN, self.OnLoginRequested)

        # If this is the first time we've launched the app we want to switch to
        # the monitor view and show the CameraSetupWizard. 'hasRunBefore' is
        # set in _showLoginDialog. Otherwise, switch to the last view the app
        # was closed in.
        if (not getFrontEndPref('hasRunBefore')) and \
            (not len(self._backEndClient.getCameraLocations())):
            # If there are any existing configured cameras we'll skip
            # the special behavior.
            self._switchView(self._monitorView)
        else:
            openViewPref = getFrontEndPref('openInMonitorOrSearchView')
            if openViewPref == 'SearchView':
                self._switchView(self._searchView)
            elif openViewPref == 'GridView':
                self._switchView(self._gridView)
            else:
                self._switchView(self._monitorView)


    ############################################################
    def OnExit(self, event=None):
        """Quit the program

        @param  event  The event (ignored).
        """
        # Close, don't use wx.Exit.  That way, python destructors get called.
        #
        # NOTE: Don't do anything important in this function, since if you
        # close the main window it will bypass this function and go straight
        # to the Window's close...
        #
        # We call Close with a CallAfter, which hopefully helps make the app
        # quit more cleanly on Mac on 10.5 if you do the following applescript:
        #   tell application "Sighthound Video" to quit
        #
        # Note: this function is not intended for other code to call--it is
        # only called in response to the menu item (or similar cases)...
        wx.CallAfter(self.Close)


    ############################################################
    def quietClose(self):
        """Close the app without prompting the user"""

        self.Close(True)


    ############################################################
    def OnHelp(self, event=None):
        """Open a web browser window with documentation.

        @param  event  The event (ignored).
        """
        webbrowser.open(kDocumentationUrl)


    ############################################################
    def OnForums(self, event=None):
        """Open a web browser window to the support forums.

        @param  event  The event (ignored).
        """
        webbrowser.open(kForumsUrl)


    ############################################################
    def OnReleaseNotes(self, event=None):
        """Open a web browser window to the app release notes.

        @param  event  The event (ignored).
        """
        webbrowser.open(kReleaseNotesUrl)


    ############################################################
    def OnLearnAboutUpgrades(self, event=None):
        """Open a web browser window with info about upgrades.

        @param  event  The event (ignored).
        """
        webbrowser.open(kUpgradeFeaturesUrl)


    ############################################################
    def OnReportAProblem(self, event=None):
        """Allow the user to report a bug.

        @param  event  The event (ignored).
        """
        dlg = BugReportDialog(self, self._logger, self._backEndClient)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ############################################################
    def OnAbout(self, event=None):
        """Show the about box.

        @param  event  The event (ignored).
        """
        ShowAboutBox(self, self._backEndClient)


    ############################################################
    def OnUpdate(self, event=None):
        """Check for an app update.

        @param  event  The event (ignored).
        """
        if self._allowUpdateChecks():
            DoAutoUpdateCheck(self, False, self.forceBackendExit,
                              self._backEndClient)
        else:
            wx.MessageBox('You must sign in with a Sighthound Account '
                'to continue receiving application updates.',
                'Updates unavailable', wx.OK | wx.ICON_ERROR,
                self.GetTopLevelParent())


    ############################################################
    def OnShowLicenseInformation(self, event=None):
        """Show licensing information

        @param  event  The event (ignored).
        """
        # Allow auth remprompts, despite how recent prior were or
        # the license dialog won't work.
        self._lastAuthPromptSeconds = 0
        doShowLicenseDialog(self, self._backEndClient)


    ############################################################
    def OnArmCameras(self, event=None):
        """Arm Cameras.

        @param  event  The event (ignored).
        """
        handleArmRequest(self, self._backEndClient)


    ############################################################
    def OnDisarmCameras(self, event=None):
        """Disarm Cameras.

        @param  event  The event (ignored).
        """
        handleDisarmRequest(self, self._backEndClient)


    ############################################################
    def OnFtpStatus(self, event=None):
        """Show FTP status dialog.

        @param  event  The event (ignored).
        """
        dlg = FtpStatusDialog(self, self._backEndClient)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnAutoCheck(self, event=None):
        """Check for an app update.

        @param  event  The event (ignored).
        """
        if self._allowUpdateChecks():
            DoAutoUpdateCheck(self, True, self.forceBackendExit,
                              self._backEndClient)

        # Call again in 24 hours
        setFrontEndPref("lastAutoUpdateTime", time.time(), True)

        if self._autoupdateTimer.IsOneShot():
            self._autoupdateTimer.Stop()

            del self._autoupdateTimer

            self._autoupdateTimer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self.OnAutoCheck, self._autoupdateTimer)
            self._autoupdateTimer.Start(_kUpdateTimeMS)


    ###########################################################
    def _allowUpdateChecks(self):
        """Check if updates are allowed or not.

        @return allow  True if update checks are allowed.
        """
        if kOpenSourceVersion:
            return False
        if isLegacyLicense(self._backEndClient.getLicenseData()):
            return False

        return True

    ###########################################################
    def ProcessLoggingMenu(self, menu, settings):
        for item in menu.GetMenuItems():
            submenu = item.GetSubMenu()
            if submenu is not None:
                self.ProcessLoggingMenu(submenu, settings)
            else:
                label = item.GetItemLabel()
                if label is not None and label != '':
                    settings[label] = item.IsChecked()

    ###########################################################
    def OnLoggingChange(self, event):
        debugSettings = {}
        self.ProcessLoggingMenu(self._debugMenu, debugSettings)
        # if trace logging is enabled, disable the ability to configure individual modules' log levels
        traceEnabled = debugSettings.get(GetVideoLibLogLevels()[0][0] ,False)
        self._debugMenu.Enable( self._debugModulesSubmenu.GetId(),  not traceEnabled )
        self._backEndClient.setDebugConfiguration(debugSettings)
        self._debugLogManager.SetLogConfig(debugSettings)




    ###########################################################
    def OnViewChanged(self, event):
        """Handle a change in views.

        @param  event  The event (ignored).
        """
        selection = self._viewControl.getSelection()

        if selection == _kMonitorViewNum:
            self._switchView(self._monitorView)
        elif selection == _kGridViewNum:
            self._switchView(self._gridView)
        elif selection == _kSearchViewNum:
            self._switchView(self._searchView)
        else:
            assert False, "Unknown view %d" % selection


    ###########################################################
    def OnMenuChangeView(self, event):
        """Handle a change in views.

        @param  event  The EVT_MENU event.
        """
        menuId = event.GetId()

        if menuId == self._monitorViewMenuId:
            self._switchView(self._monitorView)
        elif menuId == self._gridViewMenuId:
            self._switchView(self._gridView)
        elif menuId == self._searchViewMenuId:
            self._switchView(self._searchView)
        else:
            assert False, "Unknown view %d" % selection


    ############################################################
    def _switchView(self, newView, viewParams={}):
        """Switch the active view

        @param  newView     The view to make active
        @param  viewParams  A dictionary of params to give to the new view.
        """
        if newView == self._currentView:
            return

        if newView == self._monitorView:
            self._viewControl.setSelection(0)
        elif newView == self._gridView:
            self._viewControl.setSelection(1)
        elif newView == self._searchView:
            self._viewControl.setSelection(2)
        else:
            assert False, "Unknown view %d" % selection

        menu = self.GetMenuBar()
        menu.Enable(self._monitorViewMenuId, newView != self._monitorView)
        menu.Enable(self._searchViewMenuId, newView != self._searchView)
        menu.Enable(self._gridViewMenuId, newView != self._gridView)

        # Switch the views
        self.Freeze()
        try:
            if self._currentView is not None:
                self._currentView.deactivateView()
                self._currentView.Hide()
            self._currentView = newView
            self._currentView.Show()
            self._currentView.SetFocus()

            # Inform the new view it is active
            self._currentView.setActiveView(viewParams)

            self.Layout()
        finally:
            self.Thaw()


    ############################################################
    def OnOptions(self, event=None):
        """Display the options dialog.

        @param  event  The menu event (ignored).
        """
        dlg = OptionsDialog(self, self._backEndClient, self._dataManager,
                            self._logger, self._uiPrefsDataModel)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ############################################################
    def _doSearch(self, cameraLocation, queryName):
        """Perform a search in the search view.

        @param  cameraLocation  The name of the camera location to search.
        @param  queryName       The name of the search to perform.
        """
        self._switchView(self._searchView, {kCameraNameParam:cameraLocation,
                                            kQueryNameParam:queryName})


    ############################################################
    def _activateMonitorView(self):
        """Switch to the monitor view."""
        self._switchView(self._monitorView)


    ############################################################
    def _handleDebugModeChange(self, debugModeModel):
        """Handle a change in debug mode.

        @param  debugModeModel  Should match self._debugModeModel.
        """
        assert debugModeModel == self._debugModeModel

        menuBar = self.GetMenuBar()
        existingDebugMenuId = menuBar.FindMenu("Debug")

        if debugModeModel.isDebugMode():
            #self._populatePipelineSubmenu()
            if existingDebugMenuId == wx.NOT_FOUND:
                menuBar.Append(self._debugMenu, "&Debug")
        else:
            if existingDebugMenuId != wx.NOT_FOUND:
                menuBar.Remove(existingDebugMenuId)


    ############################################################
    def SetTitle(self, newTitle): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Set the title of the frame.

        We override the default version of this function from the frame so
        that our children can use the title temporarily (for debug info), then
        set the title back to default.  ...in other words, this behaves like
        the normal SetTitle() except that if you pass None, the title will
        be reset to the default title.

        @param  newTitle  The new title; if None, the default will be used.
        """
        if newTitle is None:
            newTitle = self._frameName
        else:
            newTitle = "%s - %s" % (self._frameName, newTitle)
        super(FrontEndFrame, self).SetTitle(newTitle)


    ###########################################################
    def OnBackEndTimer(self, event=None):
        """Check for and handle messages from the back end app.

        @param event  The timer event, ignored.
        """
        try:
            msg = self._backEndClient.getMessage()
            self._backEndErrorCount = 0
        except Exception:
            self._backEndErrorCount += 1
            if self._backEndErrorCount >= 5:
                # If the back end dies for any reason notify the user and exit.
                self._logger.error("Problems talking to back end.  Exiting.",
                                   exc_info=True)
                self._backEndTimer.Stop()
                self._terminatedBackEnd = True
                wx.MessageBox(_kProblemEncountered, kAppName, wx.ICON_ERROR | wx.OK,
                              self.GetTopLevelParent())
                self.Close(True)
            return

        if not msg:
            return

        msgId = msg[0]

        if msgId == MessageIds.msgIdDirectoryRemoveFailed:
            path = msg[1]
            self._logger.info('Directory removal failed: ' + str(path))
            wx.MessageBox('The folder "%s" could not be completely removed. '
                          ' You will need to manually delete it.' % path,
                          kAppName, wx.ICON_WARNING | wx.OK,
                          self.GetTopLevelParent())
        elif msgId == MessageIds.msgIdDirectoryCreateFailed:
            path = msg[1]
            errorText = 'The folder "%s" could not be created.' % msg[1]
            self._logger.info(errorText)
            wx.MessageBox(errorText, kAppName, wx.ICON_ERROR | wx.OK,
                          self.GetTopLevelParent())
        elif msgId == MessageIds.msgIdOutOfDiskSpace:
            self._logger.info("Received out of disk space message")
        elif msgId == MessageIds.msgIdDatabaseCorrupt:
            self._logger.info("Received corrupt db message, exiting.")
            self._backEndTimer.Stop()
            self._terminatedBackEnd = True
            wx.MessageBox(_kProblemEncountered, kAppName,
                          wx.ICON_ERROR | wx.OK, self.GetTopLevelParent())
            self.Close(True)
        elif msgId == MessageIds.msgIdLicenseChanged:
            try:
                self._logger.info("License change getting applied...")
                newLic = msg[2]
                self._updateBanner(newLic)
                self._updateSupportRenewal()
                self._monitorView.handleLicenseChange()
                self._gridView.handleLicenseChange()

                # TEMPORARY - this is only needed until the legacy drop dead
                # date. This addresses a legacy license converting to a starter
                # when the user had never logged in. Without this the user
                # wouldn't be prompted until the next UI launch.
                if not isLegacyLicense(newLic) and \
                        newLic[kEditionField] == kStarterEdition:
                    # _showLoginDialog will handle not displaying if the
                    # user is already logged in.
                    self._showLoginDialog()

                self._logger.info("License changed from %s to %s" %
                        (msg[1][kEditionField], newLic[kEditionField]))
            except Exception, e:
                self._logger.error("License change error: " + str(e))
        elif msgId == MessageIds.msgIdLicenseSupportExpired:
            lem = self._lastSupportExpiredMessage
            if lem and lem[3] == lem[3] and lem[2] == lem[2]:
                self._logger.info("suppressed support expiration reprompt")
            else:
                self._lastSupportExpiredMessage = msg
                self._activeCall(self._onSupportExpired, msg[1], msg[3])
        elif msgId == MessageIds.msgIdNeedRelogin:
            self._logger.info("Need re-auth, prompting user")
            self._showLoginDialog(True)
        else:
            self._logger.warn("Unsupported message ID '%s'." % str(msgId))


    ###########################################################
    def _onSupportExpired(self, expiredSeconds, serial):
        """ Prompts the support expiration dialog.

        @param  expiredSeconds  Number of seconds the support expired before the
                                major release date of the current installation.
        @param  serial          License serial number.
        """
        self._logger.info("License support expired, prompting user ...")
        dlg = SupportExpiredDialog(self, serial, expiredSeconds)

        try:
            dlg.ShowModal()

            # Get the choice the user made after the dialog has been closed but
            # *BEFORE* it gets destroyed.
            choice = dlg.GetChoiceSelection()

        except Exception, e:
            self._logger.error("Couldn't show support expired dialog: " + str(e))

            # Assuming the dialog did not show since we're in this block, change
            # the choice to 'kSupportExpiredChoiceRenew' because at least this
            # will cause a browser page to open with the renew support page.
            # The dialog's default choice is 'kSupportExpiredChoiceQuit'.
            # This is just in case they hit 'cancel' or close out of the dialog
            # without hitting any of the buttons somehow. However, this behavior
            # is undesirable if the user opens the app, and then it suddenly
            # closes just because the dialog doesn't show. At least with
            # renewing upon exception, the app will continue to run, and the
            # renew page will show up for the user. If they get annoyed by this
            # behavior and complain that this is happening to them, at least
            # we'll know it's because an exception has occured here.
            choice = kSupportExpiredChoiceRenew

        finally:
            dlg.Destroy()

        self._onSupportExpiredChoice(choice)


    ###########################################################
    def OnLoginRequested(self, event):
        """Handle a login dialog display request.

        @param  event  The EVT_SHOW_LOGIN event.
        """
        self._showLoginDialog()


    ###########################################################
    def _showLoginDialog(self, authError=False, onLaunch=False):
        """Display the user login dialog.

        @param  authError  If True dialog will always be shown, otherwise only
                           display if the user has not previously logged in.
        @param  onLaunch   Should be set to true if this is an 'on launch'
                           display request.
        """
        if self._showingLoginDialog:
            return

        if not authError:
            try:
                if self._backEndClient.getLoginStatus()[kLoginStatusLastUser]:
                    # If the user has at one point logged in previously and we aren't
                    # prompting for auth due to an auth error, return.
                    return
            except Exception, e:
                self._logger.error("Login status query failed: " + str(e))

        if authError:
            # If prompting for an auth error ensure we haven't done so recently.
            timeElapsed = time.time()-self._lastAuthPromptSeconds
            if timeElapsed < _kAuthRepromptDelaySeconds:
                return

            # Update our last auth prompt time.
            self._lastAuthPromptSeconds = time.time()

        try:
            if isLegacyLicense(self._backEndClient.getLicenseData()):
                # Only display on launch every X days and up to Y times for
                # legacy users.
                now = int(time.time())
                if onLaunch:
                    promptCount = getFrontEndPref("legacyPromptCount")
                    lastPrompt = getFrontEndPref("lastLegacySigninSkip")
                    if (_kLoginMaxPrompts <= promptCount) or \
                            ((now-lastPrompt) < _kLoginRepromptInterval):
                        return
                    setFrontEndPref("lastLegacySigninSkip", now)
                    setFrontEndPref("legacyPromptCount", promptCount+1)
        except:
            pass

        self._showingLoginDialog = True

        dlg = LoginDialog(self, self._backEndClient, authError)
        result = wx.CANCEL
        try:
            if not kOpenSourceVersion:
                result = dlg.ShowModal()
            else:
                result = wx.OK
        except Exception, e:
            self._logger.error("Couldn't show login dialog: " + str(e))
        finally:
            self._showingLoginDialog = False
            dlg.Destroy()

        if result != wx.OK:
            # An OK result indicates either a successful log in or a cancel
            # by a legacy user. If one of those cases does not apply, exit
            # the application, back end included.
            self.forceBackendExit()
            self.Close(True)
        else:
            # The user has logged in or has the right to skip, perform any
            # first run issues needed.
            if not getFrontEndPref('hasRunBefore'):
                setFrontEndPref('hasRunBefore', True)
                if not len(self._backEndClient.getCameraLocations()):
                    # If there are any existing configured cameras we'll skip
                    # the special behavior.
                    evtId = self.GetMenuBar().FindMenuItem("Tools", "Add Camera...")
                    evt = wx.CommandEvent(wx.EVT_MENU.typeId, evtId)
                    self.GetEventHandler().AddPendingEvent(evt)

                    # Ensure that the video directory exists. If not, if the user
                    # returns to the search view without configuring cameras the
                    # LocateVideoDialog will be incorrectly displayed.
                    try:
                        _, _, videoDir = self._dataManager.getPaths()
                        if not os.path.isdir(videoDir):
                            os.makedirs(videoDir)
                    except Exception:
                        self._logger.error("The video directory could not be created")

            # Ensure our banner (if any) reflects the correct state.
            self._updateBanner()


    ############################################################
    def _onSupportExpiredChoice(self, choice):
        """ Callback when the support expiration dialog is closed.

        @param  choice  User's choice about what to do next.
        """
        self._logger.info("support expiration choice is '%s'" % choice)
        if choice == kSupportExpiredChoiceRenew:
            self.OnRenewSupport()
        elif choice == kSupportExpiredChoiceStarter:
            self._backEndClient.unlinkLicense()
        else: #kSupportExpiredChoiceQuit:
            self.forceBackendExit()
            self.Close(True)


    ############################################################
    def OnRenewSupport(self, event=None):
        """Open a web browser to renew support.

        @param  event  The event (ignored).
        """
        serial = self._backEndClient.getLicenseData().get(kSerialField, "")
        if serial == kNoValueToken:
            serial = ""
        elif serial:
            serial = urllib.quote(serial)
        webbrowser.open(kRenewSupportUrl % serial)


    ###########################################################
    def _updateSupportRenewal(self, _=None):
        """Hide/Show/Update the support renewal toolbar button.

        @param  _  Ignored.
        """
        if not self._renewTimer:
            self._renewTimer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self._updateSupportRenewal,
                    self._renewTimer)

        try:
            self._renewTimer.Stop()
            toolbar = self.GetToolBar()

            # Delete any existing support renewal button and spacer.
            if self._renewButton:
                toolbar.DeleteTool(self._renewButton.GetId())
                self._renewButton = None
            if self._renewSpacer:
                toolbar.DeleteTool(self._renewSpacer.GetId())
                self._renewSpacer = None

            if not self._uiPrefsDataModel.shouldShowSupportWarning():
                return

            lic = self._backEndClient.getLicenseData()
            if isLegacyLicense(lic):
                return

            exp = int(lic[kSupportField])
            now = time.time()

            if exp < 0 or now < exp-30*_kSecondsPerDay:
                # No need for renewal, set a timer to check again in a day.
                self._renewTimer.Start(_kSecondsPerDay*1000, True)
                return
            elif now < exp:
                # Warn that support is expiring soon
                daysLeft = (exp-now)/_kSecondsPerDay
                if daysLeft < 1:
                    text = _kSupportWarnSoonText
                elif daysLeft == 1:
                    text = _kSupportWarnOneText % daysLeft
                else:
                    text = _kSupportWarnText % daysLeft
                bmpPath = _kSupportWarnBmpPath
                bmpDownPath = _kSupportWarnBmpDownPath
                if daysLeft == 0:
                    self._renewTimer.Start(max(5000, (exp-now)*1000), True)
                else:
                    self._renewTimer.Start(_kSecondsPerDay*1000, True)
            else:
                # Warn that support has expired
                text = _kSupportExpiredText
                bmpPath = _kSupportExpiredBmpPath
                bmpDownPath = _kSupportExpiredBmpDownPath

            self._renewButton = ToolbarBitmapTextButton(toolbar, -1,
                    wx.Bitmap(bmpPath), text, False)
            self._renewButton.SetBitmapSelected(wx.Bitmap(bmpDownPath))
            self._renewButton.Bind(wx.EVT_BUTTON, self.OnRenewSupport)

            self._renewSpacer = toolbar.AddStretchableSpace()
            toolbar.AddControl(self._renewButton)
            toolbar.Realize()

        except Exception, e:
            self._logger.error("Exception adding renewal button: " + str(e))


    ###########################################################
    def getUIPrefsDataModel(self):
        """Retrieve a data containing and updating UI Prefs.

        @return uiPrefsDataModel  A UIPrefsDataModel instance.
        """
        return self._uiPrefsDataModel


    ###########################################################
    def _handleSupportWarningChange(self, uiModel):
        """Handle a change to support warning display preferences.

        @param  resultsModel  The UIPrefsDataModel.
        """
        self._updateSupportRenewal()


    ###########################################################
    def _handleGridViewChange(self, uiModel):
        """ Handle a change to an active grid view's appearence. If the view is
        not visible we don't do anything since the next switch will apply
        changes as well.

        @param  resultsModel  The UIPrefsDataModel.
        """
        if self._currentView == self._gridView:

            self._logger.info("applying changes to grid view settings ...")
            self.Freeze()
            try:
                self._currentView.deactivateView()
                self._currentView.setActiveView({ "zoomLevel": 0 })
            finally:
                self.Thaw()
                self.Layout()


_kDialogPadding = 16
_kDialogWrap = 360

###############################################################
class _exitInfoDialog(wx.Dialog):
    """A dialog informing the user that the back end remains open on exit."""
    ###########################################################
    def __init__(self, parent):
        """Initializer for _exitInfoDialog.

        @param  parent  The parent window.
        """
        wx.Dialog.__init__(self, parent, -1, "Exit")

        try:
            # Create the sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            text = wx.StaticText(self, -1, "When you quit %s, recording will "
                                 "continue if your cameras are turned on.  To "
                                 "turn off your cameras, go to the Monitor view"
                                 " and turn off your cameras or disable the "
                                 "rules." % kAppName)
            self._check = wx.CheckBox(self, -1, "Don't show me this again")
            sizer.Add(text, 0, wx.ALL, _kDialogPadding)
            sizer.Add(self._check, 0, wx.BOTTOM | wx.LEFT | wx.RIGHT,
                      _kDialogPadding)
            makeFontDefault(text, self._check)
            text.Wrap(_kDialogWrap)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOK)
            self.FindWindowById(wx.ID_OK, self).SetLabel('Exit')
            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)
            sizer.Add(buttonSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, _kDialogPadding)

            self.Bind(wx.EVT_CLOSE, self.OnCancel)

            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def OnOK(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        if self._check.GetValue():
            setFrontEndPref(_kHideExitPrompt, True)
        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)
