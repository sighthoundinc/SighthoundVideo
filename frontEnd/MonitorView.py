#!/usr/bin/env python

#*****************************************************************************
#
# MonitorView.py
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
import cPickle
import os
import time
import urlparse
import webbrowser
import traceback

from PIL import Image

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.mvc.AbstractModel import AbstractModel
from vitaToolbox.networking.Upnp import isUpnpUrl
from vitaToolbox.networking.Upnp import realizeUpnpUrl
from vitaToolbox.networking.Onvif import isOnvifUrl
from vitaToolbox.networking.Onvif import realizeOnvifUrl
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from vitaToolbox.wx.BetterScrolledWindow import BetterScrolledWindow
from vitaToolbox.wx.BindChildren import bindChildren
from vitaToolbox.wx.BitmapWindow import BitmapWindow
from vitaToolbox.wx.GLCanvasSV import OsCompatibleGLCanvas, GLExceptionSV
from vitaToolbox.wx.DoubleBufferCompatGc import createDoubleBufferCompatGc
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.wx.FontUtils import makeFontNotUnderlined
from vitaToolbox.wx.GradientPanel import GradientPanel
from vitaToolbox.wx.HoverBitmapButton import HoverBitmapButton
from vitaToolbox.wx.HoverButton import HoverButton
from vitaToolbox.wx.MessageDialogWithLink import MessageDialogWithLink
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors
from vitaToolbox.wx.TranslucentStaticText import TranslucentStaticText
from vitaToolbox.wx.FixedMultiSplitterWindow import FixedMultiSplitterWindow

# Local imports...
from appCommon.CommonStrings import kCameraOn, kCameraOff
from appCommon.CommonStrings import kCameraConnecting, kCameraFailed
from CameraSetupWizard import CameraSetupWizard
from CameraTable import kWebcamCamType
from appCommon.CommonStrings import kSlowFpsUrl, kSlowProcessingUrl
import FrontEndEvents
from LicensingHelpers import checkForMaxCameras
from LicensingHelpers import showHiddenCamsWarning
from RuleListPanel import RuleListPanel
from RenameCameraDialog import RenameCameraDialog
from RemoveCameraDialog import removeCamera
from frontEnd.FrontEndUtils import getUserLocalDataDir
from frontEnd.PacketCaptureDialog import HandlePacketCaptureRequest
from FrontEndPrefs import getFrontEndPref
from FrontEndPrefs import setFrontEndPref
from appCommon.ConfigBitmapWindow import ConfigBitmapWindow
from BaseView import BaseMonitorView
from BaseView import makeVideoStatusBitmap as _makeVideoStatusBitmap
from BaseView import kStatusTextConnecting
from BaseView import kStatusTextCouldNotConnect
from BaseView import kStatusTextNoRulesScheduled
from BaseView import kStatusTextNoActiveRules
from BaseView import kStatusTextCameraTurnedOff
from BaseView import kStatusStartColor
from BaseView import kStatusEndColor

# Constants...

_kMmapMisreadTolerance = 3

_kCtrlPadding = 8
_kFullVideoSize = (480, 360)
_kSmallVideoSize = (160, 120)
_kSmallVideoFps = 2

_kRuleListPanelMinSize = (1, 150)

_kPcapDelaySeconds = 60

# Parameters for drawing the selection border
_kPreviewSelectionOffset = 3
_kPreviewSelectionRounding = 4
_kPreviewSelectionColour = (27, 87, 174)

_kShadowColor = (0, 0, 0, 10)

_kCameraStatusUpdateTime = 2

_kCameraWarningTitle = "Camera warning"

_kSlowProcessingWarning = (
"""Slow video processing was detected on this camera for the last %s.  """
"""This may reduce recognition accuracy.

Potential causes include:
- Too many cameras running at once
- Too many programs running at once
- A background process, like a virus scanner, may be running
""")

_kSlowCaptureWarning = (
"""A low frame rate was detected on this camera for the last %s.  """
"""This may reduce recognition accuracy.

Potential causes include:
- Slow network connectivity
- Very dark scenes
- A problem with your camera
- Too many clients of the same camera
""")

_kSeeReferenceGuideText = """For details, see the Reference Guide."""

_kCamerasHiddenLink = "%d cameras not shown..."
_kCameraHiddenLink = "%d camera not shown..."

_kAllowBitmapMode = False

_kActiveTimerId = 1
_kPreviewTimerId = 2

