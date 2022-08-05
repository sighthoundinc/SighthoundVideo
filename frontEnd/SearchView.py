#!/usr/bin/env python

#*****************************************************************************
#
# SearchView.py
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
import datetime
import math
import os
from sqlite3 import DatabaseError
import time

# Common 3rd-party imports...
import wx
import wx.adv
from wx.lib import throbber

# Toolbox imports...
from vitaToolbox.wx.BorderImagePanel import BorderImagePanel
from vitaToolbox.wx.BindChildren import bindChildren
from vitaToolbox.wx.FixedGenBitmapButton import FixedGenBitmapButton
from vitaToolbox.wx.FixedStaticBitmap import FixedStaticBitmap
from vitaToolbox.wx.FudgedChoice import FudgedChoice
from vitaToolbox.wx.HoverBitmapButton import HoverBitmapButton
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.TranslucentStaticText import TranslucentStaticText
from vitaToolbox.wx.VitaDatePickerCtrl import VitaDatePickerCtrl
from vitaToolbox.wx.FixedMultiSplitterWindow import FixedMultiSplitterWindow
from vitaToolbox.wx.BitmapFromFile import bitmapFromFile

# Local imports...
from backEnd.triggers.TargetTrigger import getQueryForDefaultRule
from appCommon.CommonStrings import kAnyCameraStr
from appCommon.CommonStrings import kSearchViewDefaultRules
from appCommon.CommonStrings import kInactiveSuffix
from appCommon.CommonStrings import kImportSuffix, kImportDisplaySuffix
from appCommon.CommonStrings import kCorruptDbErrorStrings
from appCommon.CommonStrings import kVideoFolder
from backEnd.RealTimeRule import RealTimeRule
from backEnd.SavedQueryDataModel import SavedQueryDataModel
from backEnd.VideoMarkupModel import VideoMarkupModel

from DeleteClipDialog import DeleteClipDialog
import FrontEndEvents
from FrontEndPrefs import getFrontEndPref
from FrontEndPrefs import setFrontEndPref
from LocateVideoDialog import LocateVideoDialog
from LookForList import LookForList
from QueryEditorDialog import QueryEditorDialog
from RemoveCameraDialog import removeCamera
from SearchResultsDataModel import SearchResultsDataModel
from SearchResultsList import SearchResultsList
from SearchResultsPlaybackPanel import SearchResultsPlaybackPanel
from BaseView import BaseView

import MenuIds


_ctrlPadding = 8
_kSearchDelay = 100
_kThrobberDelay = 50

kQueryNameParam = 'queryName'
kCameraNameParam = 'cameraName'

# Maximum duration for delete clip when in cache.
_kMaxCacheDurationMs = (2 * 60 * 1000)

_kCacheClipWarningStr = (
"""You have selected a large section of cache.  This delete operation will """
"""remove only a two minute segment centered around the frame you are """
"""currently viewing."""
)
_kCacheClipCaptionStr = "Large Cache Delete"


