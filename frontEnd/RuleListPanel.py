#!/usr/bin/env python

#*****************************************************************************
#
# RuleListPanel.py
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
import time
import locale

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from vitaToolbox.wx.BetterScrolledWindow import BetterScrolledWindow
from vitaToolbox.wx.BorderImagePanel import BorderImagePanel
from vitaToolbox.wx.GradientEndedLine import GradientEndedLine
from vitaToolbox.wx.HoverBitmapButton import HoverBitmapButton
from vitaToolbox.wx.HoverButton import HoverButton
from vitaToolbox.wx.HoverButton import kHoverButtonNormalColor_Plate
from vitaToolbox.wx.HoverButton import kHoverButtonDisabledColor_Plate
from vitaToolbox.wx.HoverButton import kHoverButtonPressedColor_Plate
from vitaToolbox.wx.HoverButton import kHoverButtonHoverColor_Plate
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.TextSizeUtils import makeFontDefault
from vitaToolbox.wx.TranslucentStaticText import TranslucentStaticText
from vitaToolbox.sysUtils.TimeUtils import formatTime

# Local imports...
from appCommon.CommonStrings import kCommandResponse
from appCommon.CommonStrings import kEmailResponse
from appCommon.CommonStrings import kIftttResponse
from appCommon.CommonStrings import kWebhookResponse
from appCommon.CommonStrings import kPushResponse
from appCommon.CommonStrings import kRecordResponse
from appCommon.CommonStrings import kSearchViewDefaultRules
from appCommon.CommonStrings import kSoundResponse
from appCommon.CommonStrings import kFtpResponse
from appCommon.CommonStrings import kLocalExportResponse
from backEnd.SavedQueryDataModel import SavedQueryDataModel
from QueryEditorDialog import QueryEditorDialog
from RuleScheduleDialog import RuleScheduleDialog


_kCtrlPadding = 8
_kShadowSize = 4
_kDividerEdgeColorWin = (171, 214, 245, 0)
_kDividerColorWin = (171, 214, 245, 255)
_kDividerEdgeColorMac = (180, 180, 180, 0)
_kDividerColorMac = (180, 180, 180, 255)
_kMaxGradientWidth = 98
_kDividerHeight = 2
_kMinHeight = 140

_kResponseBitmapMap = {
    kCommandResponse : ("frontEnd/bmps/Response_Command_Enabled.png",
                        "frontEnd/bmps/Response_Command_Disabled.png"),
    kEmailResponse :   ("frontEnd/bmps/Response_Email_Enabled.png",
                        "frontEnd/bmps/Response_Email_Disabled.png"),
    kIftttResponse :    ("frontEnd/bmps/Response_Email_Enabled.png",
                         "frontEnd/bmps/Response_Email_Disabled.png"),
    kWebhookResponse :  ("frontEnd/bmps/Response_Email_Enabled.png",
                         "frontEnd/bmps/Response_Email_Disabled.png"),
    kPushResponse :    ("frontEnd/bmps/Response_Email_Enabled.png",
                        "frontEnd/bmps/Response_Email_Disabled.png"),
    kRecordResponse :  ("frontEnd/bmps/Response_Save_Enabled.png",
                        "frontEnd/bmps/Response_Save_Disabled.png"),
    kSoundResponse :   ("frontEnd/bmps/Response_Sound_Enabled.png",
                        "frontEnd/bmps/Response_Sound_Disabled.png"),
    kFtpResponse:      ("frontEnd/bmps/Response_SendClip_Enabled.png",
                        "frontEnd/bmps/Response_SendClip_Disabled.png"),
    kLocalExportResponse:  ("frontEnd/bmps/Response_SendClip_Enabled.png",
                            "frontEnd/bmps/Response_SendClip_Disabled.png"),
}

