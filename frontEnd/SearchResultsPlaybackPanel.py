#!/usr/bin/env python
# -*- coding: utf8 -*-

#*****************************************************************************
#
# SearchResultsPlaybackPanel.py
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
import sys
import time
import os
import traceback
import math
from ctypes import CFUNCTYPE, c_int

# Common 3rd-party imports...
from PIL import Image
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from vitaToolbox.image.ImageConversion import convertPilToWxBitmap, convertClipFrameToPIL
from vitaToolbox.wx.BitmapWindow import BitmapWindow
from vitaToolbox.wx.GLCanvasSV import OsCompatibleGLCanvas, GLExceptionSV
from vitaToolbox.wx.BorderImagePanel import BorderImagePanel
from vitaToolbox.wx.HoverBitmapButton import HoverBitmapButton
from vitaToolbox.wx.MovieSlider import MovieSlider
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.RadioPushButton import RadioPushButton
from vitaToolbox.wx.TextSizeUtils import makeFontDefault
from vitaToolbox.wx.ToolbarBitmapTextButton import ToolbarBitmapTextButton
from vitaToolbox.wx.TranslucentStaticText import TranslucentStaticText
from vitaToolbox.wx.BitmapFromFile import bitmapFromFile
from vitaToolbox.sysUtils.TimeUtils import formatTime

# Local imports...
from backEnd.ClipManager import ClipManager
from backEnd.DataManager import DataManager
from appCommon.LicenseUtils import hasPaidEdition
from FrontEndPrefs import getFrontEndPref
from FrontEndPrefs import setFrontEndPref
from SubmitClipDialog import SubmitClipConsentDialog, SubmitClipDetailsDialog
from LicensingHelpers import canImport
from SearchResultsTimelineControl import SearchResultsTimelineControl
from frontEnd.ExportClipsDialog import ExportSingleClipDialog
from frontEnd.ExportClipsDialog import ExportMultipleClipsDialog
from frontEnd.ExportClipsDialog import ExportTimeRangeDialog, kUseFpsLimit, kUseSizeLimit
from frontEnd.ExportClipsProgDialog import ExportClipsProgDialog, ExportProgressDialog
from frontEnd.FrontEndUtils import getUserLocalDataDir
from appCommon.ConfigBitmapWindow import ConfigBitmapWindow
from appCommon.CommonStrings import kOpenSourceVersion

import MenuIds

_ctrlPadding = 4

_kHashMarkWidth = 5

_kMaxFramesToSkip = 8
_kAllowBitmapMode = False
# Once over 8x, we'll switch to keyframe-only playback mode
_kMaxPlaybackSpeed = 8

# We'll try to rewind this many ms from playTime when submitting a bug report...
_kBugReportRewindMs = 30000

# Maximum duration for non-matching clips
_kMaxClipDurationMs = (2 * 60 * 1000)

_kBigClipWarningStr = (
"""The maximum length of a clip that can be exported is two minutes. """
"""A two minute video clip will be created centered around the frame you """
"""are currently viewing."""
)
_kBigClipCaptionStr = "Clip Too Long"

_kTime12Hour = '%I:%M:%S %p'
_kTime24Hour = '%H:%M:%S'

_kMinPlaybackSize = (480, 360)

_kResizeShowFrameThreshold = 620
_kResizeShow2SecThreshold = 720
_kResizeShowSpeedThreshold = 820

DBG_PLAYBACK=False

# Pref to allow hiding the opengl warning on future runs.
_kHideOpenGLPrompt = 'hideOpenGLPrompt'