class MonitorView(BaseMonitorView):
    """Implements the main view for monitoring cameras with control capabilities
    and a distinction between a high-fps main view and some low-fps previews.
    """
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, searchFunc,
                 activateFunc):
        """The initializer for MonitorView

        @param  parent         The parent Window.
        @param  backEndClient  A connection to the back end app.
        @param  dataManager    The data manager for the app.
        @param  searchFunc     A function that will perform searches.
        @param  activateFunc   A function that will activate the monitor view.
        """
        # Call the base class initializer
        super(MonitorView, self).__init__(parent, backEndClient)

        # Save the passed parameters
        self._dataManager = dataManager
        self._searchFunc = searchFunc
        self._activateFunc = activateFunc

        # Keep track of debug mode...
        self._debugModeModel = wx.GetApp().getDebugModeModel()
        self._debugModeModel.addListener(self._handleDebugModeChange)

        # The name of the camera currently displayed in the large view.
        self._curSelectedCamera = None

        # Check videoClipPlaybackMode to determine which BitmapWindow class we want to use
        self._configBitmapWindow    = ConfigBitmapWindow()
        self._logger.info( 'bitmapWindowMode=' + self._configBitmapWindow.getMode() )

        # A data model for updating controls that reflect enabled status
        self._enabledModel = _cameraEnabledModel()
        self._enabledModel.addListener(self._handleCameraEnable,
                                       wantKeyParam=True)

        # Information and controls for configured cameras
        self._previewControls = {}

        # Initialize the UI
        self._initUI()

        # Timer for updating live views.
        self._previewTimer = wx.Timer(self, _kPreviewTimerId)
        self.Bind(wx.EVT_TIMER, self.OnPreviewTimer)

        # Cameras for which we have working mapped memory.
        self._openCameras = set()
        self._largeViewCamera = None
        self._disabledCameras = set()
        self._mmapMisreads = {}

        # A _FpsStats object per camera.
        self._fpsStats = {}

        self._lastStatusQueryTime = time.time()

        # The camera that caused a popup menu to display.
        self._cameraPopupSource = ''

        self._drawLastNumCams = -1
        self._drawLastSelectedCam = ''
        self._drawLastSize = (-1, -1)
        self._drawLastScrollPos = None

        # If we are ever minimized we want to temporarily disable live view.
        self._pauseLiveView = False

        self._pendingActiveViewResize = False
        self._pendingLicenseChangeEvent = False

        # Find menu items and bind to them.
        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()
        self._addCameraMenuId = menuBar.FindMenuItem("Tools", "Add Camera...")
        self._editCameraMenuId = menuBar.FindMenuItem("Tools", "Edit Camera...")
        self._editCameraLocationMenuId = menuBar.FindMenuItem("Tools",
                                                      "Edit Camera Location...")
        self._removeCameraMenuId = \
            menuBar.FindMenuItem("Tools", "Remove Camera...")
        self._reconnectCameraMenuId = \
            menuBar.FindMenuItem("Tools", "Reconnect to Camera")
        self._cameraWebPageMenuId = \
            menuBar.FindMenuItem("Tools", "Visit Camera Web Page")
        self._muteAudio = \
            menuBar.FindMenuItem("Controls", "Mute Audio")
        topWin.Bind(wx.EVT_MENU, self.OnAddCamera, id=self._addCameraMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnEditCamera, id=self._editCameraMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnRenameCamera,
                    id=self._editCameraLocationMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnReconnect,
                    id=self._reconnectCameraMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnCameraWebPage,
                    id=self._cameraWebPageMenuId)


    ###########################################################
    def _initLargeView(self):
        # The video window
        if not self._tryReinitLargeView:
            return False

        largeView = None
        bitmapMode = False
        allowReinit = False
        allowBitmap = _kAllowBitmapMode
        try:
            try:
                largeView = OsCompatibleGLCanvas(self._topLeftPanel)
                largeView.SetMinSize(_kFullVideoSize)
            except GLExceptionSV, e:
                if e.version.startswith("1"):
                    # chances are we're in RDP land ... init as bitmap for now
                    # and try re-init later
                    if self._largeView is not None:
                        # we're already in bitmap mode, no need to replace with the same
                        return False
                    self._logger.info( "OpenGL v1 detected. Falling back to Bitmap rendering until a context with better GL is available" )
                    allowBitmap = True
                    # Uncomment this if we ever get to a point where GL loading is dynamic in wxPython,
                    # and we can change GL implementation mid-flight
                    # allowReinit = True
                raise
        except:
            if allowBitmap:
                if self._largeView is not None:
                    return False
                if not allowReinit:
                    self._logger.info( 'Falling back to BitmapWindow mode:' + traceback.format_exc() )
                bitmapMode = True
                emptyBitmap = wx.Bitmap(_kFullVideoSize[0], _kFullVideoSize[1])
                largeView = BitmapWindow(self._topLeftPanel, emptyBitmap,
                                   _kFullVideoSize, scale=True)
            else:
                raise
        largeView.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)
        largeView.Bind(wx.EVT_SIZE, self.OnLargeViewSize)
        if wx.Platform == '__WXMSW__':
            bindChildren(largeView, wx.EVT_SET_FOCUS, self.OnFocusChanged)

        if bitmapMode and allowReinit:
            largeView.Bind(wx.EVT_SHOW, self.OnLargeViewShow)

        if self._largeView is None:
            self._overlapSizer.Add(largeView)
        else:
            self._logger.info( "Replacing Bitmap playback control with OpenGL one" )
            self._overlapSizer.Replace(self._largeView, largeView, False)
        self._largeView = largeView
        self._tryReinitLargeView = allowReinit
        self._bitmapMode = bitmapMode
        return True

    ###########################################################
    def OnLargeViewShow(self, event):
        self._initLargeView()

    ###########################################################
    def _initUI(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        self._mainSplitterWindow = \
            FixedMultiSplitterWindow(
                self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                (wx.SP_LIVE_UPDATE | wx.TAB_TRAVERSAL | wx.BORDER_NONE |
                wx.TRANSPARENT_WINDOW | wx.FULL_REPAINT_ON_RESIZE),
                "SplitterWindowMonitorView", None, self._logger
            )
        self._mainSplitterWindow.SetSashGravity(1)

        self._rightPanel = \
            wx.Panel(
                self._mainSplitterWindow,
                wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                (wx.TAB_TRAVERSAL | wx.BORDER_NONE | wx.TRANSPARENT_WINDOW |
                 wx.FULL_REPAINT_ON_RESIZE)
            )
        self._rightPanel.SetBackgroundStyle(kBackgroundStyle)

        self._leftPanel = \
            wx.Panel(
                self._mainSplitterWindow,
                wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                (wx.TAB_TRAVERSAL | wx.BORDER_NONE | wx.TRANSPARENT_WINDOW |
                 wx.FULL_REPAINT_ON_RESIZE)
            )
        self._leftPanel.SetBackgroundStyle(kBackgroundStyle)

        self._leftSplitterWindow = \
            FixedMultiSplitterWindow(
                self._leftPanel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                (wx.SP_LIVE_UPDATE | wx.TAB_TRAVERSAL | wx.BORDER_NONE |
                wx.TRANSPARENT_WINDOW | wx.FULL_REPAINT_ON_RESIZE),
                "SplitterWindowLargePreviewAndRulesList", None, self._logger
            )
        self._leftSplitterWindow.SetSashGravity(1)
        self._leftSplitterWindow.SetSashSize(2*_kCtrlPadding)

        self._topLeftPanel = \
            wx.Panel(
                self._leftSplitterWindow,
                wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                (wx.TAB_TRAVERSAL | wx.BORDER_NONE | wx.TRANSPARENT_WINDOW |
                 wx.FULL_REPAINT_ON_RESIZE)
            )
        self._topLeftPanel.SetBackgroundStyle(kBackgroundStyle)

        # The first column contains the selected stream and the rule list
        self._firstColSizer = wx.BoxSizer(wx.VERTICAL)

        # The second column contains small views of all cameras
        self._secondColSizer = wx.BoxSizer(wx.VERTICAL)

        # Create controls for the first column

        self._overlapSizer = OverlapSizer(True)
        self._largeView = None
        self._tryReinitLargeView = True
        self._initLargeView()

        self._shadowRight = wx.Panel(self._topLeftPanel, -1, style=wx.TRANSPARENT_WINDOW)
        self._shadowRight.SetBackgroundStyle(kBackgroundStyle)
        self._shadowRight.SetMinSize((4, -1))
        self._shadowBottom = wx.Panel(self._topLeftPanel, -1, style=wx.TRANSPARENT_WINDOW)
        self._shadowBottom.SetBackgroundStyle(kBackgroundStyle)
        self._shadowBottom.SetMinSize((-1, 4))

        self._createVideoStatusScreens()
        self._overlapSizer.Add(self._bigMessagePanel)
        self._connectingSizer.ShowItems(False)
        self._connectFailedSizer.ShowItems(False)
        self._noActiveRulesSizer.ShowItems(False)
        self._notScheduledSizer.ShowItems(False)
        self._cameraOffSizer.ShowItems(False)
        self._bigMessagePanel.Hide()
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self._overlapSizer, 1, wx.EXPAND)
        hSizer.Add(self._shadowRight, 0, wx.EXPAND)
        self._topLeftColSizer = wx.BoxSizer(wx.VERTICAL)
        self._topLeftColSizer.Add(hSizer, 1, wx.EXPAND)
        self._topLeftColSizer.Add(self._shadowBottom, 0, wx.EXPAND)
        self._activeViewTimer = wx.Timer(self, _kActiveTimerId)

        self._ruleListPanel = RuleListPanel(self._leftSplitterWindow, self._backEndClient,
                                            self._dataManager, self._searchFunc,
                                            self._enabledModel)
        self._ruleListPanel.SetMinSize(_kRuleListPanelMinSize)

        # Create a scrollable window for the second column to place camera
        # previews in.  Do two-levels of sizers so that the preview sizer
        # is exactly the right size, but scrollbar shows up on right.
        isWin = wx.Platform == '__WXMSW__'
        self._previewWin = BetterScrolledWindow(self._rightPanel, -1, osxFix=(not isWin),
                                                style=wx.TRANSPARENT_WINDOW,
                                                redrawFix=isWin)
        self._previewWin.SetMinSize((_kSmallVideoSize[0]+8*_kCtrlPadding, 1))
        self._previewWin.Bind(wx.EVT_ERASE_BACKGROUND,
                              self.OnPreviewWinPaint)
        self._previewWinSizer = wx.BoxSizer(wx.VERTICAL)
        self._previewSizer = wx.WrapSizer(wx.HORIZONTAL)

        self._previewWinSizer.Add(self._previewSizer)

        self._previewFocusHolder = wx.Window(self._previewWin, -1,
                                             style=wx.TRANSPARENT_WINDOW)
        self._previewFocusHolder.SetBackgroundStyle(kBackgroundStyle)
        self._previewFocusHolder.SetMinSize((1, -1))
        previewHorizSizer = wx.BoxSizer(wx.HORIZONTAL)
        previewHorizSizer.Add(self._previewWinSizer, 1, wx.EXPAND)
        previewHorizSizer.Add(self._previewFocusHolder, 0, wx.EXPAND)

        self._previewWin.SetSizer(previewHorizSizer)
        self._secondColSizer.Add(self._previewWin, 1, wx.EXPAND)

        self._frozenWarning = None

        self._topLeftPanel.SetSizer(self._topLeftColSizer)
        self._rightPanel.SetSizer(self._secondColSizer)

        self._firstColSizer.Add(self._leftSplitterWindow, 1, wx.EXPAND |
                                wx.TOP | wx.LEFT | wx.BOTTOM, _kCtrlPadding)
        self._leftPanel.SetSizer(self._firstColSizer)

        self._leftSplitterWindow.SplitHorizontally(
            self._topLeftPanel, self._ruleListPanel
        )
        self._mainSplitterWindow.SplitVertically(
            self._leftPanel, self._rightPanel
        )

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self._mainSplitterWindow, 1, wx.EXPAND | wx.LEFT |
                      wx.RIGHT | wx.BOTTOM | wx.TOP, _kCtrlPadding)
        self.SetSizer(mainSizer)

        # We'll handle drawing of the background in the preview list so we can
        # draw the selection highlight.
        previewSelectionColour = wx.Colour(*_kPreviewSelectionColour)
        self._kSelectionBorderBrush = wx.Brush(previewSelectionColour)
        self._kSelectionBorderPen = wx.Pen(previewSelectionColour)

        # Register for context menu event (usually right-click) so we can show
        # a popup menu.
        self._bigMessagePanel.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)

        self._shadowRight.Bind(wx.EVT_PAINT, self.OnDrawRightShadow)
        self._shadowBottom.Bind(wx.EVT_PAINT, self.OnDrawBottomShadow)

        self._previewWin.Bind(wx.EVT_CHILD_FOCUS, self.OnPreviewChildFocus)

        # Get the top level parent and register the load and save preferences methods.
        topLevelParent = self.GetTopLevelParent()
        topLevelParent.registerExitNotification(self._savePrefs)
        topLevelParent.registerPrefsNotification(self._loadPrefs)


    ###########################################################
    def _savePrefs(self):
        """Added functionality.  This function gets registered with the top level window.
        It is registered on close.  It saves the sash positions to the preferences file.
        """
        setFrontEndPref(
            "monitorViewSashPos1", self._mainSplitterWindow.GetSashPosition(0)
        )
        setFrontEndPref(
            "largePreviewAndRulesListSashPos1",
            self._leftSplitterWindow.GetSashPosition(0)
        )


    ###########################################################
    def _loadPrefs(self):
        """Added functionality.  This function gets registered with the top level window.
        It is registered on initialization.  It loads the sash positions from the preferences
        file and sets them.
        """

        # Get the preferences...
        monViewSashPos1 = \
            getFrontEndPref("monitorViewSashPos1")

        leftSplitterSashPos1 = \
            getFrontEndPref("largePreviewAndRulesListSashPos1")

        # If we don't have a previous size from preferences, then we'll
        # just set the position to 1. Setting the sash position forces
        # a resize of the splitter window, and it will set an appropriate
        # value for the sash position.
        if not monViewSashPos1:
            monViewSashPos1 = 1
        if not leftSplitterSashPos1:
            leftSplitterSashPos1 = 1

        self._mainSplitterWindow.SetSashPosition(0, monViewSashPos1)
        self._leftSplitterWindow.SetSashPosition(0, leftSplitterSashPos1)


    ###########################################################
    def OnPreviewChildFocus(self, event):
        """Handle child focus events of the preview panel by taking focus away.

        @param  event  The event.
        """
        if event.GetWindow() != self._previewFocusHolder:
            self._previewFocusHolder.SetFocus()


    ###########################################################
    def _createVideoStatusScreens(self): #PYCHECKER OK: Too many lines
        """Generate controls to convey non-streaming camera status."""
        # Make a panel for the messages...
        self._bigMessagePanel = GradientPanel(
            self._topLeftPanel, direction=(wx.NORTH|wx.WEST),
            startColor=kStatusStartColor, endColor=kStatusEndColor,
            size=_kFullVideoSize
        )

        # Create the large connecting screen
        connectingLabel = TranslucentStaticText(self._bigMessagePanel,
                                                -1, "Connecting...",
                                                style=wx.ALIGN_CENTER)
        connectingText = TranslucentStaticText(self._bigMessagePanel, -1,
                        "Finding your camera and turning it on.  Please wait.",
                        style=wx.ALIGN_CENTER)
        makeFontDefault(connectingLabel)
        titleFont = connectingLabel.GetFont()
        titleFont.SetPointSize(22)
        normalFont = connectingLabel.GetFont()
        normalFont.SetPointSize(14)
        if wx.Platform == '__WXMSW__':
            titleFont.SetPointSize(18)
            normalFont.SetPointSize(12)
        connectingLabel.SetFont(titleFont)
        connectingLabel.SetForegroundColour(wx.WHITE)
        connectingText.SetFont(normalFont)
        connectingText.SetForegroundColour(wx.WHITE)

        #_, connectingTextLineHeight = connectingText.GetTextExtent("X")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(connectingLabel, 0, wx.EXPAND)
        sizer.AddSpacer(24)
        sizer.Add(connectingText, 0, wx.EXPAND)
        sizer.AddStretchSpacer(1)
        self._connectingSizer = sizer

        # Create the small connecting screen
        self._smallConnectingScreen = \
            makeVideoStatusBitmap(kStatusTextConnecting, normalFont)

        # Create the large connect failed screen
        failedLabel = TranslucentStaticText(self._bigMessagePanel, -1,
                                           "Could not connect",
                                           style=wx.ALIGN_CENTER)
        self._failedLabelReason = TranslucentStaticText(self._bigMessagePanel, -1,
                                           "",
                                           style=wx.ALIGN_CENTER)
        failedTextA = TranslucentStaticText(self._bigMessagePanel, -1,
                                            "We will keep trying.",
                                            style=wx.ALIGN_CENTER)
        failedTextB = HoverButton(
            self._bigMessagePanel, "If this continues, click ",
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            0, style=wx.ALIGN_RIGHT,
        )
        failedLink = HoverButton(
            self._bigMessagePanel, "here",
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((186,228,250,255),(0,0,0,0),(0,0,0,0)),
            ((186,228,250,255),(0,0,0,0),(0,0,0,0)),
            0,
        )
        failedLink.Bind(wx.EVT_BUTTON, self.OnTestCamera)
        failedTextC = HoverButton(
            self._bigMessagePanel, " to go to the camera setup test screen",
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            ((255,255,255,255),(0,0,0,0),(0,0,0,0)),
            0, style=wx.ALIGN_LEFT
        )
        failedTextB.Disable()
        failedTextC.Disable()
        failedLabel.SetFont(titleFont)
        failedLabel.SetForegroundColour(wx.WHITE)
        self._failedLabelReason.SetFont(normalFont)
        self._failedLabelReason.SetForegroundColour(wx.WHITE)
        failedTextA.SetFont(normalFont)
        failedTextA.SetForegroundColour(wx.WHITE)
        failedTextB.SetFont(normalFont)
        failedTextB.SetForegroundColour(wx.WHITE)
        failedTextC.SetFont(normalFont)
        failedTextC.SetForegroundColour(wx.WHITE)
        linkFont = failedTextA.GetFont()
        linkFont.SetUnderlined(True)
        failedLink.SetFont(linkFont)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(failedLabel, 0, wx.EXPAND)
        sizer.Add(self._failedLabelReason, 0, wx.EXPAND)
        sizer.AddSpacer(24)
        sizer.Add(failedTextA, 0, wx.EXPAND, 4)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer(1)
        hSizer.Add(failedTextB, 0, wx.ALIGN_BOTTOM)
        hSizer.Add(failedLink, 0, wx.ALIGN_BOTTOM)
        hSizer.Add(failedTextC, 0, wx.ALIGN_BOTTOM)
        hSizer.AddStretchSpacer(1)
        sizer.Add(hSizer, 0, wx.EXPAND )
        sizer.AddStretchSpacer(1)
        self._connectFailedSizer = sizer

        # Create the small connect failed
        self._smallConnectFailedScreen = {}
        self._smallConnectFailedScreen[""] = \
            makeVideoStatusBitmap(kStatusTextCouldNotConnect, normalFont)

        # Create the not scheduled screen
        notScheduledLabel = TranslucentStaticText(self._bigMessagePanel, -1,
                                                  "No rules scheduled to run",
                                                  style=wx.ALIGN_CENTER)
        notScheduledText = TranslucentStaticText(self._bigMessagePanel, -1,
                                                 "This camera is on but only "
                                                 "runs rules during the times "
                                                 "you have scheduled below.",
                                                 style=wx.ALIGN_CENTER)
        clock = HoverBitmapButton(self._bigMessagePanel, wx.ID_ANY,
                                  'frontEnd/bmps/clock_large.png')
        notScheduledLabel.SetFont(titleFont)
        notScheduledLabel.SetForegroundColour(wx.WHITE)
        notScheduledText.SetFont(normalFont)
        notScheduledText.SetForegroundColour(wx.WHITE)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(notScheduledLabel, 0, wx.EXPAND)
        sizer.AddSpacer(24)
        sizer.Add(notScheduledText, 0, wx.EXPAND)
        sizer.AddSpacer(32)
        sizer.Add(clock, 0, wx.ALIGN_CENTER)
        sizer.AddStretchSpacer(1)
        self._notScheduledSizer = sizer

        # Create the small auto record screen.
        self._smallNotScheduledScreen = \
            makeVideoStatusBitmap(kStatusTextNoRulesScheduled, normalFont, False,
                                  wx.Bitmap("frontEnd/bmps/clock_small.png"))

        # Create the large no active rules screen.
        inactiveLabel = TranslucentStaticText(self._bigMessagePanel, -1,
                                              "No active rules",
                                              style=wx.ALIGN_CENTER)
        inactiveTextA = TranslucentStaticText(self._bigMessagePanel, -1,
                                              "This camera is on, but not "
                                              "running any rules. Make sure "
                                              "there is at least one rule",
                                              style=wx.ALIGN_CENTER)
        inactiveTextB = TranslucentStaticText(self._bigMessagePanel, -1, "below"
                                              " that is set to save video or "
                                              "notify, and has a selected check"
                                              "box.", style=wx.ALIGN_CENTER)
        inactiveLabel.SetFont(titleFont)
        inactiveLabel.SetForegroundColour(wx.WHITE)
        inactiveTextA.SetFont(normalFont)
        inactiveTextA.SetForegroundColour(wx.WHITE)
        inactiveTextB.SetFont(normalFont)
        inactiveTextB.SetForegroundColour(wx.WHITE)

        sizer = wx.BoxSizer(wx.VERTICAL)
        #vSizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(inactiveLabel, 0, wx.EXPAND)
        sizer.AddSpacer(24)
        sizer.Add(inactiveTextA, 0, wx.EXPAND)
        sizer.AddSpacer(4)
        sizer.Add(inactiveTextB, 0, wx.EXPAND)
        sizer.AddStretchSpacer(1)
        self._noActiveRulesSizer = sizer

        # Create the small auto record screen
        self._smallNoActiveRulesScreen = \
            makeVideoStatusBitmap(kStatusTextNoActiveRules, normalFont)

        # Create the large camera off screen
        offLabel = TranslucentStaticText(self._bigMessagePanel, -1,
                                         "Camera turned off",
                                         style=wx.ALIGN_CENTER)
        offText = TranslucentStaticText(self._bigMessagePanel, -1, "Click the "
                                        "power button to turn on the camera.",
                                        style=wx.ALIGN_CENTER)
        power = HoverBitmapButton(self._bigMessagePanel, wx.ID_ANY,
                'frontEnd/bmps/power_large.png', useMask=False)
        power.Bind(wx.EVT_BUTTON, self.OnPowerButtonClick)
        offLabel.SetFont(titleFont)
        offLabel.SetForegroundColour(wx.WHITE)
        offText.SetFont(normalFont)
        offText.SetForegroundColour(wx.WHITE)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(offLabel, 0, wx.EXPAND)
        sizer.AddSpacer(24)
        sizer.Add(offText, 0, wx.ALIGN_CENTER)
        sizer.AddSpacer(32)
        sizer.Add(power, 0, wx.ALIGN_CENTER)
        sizer.AddStretchSpacer(1)
        self._cameraOffSizer = sizer

        # Create the small camera off screen
        self._smallCameraOffScreen = \
            makeVideoStatusBitmap(kStatusTextCameraTurnedOff, normalFont, False,
                                  wx.Bitmap("frontEnd/bmps/power_small.png"))

        overlapSizer = OverlapSizer(True)
        overlapSizer.Add(self._connectingSizer)
        overlapSizer.Add(self._connectFailedSizer)
        overlapSizer.Add(self._notScheduledSizer)
        overlapSizer.Add(self._noActiveRulesSizer)
        overlapSizer.Add(self._cameraOffSizer)
        self._bigMessagePanel.SetSizer(overlapSizer)
        self._bigMessagePanel.Layout()

        self._largeViewStatusSizers = [self._connectingSizer,
                                       self._connectFailedSizer,
                                       self._notScheduledSizer,
                                       self._noActiveRulesSizer,
                                       self._cameraOffSizer]
        return


    ###########################################################
    def setActiveView(self, viewParams = {}):
        """
        @see BaseView.setActiveView
        """
        super(MonitorView, self).setActiveView(viewParams)

        # Create UI controls
        self._remakePreviews()

        # We want to be notified when cameras are changed so we can update
        self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_ADDED, self.OnCameraAdded)
        self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_EDITED, self.OnCameraEdited)
        self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_REMOVED, self.OnCameraRemoved)
        self.GetTopLevelParent().Bind(wx.EVT_MENU, self.OnRemoveCamera,
                                      id=self._removeCameraMenuId)
        self.GetTopLevelParent().Bind(wx.EVT_MENU, self.OnToggleMuteAudio,
                                      id=self._muteAudio)

        menuBar = self.GetTopLevelParent().GetMenuBar()
        menuBar.Enable(self._muteAudio, True)


        # Connect to video streams
        self._startVideoStreams()

        self._previewWin.FitInside()




    ###########################################################
    def _remakePreviews(self):
        """Create the camera preview controls"""
        self._loadCameraPreviews()
        if len(self._cameraLocations):
            if self._curSelectedCamera not in self._cameraLocations:
                self._curSelectedCamera = self._cameraLocations[0]
        else:
            self._curSelectedCamera = None

        self._setActiveCamera(self._curSelectedCamera)
        for camera in self._cameraLocations:
            if camera != self._curSelectedCamera:
                # self._curSelectedCamera was updated in the call to setActiveCamera
                # so we skip it here as a tiny optimization.
                self._updateCameraStatus(camera)
        self.Layout()
        self._previewWin.FitInside()


    ###########################################################
    def prepareToClose(self):
        """
        @see  BaseView.prepareToClose
        """
        self._activeViewTimer.Stop()
        self._previewTimer.Stop()


    ###########################################################
    def deactivateView(self):
        """
        @see  BaseView.deactivateView
        """
        super(MonitorView, self).deactivateView()

        self._previewControls = {}
        self._previewSizer.Clear(True)
        self._frozenWarning = None

        # Shut off video streams
        self._stopVideoStreams()

        # Disable the reconnect, edit and remove menu items.
        menuBar = self.GetTopLevelParent().GetMenuBar()
        menuBar.Enable(self._reconnectCameraMenuId, False)
        menuBar.Enable(self._cameraWebPageMenuId, False)
        menuBar.Enable(self._editCameraMenuId, False)
        menuBar.Enable(self._editCameraLocationMenuId, False)
        menuBar.Enable(self._muteAudio, False)

        self.GetParent().Unbind(FrontEndEvents.EVT_CAMERA_ADDED)
        self.GetParent().Unbind(FrontEndEvents.EVT_CAMERA_EDITED)
        self.GetParent().Unbind(FrontEndEvents.EVT_CAMERA_REMOVED)
        self.GetTopLevelParent().Unbind(wx.EVT_MENU,
                                        id=self._removeCameraMenuId)
        self.GetTopLevelParent().Unbind(wx.EVT_MENU,
                                        id=self._muteAudio)


    ###########################################################
    def _resetPreviews(self):
        """Destroy and recreate the previews to ensure we're up to date."""
        self._previewControls = {}
        self._previewSizer.Clear(True)
        self._frozenWarning = None
        self.Layout()

        self._remakePreviews()


    ###########################################################
    def handleLicenseChange(self):
        """To be called if a license got changed."""
        self._pendingLicenseChangeEvent = False

        if not self._isActiveView:
            return

        # With wx 2.8 we can only safely proceed if we aren't behind a dialog
        # or other window. If we do, we'll destroy a window which may have a
        # pending event. We'll simply set a flag that we want to refresh and
        # retry later.
        if self.GetTopLevelParent().shouldAnimateChild(self):
            self._resetPreviews()
            self._startVideoStreams()
        else:
            self._pendingLicenseChangeEvent = True


    ###########################################################
    def _loadCameraPreviews(self):
        """Create small views for each camera location."""
        self.Freeze()
        try:
            self._previewControls = {}
            self._cameraSettings = {}

            self._cameraLocations = self._backEndClient.getCameraLocations()
            if not len(self._cameraLocations):
                return

            camerasToHide = []

            for cameraLocation in self._cameraLocations:
                # Load the camera settings
                camType, uri, enabled, extra = \
                        self._backEndClient.getCameraSettings(cameraLocation)
                if extra.get('frozen', False):
                    camerasToHide.append(cameraLocation)
                else:
                    self._cameraSettings[cameraLocation] = (camType, uri, extra)
                    self._enabledModel.enableCamera(cameraLocation, enabled)
                    self._createPreviewControls(cameraLocation)

            self._cameraLocations = [cam for cam in self._cameraLocations if
                    cam not in camerasToHide]

            self._layoutPreviewControls()
        finally:
            self.Thaw()


    ###########################################################
    def _toggleFrozenWarning(self):
        """Display or hide a frozen camera warning as needed."""
        numConfigured = len(self._backEndClient.getCameraLocations())
        numHidden = numConfigured-len(self._cameraLocations)

        if numHidden > 0:
            if numHidden == 1:
                label = _kCameraHiddenLink % numHidden
            else:
                label = _kCamerasHiddenLink % numHidden
            if self._frozenWarning:
                self._frozenWarning.SetLabel(label)
            else:
                self._frozenWarning = wx.adv.HyperlinkCtrl(self._previewWin, -1, label, "")
                if wx.Platform == '__WXMSW__':
                    self._frozenWarning.SetBackgroundStyle(kBackgroundStyle)
                makeFontNotUnderlined(self._frozenWarning)
                setHyperlinkColors(self._frozenWarning)
                self._frozenWarning.Bind(wx.adv.EVT_HYPERLINK, self.OnFrozenWarning)
        elif self._frozenWarning:
            self._frozenWarning.Destroy()
            self._frozenWarning = None


    ###########################################################
    def _createPreviewControls(self, cameraLocation):
        """Create preview controls for a camera location.

        @param  cameraLocation  The location to create controls for.
        """
        enabled = self._enabledModel.isEnabled(cameraLocation)

        # Create the preview controls
        emptyBitmap = wx.Bitmap(_kSmallVideoSize[0], _kSmallVideoSize[1])
        videoWindow = None
        self._logger.info( 'Create preview control: pid=' + str( os.getpid() ) + '  cameraLocation=' + cameraLocation + '  bitmapWindowMode=' + self._configBitmapWindow.getMode() )
        if not videoWindow:
            videoWindow = BitmapWindow(self._previewWin, emptyBitmap,
                                       _kSmallVideoSize, scale=True,
                                       name=cameraLocation)
        recordOn = \
            HoverBitmapButton(self._previewWin, wx.ID_ANY,
                              'frontEnd/bmps/Monitor_On_Small_Enabled.png',
                              wx.EmptyString,
                              'frontEnd/bmps/Monitor_On_Small_Pressed.png',
                              'frontEnd/bmps/Monitor_Off_Small_Enabled.png',
                              'frontEnd/bmps/Monitor_On_Small_Hover.png')
        recordOff = \
            HoverBitmapButton(self._previewWin, wx.ID_ANY,
                              'frontEnd/bmps/Monitor_Off_Small_Enabled.png',
                              wx.EmptyString,
                              'frontEnd/bmps/Monitor_Off_Small_Pressed.png',
                              'frontEnd/bmps/Monitor_Off_Small_Enabled.png',
                              'frontEnd/bmps/Monitor_Off_Small_Hover.png')
        recordOn.Show(enabled)
        recordOff.Show(not enabled)

        nameLabel = TranslucentStaticText(self._previewWin, -1, cameraLocation,
                                          style=wx.ST_ELLIPSIZE_END)
        nameLabel.SetMaxSize((_kSmallVideoSize[0] - recordOn.GetSize().GetWidth(),
                              nameLabel.GetSize().GetHeight()))
        nameLabel.SetMinSize(nameLabel.GetMaxSize())

        warningIcon = HoverBitmapButton(self._previewWin, wx.ID_ANY,
                                        "frontEnd/bmps/Warning.png",
                                        name=cameraLocation)
        warningIcon.Hide()

        self._previewControls[cameraLocation] = \
                    (videoWindow, recordOn, recordOff, nameLabel, warningIcon)

        # Bind to events
        videoWindow.Bind(wx.EVT_LEFT_DOWN, self.OnPreviewSelection)
        videoWindow.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)
        recordOn.Bind(wx.EVT_BUTTON, self.OnEnableIcon)
        recordOff.Bind(wx.EVT_BUTTON, self.OnEnableIcon)
        warningIcon.Bind(wx.EVT_BUTTON, self.OnWarningIcon)


    ###########################################################
    def _layoutPreviewControls(self):
        """Update the layout of the preview controls."""
        # Empty the sizer
        self._previewSizer.Clear(False)

        # Sort the names so we display in alphabetical order
        self._cameraLocations.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))

        for cameraLocation in self._cameraLocations:
            if cameraLocation not in self._previewControls:
                # We can wind up here due to layouts from how the splitter
                # window is currently wired before we've actually entered the
                # Monitor View and created the relevant controls.
                continue

            videoWindow, recordOn, recordOff, nameLabel, warningIcon = \
                                        self._previewControls[cameraLocation]

            cameraSizer = wx.BoxSizer(wx.VERTICAL)

            # Add each set of controls to the sizer
            cameraSizer.AddSpacer(_kCtrlPadding-1)
            cameraSizer.Add(videoWindow, 0, wx.LEFT | wx.RIGHT, _kCtrlPadding)
            labelSizer = wx.BoxSizer(wx.HORIZONTAL)
            overlapSizer = OverlapSizer(True)
            overlapSizer.Add(recordOn)
            overlapSizer.Add(recordOff)
            labelSizer.Add(overlapSizer, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                           _kCtrlPadding/2)
            labelSizer.Add(nameLabel, 1, wx.ALIGN_CENTER_VERTICAL)

            # ...extra craziness to make sure that the warning takes up space
            # even if hidden...
            warningSizer = OverlapSizer(True)
            warningSizer.Add(warningIcon)
            warningSizer.AddSpacer(1)
            labelSizer.Add(warningSizer, 0, wx.ALIGN_CENTER_VERTICAL)

            cameraSizer.Add(labelSizer, 0, wx.TOP | wx.EXPAND,
                            _kCtrlPadding/2)

            self._previewSizer.Add(cameraSizer, 0)

        self._toggleFrozenWarning()
        if self._frozenWarning:
            self._previewSizer.Add(self._frozenWarning, 0,
                    wx.TOP | wx.BOTTOM | wx.LEFT, _kCtrlPadding)

        self._previewWin.Layout()
        self._previewWin.Refresh()


    ###########################################################
    def _setActiveCamera(self, cameraLocation):
        """Select a new camera location to play in the large view.

        @param  cameraLocation  The name of the camera to make active.
        """
        # Ensure the proper menu items are enabled.  We can wind up taking
        # action here when a dialog is up, which doesn't update the menu.  We
        # call again to fix this, but we must make sure they toggle, otherwise
        # wx seems to consider it a no-op.
        enableMenuItems = cameraLocation is not None

        # Only enable web page if menus should be enabled and we're not a webcam
        if cameraLocation:
            camType, _, _ = self._cameraSettings[cameraLocation]
            wantWebPage = enableMenuItems and (camType != kWebcamCamType)
        else:
            wantWebPage = False

        menuBar = self.GetTopLevelParent().GetMenuBar()
        menuBar.Enable(self._reconnectCameraMenuId, not enableMenuItems)
        menuBar.Enable(self._cameraWebPageMenuId, not wantWebPage)
        menuBar.Enable(self._editCameraMenuId, not enableMenuItems)
        menuBar.Enable(self._editCameraLocationMenuId, not enableMenuItems)
        menuBar.Enable(self._removeCameraMenuId, not enableMenuItems)
        menuBar.Enable(self._reconnectCameraMenuId, enableMenuItems)
        menuBar.Enable(self._cameraWebPageMenuId, wantWebPage)
        menuBar.Enable(self._editCameraMenuId, enableMenuItems)
        menuBar.Enable(self._editCameraLocationMenuId, enableMenuItems)
        menuBar.Enable(self._removeCameraMenuId, enableMenuItems)

        # Black the image in case the newly selected camera is not running
        self._clearLargeView()

        self._curSelectedCamera = cameraLocation

        # Notify the back end that the selected camera has changed.
        self._setLargeViewCamera(cameraLocation)

        self._lastActiveId = -1

        # Update the rule list:
        self._ruleListPanel.setCameraLocation(cameraLocation)
        self._updateCameraStatus(cameraLocation)


    ###########################################################
    def _setLargeViewCamera(self, cameraLocation):
        """Utility function to proxy backend request.

        @param  cameraLocation  The large view camera name.
        """
        w, h = self._largeView.GetSize()
        menuBar = self.GetTopLevelParent().GetMenuBar()
        audioVolume = 0 if menuBar.IsChecked(self._muteAudio) else 100
        if cameraLocation != self._largeViewCamera and self._largeViewCamera is not None:
            self._backEndClient.setLiveViewParams(self._largeViewCamera, _kSmallVideoSize[0], _kSmallVideoSize[1], 0, _kSmallVideoFps)
        self._backEndClient.setLiveViewParams(cameraLocation, w, h, audioVolume, 0)
        self._largeViewCamera = cameraLocation


    ###########################################################
    def OnPreviewWinPaint(self, event):
        """Draw a selection border and shadows around the camera previews.

        @param  event  The paint event.
        """
        # Check if our preview win is still alive before we use it, as suggested
        # by wxPython docs...
        if not self._previewWin:
            return

        dc = event.GetDC()
        clientSize = dc.GetSize()

        if len(self._cameraLocations) != self._drawLastNumCams or \
            self._curSelectedCamera != self._drawLastSelectedCam or \
            self._drawLastSize != clientSize or \
            self._drawLastScrollPos != self._previewWin.GetViewStart():
            # We only want to regenerate our bitmap if something changed.

            self._drawLastNumCams = len(self._cameraLocations)
            self._drawLastSelectedCam = self._curSelectedCamera
            self._drawLastSize = clientSize
            self._drawLastScrollPos = self._previewWin.GetViewStart()

            # We want to use a graphics context, which doesn't work on the DC
            # that's provided by the event (at least, it doesn't work on
            # Windows). We'll workaround by doing work on a bitmap...
            bitmap = wx.Bitmap.FromRGBA(*clientSize)
            mdc = wx.MemoryDC()
            mdc.SelectObject(bitmap)
            gc = wx.GraphicsContext.Create(mdc)

            # Draw selection and shadows.
            for camera in self._previewControls:
                camPreviewCtrl = self._previewControls[camera][0]
                try:
                    # Check if our camera preview is still alive before we use
                    # it, as suggested by wxPython docs...
                    if camPreviewCtrl:
                        ctrlRect = camPreviewCtrl.GetRect()
                    else:
                        del self._previewControls[camera]
                        continue
                except wx._core.PyDeadObjectError:
                    # Under windows when we close the application a background
                    # draw will be requested after the preview controls have
                    # been destroyed.  We'll catch this, remove the controls
                    # from our list and set the active camera to None, which
                    # seems like the proper thing to do if this ever happens
                    # for any other strange reason...
                    del self._previewControls[self._curSelectedCamera]

                    # Unfortunately, if this DOES happen in the closing case,
                    # there is a chance the rule panel list itself has been
                    # deleted, so the following will fail with the same error.
                    # If that happens we know the app is shutting down so we
                    # can just ignore.
                    try:
                        self._setActiveCamera(None)
                    except wx._core.PyDeadObjectError:
                        pass
                    return

                if camera == self._curSelectedCamera:
                    # Draw a selection border around the selected camera.
                    gc.SetPen(self._kSelectionBorderPen)
                    gc.SetBrush(self._kSelectionBorderBrush)
                    gc.DrawRoundedRectangle(ctrlRect.x-_kPreviewSelectionOffset,
                                        ctrlRect.y-_kPreviewSelectionOffset,
                                        ctrlRect.width+2*_kPreviewSelectionOffset-1,
                                        ctrlRect.height+2*_kPreviewSelectionOffset-1,
                                        _kPreviewSelectionRounding)
                else:
                    # Draw shadows around the other cameras.
                    c = wx.Colour(*_kShadowColor)
                    gc.SetPen(wx.Pen(c))
                    gc.SetBrush(wx.Brush(c))
                    gc.DrawRectangle(ctrlRect.x+0, ctrlRect.y+0, ctrlRect.width,
                                     ctrlRect.height)
                    gc.DrawRectangle(ctrlRect.x+1, ctrlRect.y+1, ctrlRect.width,
                                     ctrlRect.height)
                    gc.DrawRectangle(ctrlRect.x+2, ctrlRect.y+2, ctrlRect.width,
                                     ctrlRect.height)

            mdc.SelectObject(wx.NullBitmap)
            self._drawBitmap = bitmap

        dc.DrawBitmap(self._drawBitmap, 0, 0, True)


    ###########################################################
    def OnDrawRightShadow(self, event):
        """Draw the right side of the shadow for the main video view.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self._shadowRight)
        gc, finishFn = createDoubleBufferCompatGc(dc)

        # Get the rect and colors to use.
        ctrlRect = self._shadowRight.GetRect()

        c = wx.Colour(*_kShadowColor)
        gc.SetPen(wx.Pen(c))
        gc.SetBrush(wx.Brush(c))

        # Draw the shadow.
        for i in range(0, 4):
            gc.DrawRectangle(-1, i, i+1, ctrlRect.height-i)

        finishFn()


    ###########################################################
    def OnDrawBottomShadow(self, event):
        """Draw the bottom of the shadow for the main video view.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self._shadowBottom)
        gc, finishFn = createDoubleBufferCompatGc(dc)

        # Get the rect and colors to use.
        ctrlRect = self._shadowBottom.GetRect()

        c = wx.Colour(*_kShadowColor)
        gc.SetPen(wx.Pen(c))
        gc.SetBrush(wx.Brush(c))

        # Draw the shadow.
        for i in range(0, 4):
            gc.DrawRectangle(i, -1, ctrlRect.width-4, i+1)
        finishFn()


    ###########################################################
    def OnEnableIcon(self, event):
        """Draw a selection border around the selected camera.

        @param  event  The erase background event.
        """
        button = event.GetEventObject()
        for name in self._previewControls:
            if button in self._previewControls[name]:
                # Toggle whether the camera is enabled or disabled.
                enabled = self._enabledModel.isEnabled(name)
                self._backEndClient.enableCamera(name, not enabled)

                # Technically, not needed, but makes UI update faster...
                self._enabledModel.enableCamera(name, not enabled)

                return


    ###########################################################
    def OnPowerButtonClick(self, event):
        """Respond to a click event on the 'camera off' screen, enable camera.

        @param  event  The EVT_BUTTON event, ignored.
        """
        if not self._curSelectedCamera:
            return
        self._backEndClient.enableCamera(self._curSelectedCamera, True)
        self._enabledModel.enableCamera(self._curSelectedCamera, True)


    ###########################################################
    def OnToggleMuteAudio(self, event):
        # Notify the back end that the selected camera has changed.
        if self._curSelectedCamera is not None:
            self._setLargeViewCamera(self._curSelectedCamera)

    ###########################################################
    def _handleCameraEnable(self, enableModel, camera):
        """Handle a change camera enable state.

        @param  resultsModel  Should be self._enabledModel
        @param  camera        The camera that was enabled.
        """
        assert enableModel == self._enabledModel
        assert camera is not None, "Shouldn't ever have general updates!"

        enabled = self._enabledModel.isEnabled(camera)

        # Update the recording icon...
        if camera in self._previewControls:
            _, recordOn, recordOff, _, warningIcon = \
                self._previewControls[camera]

            recordOn.Show(enabled)
            recordOff.Show(not enabled)

            # Clear our FPS status if you're turning off...
            if (not enabled) and (camera in self._fpsStats):
                self._fpsStats[camera] = _FpsStats(camera)
                warningIcon.Show(False)

        if camera == self._curSelectedCamera:
            self._setLargeViewCamera(camera)


    ###########################################################
    def OnWarningIcon(self, event):
        """Handle clicks on the warning icon."""
        cameraLocation = event.GetEventObject().GetName()
        fpsStats = self._fpsStats[cameraLocation]

        if fpsStats.slowRequestFpsSince:
            message = _kSlowProcessingWarning
            since = fpsStats.slowRequestFpsSince
            url = kSlowProcessingUrl
        elif fpsStats.slowCaptureFpsSince:
            message = _kSlowCaptureWarning
            since = fpsStats.slowCaptureFpsSince
            url = kSlowFpsUrl
        else:
            message = None

        if message:
            message = message % _formatDuration(time.time() - since)
            dlg = MessageDialogWithLink(self.GetTopLevelParent(),
                                        _kCameraWarningTitle, message,
                                        _kSeeReferenceGuideText, url)
            try:
                dlg.ShowModal()
            finally:
                dlg.Destroy()


    ###########################################################
    def OnPreviewSelection(self, event):
        """Draw a selection border around the selected camera.

        @param  event  The erase background event.
        """
        cameraLocation = event.GetEventObject().GetName()
        self._setActiveCamera(cameraLocation)
        self._previewFocusHolder.SetFocus()
        self.Refresh()


    ###########################################################
    def OnCameraAdded(self, event):
        """Update the UI to include the newly added camera.

        @param  event  The camera added event.
        """
        if not self._isActiveView:
            return

        cameraLocation = event.getLocation()

        camType, uri, enabled, extra = \
                    self._backEndClient.getCameraSettings(cameraLocation)
        self._cameraLocations.append(cameraLocation)
        self._cameraSettings[cameraLocation] = (camType, uri, extra)
        self._enabledModel.enableCamera(cameraLocation, enabled)
        self._createPreviewControls(cameraLocation)
        self._layoutPreviewControls()

        self._enableLiveView(cameraLocation)

        # Make the added camera active.
        self._setActiveCamera(cameraLocation)
        self._ruleListPanel.setCameraLocation(cameraLocation)

        self._previewWin.FitInside()


    ###########################################################
    def OnCameraEdited(self, event):
        """Respond to a camera edit if necessary.

        @param  event  The camera edited event.
        """
        if not self._isActiveView:
            return

        # Get the original name and the new name (if it's been changed).
        origLocation, curLocation = event.getLocations()

        # If the name changed, we need to update the label
        if origLocation != curLocation:
            if origLocation == self._curSelectedCamera:
                self._curSelectedCamera = curLocation
                self._ruleListPanel.setCameraLocation(curLocation)

            self._cameraLocations.remove(origLocation)
            self._cameraLocations.append(curLocation)

            # Move the controls and update the name
            (videoWindow, recordOn, recordOff, nameLabel, warningIcon) = \
                                        self._previewControls[origLocation]
            videoWindow.SetName(curLocation)
            warningIcon.SetName(curLocation)
            del self._previewControls[origLocation]
            nameLabel.SetLabel(curLocation)
            self._previewControls[curLocation] = \
                    (videoWindow, recordOn, recordOff, nameLabel, warningIcon)
            self._layoutPreviewControls()

            # Delete old settings / enabled...
            del self._cameraSettings[origLocation]
            self._enabledModel.enableCamera(origLocation, None)

        # Always reget settings...
        camType, uri, enabled, extra = \
                    self._backEndClient.getCameraSettings(curLocation)
        self._cameraSettings[curLocation] = (camType, uri, extra)
        self._enabledModel.enableCamera(curLocation, enabled)

        if origLocation == self._curSelectedCamera:
            self._setLargeViewCamera(curLocation)


    ###########################################################
    def OnCameraRemoved(self, event):
        """Update the UI to reflect a camera deletion.

        @param  event  The camera removed event.
        """
        if not self._isActiveView:
            return

        cameraLocation = event.getLocation()

        # Removing a camera might cause other ones being unfrozen
        for camLoc in self._backEndClient.getCameraLocations():
            # If there's a camera which we don't have we need to check if it is
            # still in the frozen state
            if not camLoc in self._cameraLocations:
                _, _, _, extra = self._backEndClient.getCameraSettings(camLoc)
                # If it's not frozen anymore we do a complete reset of the
                # view (just to be sure, because and other ones might have also
                # been unfrozen) ...
                if not extra.get('frozen', False):
                    self._resetPreviews()
                    return

        self._cameraLocations.remove(cameraLocation)

        # If this was the selected camera pick another to highlight
        if cameraLocation == self._curSelectedCamera:
            curLocation = None
            if len(self._cameraLocations):
                curLocation = self._cameraLocations[0]
            self._setActiveCamera(curLocation)
            self._ruleListPanel.setCameraLocation(curLocation)

        # Destroy the associated preview controls
        for ctrl in self._previewControls[cameraLocation]:
            ctrl.Destroy()
        del self._previewControls[cameraLocation]

        del self._cameraSettings[cameraLocation]
        self._enabledModel.enableCamera(cameraLocation, None)

        # Close the shared memory reference to the live view
        self._closeMMap(cameraLocation)
        if cameraLocation in list(self._openCameras):
            self._openCameras.discard(cameraLocation)

        self._layoutPreviewControls()
        self._previewWin.FitInside()


    ###########################################################
    def _openCameraStream(self, cameraLocation):
        """Open the live feed for a given camera location.

        NOTES:
        - If the file doesn't exist, we'll just throw an exception.
        - It's possible that the other process is currently in the
          middle of creating the file.  If so, we'll get a wrong-sized file.
          If that's the case, reading the buffer will fail and we'll retry
          here, so no big deal.

        @param  cameraLocation  The camera location to open.
        """
        if cameraLocation in self._openCameras:
            assert cameraLocation in self._mmaps
            return

        # If this camera is active make sure we're getting the large view.
        # If the user turns a camera off and on without selecting a new camera
        # we might have an old frame in the buffer still.  Clear it now.
        if self._curSelectedCamera == cameraLocation:
            self._clearLargeView()

        # Attempt to open the mmap.
        if self._openMmap(cameraLocation):
            self._fpsStats[cameraLocation] = _FpsStats(cameraLocation)
            # only attempt to control the camera when we know it is on
            if self._curSelectedCamera == cameraLocation:
                self._setLargeViewCamera(cameraLocation)

    ###########################################################
    def _openMmap(self, cameraLocation):

        opened = super(MonitorView, self)._openMmap(cameraLocation)
        if opened:
            self._openCameras.add(cameraLocation)
            self._mmapMisreads[cameraLocation] = 0
        return opened

    ###########################################################
    def _enableLiveView(self, cameraLocation):
        self._backEndClient.enableLiveView(cameraLocation)

    ###########################################################
    def _disableLiveView(self, cameraLocation):
        self._backEndClient.enableLiveView(cameraLocation, False)
        self._closeMMap(cameraLocation)
        if cameraLocation in self._openCameras:
            self._openCameras.discard(cameraLocation)

    ###########################################################
    def _startVideoStreams(self):
        """Start the video streams."""
        for cameraLocation in self._cameraLocations:
            self._backEndClient.setLiveViewParams(cameraLocation, _kSmallVideoSize[0], _kSmallVideoSize[1], 0, _kSmallVideoFps)
            self._enableLiveView(cameraLocation)

        # Make sure currently selected camera provides fps/resolution matching "large" window requirements
        if self._curSelectedCamera:
            self._setLargeViewCamera(self._curSelectedCamera)

        self._previewTimer.Start(500, False)
        self._activeViewTimer.Start(25, False)

        self.OnPreviewTimer()
        self.OnActiveViewTimer()


    ###########################################################
    def _stopVideoStreams(self):
        """Stop the video streams."""
        self._activeViewTimer.Stop()
        self._previewTimer.Stop()

        for cameraLocation in self._cameraLocations:
            self._disableLiveView(cameraLocation)

        self._mmaps = {}
        self._openCameras = set()
        self._mmapMisreads = {}


    ###########################################################
    def _updateCameraStatus(self, location):
        """Ensure that the correct status is displayed for a camera.

        @param  location  The location to update status for.
        """
        isLargeView = (location == self._curSelectedCamera)
        largeViewStatusSizer = None

        if location is None:
            self._clearLargeView()

        elif location not in self._openCameras:
            try:
                status, reason, isEnabled = \
                    self._backEndClient.getCameraStatusEnabledAndReason(location)
                if isEnabled:
                    self._disabledCameras.discard(location)
                elif not location in self._disabledCameras:
                    # If the current camera was recently disabled, clear large view
                    if location == self._curSelectedCamera:
                        self._clearLargeView()
                    self._disabledCameras.add(location)
            except Exception:
                # If the back end dies for some reason, we'll get an exception.
                # We'll catch it so we get the abbreviated stack crawl.
                self._logger.warn("Problems talking to back end", exc_info=True)
                return

            videoWindow, _, _, _, _ = self._previewControls[location]

            # Update the enabled model, just in case someone else turned the
            # camera on/off...
            self._enabledModel.enableCamera(location, isEnabled)

            if status in (kCameraOn, kCameraOff):
                if not isEnabled:
                    videoWindow.updateBitmap(self._smallCameraOffScreen)
                    if isLargeView:
                        largeViewStatusSizer = self._cameraOffSizer
                else:
                    rules = self._ruleListPanel.getRulesForLocation(location)
                    hasEnabledRule = False
                    for _, _, _, enabled, responses in rules:
                        if enabled and responses:
                            hasEnabledRule = True
                            break
                    if hasEnabledRule:
                        videoWindow.updateBitmap(self._smallNotScheduledScreen)
                        if isLargeView:
                            largeViewStatusSizer = self._notScheduledSizer
                    else:
                        videoWindow.updateBitmap(self._smallNoActiveRulesScreen)
                        if isLargeView:
                            largeViewStatusSizer = self._noActiveRulesSizer
            elif status == kCameraConnecting:
                videoWindow.updateBitmap(self._smallConnectingScreen)
                if isLargeView:
                    largeViewStatusSizer = self._connectingSizer
            elif status == kCameraFailed:
                bmp = self._smallConnectFailedScreen.get("" if reason is None else reason, None)
                if bmp is None:
                    bmp = makeVideoStatusBitmap(kStatusTextCouldNotConnect+"\n"+reason, self._failedLabelReason.GetFont())
                    self._smallConnectFailedScreen[reason] = bmp
                videoWindow.updateBitmap(bmp)
                if isLargeView:
                    largeViewStatusSizer = self._connectFailedSizer
                    self._failedLabelReason.SetLabel("" if reason is None else reason)
            else:
                assert False, "Unknown camera status: %s" % status

        if isLargeView:
            for sizer in self._largeViewStatusSizers:
                sizer.ShowItems(sizer == largeViewStatusSizer)
            self._bigMessagePanel.Show(largeViewStatusSizer is not None)
            self._bigMessagePanel.Layout()
            self._largeView.Show(largeViewStatusSizer is None)

    ###########################################################
    def _getLiveImage(self, location, lastId = -1):

        result = super(MonitorView, self)._getLiveImage(location, lastId)

        _, _, _, id, _, _ = result
        if id is None:
            self._openCameras.discard(location)
            self._closeMMap(location)

        return result

    ###########################################################
    def OnPreviewTimer(self, event=None):
        """Update the preview windows.

        @param  event  The timer event (ignored).
        """
        # Top level parent will be None when app is closing...
        if self.GetTopLevelParent() is None:
            return

        # Re-run in a little bit if we're not supposed to be animating
        id = _kPreviewTimerId if event is None else event.GetId()
        if id == _kActiveTimerId:
            self.OnActiveViewTimer(event)
            return

        if not self.GetTopLevelParent().shouldAnimateChild(self):
            return

        if self._pendingLicenseChangeEvent:
            wx.CallAfter(self.handleLicenseChange)

        if self._pendingActiveViewResize:
            self._pendingActiveViewResize = False
            self._setLargeViewCamera(self._curSelectedCamera)

        now = time.time()
        updateStatus = \
                (now > self._lastStatusQueryTime + _kCameraStatusUpdateTime)
        if updateStatus:
            # We will check every _kCameraStatusUpdateTime seconds that we're
            # displaying the correct status information for any unavailable
            # streams.
            self._lastStatusQueryTime = now

            # We also use this interval to make sure the memory map file itself
            # still exists.  If it doesn't we close our handle to it.
            for location in list(self._openCameras):
                if not os.path.exists(os.path.join(getUserLocalDataDir(),
                            'live', location + '.live')):
                    self._closeMMap(location)
                    self._openCameras.discard(location)


        for location in self._cameraLocations:
            # If the camera doesn't have a memory map to the live stream,
            # update the displayed status screen and attempt to open the
            # live stream again.
            if location not in list(self._openCameras):
                if updateStatus:
                    self._updateCameraStatus(location)

                if location in self._disabledCameras:
                    # go to the next camera; all further operations apply
                    # only to enabled cameras
                    continue

                try:
                    self._openCameraStream(location)
                    if location == self._curSelectedCamera:
                        self._updateCameraStatus(location)
                except IOError:
                    pass
                except:
                    self._logger.error("open camera stream failed: ",
                                       exc_info=True)

            # For locations that have an open live stream update the currently
            # displayed image.
            if location in list(self._openCameras):
                try:
                    bmpData, width, height, _, requestFps, captureFps = \
                            self._getLiveImage(location)
                    warningIcon = None
                    nameLabel = None
                    try:
                        if bmpData is not None:
                            videoWindow, _, _, nameLabel, warningIcon = \
                                self._previewControls[location]
                            try:
                                videoWindow.updateImageDataRaw(
                                    bmpData, width, height
                                )
                            except (AttributeError, NotImplementedError):
                                # It's fine if we're here. It just means that
                                # this particular videoWindow does not have a
                                # function that handles raw image input. We can
                                # still use self._updatePreview to update the
                                # preview window.
                                bmp = wx.Bitmap.FromBuffer( width, height, bmpData )
                                videoWindow.updateBitmap( bmp )
                            self._mmapMisreads[location] = 0
                    except ValueError:
                        # Sometimes this will occur normally, though if it
                        # happens two or three times we are probably on osx
                        # and holding on to a corrupt file that has been
                        # deleted.  Raise and get kicked out of _openCameras +
                        # _mmaps, and open the good file on the next iteration.
                        self._mmapMisreads[location] += 1
                        if self._mmapMisreads[location] >= _kMmapMisreadTolerance:
                            raise

                    try:
                        fpsStats = self._fpsStats[location]

                        fpsStats.trackFrameRate(requestFps, captureFps, self._logger)
                        if not warningIcon is None:
                            warningIcon.Show(fpsStats.checkForErrors())

                        if self._debugModeModel.isDebugMode() and nameLabel is not None:
                            nameLabel.SetLabel("%s %.2f %.2f" % (location,
                                               requestFps, captureFps))
                    except ValueError:
                        warningIcon.Show(False)
                        if self._debugModeModel.isDebugMode():
                            nameLabel.SetLabel(location)
                except Exception:
                    self._logger.error("getting image failed: ", exc_info=True)
                    self._openCameras.discard(location)
                    self._closeMMap(location)

    ###########################################################
    def OnActiveViewTimer(self, event=None):
        """Update the active view.

        @param  event  The timer event (ignored).
        """
        # Top level parent will be None when app is closing...
        if self.GetTopLevelParent() is None:
            return

        # Re-run in a little bit if we're not supposed to be animating
        if not self.GetTopLevelParent().shouldAnimateChild(self):
            if not self._pauseLiveView:
                self._pauseLiveView = True
                for cameraLocation in self._cameraLocations:
                    try:
                        self._disableLiveView(cameraLocation, False)
                    except Exception:
                        # Going to ignore these, since we get them when the
                        # back end is being exited as we close...
                        pass
            return

        if self._pauseLiveView:
            self._pauseLiveView = False
            for cameraLocation in self._cameraLocations:
                self._enableLiveView(cameraLocation)

        if self._curSelectedCamera not in self._openCameras:
            return

        # Read the image data and update the display
        try:
            bmpData, width, height, id, _, _ = \
                self._getLiveImage(self._curSelectedCamera, self._lastActiveId)
            if id is not None:
                self._lastActiveId = id
            if bmpData is not None:
                self._updateVideoControl( self._largeView, width, height, bmpData )
        except ValueError:
            pass
        except Exception:
            self._logger.error("getting live image failed: ", exc_info=True)
            self._openCameras.discard(self._curSelectedCamera)
            self._closeMMap(self._curSelectedCamera)

    ###########################################################
    def _doShowPopup(self, position, debugModifier):
        """Actually display the context menu

        We trigger this from a wx.CallAfter from the actual context menu event
        handler as the clicked window may be destroyed before the result of
        the menu selection is completed which causes a crash on OSX when the
        context menu even resolves, seen on wx 2.8 at least.

        @param  position       The position where the menu should be shown from.
        @param  debugModifier  If True the debug modifier keys were held.
        """
        # Create our menu.  TODO: Use createMenuFromData() if more items?
        menu = wx.Menu()

        isDebugMode = self._debugModeModel.isDebugMode()

        if debugModifier:
            if isDebugMode:
                debugMenuItem = menu.Append(-1, "Disable Debug Mode")
            else:
                debugMenuItem = menu.Append(-1, "Enable Debug Mode")
            self.Bind(wx.EVT_MENU, self.OnShowHideDebugMode, debugMenuItem)
        else:
            debugMenuItem = None

        addCameraItem = menu.Append(-1, "Add Camera...")
        removeCameraItem = menu.Append(-1, "Remove Camera...")
        editCameraItem = menu.Append(-1, "Edit Camera...")
        renameCameraItem = menu.Append(-1, "Edit Camera Location...")
        reconnectCameraItem = menu.Append(-1, "Reconnect to Camera")

        if self._cameraPopupSource and \
                self._cameraPopupSource not in self._cameraSettings:
                    self._cameraPopupSource = ''

        # Add web page link if not for a webcam...
        if self._cameraPopupSource:
            cameraType, _, _ = self._cameraSettings[self._cameraPopupSource]
        else:
            cameraType = None
        if cameraType != kWebcamCamType:
            menu.AppendSeparator()
            cameraWebPageItem = menu.Append(-1, "Visit Camera Web Page")
            if isDebugMode:
                startPcapItem = menu.Append(-1, "Report Camera Connection Problem...")

        self.Bind(wx.EVT_MENU, self.OnAddCamera, addCameraItem)
        self.Bind(wx.EVT_MENU, self.OnRemoveCamera, removeCameraItem)
        self.Bind(wx.EVT_MENU, self.OnEditCamera, editCameraItem)
        self.Bind(wx.EVT_MENU, self.OnRenameCamera, renameCameraItem)
        self.Bind(wx.EVT_MENU, self.OnReconnect, reconnectCameraItem)
        if cameraType != kWebcamCamType:
            self.Bind(wx.EVT_MENU, self.OnCameraWebPage, cameraWebPageItem)
            if isDebugMode:
                self.Bind(wx.EVT_MENU, self.OnStartPcap, startPcapItem)

        if not self._cameraPopupSource:
            removeCameraItem.Enable(False)
            editCameraItem.Enable(False)
            renameCameraItem.Enable(False)
            reconnectCameraItem.Enable(False)
            if cameraType != kWebcamCamType:
                cameraWebPageItem.Enable(False)
                if isDebugMode:
                    startPcapItem.Enable(False)

        # Popup the menu
        self.PopupMenu(menu, position)

        # Unbind.  Not sure if this is necessary, but seems like a good idea.
        if debugMenuItem is not None:
            self.Unbind(wx.EVT_MENU, debugMenuItem)
        self.Unbind(wx.EVT_MENU, addCameraItem)
        self.Unbind(wx.EVT_MENU, removeCameraItem)
        self.Unbind(wx.EVT_MENU, editCameraItem)
        self.Unbind(wx.EVT_MENU, renameCameraItem)
        self.Unbind(wx.EVT_MENU, reconnectCameraItem)
        if cameraType != kWebcamCamType:
            self.Unbind(wx.EVT_MENU, cameraWebPageItem)
            if isDebugMode:
                self.Unbind(wx.EVT_MENU, startPcapItem)

        # Kill the menu
        menu.Destroy()



    ###########################################################
    def OnShowPopup(self, event):
        """Handle the context menu event.

        @param  event  The event to handle
        """
        eventObj = event.GetEventObject()

        if (eventObj == self._largeView) or \
           not isinstance(eventObj, BitmapWindow) and \
           not isinstance(eventObj, OsCompatibleGLCanvas):
            self._cameraPopupSource = self._curSelectedCamera
        else:
            self._cameraPopupSource = event.GetEventObject().GetName()

        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)

        if wx.GetKeyState(wx.WXK_SHIFT):
            debugKeys = True
        else:
            debugKeys = False

        wx.CallAfter(self._doShowPopup, pos, debugKeys)


    ###########################################################
    def OnShowHideDebugMode(self, event):
        """Handle the "Enable / Disable Debug Mode" menu item.

        @param  event  The event to handle
        """
        wasDebugMode = self._debugModeModel.isDebugMode()
        self._debugModeModel.setDebugMode(not wasDebugMode)


    ###########################################################
    def _handleDebugModeChange(self, debugModeModel):
        """Update the debug info.

        @param  debugModeModel  Should be self._debugModeModel
        """
        assert debugModeModel == self._debugModeModel
        if not debugModeModel.isDebugMode():
            for loc, (_,_,_, nameLabel,_) in self._previewControls.iteritems():
                nameLabel.SetLabel(loc)


    ###########################################################
    def OnAddCamera(self, event=None):
        """Add a new camera.

        @param  event  The menu event (ignored).
        """
        # Don't allow adding if we're already at max...
        if checkForMaxCameras(self._backEndClient, self.GetTopLevelParent()):
            return

        wizard = CameraSetupWizard(self.GetTopLevelParent(),
                                   self._backEndClient, self._dataManager)
        try:
            if wizard.run():
                # If the dialog wasn't canceled make sure the Monitor view is
                # displayed.
                self._activateFunc()
        finally:
            wizard.Destroy()

        # Any changes to the menu likely didn't update due to a bug in wx...
        # We'll re-call self._setActiveCamera to make sure things are correct.
        if self._isActiveView:
            self._setActiveCamera(self._curSelectedCamera)


    ###########################################################
    def OnRemoveCamera(self, event=None):
        """Remove the camera stored in self._cameraPopupSource.

        @param  event  The menu event (ignored).
        """
        camera = self._cameraPopupSource
        if event.GetId() == self._removeCameraMenuId:
            camera = self._curSelectedCamera

        # Remove the camera
        if not removeCamera(self, camera, self._dataManager,
                             self._backEndClient):
            return

        # Update the UI
        evt = FrontEndEvents.CameraRemovedEvent(camera)
        self.GetEventHandler().AddPendingEvent(evt)


    ###########################################################
    def OnEditCamera(self, event):
        """Edit the camera stored in self._cameraPopupSource.

        @param  event  The menu event (ignored).
        """
        camera = self._cameraPopupSource
        if event.GetId() == self._editCameraMenuId:
            camera = self._curSelectedCamera
        wizard = CameraSetupWizard(self.GetTopLevelParent(),
                                   self._backEndClient, self._dataManager,
                                   camera)
        try:
            wizard.run()
        finally:
            wizard.Destroy()


    ###########################################################
    def OnRenameCamera(self, event):
        """Rename the camera stored in self._cameraPopupSource.

        @param  event  The menu event (ignored).
        """
        camera = self._cameraPopupSource
        if event.GetId() == self._editCameraLocationMenuId:
            camera = self._curSelectedCamera
        dlg = RenameCameraDialog(self.GetTopLevelParent(), camera,
                                 self._backEndClient, self._dataManager)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnReconnect(self, event):
        """Reconnect a camera.

        @param  event  The menu event.
        """
        camera = self._cameraPopupSource
        if event.GetId() == self._reconnectCameraMenuId:
            camera = self._curSelectedCamera

        enabled = self._enabledModel.isEnabled(camera)
        if not enabled:
            choice = wx.MessageBox('"%s" is currently off.  Would you like to '
                                   'turn it on?' % camera,
                                   "Reconnect to Camera", wx.ICON_QUESTION |
                                   wx.YES_NO, self.GetTopLevelParent())
            if choice == wx.YES:
                self._enabledModel.enableCamera(camera, True)
            else:
                return

        self._backEndClient.enableCamera(camera, False)
        self._backEndClient.enableCamera(camera, True)

        if camera == self._curSelectedCamera:
            self._setLargeViewCamera(camera)


    ###########################################################
    def OnCameraWebPage(self, event):
        """Go to a camera's web page.

        @param  event  The menu event.
        """
        cameraName = self._cameraPopupSource
        if event.GetId() == self._cameraWebPageMenuId:
            cameraName = self._curSelectedCamera

        _, url, _ = self._cameraSettings[cameraName]

        if isUpnpUrl(url):
            upnpDeviceDict = cPickle.loads(self._backEndClient.getUpnpDevices())
            url = realizeUpnpUrl(upnpDeviceDict, url)

            if not url:
                wx.MessageBox("This device can no longer be found on the "
                              "network.  It may be rebooting.",
                              "Error", wx.OK | wx.ICON_ERROR,
                              self.GetTopLevelParent())
                return

        if isOnvifUrl(url):
            onvifDeviceDict = cPickle.loads(self._backEndClient.getOnvifDevices())
            url = realizeOnvifUrl(onvifDeviceDict, url)

            if not url:
                wx.MessageBox("This device can no longer be found on the "
                              "network.  It may be rebooting.",
                              "Error", wx.OK | wx.ICON_ERROR,
                              self.GetTopLevelParent())
                return

        # Copied from CameraSetupWizard...

        # Make a new URL with just the hostname and port...
        # ...we'll also force to http port 80 (as a guess) if the URL
        # is non-http...
        splitResult = urlparse.urlsplit(url)
        scheme = splitResult.scheme
        netloc = splitResult.hostname

        try:
            port = splitResult.port
        except ValueError:
            assert False, "Non-numeric port"
            port = None

        if not netloc:
            netloc = ''
        if scheme != 'http':
            # Non-http.  Guess that we can do http default port...
            scheme = 'http'
        elif port:
            # Http, and there's a port.  Add it in...
            netloc += ':%d' % port

        linkStr = urlparse.urlunsplit((scheme, netloc, "/", "", ""))
        webbrowser.open(linkStr)


    ###########################################################
    def OnStartPcap(self, event=None):
        self._logger.info(
            "Preparing packet capture for %s." % self._cameraPopupSource
        )
        try:
            # Should be fine to pass in our logger instance, since this UI will
            # be disabled while dialogs are shown to the user...
            HandlePacketCaptureRequest(
                    self, self._logger, self._backEndClient,
                    self._cameraPopupSource, _kPcapDelaySeconds,
            )
        except:
            # Catch everything, but make sure to log it.
            self._logger.error("Uncaught exception: ", exc_info=True)


    ###########################################################
    def OnTestCamera(self, event=None):
        """View the test screen for the current active camera.

        @param  event  The EVT_BUTTON event (ignored).
        """
        if not self._curSelectedCamera:
            assert False, "No camera selected"
            return

        wizard = CameraSetupWizard(self.GetTopLevelParent(),
                                   self._backEndClient, self._dataManager,
                                   self._curSelectedCamera, True)
        try:
            wizard.run()
        finally:
            wizard.Destroy()


    ###########################################################
    def _clearLargeView(self):
        """Clear the large view image."""
        if self._bitmapMode:
            emptyBitmap = wx.Bitmap(_kFullVideoSize[0], _kFullVideoSize[1])
        else:
            emptyBitmap = Image.new( 'RGB', _kFullVideoSize )
        self._largeView.updateBitmap(emptyBitmap)


    ###########################################################
    def OnFrozenWarning(self, event):
        """Handle a click of the frozne warning link.

        @param  event  The EVT_HYPERLINK event
        """
        showHiddenCamsWarning(self, self._backEndClient)


    ###########################################################
    def OnLargeViewSize(self, event):
        """Update the size of requested images.

        @param  event  The EVT_SIZE event, ignored
        """
        if event is not None:
            event.Skip()

        # We may get a string of size events in a row, we don't want to take
        # on the overhead of acting on each.
        if self._bitmapMode:
            bmp = self._largeView.getBitmap()
            if bmp:
                self._largeView.updateBitmap(bmp)

        self._pendingActiveViewResize = True