_kUS12 = "%B %d, %Y - %I:%M:%S %p"
_kUS24 = "%B %d, %Y - %H:%M:%S"
_kNonUS12 = "%d %B %Y - %I:%M:%S %p"
_kNonUS24 = "%d %B %Y - %H:%M:%S"


class RuleListPanel(BorderImagePanel):
    """Implements a panel for displaying and configuring rules."""
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, searchFunc,
                 cameraEnabledModel):
        """The initializer for RuleListPanel.

        @param  parent              The parent Window.
        @param  backEndClient       A connection to the back end app.
        @param  dataManager         The data manager for the app.
        @param  searchFunc          The function to call when a search is
                                    requested.  Takes camera location & query
                                    name as a parameter.
        @param  cameraEnabledModel  A data model that provides updates when
                                    cameras are enabled or disabled.
        """
        # Call the base class initializer
        super(RuleListPanel, self).__init__(parent, -1,
                                    'frontEnd/bmps/RaisedPanelBorder.png', 8)

        self._backEndClient = backEndClient
        self._dataManager = dataManager
        self._searchFunc = searchFunc
        self._cameraEnabledModel = cameraEnabledModel

        # Register with the data model.
        self._cameraEnabledModel.addListener(self._handleCameraEnable,
                                             wantKeyParam=True)

        # Register for time preference changes.
        self.GetTopLevelParent().getUIPrefsDataModel().addListener(
                self._handleTimePrefChange, key='time')

        self._timeFormatString = _kNonUS24

        # Initialize the UI controls
        self._initUi()

        self._curLocation = None
        self._controls = {}

        # Create a timer to update the time label
        self._dateTimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnDateTimer)
        self._dateTimer.Start(1000, False)

        minw, minh = self.GetMinSize()
        self.SetMinSize((minw, max(minh, _kMinHeight)))


    ###########################################################
    def _initUi(self):
        """Initialize the UI controls."""
        # Horizontal sizer with Record Icon/Camera Name/Date/Responses
        topSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._recordingEnabledButton = \
            HoverBitmapButton(self, wx.ID_ANY,
                                'frontEnd/bmps/Monitor_On_Enabled.png',
                                wx.EmptyString,
                                'frontEnd/bmps/Monitor_On_Pressed.png',
                                'frontEnd/bmps/Monitor_Off_Enabled.png',
                                'frontEnd/bmps/Monitor_On_Hover.png')
        self._recordingDisabledButton = \
            HoverBitmapButton(self, wx.ID_ANY,
                                'frontEnd/bmps/Monitor_Off_Enabled.png',
                                wx.EmptyString,
                                'frontEnd/bmps/Monitor_Off_Pressed.png',
                                'frontEnd/bmps/Monitor_Off_Enabled.png',
                                'frontEnd/bmps/Monitor_Off_Hover.png')
        self._recordingDisabledButton.Show(False)
        self._recordingEnabledButton.Disable()
        self._recordingDisabledButton.Disable()
        self._offText = TranslucentStaticText(self, -1, "Off")
        self._offText.Hide()
        self._onText = TranslucentStaticText(self, -1, "On")
        makeFontDefault(self._offText, self._onText)

        self._camLocLabel = TranslucentStaticText(self, -1,
                                                  "No Camera Selected",
                                                  style=wx.ST_ELLIPSIZE_END |
                                                        wx.ALIGN_CENTER)
        self._camLocLabel.SetMinSize((1, -1))
        font = self._camLocLabel.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self._camLocLabel.SetFont(font)
        self._dateLabel = TranslucentStaticText(self, -1, "")
        makeFontDefault(self._dateLabel)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        overlapSizer = OverlapSizer(True)
        overlapSizer.Add(self._recordingEnabledButton)
        overlapSizer.Add(self._recordingDisabledButton)
        hSizer.Add(overlapSizer, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                   _kCtrlPadding/2)
        hSizer.Add(self._offText, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                   _kCtrlPadding)
        hSizer.Add(self._onText, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                   _kCtrlPadding)
        topSizer.Add(hSizer, 0)
        topSizer.Add(self._camLocLabel, 1, wx.ALL |
                     wx.ALIGN_CENTER_VERTICAL, _kCtrlPadding)
        hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        hSizer2.Add(self._dateLabel, 0, wx.TOP | wx.LEFT | wx.BOTTOM |
                    wx.ALIGN_CENTER_VERTICAL, _kCtrlPadding)
        hSizer2.AddSpacer(10+_kShadowSize)
        topSizer.Add(hSizer2, 0, wx.EXPAND )

        # Add the dividing line
        isWin = wx.Platform == '__WXMSW__'
        if isWin:
            dividingLine = GradientEndedLine(self, _kDividerColorWin,
                                             _kDividerEdgeColorWin,
                                             _kDividerHeight,
                                             _kMaxGradientWidth)
        else:
            dividingLine = GradientEndedLine(self, _kDividerColorMac,
                                             _kDividerEdgeColorMac,
                                             _kDividerHeight,
                                             _kMaxGradientWidth)

        # A scrolling window to contain the actual list of rules
        self._ruleWin = BetterScrolledWindow(self, -1, osxFix=(not isWin),
                                             style=wx.TRANSPARENT_WINDOW,
                                             redrawFix=isWin)
        self._ruleWin.SetBackgroundStyle(kBackgroundStyle)
        self._ruleSizer = wx.FlexGridSizer(cols=5, vgap=_kCtrlPadding/2,
                                           hgap=_kCtrlPadding/2)
        self._ruleSizer.AddGrowableCol(1, 1)
        self._ruleSizer.AddGrowableCol(2, 1)
        self._ruleWin.SetSizer(self._ruleSizer)

        # A new rule link for when a camera has none.
        self._newHyperlink = HoverButton(self, "Add new rule...",
                                         style=wx.ALIGN_LEFT)
        makeFontDefault(self._newHyperlink)
        hyperlinkSizer = wx.FlexGridSizer(2, 2, 0, 0)
        hyperlinkSizer.AddGrowableCol(1)
        hyperlinkSizer.AddGrowableRow(1)
        hyperlinkSizer.Add(self._newHyperlink)

        # Set the main sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(topSizer, 0, wx.EXPAND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(dividingLine, 1)
        hSizer.AddSpacer(_kShadowSize)
        sizer.Add(hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        overlapSizer = OverlapSizer(True)

        overlapSizer.Add(hyperlinkSizer, 1, wx.EXPAND | wx.ALL, _kCtrlPadding)
        overlapSizer.Add(self._ruleWin, 1, wx.EXPAND | wx.ALL, 10)
        sizer.Add(overlapSizer, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # The following will be used for the popup menu we create when
        # the user selects a rule.
        self._editId = wx.NewId()
        self._newId = wx.NewId()
        self._deleteId = wx.NewId()
        self.Bind(wx.EVT_MENU, self.OnEdit, id=self._editId)
        self.Bind(wx.EVT_MENU, self.OnNew, id=self._newId)
        self.Bind(wx.EVT_MENU, self.OnDelete, id=self._deleteId)
        self._ruleMenu = wx.Menu()
        self._ruleMenu.Append(self._editId, "Edit Rule...")
        self._ruleMenu.Append(self._newId, "New Rule...")
        self._ruleMenu.Append(self._deleteId, "Delete Rule...")

        self._newHyperlink.Bind(wx.EVT_BUTTON, self.OnNew)

        self._recordingEnabledButton.Bind(wx.EVT_BUTTON, self.OnEnableDisable)
        self._recordingDisabledButton.Bind(wx.EVT_BUTTON, self.OnEnableDisable)

        # Initialize the rules lists
        self._rulesCache = {}
        self.updateRulesCache()

        # Initialize the date text
        self.OnDateTimer()


    ###########################################################
    def OnDateTimer(self, event=None):
        """Update the UI to reflect the current time.

        @param event  The timer event (ignored).
        """

        prevText = self._dateLabel.GetLabel()
        newText = formatTime(self._timeFormatString)

        if prevText != newText:
            self._dateLabel.SetLabel(newText)
            self.Layout()


    ###########################################################
    def setCameraLocation(self, cameraLocation):
        """Update the UI to reflect a given camera location.

        @param cameraLocation  The name of the camera to display rules for.
        """
        self._ruleSizer.Clear(True)
        self._curLocation = cameraLocation

        # If no camera is selected exit
        if not cameraLocation:
            self._newHyperlink.Hide()
            self._camLocLabel.SetLabel("No Camera Selected")
            self._offText.Hide()
            self._onText.Show(True)
            self._recordingEnabledButton.Disable()
            self._recordingDisabledButton.Disable()
            self.Layout()
            return

        self._camLocLabel.SetLabel(cameraLocation)

        _, _, enabled, _ = \
                        self._backEndClient.getCameraSettings(cameraLocation)

        self._onText.Show(enabled)
        self._offText.Show(not enabled)
        self._recordingEnabledButton.Show(enabled)
        self._recordingDisabledButton.Show(not enabled)
        self._recordingEnabledButton.Enable()
        self._recordingDisabledButton.Enable()

        # Retrieve information about rules at this location
        self.updateRulesCache(cameraLocation)
        self._controls = {}
        for ruleName, queryName, schedStr, enabled, responses in \
                self._rulesCache.get(cameraLocation, []):
            self._getRuleControls(ruleName, queryName, schedStr, enabled,
                                  responses)
        self._addControls()


    ###########################################################
    def _getRuleControls(self, ruleName, queryName, schedStr, enabled,
                         responses):
        """Create controls for a rule.

        @param  ruleName   The name of the rule.
        @param  queryName  The name of the rule's query.
        @param  schedStr   A string representation of the rule's schedule.
        @param  enabled    True if the rule is enabled.
        @param  responses  A list of names of enabled responses.
        """
        # Create a shortcut to the search
        searchIcon = HoverBitmapButton(self._ruleWin, wx.ID_ANY,
                                   'frontEnd/bmps/Search_link_enabled.png',
                                    wx.EmptyString,
                                   'frontEnd/bmps/Search_link_pressed.png',
                                   'frontEnd/bmps/Search_link_disabled.png',
                                   'frontEnd/bmps/Search_link_hover.png',
                                   useMask=False)
        # Create a check box indicating whether the control is enabled
        checkBox = wx.CheckBox(self._ruleWin, name=ruleName)
        checkBox.SetValue(enabled)
        checkBox.Show(len(responses) != 0)
        # Create a control for accessing operations for the rule
        nameButton = \
            HoverButton(self._ruleWin, queryName,
                        kHoverButtonNormalColor_Plate,
                        kHoverButtonDisabledColor_Plate,
                        kHoverButtonPressedColor_Plate,
                        kHoverButtonHoverColor_Plate, -1, style=wx.ALIGN_LEFT,
                        ignoreExtraSpace=True)
        nameButton.SetMinSize((1, -1))
        nameButton.SetName(ruleName)
        makeFontDefault(nameButton)
        nameButton.SetMenu(self._ruleMenu)
        # Create a control for accessing the schedule
        schedButton = HoverButton(self._ruleWin, schedStr, style=wx.ALIGN_LEFT,
                                  ignoreExtraSpace=True)
        schedButton.SetMinSize((1, -1))
        makeFontDefault(schedButton)
        schedButton.Show(len(responses) != 0)
        # Create controls for displaying information about responses
        responseControls = []
        alreadyAdded = set()
        for response in responses:
            enabledBmp, disabledBmp = _kResponseBitmapMap[response]
            if ((enabledBmp, disabledBmp)) not in alreadyAdded:
                button = HoverBitmapButton(self._ruleWin, wx.ID_ANY, enabledBmp, wx.EmptyString,
                                           bmpDisabled=disabledBmp, useMask=False)
                button.Enable(enabled)
                responseControls.append(button)

            # Keep track of bitmaps we've already added.  If two responses
            # use the same icon, we don't want to add twice.
            alreadyAdded.add((enabledBmp, disabledBmp))

        self._controls[ruleName] = [searchIcon, checkBox, nameButton,
                                    schedButton, responseControls]

        # Bind to events
        searchIcon.Bind(wx.EVT_BUTTON, self.OnSearch)
        checkBox.Bind(wx.EVT_CHECKBOX, self.OnCheckBox)
        schedButton.Bind(wx.EVT_BUTTON, self.OnScheduleButton)
        for control in responseControls:
            control.Bind(wx.EVT_BUTTON, self.OnEdit)


    ###########################################################
    def _addControls(self):
        """Add all controls to the list in a sorted order."""
        self._ruleSizer.Clear(False)

        names = self._controls.keys()
        names.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))

        enabled = []
        disabled = []
        noResponses = []

        for name in names:
            _, checkBox, _, _, _ = self._controls[name]
            if not checkBox.IsShown():
                noResponses.append(name)
            elif checkBox.GetValue():
                enabled.append(name)
            else:
                disabled.append(name)

        names = enabled + disabled + noResponses
        for name in names:
            searchIcon, checkBox, nameButton, schedButton, responses =\
                    self._controls[name]
            self._ruleSizer.Add(searchIcon, 0, wx.ALIGN_CENTER_VERTICAL)
            self._ruleSizer.Add(nameButton, 1, wx.ALIGN_LEFT | wx.EXPAND |
                                wx.ALIGN_CENTER_VERTICAL)
            self._ruleSizer.Add(schedButton, 1, wx.ALIGN_LEFT | wx.EXPAND |
                                wx.ALIGN_CENTER_VERTICAL)
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            for control in responses:
                hSizer.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT |
                           wx.RIGHT, 2)
            self._ruleSizer.Add(hSizer, 0,
                                wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(checkBox, 0)
            hSizer.AddSpacer(_kShadowSize)
            self._ruleSizer.Add(hSizer, 0, wx.ALIGN_CENTER_VERTICAL)

        self._ruleWin.Layout()
        self._ruleWin.FitInside()

        numRules = len(self._rulesCache.get(self._curLocation, []))
        self._ruleWin.Show(numRules > 0)
        if self._curLocation:
            self._newHyperlink.Show(numRules == 0)

        self.Layout()


    ###########################################################
    def OnSize(self, event=None):
        """Respond to a resize event.

        @param event  The size event (ignored).
        """
        # On windows we need to refresh on size events or we get trails from
        # the rounded edges.
        self.Refresh()
        event.Skip()


    ###########################################################
    def OnCheckBox(self, event):
        """Respond to a check box toggle.

        @param event  The checkbox event.
        """
        checkBox = event.GetEventObject()
        ruleName = checkBox.GetName()
        self._backEndClient.enableRule(ruleName, checkBox.GetValue())

        _, _, _, schedButton, responses = self._controls[ruleName]
        if checkBox.GetValue():
            _, _, schedStr, _, _ = self._backEndClient.getRuleInfo(ruleName)
            schedButton.SetLabel(schedStr)
        else:
            schedButton.SetLabel("Disabled.")

        for control in responses:
            control.Enable(checkBox.GetValue())

        self._addControls()

        self.updateRulesCache(self._curLocation)


    ###########################################################
    def OnNew(self, event=None):
        """Create a new rule.

        @param event  The menu event (ignored).
        """
        wx.CallAfter(self._doOnNew)


    ###########################################################
    def _doOnNew(self):
        ruleCreated = False

        # Launch the query editor dialog
        newQuery = SavedQueryDataModel("")
        # Set the coordinate space of the new query to that of the video from
        # the current camera location, if possible.  We have a second chance
        # in the QueryConstructionView when an image is loaded in the video
        # window.
        procSize = self._dataManager.getProcSize(self._curLocation)
        if procSize != (0, 0):
            newQuery.setCoordSpace(procSize)
        newQuery.getVideoSource().setLocationName(self._curLocation)

        dlg = QueryEditorDialog(self.GetTopLevelParent(), self._dataManager,
                                self._backEndClient,
                                newQuery,
                                kSearchViewDefaultRules +
                                self._backEndClient.getRuleNames(),
                                [self._curLocation])

        try:
            result = dlg.ShowModal()

            # If the user cancels the dialog, do nothing
            if result == wx.ID_OK:
                # Save the new rule
                self._backEndClient.addRule(newQuery, True)
                ruleCreated = True

        finally:
            dlg.Destroy()

        if ruleCreated:
            info = self._backEndClient.getRuleInfo(newQuery.getName())
            if not info:
                return
            curRules = self._rulesCache.get(self._curLocation, [])
            curRules.append(info)
            self._rulesCache[self._curLocation] = curRules
            self._getRuleControls(*info)
            self._addControls()


    ###########################################################
    def OnEdit(self, event):
        """Edit an existing rule.

        @param event  The menu or button event.
        """
        responseEdit = False
        queryName = ''
        eventObj = event.GetEventObject()

        if isinstance(eventObj, HoverBitmapButton) or \
           isinstance(eventObj, HoverButton):

            for name in self._controls:
                _, _, _, schedButton, responses = self._controls[name]
                if eventObj in responses or eventObj == schedButton:
                    responseEdit = True
                    queryName = name
                    break
        else:
            queryName = eventObj.GetInvokingWindow().GetName()
            if not queryName:
                return
        wx.CallAfter(self._doOnEdit, queryName, responseEdit)


    ###########################################################
    def _doOnEdit(self, queryName, responseEdit):
        """Edit an existing rule.

        @param  queryName     The name of the query to edit.
        @param  responseEdit  True if we should jump to the response block.
        """
        query = self._backEndClient.getQuery(queryName)
        origLocation = query.getVideoSource().getLocationName()

        if responseEdit:
            query.setLastEdited('response', None)
        dlg = QueryEditorDialog(self.GetTopLevelParent(), self._dataManager,
                                self._backEndClient, query,
                                set(kSearchViewDefaultRules +
                                    self._backEndClient.getRuleNames()) -
                                set([query.getName()]),
                                [origLocation])
        try:
            result = dlg.ShowModal()
        finally:
            dlg.Destroy()

        if result == wx.ID_CANCEL:
            return

        # Save the edited query
        self._backEndClient.editQuery(query, queryName)

        # Anything could have changed...name, schedule, responses...
        # Rebuild the UI, but delay it slightly so we don't delete an object
        # that's being used on the callstack...
        wx.CallAfter(self.setCameraLocation, self._curLocation)


    ###########################################################
    def OnDelete(self, event):
        """Delete a rule.

        @param event  The menu event.
        """
        ruleName = event.GetEventObject().GetInvokingWindow().GetName()
        wx.CallAfter(self._doOnDelete, ruleName)


    ###########################################################
    def _doOnDelete(self, ruleName):
        """Delete a rule.

        @param  ruleName  The name of the rule to delete.
        """
        if wx.NO == wx.MessageBox("Delete the rule \"%s\"?" % ruleName,
                                  "Delete rule",
                                  wx.YES_NO | wx.ICON_QUESTION,
                                  self.GetTopLevelParent()):
            return

        self._backEndClient.deleteRule(ruleName)

        # Remove the rule info from _rules
        self.updateRulesCache(self._curLocation)

        # Retrieve and destroy the related controls
        searchIcon, checkBox, nameButton, schedButton, responses = \
                self._controls[ruleName]
        searchIcon.Destroy()
        checkBox.Destroy()
        wx.CallAfter(nameButton.Destroy)
        schedButton.Destroy()
        for control in responses:
            control.Destroy()
        del self._controls[ruleName]

        # Reorganize the list
        self._addControls()


    ###########################################################
    def OnScheduleButton(self, event):
        """Respond to a schedule button click.

        @param event  The hyperlink event.
        """
        button = event.GetEventObject()

        for name in self._controls:
            if button in self._controls[name]:
                wx.CallAfter(self._showScheduleDialog, name)


    ###########################################################
    def _showScheduleDialog(self, name):
        use12, _ = self.GetTopLevelParent().getUIPrefsDataModel(
                ).getTimePreferences()
        dlg = RuleScheduleDialog(self.GetTopLevelParent(), name,
                                 self._backEndClient, not use12)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

        _, _, schedStr, _, _ = self._backEndClient.getRuleInfo(name)
        # We'd prefer to just update the button's text here, but it may
        # have been destroyed while we were in the dialog.
        self.setCameraLocation(self._curLocation)
        self._ruleWin.Layout()
        return



    ###########################################################
    def OnSearch(self, event):
        """Respond to a search request.

        @param event  The button event.
        """
        button = event.GetEventObject()

        for name in self._controls:
            searchButton, checkBox, _, _, _ = self._controls[name]
            if button == searchButton:
                queryName = checkBox.GetName()
                self._searchFunc(self._curLocation, queryName)
                return


    ###########################################################
    def _handleTimePrefChange(self, uiModel):
        """Handle a change to time display preferences.

        @param  resultsModel  The UIPrefsDataModel.
        """
        use12, useUS = uiModel.getTimePreferences()

        if useUS and use12:
            self._timeFormatString = _kUS12
        elif useUS:
            self._timeFormatString = _kUS24
        elif use12:
            self._timeFormatString = _kNonUS12
        else:
            self._timeFormatString = _kNonUS24

        self.OnDateTimer()

        self.setCameraLocation(self._curLocation)


    ###########################################################
    def _handleCameraEnable(self, enableModel, camera):
        """Handle a change camera enable state.

        @param  resultsModel  Should be self._cameraEnabledModel
        @param  camera        The camera that was enabled.
        """
        assert enableModel == self._cameraEnabledModel
        assert camera is not None, "Shouldn't ever have general updates!"

        isEnabled = self._cameraEnabledModel.isEnabled(camera)
        if self._curLocation == camera:
            self._recordingEnabledButton.Show(isEnabled)
            self._recordingDisabledButton.Show(not isEnabled)
            self._onText.Show(isEnabled)
            self._offText.Show(not isEnabled)
        self.Layout()


    ###########################################################
    def OnEnableDisable(self, event):
        """Handle a request to enable or disable the current camera.

        @param  event  The EVT_BUTTON event.
        """
        assert self._curLocation

        if not self._curLocation:
            return

        needEnable = (event.GetEventObject() == self._recordingDisabledButton)
        self._backEndClient.enableCamera(self._curLocation, needEnable)

        # Technically, not needed, but makes UI update faster...
        self._cameraEnabledModel.enableCamera(self._curLocation, needEnable)


    ###########################################################
    def updateRulesCache(self, location=None):
        """Update the rules cache.

        @param  location  The name of the location to update, none for all.
        """
        if not location:
            self._rulesCache = {}
            locations = self._backEndClient.getCameraLocations()
        else:
            locations = [location]

        for loc in locations:
            self._rulesCache[loc] = \
                    self._backEndClient.getRuleInfoForLocation(loc)


    ###########################################################
    def getRulesForLocation(self, location):
        """Return the rules for a given location.

        @param  location  The name of the location to retrieve rules for.
        @return rules     A list of rules for location or []
        """
        return self._rulesCache.get(location, [])