class SearchResultsPlaybackPanel(BorderImagePanel):
    """Implements a panel for playing back video."""
    ###########################################################
    def __init__(self, parent, logger, backEndClient, dataManager, resultsModel, markupModel):
        """The initializer for SearchResultsPlaybackPanel

        @param  parent         The parent window
        @param  logger         A logger instance.
        @param  backEndClient  A connection to the back end app.
        @param  dataManager    An interface for retrieving video frames
        @param  resultsModel   The SearchResultDataModel to listen to.
        @param  markupModel    A model describing how to markup video frames.
        """
        # Call the base class initializer
        super(SearchResultsPlaybackPanel, self).__init__(
            parent, -1, 'frontEnd/bmps/RaisedPanelBorder.png', 8
        )

        self._logger = logger
        self._backEndClient = backEndClient
        self._dataMgr = dataManager
        self._resultsModel = resultsModel
        self._markupModel = markupModel
        self._tryReinitVideoWindow = True
        self._videoWindow = None

        # Tells us how the previous and next clip buttons should behave
        # depending whether or not the SearchResultsList control sorts the
        # results by ascending or descending order.
        self._isAscending = resultsModel.isSortAscending()

        # Set a size to start with.
        self._minPlaybackSize = _kMinPlaybackSize

        # Keep track of whether we're showing duration or remaining time...
        self._showDuration = False

        self._debugModeModel = wx.GetApp().getDebugModeModel()
        self._debugModeModel.addListener(self._handleDebugModeChange)

        # Listen to our results model...
        self._resultsModel.addListener(self._handleResultsChange,
                                       False, 'results')
        self._resultsModel.addListener(self._handleVideoSegmentChange,
                                       False, 'videoSegment')
        self._resultsModel.addListener(self._handleVideoLoaded,
                                       False, 'videoLoaded')
        self._resultsModel.addListener(self._handlePlayOrPause,
                                       False, 'play')
        self._resultsModel.addListener(self._handlePlayOrPause,
                                       False, 'changingRapidly')
        self._resultsModel.addListener(self._handleMsChange,
                                       False, 'ms')
        self._resultsModel.addListener(self._handleMultipleSelected,
                                       False, 'multipleSelected')
        self._resultsModel.addListener(self._handleSortOrderChange,
                                       False, 'sortResults')

        self._markupModel.addListener(self._handlePlayAudio,
                                       False, 'playAudio')

        # Register for time preference changes.
        self.GetTopLevelParent().getUIPrefsDataModel().addListener(
                self._handleTimePrefChange, key='time')
        self._timeStr = _kTime12Hour

        # Variables controlling play state
        self._playTimer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnPlayTimer, self._playTimer)

        self._prevFrameOffset = None

        # Can be set to 0, in which case we'll play keyframes at a set rate
        self._playbackSpeed = 1.0
        self._maxFramesToSkip = _kMaxFramesToSkip

        self._wantContinuousPlayback = False

        # Find our menu items and bind to them...
        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()

        # TODO: This doesn't belong here, really, but it's where we show/hide
        # everything else, so we'll put it here for now...
        toolsMenu = menuBar.GetMenu(menuBar.FindMenu(MenuIds.kToolsMenu))
        prevMenuItem = None
        for menuItem in toolsMenu.GetMenuItems():
            itemLabelText = menuItem.GetItemLabelText()
            if itemLabelText == "FTP Status":
                self._ftpStatusMenuItem = menuItem
                self._ftpSeparatorMenuItem = prevMenuItem
            elif itemLabelText == "Arm Cameras...":
                self._armCamerasMenuItem = menuItem
                self._armCamerasSeparatorMenuItem = prevMenuItem
            elif itemLabelText == "Turn Off Cameras":
                self._turnOffCamerasMenuItem = menuItem
            prevMenuItem = menuItem

        self._exportClipMenuItem         = MenuIds.getToolsMenuItem(menuBar, MenuIds.kExportClipMenu)
        self._exportForBugReportMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kExportClipForBugReportMenu)
        self._exportFrameMenuItem        = MenuIds.getToolsMenuItem(menuBar, MenuIds.kExportFrame)
        self._deleteClipMenuItem         = MenuIds.getToolsMenuItem(menuBar, MenuIds.kDeleteClipMenu)
        self._exportForTimeRangeMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kExportAllWithinTimeRangeMenu)
        self._submitClipForAnalysisMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kSubmitClipForAnalysis)
        self._submitClipForAnalysisWithNoteMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kSubmitClipForAnalysisWithNote)

        self._menuItems = [self._deleteClipMenuItem, self._exportClipMenuItem,
                           self._exportForBugReportMenuItem,
                           self._exportFrameMenuItem,  self._exportForTimeRangeMenuItem]

        if self._submitClipForAnalysisMenuItem and self._submitClipForAnalysisWithNoteMenuItem:
            self._menuItems += [ self._submitClipForAnalysisMenuItem,
                           self._submitClipForAnalysisWithNoteMenuItem ]
            topWin.Bind(wx.EVT_MENU, self.OnSubmitClipForAnalysis, self._submitClipForAnalysisMenuItem)
            topWin.Bind(wx.EVT_MENU, self.OnSubmitClipForAnalysisWithNote, self._submitClipForAnalysisWithNoteMenuItem)

        topWin.Bind(wx.EVT_MENU, self.OnExportClip, self._exportClipMenuItem)
        topWin.Bind(wx.EVT_MENU, self.OnExportClip, self._exportForBugReportMenuItem)
        topWin.Bind(wx.EVT_MENU, self.OnExportFrame, self._exportFrameMenuItem)
        topWin.Bind(wx.EVT_MENU, self.OnExportTimeRange, self._exportForTimeRangeMenuItem)

        topWin.Bind(wx.EVT_ACTIVATE, self.OnTopWinActivate)

        # Find the controls menu items we're responsible for enabling.
        self._playMenuItem          = MenuIds.getControlsMenuItem(menuBar, "Play")
        self._prevClipMenuItem      = MenuIds.getControlsMenuItem(menuBar, "Previous Clip")
        self._nextClipMenuItem      = MenuIds.getControlsMenuItem(menuBar, "Next Clip")
        self._firstClipMenuItem     = MenuIds.getControlsMenuItem(menuBar, "Top Clip in List")
        self._lastClipMenuItem      = MenuIds.getControlsMenuItem(menuBar, "Bottom Clip in List")
        self._nextFrameMenuItem     = MenuIds.getControlsMenuItem(menuBar, "Next Frame")
        self._prevFrameMenuItem     = MenuIds.getControlsMenuItem(menuBar, "Previous Frame")
        self._forwardTwoSecsMenuItem= MenuIds.getControlsMenuItem(menuBar, "Forward 2 Seconds")
        self._backTwoSecsMenuItem   = MenuIds.getControlsMenuItem(menuBar, "Backward 2 Seconds")
        self._nextEventMenuItem     = MenuIds.getControlsMenuItem(menuBar, "Next Event in Clip")
        self._prevEventMenuItem     = MenuIds.getControlsMenuItem(menuBar, "Previous Event in Clip")
        self._firstEventMenuItem    = MenuIds.getControlsMenuItem(menuBar, "First Event in Clip")

        self._halfSpeedMenuItem    = MenuIds.getControlsMenuItem(menuBar, "1/2 Speed")
        self._normalSpeedMenuItem  = MenuIds.getControlsMenuItem(menuBar, "1x Speed")
        self._doubleSpeedMenuItem  = MenuIds.getControlsMenuItem(menuBar, "2x Speed")
        self._quadSpeedMenuItem    = MenuIds.getControlsMenuItem(menuBar, "4x Speed")
        self._previewSpeedMenuItem = MenuIds.getControlsMenuItem(menuBar, "16x Speed")
        self._muteAudioMenuItem    = MenuIds.getControlsMenuItem(menuBar, "Mute Audio")

        self._timelineMenuItem = MenuIds.getViewMenuItem(menuBar, "Show Daily Timeline")
        topWin.Bind(wx.EVT_MENU, self.OnTimelineToggle, id=self._timelineMenuItem.GetId())

        topWin.Bind(wx.EVT_MENU, self.OnHalfSpeed, id=self._halfSpeedMenuItem.GetId())
        topWin.Bind(wx.EVT_MENU, self.OnFullSpeed, id=self._normalSpeedMenuItem.GetId())
        topWin.Bind(wx.EVT_MENU, self.OnDoubleSpeed, id=self._doubleSpeedMenuItem.GetId())
        topWin.Bind(wx.EVT_MENU, self.OnQuadSpeed, id=self._quadSpeedMenuItem.GetId())
        topWin.Bind(wx.EVT_MENU, self.OnPreviewSpeed, id=self._previewSpeedMenuItem.GetId())

        self._timelineMenuItem.Check(getFrontEndPref('showDailyTimeline'))

        self._initUiWidgets()

        # Make sure we're up to date w/ debug mode...
        self._handleDebugModeChange(self._debugModeModel)

        self._cumulativeError = 0
        self._droppedFrames = 0
        self._skippingFrames = False

        PROGFUNC = CFUNCTYPE(c_int, c_int)
        self._progressFn = PROGFUNC(self.OnExportProgress)
        self._progressDlg = None

        # Get called after everything else is setup (and menu is there) to
        # make sure we're showing the right stuff...
        wx.CallAfter(self._showHideMenuItems)

    ###########################################################
    def _initVideoWindow(self):
        # The video window
        if not self._tryReinitVideoWindow:
            return False

        videoWindow = None
        bitmapMode = False
        allowReinit = False
        allowBitmap = _kAllowBitmapMode
        try:
            try:
                videoWindow = OsCompatibleGLCanvas(self)
            except GLExceptionSV, e:
                if e.version.startswith("1"):
                    # chances are we're in RDP land ... init as bitmap for now
                    # and try re-init later
                    if self._videoWindow is not None:
                        return False
                    self._logger.info(  "OpenGL v1 detected. Falling back to Bitmap rendering until a context with better GL is available" )
                    allowBitmap = True
                    # Uncomment this if we ever get to a point where GL loading is dynamic in wxPython,
                    # and we can change GL implementation mid-flight
                    # allowReinit = True
                raise
        except:
            if allowBitmap:
                if self._videoWindow is not None:
                    # we're already in bitmap mode, no need to replace with the same
                    return False
                if not allowReinit:
                    self._logger.info( 'Falling back to BitmapWindow mode:' + traceback.format_exc() )
                    # both MonitorView and this class will experience this ...
                    # we only display message box here, to avoid duplicated errors
                    wx.CallAfter(self._showOpenGLDialog)

                bitmapMode = True
                videoWindow = BitmapWindow(self, wx.Bitmap(1, 1), size=_kMinPlaybackSize, scale=True)
            else:
                raise
        videoWindow.SetMinSize(_kMinPlaybackSize)
        videoWindow.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)
        if bitmapMode:
            videoWindow.Bind(wx.EVT_SIZE, self.OnSizeVideoWindow)
            if allowReinit:
                videoWindow.Bind(wx.EVT_SHOW, self.OnVideoWindowShow)
        if self._videoWindow is None:
            self._mainSizer.Add(videoWindow, 1, wx.EXPAND | wx.LEFT | wx.TOP | wx.RIGHT, 20)
        else:
            self._logger.info( "Replacing Bitmap playback control with OpenGL one" )
            self._mainSizer.Replace(self._videoWindow, videoWindow, False)
        self._videoWindow = videoWindow
        self._tryReinitVideoWindow = allowReinit
        self._bitmapMode = bitmapMode
        return True


    ###########################################################
    def _showOpenGLDialog(self):
        # Show a warning that hardware acceleration could not be started
        # unless the user has opted to hide it.
        if getFrontEndPref(_kHideOpenGLPrompt):
            return

        dlg = _openGLWarningDialog(self)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnVideoWindowShow(self, event):
        self._logger.info( "Attempting to re-init video window" )
        self._initVideoWindow()


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""
        self._mainSizer = wx.BoxSizer(wx.VERTICAL)

        self._initVideoWindow()

        # 11:11 pm     ---------V---------     1/11/08
        self._timeText = TranslucentStaticText(self, -1, "",
                                               style=wx.ALIGN_LEFT)
        self._slider = MovieSlider(self, -1, 0, 0, 1)
        self._durationText = TranslucentStaticText(self, -1, "",
                                                   style=wx.ALIGN_RIGHT)
        makeFontDefault(self._timeText, self._durationText)

        prefix = "frontEnd/bmps/win/"
        if wx.Platform == '__WXMAC__':
            prefix = "frontEnd/bmps/mac/"

        # The playback control panel...
        # <-  -2  <|  >  |>  +2  ->
        self._playbackControlPanel = wx.Panel(self, -1,
                style=wx.TAB_TRAVERSAL | wx.BORDER_NONE | wx.TRANSPARENT_WINDOW)
        self._playbackControlPanel.SetBackgroundStyle(kBackgroundStyle)
        self._prevClipButton = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Prev_Clip_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Prev_Clip_Pressed.png',
                              prefix+'PB_Prev_Clip_Disabled.png',
                              prefix+'PB_Prev_Clip_Hover.png')
        self._minus2Button = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Minus2_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Minus2_Pressed.png',
                              prefix+'PB_Minus2_Disabled.png',
                              prefix+'PB_Minus2_Hover.png',
                              True)
        self._frameBackButton = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Frame_Back_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Frame_Back_Pressed.png',
                              prefix+'PB_Frame_Back_Disabled.png',
                              prefix+'PB_Frame_Back_Hover.png',
                              True)
        self._playButton = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Play_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Play_Pressed.png',
                              prefix+'PB_Play_Disabled.png',
                              prefix+'PB_Play_Hover.png')
        self._pauseButton = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Pause_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Pause_Pressed.png',
                              prefix+'PB_Pause_Disabled.png',
                              prefix+'PB_Pause_Hover.png')
        self._pauseButton.Show(False)
        self._frameForwardButton = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Frame_Fwd_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Frame_Fwd_Pressed.png',
                              prefix+'PB_Frame_Fwd_Disabled.png',
                              prefix+'PB_Frame_Fwd_Hover.png',
                              True)
        self._plus2Button = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Plus2_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Plus2_Pressed.png',
                              prefix+'PB_Plus2_Disabled.png',
                              prefix+'PB_Plus2_Hover.png',
                              True)
        self._nextClipButton = \
            HoverBitmapButton(self._playbackControlPanel, wx.ID_ANY,
                              prefix+'PB_Next_Clip_Enabled.png',
                              wx.EmptyString,
                              prefix+'PB_Next_Clip_Pressed.png',
                              prefix+'PB_Next_Clip_Disabled.png',
                              prefix+'PB_Next_Clip_Hover.png')
        self._updateNavigationControls()

        # Speed toggle buttons; use min size so large fonts will work...
        self._halfSpeedButton = RadioPushButton(self, u"½x")
        self._halfSpeedButton.SetMinSize((24, 20))
        self._fullSpeedButton = RadioPushButton(self, "1x")
        self._fullSpeedButton.SetMinSize((24, 20))
        self._doubleSpeedButton = RadioPushButton(self, "2x")
        self._doubleSpeedButton.SetMinSize((24, 20))
        self._quadSpeedButton = RadioPushButton(self, "4x")
        self._quadSpeedButton.SetMinSize((24, 20))
        self._previewSpeedButton = RadioPushButton(self, "16x" )
        self._previewSpeedButton.SetMinSize((24, 20))

        self._fullSpeedButton.SetValue(1)

        # Load bitmaps for the audio control...
        self._audioButtonOnBmps = (
            bitmapFromFile("frontEnd/bmps/Sound_On_Enabled.png"),
            bitmapFromFile("frontEnd/bmps/Sound_On_Pressed.png"),
            bitmapFromFile("frontEnd/bmps/Sound_On_Disabled.png"),
            bitmapFromFile("frontEnd/bmps/Sound_On_Hover.png"),
        )
        self._audioButtonOffBmps = (
            bitmapFromFile("frontEnd/bmps/Sound_Off_Enabled.png"),
            bitmapFromFile("frontEnd/bmps/Sound_Off_Pressed.png"),
            bitmapFromFile("frontEnd/bmps/Sound_Off_Disabled.png"),
            bitmapFromFile("frontEnd/bmps/Sound_Off_Hover.png"),
        )

        for bmp in self._audioButtonOnBmps + self._audioButtonOffBmps:
            assert bmp.IsOk()

        self._audioButton = HoverBitmapButton(
            self, wx.ID_ANY, self._audioButtonOnBmps[0], wx.EmptyString, None,
            None, None, False, False, wx.DefaultPosition, wx.DefaultSize, False,
            "AudioButton",
        )
        self._updateAudioControls()
        self._handlePlayAudio(self._markupModel)

        # The timeline...
        self._timelineControl = \
            SearchResultsTimelineControl(self, self._resultsModel)

        # Throw stuff in sizers...

        # ...the video window.
        self._mainSizer.AddSpacer(12)

        # |<  <|  >  |>  >|
        playPauseSizer = OverlapSizer(True)
        playPauseSizer.Add(self._playButton)
        playPauseSizer.Add(self._pauseButton)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self._prevClipButton, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._minus2Button, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)
        hSizer.Add(self._frameBackButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)
        hSizer.Add(playPauseSizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)
        hSizer.Add(self._frameForwardButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)
        hSizer.Add(self._plus2Button, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)
        hSizer.Add(self._nextClipButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)

        self._playbackControlPanel.SetSizer(hSizer)

        # |<  <|  >  |>  >| 1/2x 1x 2x 3x  11:11 pm  ---------V---------  -5:12  <))
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self._playbackControlPanel, 0, wx.ALL | wx.ALIGN_CENTER,
                _ctrlPadding)
        hSizer.Add(self._halfSpeedButton, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._fullSpeedButton, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._doubleSpeedButton, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._quadSpeedButton, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._previewSpeedButton, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._timeText, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        hSizer.Add(self._slider, 1, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._durationText, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._audioButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        self._mainSizer.AddSpacer(_ctrlPadding)
        self._mainSizer.Add(hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 16)

        # Need to hide all possible controls now for min size calculations
        self._minus2Button.Hide()
        self._frameBackButton.Hide()
        self._frameForwardButton.Hide()
        self._plus2Button.Hide()
        self._halfSpeedButton.Hide()
        self._fullSpeedButton.Hide()
        self._doubleSpeedButton.Hide()
        self._quadSpeedButton.Hide()
        self._previewSpeedButton.Hide()

        # Disable the audio control, since there won't be video loaded yet.
        self._audioButton.Disable()

        # Timeline control...
        self._mainSizer.AddSpacer(_ctrlPadding * 3)
        self._mainSizer.Add(self._timelineControl, 0, wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, 16)
        self._mainSizer.AddSpacer(_ctrlPadding)

        # Add a border sizer so we're top aligned inside the non-shadowed area...
        borderSizer = wx.BoxSizer(wx.VERTICAL)

        borderSizer.Add(self._mainSizer, 1, wx.EXPAND | wx.BOTTOM | wx.RIGHT, 4)

        # ...set the sizer...
        self.SetSizer(borderSizer)

        # This bind is necessary for the video window to scale properly.
        # Refer to self.OnSize() for more details.
        self.Bind(wx.EVT_SIZE, self.OnSize)

        # Bind to events
        self._slider.Bind(wx.EVT_SLIDER, self.OnSlider)

        self._durationText.Bind(wx.EVT_LEFT_DOWN, self.OnDurationClick)
        self._durationText.Bind(wx.EVT_LEFT_DCLICK, self.OnDurationClick)

        self._prevClipButton.Bind(wx.EVT_BUTTON, self.OnPrevClip)
        self._minus2Button.Bind(wx.EVT_BUTTON, self.OnMinus2)
        self._frameBackButton.Bind(wx.EVT_BUTTON, self.OnFrameBack)
        self._playButton.Bind(wx.EVT_BUTTON, self.OnPlayOrPauseButton)
        self._pauseButton.Bind(wx.EVT_BUTTON, self.OnPlayOrPauseButton)
        self._frameForwardButton.Bind(wx.EVT_BUTTON, self.OnFrameForward)
        self._plus2Button.Bind(wx.EVT_BUTTON, self.OnPlus2)
        self._nextClipButton.Bind(wx.EVT_BUTTON, self.OnNextClip)

        self._halfSpeedButton.Bind(wx.EVT_RADIOBUTTON, self.OnHalfSpeed)
        self._fullSpeedButton.Bind(wx.EVT_RADIOBUTTON, self.OnFullSpeed)
        self._doubleSpeedButton.Bind(wx.EVT_RADIOBUTTON, self.OnDoubleSpeed)
        self._quadSpeedButton.Bind(wx.EVT_RADIOBUTTON, self.OnQuadSpeed)
        self._previewSpeedButton.Bind(wx.EVT_RADIOBUTTON, self.OnPreviewSpeed)

        self._audioButton.Bind(wx.EVT_BUTTON, self.OnAudioButton)

        self.OnTimelineToggle()


    ###########################################################
    def OnSize(self, event):
        """Show or hide the playback buttons depending on how much space is
        available on the screen.

        @param event                   The size event.

        Note:  This function can be called with None passed into it if
        resizing is needed, but you don't want to wait for a resize.
        """

        # Get the current window size.
        (clientWidth, _) = self.GetClientSize()

        # Show and hide any buttons as necessary.
        self._frameBackButton.Show(clientWidth >= _kResizeShowFrameThreshold)
        self._frameForwardButton.Show(clientWidth >= _kResizeShowFrameThreshold)
        self._minus2Button.Show(clientWidth >= _kResizeShow2SecThreshold)
        self._plus2Button.Show(clientWidth >= _kResizeShow2SecThreshold)
        self._halfSpeedButton.Show(clientWidth >= _kResizeShowSpeedThreshold)
        self._fullSpeedButton.Show(clientWidth >= _kResizeShowSpeedThreshold)
        self._doubleSpeedButton.Show(clientWidth >= _kResizeShowSpeedThreshold)
        self._quadSpeedButton.Show(clientWidth >= _kResizeShowSpeedThreshold)
        self._previewSpeedButton.Show(clientWidth >= _kResizeShowSpeedThreshold)

        # Allow the size event to skip
        if event:
            event.Skip()


    ###########################################################
    def OnSizeVideoWindow(self, event):
        """Rescale and redraw boxes onto the current (if paused) or next
        (if playing) frame so that boxes are drawn properly.  If we don't do
        this, boxes might be missing, or their borders might be too thick from
        rescaling already-drawn frames.

        @param event                   The size event.

        Note:  This function can be called with None passed into it if
        resizing is needed, but you don't want to wait for a resize.
        """
        # Tell the data manager that we want it to scale its images,
        # and then draw on them.
        self._resultsModel.setVideoSize(
            self._videoWindow.GetDesiredFrameSize()
        )

        # The cached image in the results model already has bounding boxes drawn on it.
        # So we need to reload the current frame in order to have the correct image
        # with bounding boxes drawn on it.
        self._resultsModel.reloadCurrentFrame()

        # Allow the size event to skip
        if event:
            event.Skip()


    ###########################################################
    def _handleSortOrderChange(self, resultsModel=None):
        """Update next clip / prev clip controls to match the data model and
        the new sort order from the SearchResultsList control.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel
        if self._isAscending != self._resultsModel.isSortAscending():
            self._isAscending = self._resultsModel.isSortAscending()
            self._updateClipControls()


    ###########################################################
    def _updateClipControls(self):
        """Update next clip / prev clip controls to match the data model."""
        numMatchingClips = self._resultsModel.getNumMatchingClips()
        if numMatchingClips == 0:
            self._prevClipButton.Enable(False)
            self._nextClipButton.Enable(False)
            self._prevClipMenuItem.Enable(False)
            self._nextClipMenuItem.Enable(False)
            self._firstClipMenuItem.Enable(False)
            self._lastClipMenuItem.Enable(False)
        else:
            clipNum = self._resultsModel.getCurrentClipNum()

            if self._isAscending:
                prevClipButtonDoEnable = clipNum > 0
                nextClipButtonDoEnable = clipNum < (numMatchingClips-1)
            else:
                prevClipButtonDoEnable = clipNum < (numMatchingClips-1)
                nextClipButtonDoEnable = clipNum > 0

            self._prevClipButton.Enable(prevClipButtonDoEnable)
            self._prevClipMenuItem.Enable(prevClipButtonDoEnable)
            self._firstClipMenuItem.Enable(prevClipButtonDoEnable)
            self._nextClipButton.Enable(nextClipButtonDoEnable)
            self._nextClipMenuItem.Enable(nextClipButtonDoEnable)
            self._lastClipMenuItem.Enable(nextClipButtonDoEnable)


    ###########################################################
    def _updateNavigationControls(self):
        """Enable or disable the video navigation controls.

        They will be disabled if video is not loaded and usually enabled if
        video is loaded (depending on where we are in the video).
        """
        isLoaded = self._resultsModel.isVideoLoaded()
        relativeMs = self._resultsModel.getCurrentRelativeMs()
        lastMs = self._resultsModel.getCurrentClipDuration()-1

        # Compute whether we can move forward or backward; note that short-
        # circuiting should prevent the (relatively slow) "canPassClipBeginning"
        # and "canPassClipEnd" from running most of the time...
        canMoveBackward = ((isLoaded)                                       and
                           ((relativeMs != 0)                           or
                            (self._resultsModel.canPassClipBeginning())   )    )
        canMoveForward = ((isLoaded)                                and
                          ((relativeMs < lastMs)                 or
                           (self._resultsModel.canPassClipEnd())   )    )

        self._slider.Enable(isLoaded)
        self._minus2Button.Enable(isLoaded and canMoveBackward)
        self._backTwoSecsMenuItem.Enable(isLoaded and canMoveBackward)
        self._frameBackButton.Enable(isLoaded and canMoveBackward)
        self._prevFrameMenuItem.Enable(isLoaded and canMoveBackward)
        self._playButton.Enable(isLoaded and ((relativeMs < lastMs) or
                                               self._continuousPlayAvailable()))
        self._pauseButton.Enable(isLoaded)
        self._playMenuItem.Enable((self._playButton.IsShown() and
                                   self._playButton.IsEnabled()) or
                                  (self._pauseButton.IsShown() and
                                   self._pauseButton.IsEnabled()))
        self._frameForwardButton.Enable(isLoaded and canMoveForward)
        self._nextFrameMenuItem.Enable(isLoaded and canMoveForward)
        self._plus2Button.Enable(isLoaded and canMoveForward)
        self._forwardTwoSecsMenuItem.Enable(isLoaded and canMoveForward)
        self._firstEventMenuItem.Enable(isLoaded and relativeMs > 0)
        self._prevEventMenuItem.Enable(isLoaded and relativeMs > 0)
        self._nextEventMenuItem.Enable(isLoaded and relativeMs < lastMs)


    ###########################################################
    def _updateAudioControls(self):
        """Enable or disable the audio controls.

        They will be disabled if video is not loaded and usually enabled if
        video is loaded.
        """
        isLoaded = self._resultsModel.isVideoLoaded()
        hasAudio = self._resultsModel.hasAudio()

        self._audioButton.Enable(isLoaded and hasAudio)
        self._muteAudioMenuItem.Enable(isLoaded and hasAudio)


    ###########################################################
    def _updatePlayButton(self):
        """Toggle the graphic displayed on the play button.

        It will be updated to match self._resultsModel.
        """
        play = self._resultsModel.isPlaying()

        if not play and self._continuousPlayAvailable():
            self._playButton.Enable(True)

        self._playButton.Show(not play)
        self._pauseButton.Show(play)
        self._playMenuItem.Enable((self._playButton.IsShown() and
                                   self._playButton.IsEnabled()) or
                                  (self._pauseButton.IsShown() and
                                   self._pauseButton.IsEnabled()))


    ###########################################################
    def _continuousPlayAvailable(self):
        """Determine if continuous play is available.

        @return avail  True if we are paused at the end of a video with
                       more cache or clips available.
        """
        if not self._resultsModel.isPlaying():
            relativeMs = self._resultsModel.getCurrentRelativeMs()
            lastMs = self._resultsModel.getCurrentClipDuration()-1

            return (self._resultsModel.isVideoLoaded() and
                    relativeMs == lastMs and
                    self._resultsModel.canPassClipEnd(False))
        return False


    ###########################################################
    def _resetControls(self):
        """Reset the controls to a blank state"""
        self._updatePlayButton()
        self._updateNavigationControls()
        self._updateAudioControls()
        self._updateClipControls()

        self._setEmptyTimeText()
        self.Layout()

        self._resetVideoImage( Image.new( 'RGB', self._minPlaybackSize ))


    ###########################################################
    def _resetVideoImage( self, img ):
        """Reset the UI to a non video frame

        @param  img  A PIL image representing the new frame
        """
        if self._bitmapMode:
            bmp = convertPilToWxBitmap( img )
        else:
            bmp = img
        self._videoWindow.updateBitmap( bmp )


    ###########################################################
    def _updateVideoImage(self, img):
        """Update the UI to reflect a new video frame

        @param  img  A ClipReader frame image representing the new frame
        """
        if self._skippingFrames:
            return

        if self._bitmapMode:
            self._videoWindow.updateBitmap(img.asWxBuffer())
        else:
            self._videoWindow.updateImageData( img )


    ###########################################################
    #def _getFps(self):
    #    """Return the current instantaneous frames per second.
    #
    #    Note: not very accurate...
    #
    #    @return fps  The frames per second.
    #    """
    #    prevOffset = self._dataMgr.getPrevFrameOffset()
    #    currOffset = self._dataMgr.getCurFrameOffset()
    #    nextOffset = self._dataMgr.getNextFrameOffset()
    #
    #    # Try to use (next - prev), which should be 2 frames worth.  If not,
    #    # just use 1 frame worth.  Note: also need to convert ms to seconds.
    #    if prevOffset != -1:
    #        if nextOffset != -1:
    #            return 2000.0 / (nextOffset - prevOffset)
    #        else:
    #            return 1000.0 / (currOffset - prevOffset)
    #    else:
    #        return 1000.0 / (nextOffset - currOffset)


    ###########################################################
    def _updateDateAndTimeText(self):
        """Update the date and time text beneath the video frame"""
        absoluteMs = self._resultsModel.getCurrentAbsoluteMs()

        # Handle case if this gets called when no video loaded, like when
        # we switch into debug mode when not looking at a video.
        if absoluteMs is None:
            self._setEmptyTimeText()
            return

        if self._resultsModel.getMidnightMs() is None:
            # Show the time from the start of the current clip...
            ms = self._resultsModel.getCurrentFileRelativeMs()

            # Show the time text...
            seconds, ms = divmod(ms, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            timeText = "%02d:%02d:%02d" % (hours, minutes, seconds)
        else:
            # Show real time...
            seconds, ms = divmod(absoluteMs, 1000)
            timeStruct = time.localtime(seconds)

            if self._debugModeModel.isDebugMode():
                timeText = formatTime(_kTime24Hour, timeStruct)
            else:
                timeText = formatTime(self._timeStr, timeStruct).swapcase()
                if timeText[0] == '0':
                    timeText = timeText[1:]

        if self._debugModeModel.isDebugMode():
            timeText += (".%02d" % (ms // 10))

        self._timeText.SetLabel(timeText)

        duration = self._resultsModel.getCurrentClipDuration()
        if self._showDuration:
            durationText = ""
            seconds = int(round(duration / 1000))
        else:
            durationText = "-"
            timeLeft = duration - self._resultsModel.getCurrentRelativeMs()
            seconds = int(round(timeLeft / 1000))
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        if hours:
            durationText += "%d:%02d:%02d" % (hours, minutes, seconds)
        else:
            durationText += "%d:%02d" % (minutes, seconds)

        self._durationText.SetLabel(durationText)

        # Make sure that our best size is never over our min size; if it is
        # then we need to do a (somewhat slow) layout.
        # (Don't mind me, I'm just being paranoid)...
        for ctrl in (self._timeText, self._durationText):
            bestWidth, _ = ctrl.GetBestSize()
            minWidth, _ = ctrl.GetMinSize()
            if bestWidth > minWidth:
                ctrl.SetMinSize((bestWidth, -1))
                self.Layout()


    ###########################################################
    def OnTopWinActivate(self, event):
        """Handles activate / deactivate of our top-level window.

        @param  event  The event.
        """
        # Never eat these!  Others may care about them...
        event.Skip()

        # If our window is becoming active, update UI for settings that may
        # have been changed by another top-level window.
        if event.GetActive():
            self._showHideMenuItems()


    ###########################################################
    def _showHideMenuItems(self):
        """Show an hide menu items managed by us."""
        topWin = self.GetTopLevelParent()
        toolbar = topWin.GetToolBar()
        menuBar = topWin.GetMenuBar()

        paid = False
        try:
            paid = hasPaidEdition(self._backEndClient.getLicenseData())
        except:
            # This can be called when we are shutting down and have requested
            # the back end to exit. Catch exceptions, default paid to False.
            pass

        if paid:
            if self._ftpStatusMenuItem.GetMenu() is None:
                toolsMenu = menuBar.GetMenu(menuBar.FindMenu("Tools"))

                # Hardcoding that we're 2 from the bottom (except on Mac) for
                # simplicity.
                if wx.Platform == '__WXMAC__':
                    # Options moves on Mac.  ICK!
                    insertLoc = toolsMenu.GetMenuItemCount()
                else:
                    # Need to account for Options menu on Windows.  ICK!
                    insertLoc = toolsMenu.GetMenuItemCount()-2
                toolsMenu.InsertItem(insertLoc, self._ftpStatusMenuItem)
                toolsMenu.InsertItem(insertLoc, self._ftpSeparatorMenuItem)
        else:
            if self._ftpStatusMenuItem.GetMenu() is not None:
                toolsMenu = menuBar.GetMenu(menuBar.FindMenu("Tools"))
                toolsMenu.Remove(self._ftpStatusMenuItem)
                toolsMenu.Remove(self._ftpSeparatorMenuItem)

        # MUST BE AFTER FTP, since we are hardcoding positions...
        if paid:
            if self._armCamerasMenuItem.GetMenu() is None:
                toolsMenu = menuBar.GetMenu(menuBar.FindMenu("Tools"))

                assert self._ftpStatusMenuItem.GetMenu() is not None, \
                       "FTP Status must be there for placement to be right"

                # Hardcoding that we're 4 from the bottom (except on Mac) for
                # simplicity.
                if wx.Platform == '__WXMAC__':
                    # Options moves on Mac.  ICK!
                    insertLoc = toolsMenu.GetMenuItemCount()-2
                else:
                    # Need to account for Options menu on Windows.  ICK!
                    insertLoc = toolsMenu.GetMenuItemCount()-4
                toolsMenu.InsertItem(insertLoc, self._turnOffCamerasMenuItem)
                toolsMenu.InsertItem(insertLoc, self._armCamerasMenuItem)
                toolsMenu.InsertItem(insertLoc, self._armCamerasSeparatorMenuItem)

            if toolbar.FindById(self._armCamerasMenuItem.GetId()) is None:
                arm = ToolbarBitmapTextButton(toolbar, self._armCamerasMenuItem.GetId(),
                        wx.Bitmap("frontEnd/bmps/Toolbar_Arm_MouseUp.png"),
                        "Arm Cameras")
                arm.SetBitmapSelected(wx.Bitmap(
                        "frontEnd/bmps/Toolbar_Arm_MouseDown.png"))
                disarm = ToolbarBitmapTextButton(toolbar, self._turnOffCamerasMenuItem.GetId(),
                        wx.Bitmap("frontEnd/bmps/Toolbar_AllOff_MouseUp.png"),
                        "Turn Off Cameras")
                disarm.SetBitmapSelected(wx.Bitmap(
                        "frontEnd/bmps/Toolbar_AllOff_MouseDown.png"))
                toolbar.InsertControl(1, arm)
                toolbar.InsertControl(2, disarm)
                toolbar.Realize()

                # On arm/disarm click simply call the assocaited menu item.
                def callMenuItem(event):
                    try:
                        wx.PostEvent(event.GetEventObject().GetEventHandler(),
                            wx.CommandEvent(wx.EVT_MENU.typeId, event.GetId()))
                    except Exception, e:
                        self._logger.error("Exception calling menu: " + str(e))

                arm.Bind(wx.EVT_BUTTON, callMenuItem)
                disarm.Bind(wx.EVT_BUTTON, callMenuItem)

        else:
            if self._armCamerasMenuItem.GetMenu() is not None:
                toolsMenu = menuBar.GetMenu(menuBar.FindMenu("Tools"))
                toolsMenu.Remove(self._armCamerasMenuItem)
                toolsMenu.Remove(self._turnOffCamerasMenuItem)
                toolsMenu.Remove(self._armCamerasSeparatorMenuItem)

            if toolbar.FindById(self._armCamerasMenuItem.GetId()) is not None:
                toolbar.DeleteTool(self._armCamerasMenuItem.GetId())
                toolbar.DeleteTool(self._turnOffCamerasMenuItem.GetId())



    ###########################################################
    def OnSlider(self, event):
        """Navigate in the video to reflect the current slider position

        @param  event  The event.
        """
        # Enable changingRapidly before changing the time so we make sure we
        # don't start the play timer...
        if event.isPressed():
            self._resultsModel.setChangingRapidly(True)

        self._resultsModel.setCurrentRelativeMs(self._slider.GetValue())

        # Disable changingRapidly after changing the time so that we don't
        # start playing the wrong time...
        if not event.isPressed():
            self._resultsModel.setChangingRapidly(False)

        # Make sure that the video updates right away...
        self._videoWindow.Update()


    ###########################################################
    def OnDurationClick(self, event=None):
        """Handle clicks on the duration / remaining time label.

        We'll swap between duration and remaining time when this happens.

        @param  event  The event, ignored
        """
        self._showDuration = not self._showDuration
        self._updateDateAndTimeText()


    ###########################################################
    def OnMinus2(self, event=None):
        """Move the video back 2 seconds.

        @param  event  The event, ignored
        """
        self._resultsModel.goBackwardXMs(2000)


    ###########################################################
    def OnFrameBack(self, event=None):
        """Move the video back one frame

        @param  event  The event, ignored
        """
        relativeMs = self._resultsModel.getCurrentRelativeMs()

        self._resultsModel.setPlay(False)
        if relativeMs > 0:
            self._resultsModel.goToPrevFrame()
        else:
            didMove = self._resultsModel.passClipBeginning()
            assert didMove


    ###########################################################
    def OnPrevClip(self, event=None):
        """Skip to previous clip.

        @param  event  The event, ignored
        """
        if self._isAscending:
            self._resultsModel.goToPrevClip()
        else:
            self._resultsModel.goToNextClip()


    ###########################################################
    def OnPlayOrPauseButton(self, event=None):
        """Play the video

        @param  event  The event, ignored
        """
        playing = self._resultsModel.isPlaying()

        if not playing and self._continuousPlayAvailable():
            self._resultsModel.passClipEnd(False, False)

        self._resultsModel.setPlay(not playing)


    ###########################################################
    def handleSpaceBar(self):
        """Play or pause if in a situation to do so."""
        if (self._playButton.IsEnabled() and self._playButton.IsShown()) or \
           (self._pauseButton.IsEnabled() and self._pauseButton.IsShown()):
            self.OnPlayOrPauseButton()


    ###########################################################
    def _handlePlayOrPause(self, resultsModel):
        """Handle a request to play or pause.

        ...also gets called whenever 'changingRapidly' changes.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        self._updatePlayButton()
        self._dataMgr.setMute(self._shouldMute())

        self._prevFrameOffset = None
        if (self._resultsModel.isPlaying()) and \
           (not self._resultsModel.isChangingRapidly()):
            self._startTimer(1)


    ###########################################################
    def _handleResultsChange(self, resultsModel):
        """Handle when the search results change.

        We'll just reset our UI until a clip gets loaded.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        self._resetControls()
        self._updateClipControls()

        # Disable export menu items until clip is fully loaded...
        self.enableMenuItems(False)


    ###########################################################
    def _handleVideoSegmentChange(self, resultsModel):
        """Handle when the chosen video segment changes.

        Note: we do most of our work when we the video gets loaded, but do
        a little bit here too...

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel
        self._updateClipControls()

        # Disable export menu items until clip is fully loaded...
        self.enableMenuItems(False)


    ###########################################################
    def _handleVideoLoaded(self, resultsModel):
        """Handle when a video finishes loading.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        clipDuration = self._resultsModel.getCurrentClipDuration()

        self._updatePlayButton()
        self._updateNavigationControls()
        self._updateAudioControls()

        # Update the slider to reflect the range of the video
        self._slider.SetRange(0, (clipDuration-1))

        # Set hash marks as start times...
        startTimes = self._resultsModel.getStartTimes()
        specialList = [(startTime, -_kHashMarkWidth)
                       for startTime in startTimes]
        self._slider.SetSpecialRanges(specialList)

        # Set the title
        if self._debugModeModel.isDebugMode() and \
           self._resultsModel.isVideoLoaded():
            self.GetTopLevelParent().SetTitle(self._dataMgr.getCurFilename())
        else:
            self.GetTopLevelParent().SetTitle(None)

        self._updateVideoUi()

        # Handle any autoplay...
        self._handlePlayOrPause(resultsModel)

        # Enable menu items...
        if self._resultsModel.isVideoLoaded():
            self.enableMenuItems(True)
        else:
            self.enableDeleteIfPossible()
            self.enableExportIfPossible()


    ###########################################################
    def _handleMsChange(self, resultsModel):
        """Handle when the clip changes.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel
        self._updateVideoUi()

        self._prevFrameOffset = None

    ###########################################################
    def _startTimer(self, delayTime):
        self._playTimer.Start(delayTime, True)
        self._expectedTimerTime = time.time()*1000 + delayTime
        return True

    ###########################################################
    def _dbgPlayback(self,str):
        print "Playback:" + str
        pass

    ###########################################################
    def OnPlayTimer(self, event=None):
        """Show the next frame in the video and set the next timer

        @param  event  The timer event, ignored
        """
        if DBG_PLAYBACK: self._dbgPlayback(  "timer event ... current error is " + str(self._cumulativeError) )

        if (not self._resultsModel.isPlaying()) or \
           (self._resultsModel.isChangingRapidly()) or \
           (not self._resultsModel.isVideoLoaded()):
            if DBG_PLAYBACK: self._dbgPlayback( "Not renewing timer: isPlaying=" + str(self._resultsModel.isPlaying()) + \
                            " isChangingRapidly=" + str(self._resultsModel.isChangingRapidly()) + \
                            " isVideoLoaded=" + str(self._resultsModel.isVideoLoaded()) )
            self._cumulativeError = 0
            return

        # Re-run in a little bit if we're not supposed to be animating
        if not self.GetTopLevelParent().shouldAnimateChild(self):
            self._startTimer(200)
            self._cumulativeError = 0
            return

        self._cumulativeError = self._cumulativeError + \
                        (time.time()*1000 - self._expectedTimerTime)

        try:
            timerSet = False
            while not timerSet:
                # Capture the time at the start of the function
                processTimeBase = time.time()
                if not self._prevFrameOffset:
                    prevFrameOffset = self._dataMgr.getCurFrameOffset()
                else:
                    prevFrameOffset = self._prevFrameOffset

                # Tell the model to switch to the next frame...
                start = time.time()
                self._resultsModel.goToNextFrame()
                if not self._resultsModel.isPlaying():
                    if self._wantContinuousPlayback:
                        self._resultsModel.goToNextClip()
                    return
                if DBG_PLAYBACK: self._dbgPlayback( "getting new frame took " + str(int(1000*(time.time()-start))) )

                # Calculate when the next frame should be shown and how much time
                # we spent in processing
                nextFrameOffset = self._resultsModel.getNextRelativeMs()
                assert nextFrameOffset != -1, "Should have stopped playing"
                frameSeparation = nextFrameOffset-prevFrameOffset
                frameSeparationSpeedAdjusted = frameSeparation / self._playbackSpeed if self._playbackSpeed != 0 else 0

                processingTime = (time.time()-processTimeBase)*1000
                self._cumulativeError = self._cumulativeError + processingTime

                # Set a timer to show the next frame
                if frameSeparationSpeedAdjusted > self._cumulativeError or \
                   self._droppedFrames >= self._maxFramesToSkip or \
                   self._playbackSpeed == 0:
                    # we need to have at least 1ms separation to the next timer
                    if self._playbackSpeed == 0:
                        delayTime = 50 # is it okay to hardcode ?
                        self._cumulativeError = 0
                    elif frameSeparationSpeedAdjusted > self._cumulativeError + 1:
                        delayTime = frameSeparationSpeedAdjusted - self._cumulativeError
                        self._cumulativeError = 0
                    else:
                        # frame will be played back without any correction to the current delay, to avoid skipping too many frames in a row:
                        # - we're still behind as much as before
                        # - we're not going to accelerate display of the next frame more than the separation value, to not compound on the delay
                        #   that already exists
                        delayTime = frameSeparationSpeedAdjusted

                    # Just a safety check, in case frame separation is too small
                    if delayTime < 1:
                        if DBG_PLAYBACK: self._dbgPlayback( "delayTime=" + str(delayTime) + \
                                            " frameSeparationSpeedAdjusted=" + str(frameSeparationSpeedAdjusted) + \
                                            " cumulativeError=" + str(self._cumulativeError) )
                        delayTime = 1

                    timerSet = self._startTimer(delayTime)
                    # we can drop more frames if needed
                    self._droppedFrames = 0
                    if DBG_PLAYBACK: self._dbgPlayback( "scheduling timer in " + str(delayTime) + " current error is " + str(self._cumulativeError) )
                else:
                    self._cumulativeError = self._cumulativeError - frameSeparationSpeedAdjusted
                    self._droppedFrames = self._droppedFrames + 1
                    self._skippingFrames = True
                    if DBG_PLAYBACK: self._dbgPlayback( "skipping a frame: currently behind by " + str(self._cumulativeError) )

                self._prevFrameOffset = nextFrameOffset

        except Exception:
            # If we cut off playing while this is executing it can trigger some
            # exceptions, we want to ignore these.  If an exception happens
            # normally, we just want to simulate a pause action.
            if DBG_PLAYBACK: self._dbgPlayback( "exception! " + traceback.format_exc() )
            self._resultsModel.setPlay(False, False)
        finally:
            self._skippingFrames = False


    ###########################################################
    def OnFrameForward(self, event=None):
        """Move the video forward one frame

        @param  event  The event, ignored
        """
        relativeMs = self._resultsModel.getCurrentRelativeMs()
        clipDuration = self._resultsModel.getCurrentClipDuration()

        self._resultsModel.setPlay(False)
        if relativeMs < clipDuration-1:
            self._resultsModel.goToNextFrame()
        else:
            didMove = self._resultsModel.passClipEnd()
            assert didMove


    ###########################################################
    def OnPlus2(self, event=None):
        """Move the video forward 2 seconds.

        @param  event  The event, ignored
        """
        self._resultsModel.goForwardXMs(2000)

    ###########################################################
    def _changeSpeed(self, speed, menu, button):
        self._playbackSpeed = speed

        if self._playbackSpeed != 0:
            speedLog2 = math.log(self._playbackSpeed,2)
            self._maxFramesToSkip = _kMaxFramesToSkip*(speedLog2+1) if speedLog2 > 0 else _kMaxFramesToSkip/2

        menu.Check()
        button.SetValue(1)
        self._dataMgr.setMute( True )
        self._markupModel.setKeyframeOnlyPlayback( self._playbackSpeed > _kMaxPlaybackSpeed or \
                    self._playbackSpeed == 0 )

    ###########################################################
    def OnHalfSpeed(self, event=None):
        """Switch to half speed."""
        self._changeSpeed(.5, self._halfSpeedMenuItem, self._halfSpeedButton)

    ###########################################################
    def OnFullSpeed(self, event=None):
        """Switch to full speed."""
        self._changeSpeed(1.0, self._normalSpeedMenuItem, self._fullSpeedButton)

    ###########################################################
    def OnDoubleSpeed(self, event=None):
        """Switch to double speed."""
        self._changeSpeed(2.0, self._doubleSpeedMenuItem, self._doubleSpeedButton)

    ###########################################################
    def OnQuadSpeed(self, event=None):
        """Switch to quad speed."""
        self._changeSpeed(4.0, self._quadSpeedMenuItem, self._quadSpeedButton)

    ###########################################################
    def OnPreviewSpeed(self, event=None):
        """Switch to preview speed."""
        self._changeSpeed(16.0, self._previewSpeedMenuItem, self._previewSpeedButton)

    ###########################################################
    def OnNextClip(self, event=None):
        """Skip to the next clip.

        @param  event  The event, ignored
        """
        if self._isAscending:
            self._resultsModel.goToNextClip()
        else:
            self._resultsModel.goToPrevClip()


    ###########################################################
    def OnAudioButton(self, event=None):
        """Toggle audio playback.

        @param  event  The event, ignored
        """
        self._markupModel.setPlayAudio(
            not self._markupModel.getPlayAudio()
        )


    ###########################################################
    def _handlePlayAudio(self, markupModel=None):
        """Handle updating our audio control UI to match the markup data model.

        @param  markupModel  Should be self._markupModel
        """
        assert markupModel == self._markupModel

        isAudioOn = self._markupModel.getPlayAudio()
        bmps = self._audioButtonOnBmps if isAudioOn else self._audioButtonOffBmps

        (bmpEnabled, bmpPressed, bmpDisabled, bmpHover) = bmps

        self._audioButton.SetBitmap(bmpEnabled)
        self._audioButton.SetBitmapPressed(bmpPressed)
        self._audioButton.SetBitmapDisabled(bmpDisabled)
        self._audioButton.SetBitmapCurrent(bmpHover)

        self._dataMgr.setMute(self._shouldMute())


    ###########################################################
    def _shouldMute(self):
        return (
            (not self._markupModel.getPlayAudio()) or
            (not self._resultsModel.isPlaying()) or
            (self._playbackSpeed != 1.0)
        )


    ###########################################################
    def OnShowPopup(self, event):
        """Handle the context menu event.

        @param  event  The event to handle
        """
        # Create our menu.  TODO: Use createMenuFromData() if more items?
        menu = wx.Menu()

        debugOn = self._debugModeModel.isDebugMode()
        if (wx.GetKeyState(wx.WXK_SHIFT) and wx.GetKeyState(wx.WXK_ALT)) or \
           debugOn:
            if debugOn:
                debugMenuItem = menu.Append(-1, "Disable Debug Mode")
            else:
                debugMenuItem = menu.Append(-1, "Enable Debug Mode")
            menu.AppendSeparator()
            self.Bind(wx.EVT_MENU, self.OnShowHideDebugMode, debugMenuItem)
        else:
            debugMenuItem = None

        # Add any currently enabled / attached export-related items...
        # ...note that we should already be bound to them...
        for menuItem in self._menuItems:
            if menuItem.IsEnabled() and (menuItem.GetMenu() is not None):
                menu.Append(menuItem.GetId(), menuItem.GetItemLabel())

        # Popup the menu
        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)
        self.PopupMenu(menu, pos)

        # Unbind.  Not sure if this is necessary, but seems like a good idea.
        if debugMenuItem is not None:
            self.Unbind(wx.EVT_MENU, debugMenuItem)

        # Kill the menu
        menu.Destroy()


    ###########################################################
    def OnShowHideDebugMode(self, event):
        """Handle the "Enable / Disable Debug Mode" menu item.

        @param  event  The event to handle
        """
        wasDebugMode = self._debugModeModel.isDebugMode()
        self._debugModeModel.setDebugMode(not wasDebugMode)


    ############################################################
    def OnTimelineToggle(self, event=None):
        """Hide or show the daily timeline.

        @param  event  The menu event (ignored).
        """
        show = self._timelineMenuItem.IsChecked()
        self._timelineControl.Show(show)
        setFrontEndPref('showDailyTimeline', show)
        if show:
            self._timelineControl.recreateTimeline()

        # Call the OnSize handler as well as we need to do much of the same
        # logic, particularly with the video window.
        self.OnSize(None)


    ###########################################################
    def _getClipExportPath(self):
        """Gets the directory where the last clip was saved to.

        @return: defDir  The path where the last clip was saved.
                         If the path does not exist, an empty
                         string is returned.
        """
        defDir = getFrontEndPref('lastPathExportClip')
        if not os.path.exists(defDir):
            defDir = wx.StandardPaths.Get().GetDocumentsDir()
        if not os.path.exists(defDir):
            defDir = ''
        return defDir


    ###########################################################
    def _setClipExportPath(self, path):
        """Gets the directory where the last clip was saved to.

        @param: path     The default path where clips should be saved.
                         If the path does not exist, then this will
                         behave like a no-op.
        """
        if os.path.exists(path):
            setFrontEndPref('lastPathExportClip', path)


    ###########################################################
    def _exportMultipleClips(self):
        """Export the current clip.
        """

        # Do dialog to pick target directory...
        defPath = self._getClipExportPath()
        defWantTimestampOverlay = getFrontEndPref('lastTimestampOverlayExportClip')
        defWantBoundingBoxes = getFrontEndPref('lastBoundingBoxesExportClip')
        use12Hour, useUSDate = self._backEndClient.getTimePreferences()

        dlg = ExportMultipleClipsDialog(
            self.GetTopLevelParent(), "Export Clips",
            "Choose a folder to export clips to", defPath,
        )
        dlg.WantTimestampOverlay = defWantTimestampOverlay
        dlg.WantBoundingBoxes = defWantBoundingBoxes

        dlg.CenterOnParent()

        try:
            if dlg.ShowModal() == wx.ID_OK:
                savePath = dlg.GetSavePath()
                wantTimestampOverlay = dlg.WantTimestampOverlay
                wantBoundingBoxes = dlg.WantBoundingBoxes
            else:
                return
        except:
            return
        finally:
            dlg.Destroy()

        if defPath != savePath:
            self._setClipExportPath(os.path.dirname(savePath))

        if defWantTimestampOverlay != wantTimestampOverlay:
            setFrontEndPref('lastTimestampOverlayExportClip', wantTimestampOverlay)

        if defWantBoundingBoxes != wantBoundingBoxes:
            setFrontEndPref('lastBoundingBoxesExportClip', wantBoundingBoxes)

        extras = {
            "enableTimestamps": wantTimestampOverlay,
            "drawBoxes": wantBoundingBoxes,
            "use12HrTime" : wantTimestampOverlay and use12Hour,
            "useUSDate" : wantTimestampOverlay and useUSDate,
        }

        # Create ClipManager and DataManager.
        dbPath, clipDbPath, storagePath = self._dataMgr.getPaths()
        clipManager = ClipManager(self._logger)
        clipManager.open(clipDbPath)
        dataManager = DataManager(self._logger, clipManager, storagePath)
        dataManager.open(dbPath)

        # Get selection ID list
        selectedIds = self._resultsModel.getSelectedIds()
        clips = self._resultsModel.getMatchingClips()

        clipList = []

        for selectedId in selectedIds:
            clipList.append(clips[selectedId])

        exportDlg = ExportClipsProgDialog(
            self.GetTopLevelParent(), dataManager, clipManager, savePath,
            clipList, extras
        )

        try:
            exportDlg.ShowModal()
        finally:
            exportDlg.Destroy()

    ###########################################################
    def OnExportTimeRange(self, event):

        dbPath, clipDbPath, storagePath = self._dataMgr.getPaths()
        clipManager = ClipManager(self._logger)
        clipManager.open(clipDbPath)
        cameraLocations = clipManager.getCameraLocations()
        cameraLocations.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))

        currentCamera = self._resultsModel.getCurrentCameraName()
        if self._resultsModel.isVideoLoaded():
            centerTimeAround = self._resultsModel.getCurrentAbsoluteMs()
        else:
            centerTimeAround = self._resultsModel.getMidnightMs() + 24*60*60*1000 / 2

        defName = "export"
        defPath = self._getClipExportPath()

        dlg = ExportTimeRangeDialog(
            cameraLocations,
            currentCamera,
            centerTimeAround,
            self._markupModel,
            self.GetTopLevelParent(), "Export Time Range", "Export Time Range as ",
            defPath, defName, ["mp4", "gif"], kUseFpsLimit|kUseSizeLimit
        )

        res, extras, savePath = self._executeExportOptionsDialog(dlg, defPath)
        if res != wx.ID_OK:
            return

        camLoc = dlg.getCameraLocation()
        startTime = dlg.getStartTime()
        endTime = dlg.getEndTime()

        dlg.Destroy()

        files, procSize = clipManager.getFilesAndProcSizeBetween(camLoc, startTime, endTime)

        if extras.get("drawBoxes", False):
            # Figure out bounding boxes
            dm = DataManager(self._logger, clipManager)
            dm.open(dbPath)
            dm.setMarkupModel(self._markupModel)
            bboxes = dm.getBoundingBoxesBetweenTimes(camLoc, startTime, endTime, procSize)
            extras['boxList'] = bboxes

        fileList = []
        for filename, startms, _ in files:
            fileList.append((os.path.join(storagePath, filename), startms))

        self._progressDlg = ExportProgressDialog(self, fileList, savePath, startTime, endTime,
            getUserLocalDataDir(), extras, self._logger, self._progressFn)
        try:
            self._progressDlg.ShowModal()
            if not self._progressDlg.Success():
                wx.MessageBox("There was an error exporting the video.",
                            "Error", wx.ICON_ERROR | wx.OK,
                            self.GetTopLevelParent())

        finally:
            self._progressDlg.Destroy()
            self._progressDlg = None

    ###########################################################
    def OnSubmitClipForAnalysis(self, event):
        self._submitClipForAnalysis(False)

    ###########################################################
    def OnSubmitClipForAnalysisWithNote(self, event):
        self._submitClipForAnalysis(True)

    ###########################################################
    def _submitClipForAnalysis(self, needsNote):
        kMultiUploadThreshold = 2
        note = ""
        multiUpload = self._resultsModel.getMultipleSelected()
        multiUploadClips = None

        # Acquire consent
        if not getFrontEndPref("hasConsentToSubmitVideo"):
            dlg = SubmitClipConsentDialog(self)
            try:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                if dlg.permanentConsent():
                    # Make consent permanent
                    setFrontEndPref("hasConsentToSubmitVideo", True)
            finally:
                dlg.Destroy()

        # Make sure user isn't uploading something they don't want to
        if multiUpload:
            multiUploadClips = self._resultsModel.getSelectedIds()
            if len(multiUploadClips) >= kMultiUploadThreshold:
                try:
                    msg = "You have selected " + str(len(multiUploadClips)) + " clips to upload. Do you want to continue?"
                    dlg = wx.MessageDialog(None, msg,'Upload multiple files', wx.YES_NO | wx.ICON_WARNING)
                    if dlg.ShowModal() != wx.ID_YES:
                        return
                finally:
                    dlg.Destroy()

        # Collect a note, if requested
        if needsNote:
            dlg = SubmitClipDetailsDialog(self)
            try:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                note = dlg.getNote()
            finally:
                dlg.Destroy()

        if multiUpload:
            # Get selection ID list
            for clip in multiUploadClips:
                camera, startTime, stopTime = self._resultsModel.getClipInformation(clip)
                self._backEndClient.submitClipToSighthound(camera, note, startTime, stopTime-startTime)
        else:
            # Tell backend to queue the clip export
            camera = self._resultsModel.getCurrentCameraName()
            startTime = self._resultsModel.getCurrentClipStart()
            stopTime = self._resultsModel.getCurrentClipStop()
            self._backEndClient.submitClipToSighthound(camera, note, startTime, stopTime-startTime)

    ###########################################################
    def OnExportProgress(self, percentage):
        if self._progressDlg is None:
            return -1
        return self._progressDlg.SetPercentageDone(percentage)

    ###########################################################
    def OnExportFrame(self, event):
        """Export the current frame.

        @param  event  The menu event.
        """
        startTime = self._resultsModel.getCurrentClipStart() + \
                    self._resultsModel.getCurrentRelativeMs()
        savePath, extras = self._getExportOptions( startTime,
                                "Export Frame",
                                "Export Frame As ",
                                ["jpg"], False )
        if savePath is None:
            return

        extras["format"] = "jpg"
        success = self._dataMgr.saveCurrentClip(savePath, startTime,
                                                startTime, getUserLocalDataDir(),
                                                extras)

        if not success:
            wx.MessageBox("There was an error exporting the frame.",
                          "Error", wx.ICON_ERROR | wx.OK,
                          self.GetTopLevelParent())

    ###########################################################
    def _executeExportOptionsDialog(self, dlg, defDir):
        # read default options from config
        defWantTimestampOverlay = getFrontEndPref('lastTimestampOverlayExportClip')
        defWantBoundingBoxes = getFrontEndPref('lastBoundingBoxesExportClip')
        defFpsLimit = getFrontEndPref('lastFpsLimitExportClip')
        defSizeLimit = getFrontEndPref('lastSizeLimitExportClip')

        # set default options to the dialog
        dlg.WantTimestampOverlay = defWantTimestampOverlay
        dlg.WantBoundingBoxes = defWantBoundingBoxes
        dlg.FPSLimit = defFpsLimit
        dlg.SizeLimit = defSizeLimit

        # execute dialog
        extras = None
        savePath = None
        try:
            dlg.CenterOnParent()
            res = dlg.ShowModal()
            # save default values, if we're going ahead with saving
            if res == wx.ID_OK:
                wantTimestampOverlay = dlg.WantTimestampOverlay
                if defWantTimestampOverlay != wantTimestampOverlay:
                    setFrontEndPref('lastTimestampOverlayExportClip', wantTimestampOverlay)

                fpsLimit = dlg.FPSLimit
                if defFpsLimit != fpsLimit:
                    setFrontEndPref('lastFpsLimitExportClip', fpsLimit)

                wantBoundingBoxes = dlg.WantBoundingBoxes
                if defWantBoundingBoxes != wantBoundingBoxes:
                    setFrontEndPref('lastBoundingBoxesExportClip', wantBoundingBoxes)

                sizeLimit = dlg.SizeLimit
                if defSizeLimit != sizeLimit:
                    setFrontEndPref('lastSizeLimitExportClip', sizeLimit)

                savePath = dlg.GetSavePath()
                if defDir != os.path.dirname(savePath):
                    self._setClipExportPath(os.path.dirname(savePath))

                selectedType = dlg.SelectedType

                use12Hour, useUSDate = self._backEndClient.getTimePreferences()

                extras = {
                    "enableTimestamps": wantTimestampOverlay,
                    "drawBoxes": wantBoundingBoxes,
                    "use12HrTime" : wantTimestampOverlay and use12Hour,
                    "useUSDate" : wantTimestampOverlay and useUSDate,
                    "format" : selectedType
                }
                if fpsLimit > 0:
                    extras["fps"] = fpsLimit
                if sizeLimit > 0:
                    extras["maxSize"] = (0,sizeLimit)
        except:
            self._logger.info( 'Dialog exception saving a clip/frame:' + traceback.format_exc() )
            res = wx.CANCEL

        return res, extras, savePath


    ###########################################################
    def _getExportOptions(self, startTime, title1, title2, fileTypes, useFpsLimit):
        """ Run export dialog, and procure options for export

        @param  startTime - start time of the clip
        @param  title1, e.g. "Export Clip"
        @param  title2, e.g. "Export Clip As ..."
        @param  fileTypes, e.g. "[mp4, gif]"
        @return savePath, location to save to
        @return extras, export options dict
        """
        baseName = self._resultsModel.getCurrentCameraName()

        if self._resultsModel.getMidnightMs() is None:
            # Imported clip; show startTime in file-relative time.
            clipMsInFile = self._resultsModel.getCurrentFileRelativeMs() - \
                           self._resultsModel.getCurrentRelativeMs()
            ms = clipMsInFile + \
                 (startTime - self._resultsModel.getCurrentClipStart())
            ms = max(0, ms)
            seconds, _ = divmod(ms, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            timeStr = "%02d-%02d-%02d" % (hours, minutes, seconds)

            # File should start with original filename, not camera name.
            baseName = self._resultsModel.getCurrentFilename()
        else:
            # Normal (non-imported) case; show real time...
            timeStr = time.asctime(time.localtime(startTime/1000))

        defName = baseName + ' - ' + timeStr.replace(':', '-')

        defDir = self._getClipExportPath()
        flags = kUseSizeLimit
        if useFpsLimit:
            flags |= kUseFpsLimit

        dlg = ExportSingleClipDialog(
            self.GetTopLevelParent(), title1, title2,
            defDir, defName, fileTypes, flags )

        res, extras, savePath = self._executeExportOptionsDialog(dlg, defDir)
        dlg.Destroy()

        return savePath, extras

    ###########################################################
    def OnExportClip(self, event):
        """Export the current clip.

        @param  event  The menu event.
        """

        if self._resultsModel.getMultipleSelected():
            self._exportMultipleClips()
            return

        # Start out trying to export the whole clip...
        startTime = self._resultsModel.getCurrentClipStart()
        stopTime = self._resultsModel.getCurrentClipStop()

        # For bug reports, try to rewind 30 seconds from the event time to
        # make sure that the tracker can get initialized...  Do this before
        # trimming big clips so that the trimming code takes this modified
        # startTime into account...
        if event.GetId() == self._exportForBugReportMenuItem.GetId():
            startTime = self._resultsModel.getCurrentClipPlayTime() - \
                        _kBugReportRewindMs
        else:
            assert event.GetId() == self._exportClipMenuItem.GetId()

        # If it's too long and we're in cache, we'll center around the
        # location we're currently looking at.
        if not self._resultsModel.isCurrentClipMatching():
            duration = (stopTime - startTime) + 1
            if duration > _kMaxClipDurationMs:
                result = wx.MessageBox(_kBigClipWarningStr, _kBigClipCaptionStr,
                                       wx.ICON_ERROR | wx.OK | wx.CANCEL,
                                       self.GetTopLevelParent())
                if result != wx.OK:
                    return

                absMs = self._resultsModel.getCurrentAbsoluteMs()
                rewindAmt = _kMaxClipDurationMs/2

                if (absMs + rewindAmt) > stopTime:
                    startTime = (stopTime - _kMaxClipDurationMs) + 1
                else:
                    startTime = max(startTime, absMs - rewindAmt)
                    stopTime = (startTime + _kMaxClipDurationMs) - 1

        # run the options dialog
        savePath, extras = self._getExportOptions( startTime,
                                "Export Clip",
                                "Export Clip As ",
                                ["mp4", "gif"],
                                True )
        if savePath is None:
            return

        success = self._dataMgr.saveCurrentClip(savePath, startTime,
                                                stopTime, getUserLocalDataDir(),
                                                extras)

        if not success:
            wx.MessageBox("There was an error exporting the clip.",
                          "Error", wx.ICON_ERROR | wx.OK,
                          self.GetTopLevelParent())


    ###########################################################
    def _updateVideoUi(self):
        """Update the video UI to match the resultsModel."""

        img = self._resultsModel.getCurrentImg()
        if img is None:
            self._resetControls()
        else:
            relativeMs = self._resultsModel.getCurrentRelativeMs()

            self._updateVideoImage(img)
            self._slider.SetValue(relativeMs)
            self._updateDateAndTimeText()

            self._updateNavigationControls()
            self._updateAudioControls()


    ###########################################################
    def _handleDebugModeChange(self, debugModeModel):
        """Update the debug info.

        @param  debugModeModel  Should be self._debugModeModel
        """
        assert debugModeModel == self._debugModeModel

        # TODO: Maybe this belongs elsewhere?
        if self._debugModeModel.isDebugMode() and \
           self._resultsModel.isVideoLoaded():
            self.GetTopLevelParent().SetTitle(self._dataMgr.getCurFilename())
        else:
            self.GetTopLevelParent().SetTitle(None)

        self._updateDateAndTimeText()

        # Show / hide the extra "export clip" item...
        toolsMenu = self._exportClipMenuItem.GetMenu()
        if self._debugModeModel.isDebugMode():
            exportPos = toolsMenu.GetMenuItems().index(self._exportClipMenuItem)

            if self._exportForBugReportMenuItem.GetMenu() != toolsMenu:
                toolsMenu.InsertItem(exportPos+1,
                                     self._exportForBugReportMenuItem)

                # On Vista, we get a crash if we try to enable / disable a
                # menu item that has no parent menu.  ...so now that we added the
                # "export for bug report" menu item back in we can do it...
                isEnabled = self._exportClipMenuItem.IsEnabled()
                self._exportForBugReportMenuItem.Enable(isEnabled)
        else:
            if self._exportForBugReportMenuItem.GetMenu() == toolsMenu:
                toolsMenu.Remove(self._exportForBugReportMenuItem)


    ###########################################################
    def enableMenuItems(self, enable=True):
        """Enable or disable controled menu items.

        @param  enable  If True menu items will be enabled.
        """
        for menuItem in self._menuItems:
            if menuItem.GetMenu() is not None:
                menuItem.Enable(enable)


    ###########################################################
    def enableExportIfPossible(self):
        """Enable the export clips menu item if it can be used."""
        if (self._exportClipMenuItem.GetMenu() is not None) and \
           self._resultsModel.getSelectedIds():
            self._exportClipMenuItem.Enable()
            if self._debugModeModel.isDebugMode():
                self._exportForBugReportMenuItem.Enable()
            if not kOpenSourceVersion:
                if self._submitClipForAnalysisMenuItem:
                    self._submitClipForAnalysisMenuItem.Enable()
                if self._submitClipForAnalysisWithNoteMenuItem:
                    self._submitClipForAnalysisWithNoteMenuItem.Enable()

        self._exportFrameMenuItem.Enable(self._exportClipMenuItem.IsEnabled() and \
                        not self._resultsModel.isPlaying())


    ###########################################################
    def enableDeleteIfPossible(self):
        """Enable the delete clips menu item if it can be used."""
        if (self._deleteClipMenuItem.GetMenu() is not None) and \
           self._resultsModel.getSelectedIds():
            self._deleteClipMenuItem.Enable()


    ###########################################################
    def _handleMultipleSelected(self, resultsModel):
        """Handle when the number of selected clips changes.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        if not resultsModel.getMultipleSelected():
            self._resetControls()
            self._updateVideoUi()
            self.enableMenuItems(True)
        else:
            # Otherwise we need to disable everything.
            self._playTimer.Stop()
            self._prevClipButton.Enable(False)
            self._prevClipMenuItem.Enable(False)
            self._nextClipButton.Enable(False)
            self._nextClipMenuItem.Enable(False)
            self._slider.Enable(False)
            self._minus2Button.Enable(False)
            self._backTwoSecsMenuItem.Enable(False)
            self._frameBackButton.Enable(False)
            self._prevFrameMenuItem.Enable(False)
            self._playButton.Enable(False)
            self._playMenuItem.Enable(False)
            self._pauseButton.Enable(False)
            self._frameForwardButton.Enable(False)
            self._nextFrameMenuItem.Enable(False)
            self._plus2Button.Enable(False)
            self._forwardTwoSecsMenuItem.Enable(False)
            self._firstEventMenuItem.Enable(False)
            self._prevEventMenuItem.Enable(False)
            self._nextEventMenuItem.Enable(False)
            self._setEmptyTimeText()
            #self._updateVideoImage(Image.new('RGB', self._minPlaybackSize))
            self._resetVideoImage( Image.new( 'RGB', self._minPlaybackSize ))

            self.enableMenuItems(False)
            self.enableDeleteIfPossible()
            self.enableExportIfPossible()


    ###########################################################
    def setContinuousPlayback(self, continuous):
        self._wantContinuousPlayback = continuous


    ###########################################################
    def _handleTimePrefChange(self, uiModel):
        """Handle a change to time display preferences.

        @param  resultsModel  The UIPrefsDataModel.
        """
        use12, _ = uiModel.getTimePreferences()

        if use12:
            self._timeStr = _kTime12Hour
        else:
            self._timeStr = _kTime24Hour

        self._timelineControl.enable12HourTime(use12)

        self._updateDateAndTimeText()
        # We typicall reserve the largest size we've seen so the playback bar
        # isn't sliding around - reset this when we change formats.
        bestWidth, _ = self._timeText.GetBestSize()
        self._timeText.SetMinSize((bestWidth, -1))
        self.Layout()


    ###########################################################
    def _setEmptyTimeText(self):
        """Set empty time strings and update min sizes."""
        self._timeText.SetLabel("--:--:--")
        self._timeText.SetMinSize((self._timeText.GetBestSize()[0], -1))

        if self._showDuration:
            self._durationText.SetLabel("0:00")
        else:
            self._durationText.SetLabel("-0:00")
        self._durationText.SetMinSize((self._durationText.GetBestSize()[0], -1))

        self.Layout()


###############################################################
class _openGLWarningDialog(wx.Dialog):
    """A dialog informing the user that the back end remains open on exit."""
    kDialogPadding = 16
    kDialogWrap = 360

    ###########################################################
    def __init__(self, parent):
        """Initializer for _openGLWarningDialog.

        @param  parent  The parent window.
        """
        wx.Dialog.__init__(self, parent, -1, "Compatibility Mode")

        try:
            # Create the sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)
            text = wx.StaticText(self, -1,
                    "Hardware acceleration could not be initialized and video "
                    "playback performance may be impacted. This can occur when "
                    "operating over software such as Remote Desktop. If "
                    "encountered under other circumstances please select "
                    "\"Help->Report a Problem...\" or email support@sighthound.com.")

            self._check = wx.CheckBox(self, -1, "Don't show me this again")
            sizer.Add(text, 0, wx.ALL, self.kDialogPadding)
            sizer.Add(self._check, 0, wx.BOTTOM | wx.LEFT | wx.RIGHT,
                      self.kDialogPadding)
            makeFontDefault(text, self._check)
            text.Wrap(self.kDialogWrap)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK)
            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnDialogExit)
            sizer.Add(buttonSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM |
                      wx.EXPAND | wx.ALIGN_RIGHT, self.kDialogPadding)

            self.Bind(wx.EVT_CLOSE, self.OnDialogExit)

            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def OnDialogExit(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The triggering event, ignored.
        """
        if self._check.GetValue():
            setFrontEndPref(_kHideOpenGLPrompt, True)
        self.EndModal(wx.OK)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "NO TESTS"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