##############################################################################
def makeVideoStatusBitmap(statusText, font, needPil=False, icon=None,
                         width=_kSmallVideoSize[0], height=_kSmallVideoSize[1]):
    """Make a wx.Bitmap to show for small status windows.

    NOTE: This is called from outside of this file.

    @param  statusText  The text to display.
    @param  font        The font to use.
    @param  icon        An wx.Bitmap to show in the status window
    @param  width       The width to make the window.
    @param  height      The height to make the window.
    @return bmp         An image to show when we have an error, as a wx.Bitmap.
    """
    return _makeVideoStatusBitmap(statusText, font,
                                  kStatusStartColor, kStatusEndColor,
                                  needPil, icon, width, height)


##############################################################################
# We'll ignore FPS until we've processed this many frames, to avoid weird
# boundary conditions at the beginning...
_kFpsIgnoreSamples = 20

# If we see low FPS for this many frames in a row, it's a problem.
_kFpsTriggerCount = 15

# If we see capture FPS fall below this, it's an error...
_kMinCaptureFps = 7.5

# Do not warn more often than that, unless declining fps
_kMinWarningDistance = 60

class _FpsStats(object):
    """A little internal class for tracking frames per second."""

    ###########################################################
    def __init__(self, camLoc):
        """_FpsStats constructor."""

        super(_FpsStats, self).__init__()

        self._camLoc = camLoc

        # Keep track of slow FPS
        # ...the count is how many instances of slowness have happened in a row.
        # It is reset whenever we get a fast FPS.  The start is set whenever it
        # is None and the count > _kFpsTriggerCount.  The end is set whenever
        # the count > _kFpsTriggerCount.  See _trackFrameRate()
        self._slowRequestFpsCount = 0
        self._slowRequestFpsStart = None
        self._slowCaptureFpsCount = 0
        self._slowCaptureFpsStart = None

        # Keep track of number of samples we've been given...
        self._numSamples = 0

        # We'll set these in checkForErrors()
        self.slowRequestFpsSince = None
        self.slowCaptureFpsSince = None

        self._lastWarningTime = time.time() - _kMinWarningDistance
        self._lastWarningReqFps = 0
        self._lastWarningCapFps = 0
        self._warningsSkipped = 0


    ###########################################################
    def checkForErrors(self):
        """Return true if an error condition is present.

        Will set slowRequestFpsSince and slowCaptureFpsSince so you
        can check what type of error it was.

        @return isError  True if there's an error.
        """
        if self._slowRequestFpsCount >= _kFpsTriggerCount:
            self.slowRequestFpsSince = self._slowRequestFpsStart
        else:
            self.slowRequestFpsSince = None

        if self._slowCaptureFpsCount >= _kFpsTriggerCount:
            self.slowCaptureFpsSince = self._slowCaptureFpsStart
        else:
            self.slowCaptureFpsSince = None

        return (self.slowRequestFpsSince is not None) or \
               (self.slowCaptureFpsSince is not None)


    ###########################################################
    def trackFrameRate(self, requestFps, captureFps, logger=None):
        """Keep track of the frame rate, noting instances of slow processing.

        @return requestFps  The average # of times per second that getNewFrame()
                            has been called.  Note: this can be higher than
                            captureFps, since getNewFrame() effectively polls
                            for a new frame.
        @return captureFps  The average # of times per second that a new frame
                            came in from the camera.
        """
        self._numSamples += 1
        if self._numSamples < _kFpsIgnoreSamples:
            return

        nowTime = time.time()

        if requestFps < captureFps:
            self._slowRequestFpsCount += 1
            if self._slowRequestFpsCount >= _kFpsTriggerCount:
                if self._slowRequestFpsStart is None:
                    self._slowRequestFpsStart = nowTime
        else:
            self._slowRequestFpsCount = 0
            self._slowRequestFpsStart = None

        if captureFps < _kMinCaptureFps:
            self._slowCaptureFpsCount += 1
            if self._slowCaptureFpsCount >= _kFpsTriggerCount:
                if self._slowCaptureFpsStart is None:
                    self._slowCaptureFpsStart = nowTime
        else:
            self._slowCaptureFpsCount = 0
            self._slowCaptureFpsStart = None

        if logger and ( self._slowRequestFpsCount > 0 or self._slowCaptureFpsCount > 0 ):
            if nowTime - self._lastWarningTime > _kMinWarningDistance or \
                requestFps < self._lastWarningReqFps or \
                captureFps < self._lastWarningCapFps:
                durReq = 0 if self._slowRequestFpsStart is None else (nowTime - self._slowRequestFpsStart)
                durCap = 0 if self._slowCaptureFpsStart is None else (nowTime - self._slowCaptureFpsStart)
                logger.warning( "%s: requestFps=%.2f(%d, %.2fs) captureFps=%.2f(%d, %.2fs) (%d warnings skipped)" % (self._camLoc, requestFps, self._slowRequestFpsCount, durReq, captureFps, self._slowCaptureFpsCount, durCap, self._warningsSkipped))
                self._lastWarningCapFps = captureFps
                self._lastWarningReqFps = requestFps
                self._lastWarningTime = nowTime
                self._warningsSkipped = 0
            else:
                self._warningsSkipped += 1