class SearchView(BaseView):
    """Implements a view for performing searching."""
    ###########################################################
    def __init__(self, parent, dataManager, clipManager, backEndClient):
        """The initializer for SearchView

        @param  parent       The parent Window.
        @param  dataManager  The data manager to use for searches.
        @param  clipManager  The clip manager to use for searches.
        @param  backEndClient  A connection to the back end app.
        """
        # Call the base class initializer
        super(SearchView, self).__init__(parent, backEndClient,
                                         style=wx.BORDER_NONE | wx.WANTS_CHARS)

        self._dataMgr = dataManager
        self._clipManager = clipManager

        # A list of rule names for the current camera selection
        self._rules = []

        self._debugModeModel = wx.GetApp().getDebugModeModel()
        self._debugModeModel.addListener(self._handleDebugModeChange)

        # Create the data model keeping track of different ways of marking
        # up the video.  Init using frontEndPrefs...
        use12Hour, useUSDate = self._backEndClient.getTimePreferences()
        self._markupModel = VideoMarkupModel(
            getFrontEndPref('showBoxesAroundObjects'),
            getFrontEndPref('showDifferentColorBoxes'),
            getFrontEndPref('showRegionZones'),
            self._debugModeModel.isDebugMode(),
            self._debugModeModel.isDebugMode(),
            getFrontEndPref('playAudio'),
            getFrontEndPref('overlayTimestamp'),
            useUSDate,
            use12Hour
        )
        self._markupModel.addListener(self._handleMarkupChange, True)
        self._dataMgr.setMarkupModel(self._markupModel)

        # Create the data model for keeping track of search results, plus
        # what we're looking at...
        self._resultsModel = \
            SearchResultsDataModel(dataManager, clipManager)

        # Listen for changes...
        self._resultsModel.addListener(self._handleSearchResultsChange,
                                       False, 'results')
        self._resultsModel.addListener(self._handleSearch, False, 'searching')
        self._resultsModel.addListener(self._handleSort, False, 'sortResults')

        # We delay our searches by a few ms to make some UI more responsive
        self._searchTimer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnSearchTimer, self._searchTimer)

        # A timer for updating the progress throbber.
        self._throbberTimer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnThrobberTimer, self._throbberTimer)

        # Find our menu items and bind to them...
        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()
        self._showBoxesAroundObjectsMenuId = \
            menuBar.FindMenuItem(MenuIds.kViewMenu, "Show Boxes Around Objects")
        self._showDifferentColorBoxesMenuId = \
            menuBar.FindMenuItem(MenuIds.kViewMenu, "Show Different Color Boxes")
        self._showRegionZonesMenuId = \
            menuBar.FindMenuItem(MenuIds.kViewMenu, "Show Region Zones")
        self._muteAudio = \
            menuBar.FindMenuItem("Controls", "Mute Audio")
        self._overlayTimestamp = None
        self._deleteClipMenuId = \
            menuBar.FindMenuItem("Tools", "Delete Clip...")
        self._selectAllClipsMenuId = \
            menuBar.FindMenuItem("Tools", "Select All Clips")
        self._removeCameraMenuId = \
            menuBar.FindMenuItem("Tools", "Remove Camera...")
        topWin.Bind(wx.EVT_MENU, self.OnMarkupMenuItemChange,
                    id=self._showBoxesAroundObjectsMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnMarkupMenuItemChange,
                    id=self._showDifferentColorBoxesMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnMarkupMenuItemChange,
                    id=self._showRegionZonesMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnDeleteClip,
                    id=self._deleteClipMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnSelectAllClips,
                    id=self._selectAllClipsMenuId)

        # Find the controls menu items and bind to them.
        self._playMenuId = \
            menuBar.FindMenuItem("Controls", "Play")
        self._prevClipMenuId = \
            menuBar.FindMenuItem("Controls", "Previous Clip")
        self._nextClipMenuId = \
            menuBar.FindMenuItem("Controls", "Next Clip")
        self._firstClipMenuId = \
            menuBar.FindMenuItem("Controls", "Top Clip in List")
        self._lastClipMenuId = \
            menuBar.FindMenuItem("Controls", "Bottom Clip in List")
        self._prevDayMenuId = \
            menuBar.FindMenuItem("Controls", "Previous Day")
        self._prevDayMenuItem = menuBar.FindItemById(self._prevDayMenuId)
        self._nextDayMenuId = \
            menuBar.FindMenuItem("Controls", "Next Day")
        self._nextDayMenuItem = menuBar.FindItemById(self._nextDayMenuId)
        self._nextFrameMenuId = \
            menuBar.FindMenuItem("Controls", "Next Frame")
        self._prevFrameMenuId = \
            menuBar.FindMenuItem("Controls", "Previous Frame")
        self._forwardTwoSecsMenuId = \
            menuBar.FindMenuItem("Controls", "Forward 2 Seconds")
        self._backTwoSecsMenuId = \
            menuBar.FindMenuItem("Controls", "Backward 2 Seconds")
        self._nextEventMenuId = \
            menuBar.FindMenuItem("Controls", "Next Event in Clip")
        self._prevEventMenuId = \
            menuBar.FindMenuItem("Controls", "Previous Event in Clip")
        self._firstEventMenuId = \
            menuBar.FindMenuItem("Controls", "First Event in Clip")
        self._continuousEventMenuId = \
            menuBar.FindMenuItem("Controls", "Continuous Playback")
        self._controlsMenuItems = \
            [self._playMenuId, self._prevClipMenuId, self._nextClipMenuId,
             self._firstClipMenuId, self._lastClipMenuId, self._prevDayMenuId,
             self._nextDayMenuId, self._nextFrameMenuId, self._prevFrameMenuId,
             self._forwardTwoSecsMenuId, self._backTwoSecsMenuId,
             self._nextEventMenuId, self._prevEventMenuId,
             self._firstEventMenuId, self._continuousEventMenuId]
        topWin.Bind(wx.EVT_MENU, self.OnPlay, id=self._playMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnPrevClip, id=self._prevClipMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnNextClip, id=self._nextClipMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnFirstClip, id=self._firstClipMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnLastClip, id=self._lastClipMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnPrevDay, id=self._prevDayMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnNextDay, id=self._nextDayMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnNextFrame, id=self._nextFrameMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnPrevFrame, id=self._prevFrameMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnForwardTwoSecs, id=self._forwardTwoSecsMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnBackTwoSecs, id=self._backTwoSecsMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnNextEvent, id=self._nextEventMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnPrevEvent, id=self._prevEventMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnFirstEvent, id=self._firstEventMenuId)
        topWin.Bind(wx.EVT_MENU, self.OnContinuousToggle, id=self._continuousEventMenuId)

        self._menuItemsEnabledWithView = [
                menuBar.FindMenuItem(MenuIds.kControlsMenu, "1/2 Speed"),
                menuBar.FindMenuItem(MenuIds.kControlsMenu, "1x Speed"),
                menuBar.FindMenuItem(MenuIds.kControlsMenu, "2x Speed"),
                menuBar.FindMenuItem(MenuIds.kControlsMenu, "4x Speed"),
                menuBar.FindMenuItem(MenuIds.kControlsMenu, "16x Speed"),
                menuBar.FindMenuItem(MenuIds.kViewMenu, "Show Daily Timeline")]

        self._initUiWidgets()

        # Make sure our sort buttons are shown correctly...
        self._handleSort(self._resultsModel)

        # Make sure we're up to date on markup model...
        self._handleMarkupChange(self._markupModel, None)

        menuBar.Check(self._continuousEventMenuId,
                getFrontEndPref('wantContinuousPlayback'))
        self.OnContinuousToggle()

        self.OnRuleChoice()

    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""
        splitterWindow = FixedMultiSplitterWindow(
            self, wx.ID_ANY,
                wx.DefaultPosition, wx.DefaultSize,
                (
                    wx.SP_LIVE_UPDATE | wx.TAB_TRAVERSAL | wx.BORDER_NONE |
                    wx.TRANSPARENT_WINDOW | wx.FULL_REPAINT_ON_RESIZE
                ),
                "SplitterWindowSearchView", None, self._logger
        )

        self._splitterWindow = splitterWindow

        leftPanel = BorderImagePanel(splitterWindow, -1,
                                     'frontEnd/bmps/RaisedPanelBorder.png', 8)
        leftPanelSizer = wx.BoxSizer(wx.VERTICAL)

        # Camera selection
        cameraLabel = TranslucentStaticText(leftPanel, -1, "Camera:")
        self._cameraChoice = FudgedChoice(leftPanel, -1, size=(256, -1),
                                          fudgeList=[(kImportSuffix,
                                                      kImportDisplaySuffix)])
        self._populateCameraChoice()

        # Rule selection
        lookForLabel = TranslucentStaticText(leftPanel, -1, "Look for:")
        self._ruleListBorder = wx.Panel(leftPanel, style=wx.BORDER_THEME)
        self._ruleList = LookForList(self._ruleListBorder)
        self._populateRuleList()

        # Edit button
        bmp = wx.Bitmap(os.path.join("frontEnd/bmps", "Edit.png"))
        bmpSel = wx.Bitmap(os.path.join("frontEnd/bmps", "Edit_Pressed.png"))
        bmpDisabled = wx.Bitmap(os.path.join("frontEnd/bmps",
                                             "Edit_Disabled.png"))
        self._editButton = FixedGenBitmapButton(leftPanel, bmp,
                                                bmpSel, bmpDisabled)
        self._editButton.Disable()

        # Duplicate button
        bmp = wx.Bitmap(os.path.join("frontEnd/bmps", "Duplicate.png"))
        bmpSel = wx.Bitmap(os.path.join("frontEnd/bmps",
                                        "Duplicate_Pressed.png"))
        bmpDisabled = wx.Bitmap(os.path.join("frontEnd/bmps",
                                             "Duplicate_Disabled.png"))
        self._duplicateButton = FixedGenBitmapButton(leftPanel, bmp,
                                                     bmpSel, bmpDisabled)
        self._duplicateButton.Disable()

        # Add/Delete buttons
        bmp = wx.Bitmap(os.path.join("frontEnd/bmps", "Plus.png"))
        bmpSel = wx.Bitmap(os.path.join("frontEnd/bmps", "Plus_Pressed.png"))
        self._addButton = FixedGenBitmapButton(leftPanel, bmp, bmpSel)
        bmp = wx.Bitmap(os.path.join("frontEnd/bmps", "Minus.png"))
        bmpSel = wx.Bitmap(os.path.join("frontEnd/bmps", "Minus_Pressed.png"))
        bmpDisabled = wx.Bitmap(os.path.join("frontEnd/bmps",
                                             "Minus_Disabled.png"))
        self._deleteButton = FixedGenBitmapButton(leftPanel, bmp,
                                                  bmpSel, bmpDisabled)
        self._deleteButton.Disable()

        # Day selection controls
        self._whenLabel = TranslucentStaticText(leftPanel, -1, "When:")
        self._datePicker = VitaDatePickerCtrl(leftPanel, None,
                                              datetime.date.fromtimestamp(0),
                                              "today",
                                              self._isDateBold)

        # A counter for the results list
        self._resultsCounter = TranslucentStaticText(leftPanel, -1, "0 Results",
                                                     style=wx.ALIGN_RIGHT)

        # Refresh button
        self._refreshButton = HoverBitmapButton(
            leftPanel, wx.ID_ANY,
            'frontEnd/bmps/Refresh_enabled.png',
            wx.EmptyString,
            'frontEnd/bmps/Refresh_pressed.png',
            'frontEnd/bmps/Refresh_disabled.png',
            'frontEnd/bmps/Refresh_hover.png',
            useMask=False
        )

        # Create the sort buttons for the search results contained in the
        # SearchResultsList...
        self._resultsSortAscendingButton = HoverBitmapButton(
            leftPanel, wx.ID_ANY,
            'frontEnd/bmps/Sort_Ascending_Enabled.png',
            wx.EmptyString,
            'frontEnd/bmps/Sort_Ascending_Pressed.png',
            'frontEnd/bmps/Sort_Ascending_Disabled.png',
            'frontEnd/bmps/Sort_Ascending_Hover.png',
            False,
            False,
            wx.DefaultPosition,
            wx.DefaultSize,
            False,
            'Sort Ascending Button',
        )
        self._resultsSortDescendingButton = HoverBitmapButton(
            leftPanel, wx.ID_ANY,
            'frontEnd/bmps/Sort_Descending_Enabled.png',
            wx.EmptyString,
            'frontEnd/bmps/Sort_Descending_Pressed.png',
            'frontEnd/bmps/Sort_Descending_Disabled.png',
            'frontEnd/bmps/Sort_Descending_Hover.png',
            False,
            False,
            wx.DefaultPosition,
            wx.DefaultSize,
            False,
            'Sort Descending Button',
        )

        # Search throbber
        progBmps = [wx.Bitmap("frontEnd/bmps/prog%d.png" % i) for i in xrange(8)]
        self._throbberBmps = [FixedStaticBitmap(leftPanel, -1, progBmps[i])
                                 for i in xrange(8)]
        self._curThrobberId = 0

        # Add to sizer
        choiceSizer = wx.FlexGridSizer(4, 2, _ctrlPadding/2, _ctrlPadding)
        choiceSizer.AddGrowableCol(1)
        choiceSizer.Add(cameraLabel, 0, wx.ALIGN_LEFT)
        choiceSizer.Add(self._cameraChoice, 1, wx.EXPAND)
        choiceSizer.Add(lookForLabel, 0, wx.ALIGN_LEFT)
        choiceSizer.Add(self._ruleListBorder, 1, wx.EXPAND)
        borderSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._ruleListBorder.SetSizer(borderSizer)
        borderSizer.Add(self._ruleList, 1, wx.EXPAND)
        choiceSizer.AddSpacer(1)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self._addButton, 0)
        hSizer.Add(self._deleteButton, 0)
        hSizer.Add(self._editButton, 0, wx.LEFT, _ctrlPadding)
        hSizer.Add(self._duplicateButton, 0, wx.LEFT, _ctrlPadding)
        choiceSizer.Add(hSizer)
        choiceSizer.Add(self._whenLabel, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                        wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        hSizer2.Add(self._datePicker, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                    wx.ALIGN_CENTER_VERTICAL)
        hSizer2.Add(self._resultsCounter, 1)
        overlapSizer = OverlapSizer(True)
        overlapSizer.Add(self._resultsSortAscendingButton, 0,
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        overlapSizer.Add(self._resultsSortDescendingButton, 0,
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        hSizer2.Add(overlapSizer, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                    wx.LEFT | wx.ALIGN_CENTER_VERTICAL, _ctrlPadding)
        overlapSizer = OverlapSizer(True)
        overlapSizer.Add(self._refreshButton, 0,
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        for bmp in self._throbberBmps:
            overlapSizer.Add(bmp, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
            bmp.Hide()
        hSizer2.Add(overlapSizer, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                    wx.ALIGN_CENTER_VERTICAL)
        choiceSizer.Add(hSizer2, 1, wx.EXPAND)
        leftPanelSizer.Add(choiceSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT |
                           wx.TOP, 20)
        leftPanelSizer.AddSpacer(4)

        # A List box for search results
        self._resultsListBorder = wx.Panel(leftPanel, style=wx.BORDER_THEME)
        self._resultsList = SearchResultsList(self._resultsListBorder,
                                              self._dataMgr, self._resultsModel,
                                              self._markupModel)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddSpacer(18)
        hSizer.Add(self._resultsListBorder, 1, wx.EXPAND)
        borderSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._resultsListBorder.SetSizer(borderSizer)
        borderSizer.Add(self._resultsList, 1, wx.EXPAND)
        hSizer.AddSpacer(20)
        leftPanelSizer.Add(hSizer, 1, wx.EXPAND | wx.BOTTOM, 24)

        leftPanel.SetSizer(leftPanelSizer)

        # Add video playback controls
        self._videoPanel = SearchResultsPlaybackPanel(splitterWindow, self._logger,
                                                      self._backEndClient,
                                                      self._dataMgr,
                                                      self._resultsModel,
                                                      self._markupModel)

        splitterWindow.SplitVertically(leftPanel, self._videoPanel)

        self.borderSizer = wx.BoxSizer(wx.VERTICAL)
        self.borderSizer.Add(splitterWindow, 1, wx.EXPAND | wx.ALL, 12)

        self.SetSizer(self.borderSizer)

        # Bind to events
        self._cameraChoice.Bind(wx.EVT_CHOICE, self.OnCameraChoice)
        self._ruleList.Bind(wx.EVT_LISTBOX, self.OnRuleChoice)
        self._ruleList.Bind(wx.EVT_LISTBOX_DCLICK, self.OnEditQuery)
        self._ruleList.Bind(wx.EVT_MOUSE_EVENTS, self.OnRuleMouse)
        self._editButton.Bind(wx.EVT_BUTTON, self.OnEditQuery)
        self._duplicateButton.Bind(wx.EVT_BUTTON, self.OnNewRule)
        self._addButton.Bind(wx.EVT_BUTTON, self.OnNewRule)
        self._deleteButton.Bind(wx.EVT_BUTTON, self.OnDeleteRule)
        self._refreshButton.Bind(wx.EVT_BUTTON, self.OnRefresh)
        self._datePicker.Bind(wx.adv.EVT_DATE_CHANGED, self.OnDateChanged)

        self._resultsSortAscendingButton.Bind(
            wx.EVT_BUTTON, self.OnSortAscendDescendButton
        )
        self._resultsSortDescendingButton.Bind(
            wx.EVT_BUTTON, self.OnSortAscendDescendButton
        )

        if wx.Platform == '__WXMSW__':
            bindChildren(self, wx.EVT_SET_FOCUS, self.OnFocusChanged)
            # On Windows, we let choice controls get focus; we try to take it
            # back if they ever change values...
            bindChildren(self, wx.EVT_CHOICE, self.OnAnyChoice)

            # Since we have focus, we'll be getting all mouse wheel events
            # on Windows.  Handle them and dole them out to children.
            self.Bind(wx.EVT_MOUSEWHEEL, self.OnScrollWheel)

        # Get the top level parent and register the load and save preferences methods.
        topLevelParent = self.GetTopLevelParent()
        topLevelParent.registerExitNotification(self._savePrefs)
        topLevelParent.registerPrefsNotification(self._loadPrefs)

        uiPrefsModel = self.GetTopLevelParent().getUIPrefsDataModel()
        uiPrefsModel.addListener(self._handleTimePrefChange, key='time')
        self._handleTimePrefChange(uiPrefsModel)


    ###########################################################
    def _savePrefs(self):
        """Added functionality.  This function gets registered with the top level window.
        It is registered on close.  It saves the sash positions to the preferences file.
        """
        setFrontEndPref("searchViewSashPos1", self._splitterWindow.GetSashPosition(0))


    ###########################################################
    def _loadPrefs(self):
        """Added functionality.  This function gets registered with the top level window.
        It is registered on initialization.  It loads the sash positions from the preferences
        file and sets them.
        """
        pos1 = getFrontEndPref("searchViewSashPos1")
        if pos1:
            self._splitterWindow.SetSashPosition(0, pos1)
        else:
            # If we don't have a previous size from preferences, then we'll
            # just set the position to 1. Setting the sash position forces
            # a resize of the splitter window, and it will set an appropriate
            # value for the sash position.
            self._splitterWindow.SetSashPosition(0, 1)


    ############################################################
    def _isDateBold(self, date):
        """Returns true if the given date should be bold.

        A date should be bold if there's video on that day.

        @param  date  True if the date should be bold.
        """
        cameraLoc = self._searchCamLoc
        if cameraLoc == kAnyCameraStr:
            cameraLoc = None

        try:
            return self._clipManager.isVideoOnDay(date, cameraLoc)
        except Exception:
            # Happens if the user goes too far in the past on Windows...
            return False


    ############################################################
    def OnAnyChoice(self, event):
        """Handle any child choice event and steal focus back.

        This is only used on wx.MSW where we don't steal focus from choices
        right when they get it (since it breaks wx.Choice controls).

        @param  event  The choice event.
        """
        wx.CallAfter(self._safeSetFocusIgnoringChildren)
        event.Skip()


    ############################################################
    def OnScrollWheel(self, event):
        """Handle scroll wheel events and hand to children.

        @param  event  The scroll wheel event.
        """
        # Get the point relating to the scroll wheel in screen coords...
        pt = event.GetEventObject().ClientToScreen(event.GetPosition())

        # Find the window associated with the point...
        win = wx.FindWindowAtPoint(pt)

        # Hand the scroll wheel event off...
        if win:
            win.GetEventHandler().ProcessEvent(event)


    ############################################################
    def OnChar(self, event):
        """Handle key character events.

        @param  event  The key event, from the system
        """
        keycode = event.GetKeyCode()

        handled = False

        if wx.Platform == '__WXMAC__':
            commandKey = wx.MOD_CMD
        else:
            commandKey = wx.MOD_CONTROL

        # Here's the default key set...
        #
        # By having a map like this, we could allow overrides.  Right now we
        # don't...
        keyMap = {
            (wx.WXK_LEFT,  0):                       ('stepBack',tuple()),
            (wx.WXK_RIGHT, 0):                       ('stepFwd', tuple()),
            (wx.WXK_LEFT,  wx.MOD_SHIFT):            ('back2S',  tuple()),
            (wx.WXK_RIGHT, wx.MOD_SHIFT):            ('fwd2S',   tuple()),
            (wx.WXK_LEFT,  commandKey):              ('prevStartTime', tuple()),
            (wx.WXK_RIGHT, commandKey):              ('nextStartTime', tuple()),

            (ord(' '),     0):                       ('pause',      tuple()),
            (wx.WXK_RETURN, 0):                      ('clipPlayPt', tuple()),

            (wx.WXK_UP,    0):                       ('prevClip',   tuple()),
            (wx.WXK_DOWN,  0):                       ('nextClip',   tuple()),
            (wx.WXK_UP,    wx.MOD_SHIFT):            ('firstClip',  tuple()),
            (wx.WXK_DOWN,  wx.MOD_SHIFT):            ('lastClip',   tuple()),
            (wx.WXK_UP,    commandKey):              ('prevDay',    tuple()),
            (wx.WXK_DOWN,  commandKey):              ('nextDay',    tuple()),
            (ord('C'),     0):                       ('continuous', tuple()),
        }

        if wx.Platform == '__WXMAC__':
            keyMap[(wx.WXK_BACK,  0)] =              ('deleteClip', tuple())
            keyMap[(wx.WXK_BACK,  commandKey)] =     ('deleteClip', tuple())

        # We only do things with characters if nothing important has focus.
        # We use a heuristic that any UI object that has a "GetValue()" call
        # might want key presses...
        # NOTE: elsewhere, we try not to let anything else get focus, but
        # this is just in case...
        focusedObject = self.FindFocus()
        if (not focusedObject) or (not hasattr(focusedObject, "GetValue")):
            mods = event.GetModifiers()

            keyAndMods = (keycode, mods)
            if keyAndMods in keyMap:
                funcName, args = keyMap[keyAndMods]

                if funcName == 'stepBack':
                    self.OnPrevFrame()
                    handled = True

                elif funcName == 'stepFwd':
                    self.OnNextFrame()
                    handled = True

                elif funcName == 'back2S':
                    self.OnBackTwoSecs()
                    handled = True

                elif funcName == 'fwd2S':
                    self.OnForwardTwoSecs()
                    handled = True

                elif funcName == 'pause':
                    self.OnPlay()
                    handled = True

                elif funcName == 'prevStartTime':
                    self.OnPrevEvent()
                    handled = True

                elif funcName == 'nextStartTime':
                    self.OnNextEvent()
                    handled = True

                elif funcName == 'clipPlayPt':
                    self.OnFirstEvent()
                    handled = True

                elif funcName == 'prevClip':
                    self.OnPrevClip()
                    handled = True

                elif funcName == 'nextClip':
                    self.OnNextClip()
                    handled = True

                elif funcName == 'firstClip':
                    self.OnFirstClip()
                    handled = True

                elif funcName == 'lastClip':
                    self.OnLastClip()
                    handled = True

                elif funcName == 'prevDay':
                    self.OnPrevDay()
                    handled = True

                elif funcName == 'nextDay':
                    self.OnNextDay()
                    handled = True

                elif funcName == 'deleteClip':
                    if self._resultsModel.getCurrentClipNum() != -1:
                        self.OnDeleteClip(None)
                    handled = True

                elif funcName == 'continuous':
                    self.OnContinuousToggle()
                    handled = True


        # Pass the key event on if unhandled
        if not handled:
            event.Skip()


    ###########################################################
    def OnPlay(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        self._videoPanel.handleSpaceBar()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnPrevClip(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return

        if self._resultsModel.isSortAscending():
            self._resultsModel.goToPrevClip()
        else:
            self._resultsModel.goToNextClip()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnNextClip(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return

        if self._resultsModel.isSortAscending():
            self._resultsModel.goToNextClip()
        else:
            self._resultsModel.goToPrevClip()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnFirstClip(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        numClips = self._resultsModel.getNumMatchingClips()
        if numClips:
            if self._resultsModel.isSortAscending():
                self._resultsModel.setCurrentClipNum(0)
            else:
                self._resultsModel.setCurrentClipNum(numClips - 1)

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnLastClip(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        numClips = self._resultsModel.getNumMatchingClips()
        if numClips:
            if self._resultsModel.isSortAscending():
                self._resultsModel.setCurrentClipNum(numClips - 1)
            else:
                self._resultsModel.setCurrentClipNum(0)

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnPrevDay(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        # Nothing to do for imported cams...
        if self._isSearchCamImported():
            return

        self._resultsModel.setPlay(False, False)
        oldDate = self._datePicker.GetValue()
        dateDelta = datetime.timedelta(-1)
        self._datePicker.SetValue(oldDate + dateDelta)
        self.OnDateChanged()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnNextDay(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        # Nothing to do for imported cams...
        if self._isSearchCamImported():
            return

        oldDate = self._datePicker.GetValue()
        if oldDate != datetime.date.today():
            self._resultsModel.setPlay(False, False)
            dateDelta = datetime.timedelta(1)
            self._datePicker.SetValue(oldDate + dateDelta)
            self.OnDateChanged()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnNextFrame(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        relativeMs = self._resultsModel.getCurrentRelativeMs()
        clipDuration = self._resultsModel.getCurrentClipDuration()
        self._resultsModel.setPlay(False)
        if relativeMs < clipDuration-1:
            self._resultsModel.goToNextFrame()
        else:
            self._resultsModel.passClipEnd()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnPrevFrame(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        relativeMs = self._resultsModel.getCurrentRelativeMs()
        self._resultsModel.setPlay(False)
        if relativeMs > 0:
            self._resultsModel.goToPrevFrame()
        else:
            self._resultsModel.passClipBeginning()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnForwardTwoSecs(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        self._resultsModel.goForwardXMs(2000)

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnBackTwoSecs(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        self._resultsModel.goBackwardXMs(2000)

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnNextEvent(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        self._resultsModel.goToNextStartTime()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnPrevEvent(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        self._resultsModel.goToPrevStartTime()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()


    ###########################################################
    def OnContinuousToggle(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        menuBar = self.GetTopLevelParent().GetMenuBar()
        enable = menuBar.IsChecked(self._continuousEventMenuId)
        self._videoPanel.setContinuousPlayback(enable)
        setFrontEndPref('wantContinuousPlayback', enable)


    ###########################################################
    def OnFirstEvent(self, event=None):
        """

        @param  event  The triggering event, ignored.
        """
        if self._resultsModel.getMultipleSelected():
            return
        self._resultsModel.resetLocationInSegment()

        # On Windows, we need to make sure that our UI updates right away.
        # If we don't do this and the above code was really slow (like
        # stepBack sometimes is), the user will never get any UI update.
        # ...doesn't seem to be needed on Mac, so don't do it there...
        if wx.Platform == '__WXMSW__':
            self.Update()

    ###########################################################
    def _getCameraLocations(self):
        """ Get a complete list of camera locations
        """
        # Cameras that are currently setup; may or may not have recorded video.
        activeCameras = self._backEndClient.getCameraLocations()

        # A list of cameras that have recorded video; may or may not be
        # currently setup...
        allCameras = self._clipManager.getCameraLocations()

        # Get inactive cameras out...
        inactiveCameras = [
            camName + kInactiveSuffix
            for camName in allCameras if (
                (not camName.endswith(kImportSuffix)) and
                (camName not in activeCameras)
            )
        ]
        cameraLocations = activeCameras + inactiveCameras
        cameraLocations.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))

        return cameraLocations

    ###########################################################
    def _populateCameraChoice(self):
        """Populate the camera choice control with camera locations"""
        curSelection = self._cameraChoice.GetStringSelection()

        cameraLocations = self._getCameraLocations()

        self._cameraChoice.Clear()
        if len(cameraLocations) != 1:
            self._cameraChoice.Append(kAnyCameraStr)
        self._cameraChoice.AppendItems(cameraLocations)

        if curSelection in cameraLocations:
            self._cameraChoice.SetStringSelection(curSelection)
        else:
            self._cameraChoice.SetSelection(0)


    ###########################################################
    def _populateRuleList(self):
        """Populate the query list control"""
        location = self._cameraChoice.GetStringSelection()
        location = location.rsplit(kInactiveSuffix)[0]
        if location == kAnyCameraStr:
            location = None

        menuBar = self.GetTopLevelParent().GetMenuBar()
        if not location:
            menuBar.Enable(self._removeCameraMenuId, False)
        else:
            menuBar.Enable(self._removeCameraMenuId, True)

        ruleInfoList = self._backEndClient.getRuleInfoForLocation(location)
        self._ruleList.setRuleInfo(kSearchViewDefaultRules, ruleInfoList)


    ###########################################################
    def OnRuleMouse(self, event):
        """Ensure we behave properly if anything triggers a deselection

        @param  event  The mouse event
        """
        if self._ruleList.GetSelection() < len(kSearchViewDefaultRules):
            self._editButton.Disable()
            self._deleteButton.Disable()
            self._duplicateButton.Disable()

        event.Skip()


    ###########################################################
    def OnCameraChoice(self, event=None):
        """Populate the rule list and perform a search.

        @param  event  The event, ignored.
        """
        self._populateRuleList()
        self.OnRuleChoice()


    ###########################################################
    def OnRefresh(self, event=None):
        """Handle the refresh button.

        @param  event  The event, ignored.
        """
        self._searchTimer.Stop()

        self._searchTimer.Start(_kSearchDelay, True)


    ###########################################################
    def OnDateChanged(self, event=None):
        """Handle a change in the date.

        @param  event  The event, ignored.
        """
        self._validateDateMenuItems()
        self._searchTimer.Stop()
        self._searchTimer.Start(_kSearchDelay, True)


    ###########################################################
    def OnSortAscendDescendButton(self, event=None):
        """Handle the sort button.

        @param  event  The event, ignored.
        """
        self._resultsModel.toggleSortAscending()


    ###########################################################
    def _validateDateMenuItems(self):
        """Enable and disable the next day menu item as necessary."""
        curDate = self._datePicker.GetValue()

        self._nextDayMenuItem.Enable((curDate != datetime.date.today()) and
                                     (not self._isSearchCamImported())     )
        self._prevDayMenuItem.Enable((not self._isSearchCamImported())     )


    ###########################################################
    def OnRuleChoice(self, event=None):
        """Perform a search based on the rule selection.

        @param  event  The event, ignored.
        """
        self._searchTimer.Stop()

        # Retrieve the selected query and perform a search
        camera = self._cameraChoice.GetStringSelection()
        ruleName = self._ruleList.GetStringSelection()
        if not ruleName or not camera:
            return

        isDefaultRule = ruleName in kSearchViewDefaultRules
        self._deleteButton.Enable(not isDefaultRule)
        self._editButton.Enable(not isDefaultRule)
        self._duplicateButton.Enable(not isDefaultRule)

        self._searchCamLoc = camera.rsplit(kInactiveSuffix)[0]

        self._searchQuery = getQueryForDefaultRule(self._dataMgr, ruleName)
        if self._searchQuery is None:
            query = self._backEndClient.getQuery(ruleName)
            assert query is not None, "BackEnd returned invalid query."  # TODO: Don't start search timer...
            self._searchQuery = query.getUsableQuery(self._dataMgr)
            if camera == kAnyCameraStr:
                self._searchCamLoc = query.getVideoSource().getLocationName()

        self._adjustUiForImportedCam()

        self._searchTimer.Start(_kSearchDelay, True)


    ###########################################################
    def _isSearchCamImported(self):
        """Return true if the current search cam is imported.

        @return isImported  True if the current search cam was imported.
        """
        return self._searchCamLoc.endswith(kImportSuffix)


    ###########################################################
    def _adjustUiForImportedCam(self):
        """Adjust the UI based on whether the currently selected cam is imported

        Don't let this be too slow--it's called every time the user chooses a
        new rule.
        """
        isCamImported = self._isSearchCamImported()

        # Just hide the "when" label and date picker; the time bar will auto
        # hide itself when it realizes that a date wasn't used in the search.
        uiToHide = [
            self._whenLabel, self._datePicker,
        ]

        for uiElement in uiToHide:
            uiElement.Show(not isCamImported)

        # May need to enable/disable date menu items...
        self._validateDateMenuItems()


    ###########################################################
    def OnThrobberTimer(self, event):
        """Update the spinner

        @param  event  The timer event
        """
        self._throbberBmps[self._curThrobberId].Hide()
        self._curThrobberId = (self._curThrobberId+1) % len(self._throbberBmps)
        self._throbberBmps[self._curThrobberId].Show()
        self._throbberBmps[0].GetParent().Update()

        # Periodically cause the "Searching on <camera>..." text to update in
        # the results list.
        if self._curThrobberId == 0:
            self._resultsList.Refresh()


    ###########################################################
    def OnSearchTimer(self, event):
        """Execute the specified search

        @param  event  The timer event
        """
        # If the video directory is not available we want to prompt the user
        # rather than searching.
        videoDir = os.path.join(self._backEndClient.getVideoLocation(),
                                kVideoFolder)
        if not os.path.isdir(videoDir):
            dlg = LocateVideoDialog(self, self._backEndClient, self._dataMgr)
            try:
                dlg.ShowModal()
            finally:
                dlg.Destroy()

            # Check if there is a video directory available now, if there is
            # allow the search, else return.
            videoDir = self._backEndClient.getVideoLocation()
            if not os.path.isdir(videoDir):
                return

        # Do the search.
        self._doSearch(self._searchQuery, self._searchCamLoc)


    ###########################################################
    def _doSearch(self, query, camLoc):
        """Execute a search and update the results list

        @param  query   The query to execute
        @param  camLoc  The camera location to filter the search by
        """
        # Stop any worker threads in the search results list...
        self._resultsList.stopLoader()

        cameraList = [camLoc]

        if camLoc == kAnyCameraStr:
            cameraList = [cameraName.rsplit(kInactiveSuffix)[0] for cameraName
                          in self._cameraChoice.GetStrings()[1:]
                          if (not cameraName.endswith(kImportSuffix))]

        # Figure out what date we're searching for...
        if self._isSearchCamImported():
            searchDate = None
        else:
            searchDate = self._datePicker.GetValue()

            if searchDate == datetime.date.today():
                self._refreshButton.Enable(True)
            else:
                self._refreshButton.Enable(False)

        # Do the search.
        try:
            self._resultsModel.doSearch(query, cameraList, searchDate,
                                        self._backEndClient.flushVideo)
        except DatabaseError, e:
            self._logger.error("Database exception during search.",
                               exc_info=True)
            if e.message in kCorruptDbErrorStrings:
                self._backEndClient.sendCorruptDbMessage()
            raise



    ###########################################################
    def OnMarkupMenuItemChange(self, event=None):
        """Handle changes to one of the markup-related menu items.

        We just have one handler for all 3 menu items, since it's pretty easy
        and quick to just update the model for all 3 at once.

        @param  event  The menu event.
        """
        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()

        if self._overlayTimestamp is not None:
            self._markupModel.setOverlayTimestamp(
                menuBar.IsChecked(self._overlayTimestamp)
            )
        self._markupModel.setPlayAudio(
            not menuBar.IsChecked(self._muteAudio)
        )
        self._markupModel.setShowBoxesAroundObjects(
            menuBar.IsChecked(self._showBoxesAroundObjectsMenuId)
        )
        if menuBar.IsEnabled(self._showDifferentColorBoxesMenuId):
            # Only pay attention to the "show different color boxes" menu
            # item if it's enabled.  That's because we uncheck it when it's
            # disabled due to not showing boxes at all...
            self._markupModel.setShowDifferentColorBoxes(
                menuBar.IsChecked(self._showDifferentColorBoxesMenuId)
            )
        self._markupModel.setShowRegionZones(
            menuBar.IsChecked(self._showRegionZonesMenuId)
        )


    ###########################################################
    def _handleSort(self, resultsModel):
        """Update the sort buttons to reflect the current state of resultsModel.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        self._resultsSortAscendingButton.Show(
            resultsModel.isSortAscending()
        )
        self._resultsSortDescendingButton.Show(
            not resultsModel.isSortAscending()
        )


    ###########################################################
    def _handleDebugModeChange(self, debugModeModel):
        """Update the debug info.

        @param  debugModeModel  Should be self._debugModeModel
        """
        assert debugModeModel == self._debugModeModel

        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()

        if debugModeModel.isDebugMode():
            self._overlayTimestamp = menuBar.FindMenuItem("Debug", "Overlay Timestamp On Clips")
            topWin.Bind(wx.EVT_MENU, self.OnMarkupMenuItemChange, id=self._overlayTimestamp)
            menuBar.Check(self._overlayTimestamp, self._markupModel.getOverlayTimestamp())
        else:
            topWin.Unbind(wx.EVT_MENU, id=self._overlayTimestamp)
            self._overlayTimestamp = None


        self._markupModel.setShowLabels(debugModeModel.isDebugMode())
        self._markupModel.setShowObjIds(debugModeModel.isDebugMode())

        # Repopulate the clip list
        self.OnRefresh()


    ###########################################################
    def _handleMarkupChange(self, markupModel, whatChanged):
        """Handle changes in the markup model.

        We are in charge of updating:
        - front end preferences
        - menus
        - search results data model (we need to tell it to reload the current
          frame).

        We don't handle the SearchList--that listens for changes itself.

        @param  markupModel  Should be self._markupModel.
        @param  whatChanged  The thing that changed; if None, assume that
                             everything changed.
        """
        assert markupModel == self._markupModel

        menuBar = self.GetTopLevelParent().GetMenuBar()

        if (whatChanged == 'showBoxesAroundObjects') or (not whatChanged):
            showBoxesAroundObjects = markupModel.getShowBoxesAroundObjects()
            showDifferentColorBoxes = markupModel.getShowDifferentColorBoxes()

            # Make sure prefs are saved...
            setFrontEndPref('showBoxesAroundObjects', showBoxesAroundObjects)

            # Update menu item...
            menuBar.Check(self._showBoxesAroundObjectsMenuId,
                          showBoxesAroundObjects)

            # Disable / enable showDifferentColorBoxes, which can only be used
            # if showBoxesAroundObjects is checked...
            menuBar.Enable(self._showDifferentColorBoxesMenuId,
                           showBoxesAroundObjects)
            menuBar.Check(self._showDifferentColorBoxesMenuId,
                          showBoxesAroundObjects and showDifferentColorBoxes)
        if (whatChanged == 'showDifferentColorBoxes') or (not whatChanged):
            showDifferentColorBoxes = markupModel.getShowDifferentColorBoxes()

            # Make sure prefs are saved...
            setFrontEndPref('showDifferentColorBoxes', showDifferentColorBoxes)

            # Update menu item...
            menuBar.Check(self._showDifferentColorBoxesMenuId,
                          showDifferentColorBoxes)
        if (whatChanged == 'showRegionZones') or (not whatChanged):
            showRegionZones = markupModel.getShowRegionZones()

            # Make sure prefs are saved...
            setFrontEndPref('showRegionZones', showRegionZones)

            # Update menu item...
            menuBar.Check(self._showRegionZonesMenuId, showRegionZones)
        if (whatChanged == 'showLabels') or (not whatChanged):
            pass
        if (whatChanged == 'showObjIds') or (not whatChanged):
            pass
        if (whatChanged == 'playAudio') or (not whatChanged):
            playAudio = markupModel.getPlayAudio()
            # Make sure prefs are saved...
            setFrontEndPref('playAudio', playAudio)
            # Update menu item...
            menuBar.Check(self._muteAudio, not playAudio)
        if ((whatChanged == 'overlayTimestamp') or (not whatChanged)) \
            and self._overlayTimestamp is not None:
            overlayTimestamp = markupModel.getOverlayTimestamp()
            # Make sure prefs are saved...
            setFrontEndPref('overlayTimestamp', overlayTimestamp)
            # Update menu item...
            menuBar.Check(self._overlayTimestamp, overlayTimestamp)


        self._resultsModel.reloadCurrentClip()


    ###########################################################
    def _handleSearchResultsChange(self, resultsModel):
        """Handle a change in search results.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        self._updateResultsCounter()
        self._throbberTimer.Stop()
        for bmp in self._throbberBmps:
            bmp.Hide()
        self._refreshButton.Show()


    ###########################################################
    def _handleSearch(self, resultsModel):
        """Handle a change in search results.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        self._resultsCounter.SetLabel("")
        self._throbberBmps[self._curThrobberId].Show()
        self._throbberTimer.Start(_kThrobberDelay)
        self._refreshButton.Hide()


    ###########################################################
    def updateCameraChoices(self):
        """Ensure the camera choice list is up to date"""
        curSelection = self._cameraChoice.GetStringSelection()
        self._populateCameraChoice()
        self._cameraChoice.SetStringSelection(curSelection)

        self.OnRuleChoice()


    ###########################################################
    def OnEditQuery(self, event=None):
        """Edit the selected query

        @param  event  The button event, ignored
        """
        # Get the selected query
        queryName = self._ruleList.GetStringSelection()
        if not queryName or queryName in kSearchViewDefaultRules:
            return

        query = self._backEndClient.getQuery(queryName)
        if query is None:
            wx.MessageBox("Couldn't find the rule \"%s\"." % (queryName),
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            return

        # Edit the specified query
        dlg = QueryEditorDialog(self.GetTopLevelParent(), self._dataMgr,
                                self._backEndClient, query,
                                set(kSearchViewDefaultRules +
                                    self._backEndClient.getRuleNames()) -
                                set([query.getName()]),
                                [camName.rsplit(kInactiveSuffix)[0] for camName
                                 in self._cameraChoice.GetStrings()])
        try:
            result = dlg.ShowModal()
        finally:
            dlg.Destroy()

        if result == wx.ID_CANCEL:
            return

        self._backEndClient.editQuery(query, queryName)

        newName = query.getName()
        cameraLocation = query.getVideoSource().getLocationName()
        if cameraLocation not in self._cameraChoice.GetStrings():
            cameraLocation += kInactiveSuffix
        self._cameraChoice.SetStringSelection(cameraLocation)
        self._populateRuleList()
        if newName in self._ruleList.GetStrings():
            self._ruleList.SetStringSelection(newName)

        self._populateRuleList()
        if newName in self._rules:
            self._ruleList.SetStringSelection(newName)

        # Rerun the search so that it is up to date
        self.OnRuleChoice()


    ###########################################################
    def _updateResultsCounter(self):
        """Ensure the results counter is displaying the correct information"""
        if self._resultsModel.didSearch():
            numResults = self._resultsModel.getNumMatchingClips()
            self._resultsCounter.SetLabel("%i Results" % numResults)
            # The results label is potentially changing sizes here. Force a
            # layout to display ourselves properly...
            self._resultsCounter.GetContainingSizer().Layout()
        else:
            pass

    ###########################################################
    def _setMenuItemsStatus(self, enable):
        # Enable menus...
        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()
        menuBar.Enable(self._showBoxesAroundObjectsMenuId, enable)
        menuBar.Enable(self._showDifferentColorBoxesMenuId,
                       self._markupModel.getShowBoxesAroundObjects() and enable)
        menuBar.Enable(self._showRegionZonesMenuId, enable)
        menuBar.Enable(self._selectAllClipsMenuId, enable)
        menuBar.Enable(self._continuousEventMenuId, enable)
        menuBar.Enable(self._muteAudio, enable)
        if self._overlayTimestamp is not None:
            menuBar.Enable(self._overlayTimestamp, enable)
        self._videoPanel.enableMenuItems(enable)
        for menuItem in self._menuItemsEnabledWithView:
            menuBar.Enable(menuItem, enable)
        if enable:
            menuBar.Enable(self._continuousEventMenuId, True)
            topWin.Bind(wx.EVT_MENU, self.OnRemoveCamera,
                        id=self._removeCameraMenuId)
            topWin.Bind(wx.EVT_MENU, self.OnMarkupMenuItemChange,
                        id=self._muteAudio)
        else:
            for menuItem in self._controlsMenuItems:
                menuBar.Enable(menuItem, False)
            topWin.Unbind(wx.EVT_MENU, id=self._removeCameraMenuId)
            topWin.Unbind(wx.EVT_MENU, id=self._muteAudio)


    ###########################################################
    def setActiveView(self, viewParams={}):
        """
        @see  BaseView.setActiveView
        """
        super(SearchView, self).setActiveView(viewParams)

        self.SetFocusIgnoringChildren()

        self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_ADDED,
                              self.OnCameraAdded)
        self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_EDITED,
                              self.OnCameraEdited)
        self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_REMOVED,
                              self.OnCameraRemoved)

        # Enable menus...
        self._setMenuItemsStatus(True)
        self._validateDateMenuItems()
        self._prevDayMenuItem.Enable(True)


        self._populateCameraChoice()
        if kCameraNameParam in viewParams:
            camName = viewParams[kCameraNameParam]
            if camName not in self._cameraChoice.GetStrings():
                camName+= kInactiveSuffix
            self._cameraChoice.SetStringSelection(camName)

        self._populateRuleList()
        if kQueryNameParam in viewParams:
            self._ruleList.SetStringSelection(viewParams[kQueryNameParam])

        self.OnRuleChoice()


    ###########################################################
    def deactivateView(self):
        """
        @see  BaseView.deactivateView
        """
        # Ensure that the search results data model and any controls listening
        # to it aren't going to do any more work.
        self._searchTimer.Stop()
        self._resultsModel.abortProcessing()

        # Stop any worker threads in the search results list...
        self._resultsList.stopLoader()

        # Disable menus...
        topWin = self.GetTopLevelParent()
        self._setMenuItemsStatus(False)

        self.GetParent().Unbind(FrontEndEvents.EVT_CAMERA_ADDED)
        self.GetParent().Unbind(FrontEndEvents.EVT_CAMERA_EDITED)
        self.GetParent().Unbind(FrontEndEvents.EVT_CAMERA_REMOVED)

        super(SearchView, self).deactivateView()


    ###########################################################
    def OnNewRule(self, event):
        """Display the QueryEditorDialog with a new query

        @param  event  The button event
        """
        if event.GetEventObject() == self._duplicateButton:
            # Start with a copy of the currently selected rule...
            ruleName = self._ruleList.GetStringSelection()
            if not ruleName:
                return
            newQuery = self._backEndClient.getQuery(ruleName)

            # Set the name of the rule to ""; this will change when we get
            # auto-rule naming...
            newQuery.setName("")
        else:
            assert event.GetEventObject() == self._addButton
            newQuery = SavedQueryDataModel("")

            # Try our darndest not to start out the new query with "Any camera"
            cameraLoc = self._searchCamLoc
            if cameraLoc == kAnyCameraStr:
                try:
                    cameraLoc = self._cameraChoice.GetStrings()[1]
                    cameraLoc = cameraLoc.rsplit(kInactiveSuffix)[0]
                except IndexError: pass
            newQuery.getVideoSource().setLocationName(cameraLoc)

        # Edit the specified query
        dlg = QueryEditorDialog(self.GetTopLevelParent(), self._dataMgr,
                                self._backEndClient, newQuery,
                                kSearchViewDefaultRules +
                                self._backEndClient.getRuleNames(),
                                [camName.rsplit(kInactiveSuffix)[0] for camName
                                 in self._cameraChoice.GetStrings()])
        try:
            result = dlg.ShowModal()
        finally:
            dlg.Destroy()

        # If the user cancels the dialog, do nothing
        if result == wx.ID_CANCEL:
            return

        # Save the new query
        self._backEndClient.addRule(newQuery, True)

        cameraLocation = newQuery.getVideoSource().getLocationName()
        self._cameraChoice.SetStringSelection(cameraLocation)
        self._populateRuleList()
        if newQuery.getName() in self._ruleList.GetStrings():
            self._ruleList.SetStringSelection(newQuery.getName())

        # Insure the search list is up to date with the current selections
        self.OnRuleChoice()


    ###########################################################
    def OnDeleteRule(self, event=None):
        """Delete the selected rule.

        @param  event  The button event, ignored.
        """
        ruleName = self._ruleList.GetStringSelection()

        if wx.NO == wx.MessageBox("Delete the rule \"%s\"?" % ruleName,
                                  "Delete rule",
                                  wx.YES_NO | wx.ICON_QUESTION,
                                  self.GetTopLevelParent()):
            return

        self._backEndClient.deleteRule(ruleName)
        self._populateRuleList()

        self.OnRuleChoice()


    ###########################################################
    def OnCameraAdded(self, event):
        """Update the UI to include the newly added camera.

        @param  event  The camera added event.
        """
        if not self._isActiveView:
            return

        cameraLocation = event.getLocation()

        self._populateCameraChoice()
        self._cameraChoice.SetStringSelection(cameraLocation)
        self._populateRuleList()
        self.OnRuleChoice()

        event.Skip()


    ###########################################################
    def OnCameraEdited(self, event):
        """Respond to a camera edit if necessary.

        @param  event  The camera edited event.
        """
        if not self._isActiveView:
            return

        _, newLocation = event.getLocations()

        if newLocation not in self._cameraChoice.GetItems():
            self._populateCameraChoice()
            self.OnRuleChoice()

        event.Skip()


    ###########################################################
    def OnCameraRemoved(self, event):
        """Respond to a camera removal if necessary.

        @param  event  The camera edited event.
        """
        if not self._isActiveView:
            return

        self._populateCameraChoice()
        self._populateRuleList()
        self.OnRuleChoice()

        event.Skip()


    ###########################################################
    def OnDeleteProgressActivate(self, event):
        """Handle an activate event.

        @param  event  The EVT_ACTIVATE event.
        """
        eventObj = event.GetEventObject()
        def safeRaise():
            try:
                eventObj.Raise()
            except Exception:
                pass
        wx.CallAfter(safeRaise)


    ###########################################################
    def OnDeleteClip(self, event=None):
        """Delete the current clip.

        @param  event  The menu event, ignored.
        """
        multiple = self._resultsModel.getMultipleSelected()

        startTime = self._resultsModel.getCurrentClipStart()
        stopTime = self._resultsModel.getCurrentClipStop()
        cameraName = self._resultsModel.getCurrentCameraName()

        if not multiple and not self._resultsModel.isCurrentClipMatching():
            # If we're deleting from the cache check if we need to trim the
            # delete down to something reasonable.
            duration = (stopTime - startTime) + 1

            if duration > _kMaxCacheDurationMs:
                result = wx.MessageBox(_kCacheClipWarningStr,
                                       _kCacheClipCaptionStr, wx.ICON_WARNING |
                                       wx.OK | wx.CANCEL,
                                       self.GetTopLevelParent())
                if result != wx.OK:
                    return

                absMs = self._resultsModel.getCurrentAbsoluteMs()
                rewindAmt = _kMaxCacheDurationMs/2

                if (absMs + rewindAmt) > stopTime:
                    startTime = (stopTime - _kMaxCacheDurationMs) + 1
                else:
                    startTime = max(startTime, absMs - rewindAmt)
                    stopTime = (startTime + _kMaxCacheDurationMs) - 1
            else:
                if wx.NO == wx.MessageBox("Delete the current clip? This operation "
                                          "cannot be undone.", "Delete clip",
                                          wx.YES_NO | wx.ICON_QUESTION,
                                          self.GetTopLevelParent()):
                    return

            startSec = int(math.floor(startTime/1000.))
            stopSec = int(math.ceil(stopTime/1000.))

            # Perform the delete operation.
            self._backEndClient.deleteVideo(cameraName, startSec, stopSec, False)

            # Block until the operation has completed.
            progDlg = wx.ProgressDialog("Deleting..." ,
                                    "Just a moment...                         ",
                                    parent=self.GetTopLevelParent(),
                                    style=wx.PD_APP_MODAL)
            progDlg.Bind(wx.EVT_ACTIVATE, self.OnDeleteProgressActivate)
            try:
                mid = (stopTime+startTime)/2
                while len(self._clipManager.getFilesBetween(cameraName,
                                                            mid, mid)):
                    progDlg.Pulse()
                    time.sleep(.2)
            finally:
                progDlg.Unbind(wx.EVT_ACTIVATE)
                progDlg.Destroy()

        # If we're not deleting a cache clip, use the DeleteClipDialog.
        else:
            clipList = []
            if not multiple and cameraName:
                clipList = [(cameraName, int(math.floor(startTime/1000.)),
                             int(math.ceil(stopTime/1000.)))]
            else:
                ids = self._resultsModel.getSelectedIds()
                for clipId in ids:
                    cam, startMs, stopMs = \
                                self._resultsModel.getClipInformation(clipId)
                    clipList.append((cam, int(math.floor(startMs/1000.)),
                                     int(math.ceil(stopMs/1000.))))

            result = None
            dlg = DeleteClipDialog(self.GetTopLevelParent(),
                                   self._backEndClient, self._dataMgr,
                                   self._clipManager, clipList)
            try:
                result = dlg.ShowModal()
            finally:
                dlg.Destroy()

            if result == wx.CANCEL:
                return

        # Update the current view.
        self.OnRefresh()


    ###########################################################
    def OnSelectAllClips(self, event=None):
        """Select all clips.

        @param  event  The event (ignored).
        """
        totalNumClips = len(self._resultsModel.getMatchingClips())

        # Put the last item currently selected at the end of the selection
        # list, which will keep us from scrolling the list...
        oldSelected = self._resultsModel.getSelectedIds()
        if oldSelected:
            lastSelected = int(oldSelected[-1])
            newSelected = range(0, lastSelected) + \
                          range(lastSelected+1, totalNumClips) + \
                          [lastSelected]
        else:
            newSelected = range(0, totalNumClips)

        self._resultsModel.setMultipleSelected(True, newSelected)


    ###########################################################
    def OnRemoveCamera(self, event=None):
        """Remove the currently selected camera.

        @param  event  The menu event (ignored).
        """
        cam = self._cameraChoice.GetStringSelection()
        cam = cam.rsplit(kInactiveSuffix)[0]
        if cam == kAnyCameraStr or not cam:
            return

        # Remove the camera
        if not removeCamera(self, cam, self._dataMgr, self._backEndClient):
            return

        self._populateCameraChoice()
        self._populateRuleList()
        self.OnRuleChoice()


    ###########################################################
    def _handleTimePrefChange(self, uiModel):
        """Handle a change to time display preferences.

        @param  resultsModel  The UIPrefsDataModel.
        """
        use12, useUS = uiModel.getTimePreferences()
        self._datePicker.useUSDateFormat(useUS)
        self._markupModel.set12HrTime(use12)
        self._markupModel.setUSDate(useUS)


if __name__ == '__main__':
    from FrontEndApp import main
    main()