##############################################################################
def _formatDuration(durationSeconds):
    """Format a duration given in seconds to a pretty string.

    @param  durationSeconds  The duration, in seconds.
    @return prettyStr        A pretty string describing it.
    """
    duration = durationSeconds

    if duration < 1:
        return "%.1f seconds" % duration
    elif duration < 60:
        duration = int(round(duration))
        if duration == 1:
            return "1 second"
        else:
            return "%d seconds" % duration
    duration /= 60

    if duration < 60:
        duration = int(round(duration))
        if duration == 1:
            return "1 minute"
        else:
            return "%d minutes" % duration
    duration /= 60

    duration = int(round(duration))
    if duration == 1:
        return "1 hour"
    return "%d hours" % duration


##############################################################################
class _cameraEnabledModel(AbstractModel):
    """A model updated when cameras are enabled or disabled.

    Listeners will be called with the name of the camera that was updated.
    """
    ###########################################################
    def __init__(self):
        """Create a camera enabled model."""

        super(_cameraEnabledModel, self).__init__()
        self._isEnabledDict = {}


    ###########################################################
    def isEnabled(self, camera):
        """Returns whether the given camera is enabled.

        @param  camera  The camera to check.
        @return enabled  True if the camera is enabled.
        """
        return self._isEnabledDict.get(camera, False)


    ###########################################################
    def enableCamera(self, cameraLocation, enable=True):
        """Mark a camera as enabled or disabled.

        @param  cameraLocation  The location to update.
        @param  enable          True if the camera is enabled; None if the
                                camera has been deleted.
        """
        # Handle cameras that are deleted...
        if enable is None:
            if cameraLocation in self._isEnabledDict:
                del self._isEnabledDict[cameraLocation]
                self.update(cameraLocation)
            return

        # Force to bool type, so we can compare with ==
        enable = bool(enable)

        if enable != self.isEnabled(cameraLocation):
            self._isEnabledDict[cameraLocation] = enable
            self.update(cameraLocation)


##############################################################################

if __name__ == '__main__':
    from FrontEndApp import main
    main()
