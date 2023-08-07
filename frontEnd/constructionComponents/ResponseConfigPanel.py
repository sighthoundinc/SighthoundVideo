#!/usr/bin/env python

#*****************************************************************************
#
# ResponseConfigPanel.py
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
import shlex
from subprocess import Popen, PIPE
import sys
import time
import re
import json

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.path.PathUtils import abspathU
from vitaToolbox.path.PathUtils import existsInPath
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors
from vitaToolbox.wx.AutoWrapStaticText import AutoWrapStaticText
from vitaToolbox.wx.FileBrowseButtonFixed import DirBrowseButton
from vitaToolbox.wx.FileBrowseButtonFixed import FileBrowseButton
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8

# Local imports...
from appCommon.CommonStrings import kCommandResponse, kCommandResponseLookup
from appCommon.CommonStrings import kEmailResponse
from appCommon.CommonStrings import kIftttResponse
from appCommon.CommonStrings import kWebhookResponse
from appCommon.CommonStrings import kPushResponse
from appCommon.CommonStrings import kRecordResponse
from appCommon.CommonStrings import kSoundResponse
from appCommon.CommonStrings import kFtpResponse
from appCommon.CommonStrings import kLocalExportResponse
from appCommon.CommonStrings import kDefaultPreRecord
from appCommon.CommonStrings import kIftttHelpUrl
from appCommon.CommonStrings import kPushHelpUrl
from appCommon.CommonStrings import kFrontEndLogName
from appCommon.LicenseUtils import hasPaidEdition
from frontEnd.EmailSetupDialog import EmailSetupDialog
from frontEnd.FtpSetupDialog import FtpSetupDialog
from frontEnd.OptionsDialog import OptionsDialog
from frontEnd.FrontEndUtils import promptUserIfRemotePathEvtHandler
from ConfigPanel import ConfigPanel

# Constants...

_kPanelTitle = "If seen"

_kSavePageName = "Save clips"
_kActionPageName = "Take actions"

_kSaveHelpStr = (
"""Mark this clip to be saved on:"""
)

_kExportHelpStr = (
"""Export this clip to:"""
)

_kSaveHelp2Str = (
"""Tip: You can create new rules to find events in video that has already """
"""been recorded."""
)

_kSettingsButtonLabel = "Settings..."

_kRunCommandStr = "Run the command:"
_kRunTestStr = "Test"

_kWebhookStr = "Execute a webhook:"

_kRecordEventStr = "My computer"

_kFtpStr = "My FTP server"
_kLocalStr = "A local folder"

_kSendPushStr = "Send a "
_kSendPushHelpStr = "mobile app notification"
_kSendEmailStr = "Send an email"
_kPlaySoundStr = "Play this sound:"
_kIftttStr = "Send an "
_kIftttHelpStr = "IFTTT event"
_kIftttTestStr = "Test"

_kCustomSoundLabel = "Custom"
_kSoundChoiceDict = {"Bells"            : u"frontEnd/sounds/Bells.wav",
                     "Person Detected"  : u"frontEnd/sounds/Person Detected.wav",
                     "Ping"             : u"frontEnd/sounds/Ping.wav"}


_kNoEmailAddrTitleStr = "Email notification"
_kNoEmailAddrStr = (
"""You have selected email notification for this rule without providing an """
"""email address to send the alerts.  Return to the Rule Editor and enter """
"""an address, """
"""or clear the checkbox labeled "%s" in the "%s" tab of the block labeled """
""""%s." """
) % (_kSendEmailStr, _kActionPageName, _kPanelTitle)

_kBadEmailAddrTitleStr = "Email notification"
_kBadEmailAddrStr = (
"""You have selected email notification for this rule but the email address """
"""to send the alerts contains an invalid character (%%s).  Return to the """
"""Rule Editor and correct the address, """
"""or clear the checkbox labeled "%s" in the "%s" tab of the block labeled """
""""%s." """
) % (_kSendEmailStr, _kActionPageName, _kPanelTitle)

_kNoEmailAccountTitleStr = "Email notification"
_kNoEmailAccountStr = (
"""You have selected email notification for this rule but have not provided """
"""your email account information.  Return to the Rule Editor and enter """
"""settings, """
"""or clear the checkbox labeled "%s" in the "%s" tab of the block labeled """
""""%s." """
) % (_kSendEmailStr, _kActionPageName, _kPanelTitle)

_kPushRegFailedTitleStr = "Mobile notification"
_kPushRegFailedStr = (
"""Your computer could not be registered for mobile notifications. Please """
"""ensure that you have internet connectivity and try again."""
)

_kNoCommandTitleStr = "Command notification"
_kNoCommandStr = (
"""You have selected to run a custom command as a notification for this rule """
"""but have not provided the command to execute.  Return to the Rule Editor """
"""and enter a command, """
"""or clear the checkbox labeled "%s" in the "%s" tab of the block labeled """
""""%s." """
) % (_kRunCommandStr, _kActionPageName, _kPanelTitle)

_kCommandErrorTitleStr = "Command notification"
_kCommandErrorStr = (
"""There was an error executing the command.  Please check that the path and """
"""parameters are correct and try again."""
)
_kCommandNotFoundErrorStr = (
"""The command was not found.  Please check that the path is """
"""correct and try again."""
)

_kFtpErrorTitleStr = "FTP response"
_kFtpErrorStr = (
"""You have selected to upload video clips saved by this rule """
"""but have not provided FTP site information.  Return to the Rule Editor """
"""and enter settings, """
"""or clear the checkbox labeled "%s" in the "%s" tab of the block labeled """
""""%s." """
) % (_kFtpStr, _kSavePageName, _kPanelTitle)

_kLocalExportSelectTitle = "Local Export"
_kLocalExportSelectLabel = (
"""Click Browse to select a directory in which to export clips matching """
"""this rule."""
)

_kPathDoesntExistTitle = "Path doesn't exist"
_kPathDoesntExistLabel = "The specified directory does not exist."

_kLocalExportErrorTitle = "Local export response"
_kLocalExportErrorLabel = (
"""You have selected to export video clips saved by this rule to a local """
"""directory but that directory does not exist. Return to the Rule Editor """
"""and enter settings, or clear the checkbox labeled "%s" in the "%s" tab """
"""of the block labeled "%s." """
) % (_kLocalStr, _kSavePageName, _kPanelTitle)

kTextPlain = "text/plain"
kApplicationJSON = "application/json"

##############################################################################
def _validateWebhook(uri, contentType, content):
    if contentType == kApplicationJSON:
        # validate JSON
        try:
            json.loads(content)
        except Exception as e:
            return ensureUtf8( "Please make sure your input is valid JSON!\n" + \
                   "Error: " + str(e) + "\n" + \
                   "JSON: " + content + \
                   "Quote: " + str(ord(content[2])) + "-" + str(ord("\"")))
    elif contentType != kTextPlain:
        return "Unsupported content type: " + contentType

    # Django checker, borrowed from https://stackoverflow.com/questions/7160737/python-how-to-validate-a-url-in-python-malformed-or-not
    regex = re.compile(
            r'^(?:http)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
            r'localhost|' #localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if not re.match(regex, uri):
        return "Please specify a valid webhook URL."

    return None

##############################################################################
class WebhookEditor(wx.Dialog):
    kSupportedTypes = [
        kTextPlain,
        kApplicationJSON
    ]
    ###########################################################
    def __init__(self, parent, uri, contentType, content):
        """WebhookEditor constructor.

        @param  parent         Our parent UI element.
        """
        # Call our super
        super(WebhookEditor, self).__init__(
            parent, title="Data to send ...",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self._contentTypeCtrl = wx.Choice(self, choices=self.kSupportedTypes)
        self._contentTypeCtrl.SetSelection( 1 if contentType == kApplicationJSON else 0 )
        contentTypeLabel = wx.StaticText(self, -1, "Send as")

        self._descField = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE)
        self._descField.SetMinSize((100, 200))
        self._descField.SetValue( content )
        # self._descField.OSXEnableAutomaticQuoteSubstitution(False)
        self._descField.SetFocus()

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        webhookUriLabel = wx.StaticText(self, -1, "URI")
        self._webhookUriField = wx.TextCtrl(self, -1)
        self._webhookUriField.SetMinSize((100, -1))
        self._webhookUriField.SetValue(uri)

        hint = wx.StaticText(self, -1, "You can use the following substitution variables:\n{SvRuleName}, {SvCameraName}, {SvEventTime}")

        uriSizer = wx.BoxSizer(wx.HORIZONTAL)
        uriSizer.Add(webhookUriLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        uriSizer.Add(self._webhookUriField, 1, wx.ALIGN_CENTER_VERTICAL)

        choicesSizer = wx.BoxSizer(wx.HORIZONTAL)
        choicesSizer.Add(contentTypeLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        choicesSizer.Add(self._contentTypeCtrl, 1, wx.ALIGN_CENTER_VERTICAL)

        mainSizer.Add(uriSizer, 0, wx.EXPAND | wx.BOTTOM, 10)
        mainSizer.Add(choicesSizer, 0, wx.EXPAND | wx.BOTTOM, 10)
        mainSizer.Add(hint, 0, wx.EXPAND | wx.BOTTOM, 10)
        mainSizer.Add(self._descField, 1, wx.EXPAND)

        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)

        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=wx.ID_CANCEL)

        self.CenterOnParent()

    ###########################################################
    def Content(self):
        content = self._descField.GetValue()
        # Replacing fancy UTF-8 quotes, which unfortunately aren't a valid JSON ...
        # Reference:
        # https://www.cl.cam.ac.uk/~mgk25/ucs/quotes.html
        # https://stackoverflow.com/questions/28977618/how-to-convert-utf-8-fancy-quotes-to-neutral-quotes
        content = re.sub(u'\u201c','"',content)
        content = re.sub(u'\u201d','"',content)
        # And we'll do a '-', too, but only because Kevin ran into it
        content = re.sub(u'\u2014','-',content)
        # Blanket replace things we do not understand with question marks
        content = content.encode('ascii', 'replace')
        return content

    ###########################################################
    def URI(self):
        return self._webhookUriField.GetValue()

    ###########################################################
    def ContentType(self):
        selection = self._contentTypeCtrl.GetSelection()
        return self._contentTypeCtrl.GetString(selection)

    ###########################################################
    def OnOK(self, event):
        error = _validateWebhook(self.URI(), self.ContentType(), self.Content() )
        if error is not None:
            wx.MessageBox(error, "Invalid webhook params.", wx.OK | wx.ICON_ERROR, self)
            return

        self.EndModal(wx.OK)

    ###########################################################
    def OnCancel(self, event):
        self.EndModal(wx.CANCEL)


##############################################################################
class ResponseConfigPanel(ConfigPanel):
    """The block configuration panel for a camera."""

    ###########################################################
    def __init__(self, parent, dataModel, backEndClient, dataMgr):
        """ResponseConfigPanel constructor.

        @param  parent          Our parent UI element.
        @param  dataModel       The SavedQueryDataModel.
        @param  backEndClient   Client to the back end.
        @param  dataMgr         The data manager for the app.
        """
        # Call our super
        super(ResponseConfigPanel, self).__init__(parent)

        # Keep track of params...
        self._dataModel = dataModel
        self._backEndClient = backEndClient
        self._dataMgr = dataMgr

        # Create a logger
        self._logger = getLogger(kFrontEndLogName)

        self._toggledIfttt = False
        self._hasPaidVersion = hasPaidEdition(backEndClient.getLicenseData())

        # Create our UI elements...
        notebook = wx.Notebook(self, -1)

        savePanel = wx.Panel(notebook, -1)

        saveHelpLabel = wx.StaticText(savePanel, -1, _kSaveHelpStr)

        self._recordCheckbox = wx.CheckBox(savePanel, -1, _kRecordEventStr)
        self._recordSettingsButton = wx.Button(savePanel, -1,
                                               _kSettingsButtonLabel)

        if self._hasPaidVersion:
            self._ftpCheckbox = wx.CheckBox(savePanel, -1, _kFtpStr)
            self._ftpSettingsButton = wx.Button(savePanel, -1,
                                                _kSettingsButtonLabel)

            self._localExportField = DirBrowseButton(savePanel, -1, labelText='',
                    changeCallback=self.OnLocalExportConfig)
            self._localExportCheckbox = wx.CheckBox(savePanel, -1, _kLocalStr)

        saveHelp2Label = AutoWrapStaticText(savePanel, -1, _kSaveHelp2Str)
        makeFontDefault(saveHelp2Label)
        saveHelp2Label.SetMinSize((1, saveHelp2Label.GetBestSize()[1]))

        actionPanel = wx.Panel(notebook, -1)

        self._emailCheckbox = wx.CheckBox(actionPanel, -1, _kSendEmailStr)
        self._emailSettingsButton = wx.Button(actionPanel, -1,
                                              _kSettingsButtonLabel)
        if self._hasPaidVersion:
            self._pushCheckbox = wx.CheckBox(actionPanel, -1, _kSendPushStr)
            pushHelpLink = wx.adv.HyperlinkCtrl(actionPanel, wx.ID_ANY, _kSendPushHelpStr, kPushHelpUrl)
            setHyperlinkColors(pushHelpLink)

            self._iftttCheckbox = wx.CheckBox(actionPanel, -1, _kIftttStr)
            iftttHelpLink = wx.adv.HyperlinkCtrl(actionPanel, wx.ID_ANY, _kIftttHelpStr, kIftttHelpUrl)
            setHyperlinkColors(iftttHelpLink)
            self._iftttTestButton = wx.Button(actionPanel, -1, _kIftttTestStr)

            self._webhookCheckbox = wx.CheckBox(actionPanel, -1, _kWebhookStr)
            self._webhookEditButton = wx.Button(actionPanel, -1, "Edit...")

            self._commandCheckbox = wx.CheckBox(actionPanel, -1,
                                                _kRunCommandStr)
            self._commandField = wx.TextCtrl(actionPanel, -1)
            self._commandTestButton = wx.Button(actionPanel, -1, _kRunTestStr)

        self._soundCheckbox = wx.CheckBox(actionPanel, -1, _kPlaySoundStr)
        choices = sorted(_kSoundChoiceDict.keys())
        choices.append(_kCustomSoundLabel)
        self._soundChoice = wx.Choice(actionPanel, -1, choices=choices)
        self._soundChoice.SetSelection(0)
        self._soundChoice.SetMinSize((1, -1))       # Needed to keep sizing OK.
        self._customSoundField = FileBrowseButton(actionPanel, -1, labelText='',
                                                  fileMask="*.wav",
                                                  changeCallback=
                                                  self.OnCustomSoundChange)
        self._customSoundField.SetMinSize((1, -1))  # Needed to keep sizing OK.

        # Put stuff in the notebook...
        notebook.AddPage(savePanel, _kSavePageName)
        notebook.AddPage(actionPanel, _kActionPageName)

        # Throw our stuff into our sizer...
        mainSizer = wx.BoxSizer()
        mainSizer.Add(notebook, 1, wx.EXPAND | wx.TOP, 5)

        saveSizer = wx.BoxSizer(wx.VERTICAL)
        saveSizer.Add(saveHelpLabel, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)

        saveGSizer = wx.FlexGridSizer(rows=0, cols=2, vgap=12, hgap=5)
        saveGSizer.AddGrowableCol(0)

        saveGSizer.Add(self._recordCheckbox, 0, wx.ALIGN_CENTER_VERTICAL)
        saveGSizer.Add(self._recordSettingsButton, 0, wx.ALIGN_CENTER_VERTICAL)
        saveSizer.Add(saveGSizer, 0, wx.EXPAND | wx.BOTTOM, 5)

        exportGSizer = wx.FlexGridSizer(rows=0, cols=2, vgap=12, hgap=5)
        exportGSizer.AddGrowableCol(0)
        if self._hasPaidVersion:
            exportHelpLabel = wx.StaticText(savePanel, -1, _kExportHelpStr)
            saveSizer.Add(exportHelpLabel, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)
            exportGSizer.Add(self._ftpCheckbox, 0, wx.ALIGN_CENTER_VERTICAL)
            exportGSizer.Add(self._ftpSettingsButton, 0, wx.ALIGN_CENTER_VERTICAL)
            exportGSizer.Add(self._localExportCheckbox, 0, wx.ALIGN_CENTER_VERTICAL)
            exportGSizer.AddSpacer(1)

        saveSizer.Add(exportGSizer, 0, wx.EXPAND | wx.BOTTOM, 12)
        if self._hasPaidVersion:
            self._localExportField.SetMinSize((1, -1))
            saveSizer.Add(self._localExportField, 0, wx.EXPAND)
            saveSizer.AddSpacer(10)

        saveSizer.Add(saveHelp2Label, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        saveBorderSizer = wx.BoxSizer()
        saveBorderSizer.Add(saveSizer, 1, wx.EXPAND | wx.ALL, 5)
        savePanel.SetSizer(saveBorderSizer)

        actionSizer = wx.GridBagSizer(vgap=10, hgap=5)
        actionSizer.AddGrowableCol(0)

        row=0
        if self._hasPaidVersion:
            box = wx.BoxSizer(wx.HORIZONTAL)
            box.Add(self._pushCheckbox, 0, wx.EXPAND)
            box.Add(pushHelpLink, 1, wx.ALIGN_LEFT | wx.EXPAND)
            actionSizer.Add(box, pos=(row, 0), span=(1, 2))
            row += 1

        actionSizer.Add(self._emailCheckbox, pos=(row, 0), flag=wx.EXPAND)
        actionSizer.Add(self._emailSettingsButton, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        if self._hasPaidVersion:
            box = wx.BoxSizer(wx.HORIZONTAL)
            box.Add(self._iftttCheckbox, 0, wx.EXPAND)
            box.Add(iftttHelpLink, 1, wx.ALIGN_LEFT | wx.EXPAND)
            actionSizer.Add(box, pos=(row, 0))
            actionSizer.Add(self._iftttTestButton, pos=(row, 1), flag=wx.EXPAND)
            row += 1

            actionSizer.Add(self._webhookCheckbox, pos=(row, 0))
            actionSizer.Add(self._webhookEditButton, pos=(row, 1), flag=wx.EXPAND)
            row += 1

            actionSizer.Add(self._commandCheckbox, pos=(row, 0), span=(1, 2))
            row += 1
            actionSizer.Add(self._commandField, pos=(row, 0), flag=wx.EXPAND)
            actionSizer.Add(self._commandTestButton, pos=(row, 1), flag=wx.EXPAND)
            row += 1

        soundSizer = wx.BoxSizer(wx.HORIZONTAL)
        soundSizer.Add(self._soundCheckbox, 0, wx.ALIGN_CENTER_VERTICAL |
                       wx.RIGHT, 5)
        soundSizer.Add(self._soundChoice, 1, wx.ALIGN_CENTER_VERTICAL)
        actionSizer.Add(soundSizer, pos=(row, 0), span=(1, 2),
                        flag=wx.EXPAND)
        row += 1

        actionSizer.Add(self._customSoundField, pos=(row, 0), span=(1, 2),
                        flag=wx.EXPAND)
        row += 1

        actionBorderSizer = wx.BoxSizer(wx.VERTICAL)
        actionBorderSizer.AddSpacer(10)
        actionBorderSizer.Add(actionSizer, 1, wx.EXPAND | wx.ALL, 5)
        actionPanel.SetSizer(actionBorderSizer)

        self.SetSizer(mainSizer)

        # Bind...
        self._recordCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
        self._recordSettingsButton.Bind(wx.EVT_BUTTON, self.OnRecordConfig)
        self._emailCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
        self._emailSettingsButton.Bind(wx.EVT_BUTTON, self.OnEmailConfig)
        if self._hasPaidVersion:
            self._pushCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
            self._iftttCheckbox.Bind(wx.EVT_CHECKBOX, self.OnIftttCheck)
            self._webhookCheckbox.Bind(wx.EVT_CHECKBOX, self.OnWebhookCheck)
        self._soundCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
        self._soundChoice.Bind(wx.EVT_CHOICE, self.OnSoundChoice)

        if self._hasPaidVersion:
            self._ftpCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
            self._ftpSettingsButton.Bind(wx.EVT_BUTTON, self.OnFtpConfig)

            self._localExportCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
            #self._localExportButton.Bind(wx.EVT_BUTTON, self.OnLocalExportConfig)

            self._commandCheckbox.Bind(wx.EVT_CHECKBOX, self.OnUiChange)
            self._commandField.Bind(wx.EVT_TEXT, self.OnCommandChange)
            self._commandTestButton.Bind(wx.EVT_BUTTON, self.OnCommandTest)
            self._iftttTestButton.Bind(wx.EVT_BUTTON, self.OnIftttTest)
            self._webhookEditButton.Bind(wx.EVT_BUTTON, self.OnWebhookEdit)

        # those will be updated momentarily
        self._webhookURI = None
        self._webhookContentType = None
        self._webhookContent = None

        # Listen for changes.
        self._dataModel.addListener(self._handleModelChange, False, 'responses')

        # Update everything...
        self._ignoreCustomFieldUpdate = True
        self._handleModelChange(self._dataModel)
        self._ignoreCustomFieldUpdate = False


    ###########################################################
    def __del__(self):
        """Destructor.

        Ensure that if we sent a temporary IFTTT state we reset to reality.
        """
        if self._toggledIfttt:
            self._sendIftttState(False)


    ###########################################################
    def getIcon(self):
        """Return the path to the bitmap associated with this panel.

        @return bmpPath  The path to the bitmap.
        """
        return "frontEnd/bmps/Block_Icon_If_Seen.png"


    ###########################################################
    def getTitle(self):
        """Return the title associated with this panel.

        @return title  The title
        """
        return _kPanelTitle


    ###########################################################
    def OnSoundChoice(self, event):
        """Play the sound selected by the user.

        @param  event  The event (ignored).
        """
        self._soundCheckbox.SetValue(True)
        self.OnUiChange(event)
        wx.CallLater(100, self._playSound)


    ##########################################################
    def _playSound(self):
        """Play the currently configured sound."""
        responseConfigList = self._dataModel.getResponses()
        for responseName, config in responseConfigList:
            if responseName == kSoundResponse:
                soundPath = config.get('soundPath', '')
                if not soundPath:
                    # If the user chose 'custom' but hasn't entered a path yet
                    # we don't want to complain about files not existing.
                    return
                try:
                    from backEnd.responses.SoundResponse import playSound
                    playSound(soundPath, False)
                except Exception, e:
                    wx.MessageBox("The sound file could not be played.",
                                  "Error", wx.OK | wx.ICON_ERROR,
                                  self.GetTopLevelParent())
                    self._logger.warn(
                            "The sound file (%s) couldn't be played - %s %s"
                            % (soundPath, str(type(e)), str(e)))


#    ###########################################################
#    def _handleRuleNameChange(self, dataModel):
#        """Handle a change in our data model.
#
#        @param  dataModel  The changed data model.
#        """
#        if self._iftttCheckbox.GetValue():
#            self._sendIftttState()


    ###########################################################
    def OnIftttCheck(self, event=None):
        """Handle a toggle of the IFTTT checkbox.

        @param  event  The event (ignored).
        """
        self._toggledIfttt = True
        self.OnUiChange(event)
        self._sendIftttState()

    ###########################################################
    def OnWebhookCheck(self, event=None):
        """Handle a toggle of the webhook checkbox.

        @param  event  The event (ignored).
        """
        if self._ignoreCustomFieldUpdate or not self._hasPaidVersion:
            return

        self.OnUiChange(event)

    ###########################################################
    def _sendIftttState(self, allowExtras=True):
        """Send the current IFTTT rule/camera status to the server.

        This includes additive temporary changes, but will not remove
        anything from the current saved reality - temporary changes should
        never break currently running IFTTT rules which removing would do.

        @param  allowTemporaryState  If True, allow temp state to be sent.
        """
        # TODO: Listen for camera location and rule name changes and call this
        #       function in response? Too much chatter to do that in order to
        #       cover those edge cases? If desired, add the following to init:
        # self._dataModel.addListener(self._handleRuleNameChange, False, 'name')

        rules = []
        cameras = []

        if allowExtras and self._iftttCheckbox.GetValue():
            cameras = [self._dataModel.getVideoSource().getLocationName()]
            rules = [self._dataModel.getName()]

        self._backEndClient.sendIftttRulesAndCameras(rules, cameras)


    ###########################################################
    def OnUiChange(self, event=None):
        """Handle various UI events and update our model.

        @param  event  The event (ignored).
        """
        responseConfigList = self._dataModel.getResponses()
        for responseName, config in responseConfigList:
            if responseName == kRecordResponse:
                config['isEnabled'] = bool(self._recordCheckbox.GetValue())
            elif responseName == kPushResponse:
                if self._hasPaidVersion:
                    config['isEnabled'] = bool(self._pushCheckbox.GetValue())
            elif responseName == kEmailResponse:
                config['isEnabled'] = bool(self._emailCheckbox.GetValue())

            elif responseName == kWebhookResponse:
                if self._hasPaidVersion:
                    config['isEnabled'] = bool(self._webhookCheckbox.GetValue())
                    config['webhookUri'] = self._webhookURI
                    config['webhookContent'] = self._webhookContent
                    config['webhookContentType'] = self._webhookContentType

            elif responseName == kIftttResponse:
                if self._hasPaidVersion:
                    config['isEnabled'] = bool(self._iftttCheckbox.GetValue())

            elif responseName == kCommandResponse:
                if self._hasPaidVersion:
                    config['isEnabled'] = bool(self._commandCheckbox.GetValue())
                    config[kCommandResponseLookup] = self._commandField.GetValue()
                else:
                    config['isEnabled'] = False
                    config[kCommandResponseLookup] = ''

            elif responseName == kSoundResponse:
                config['isEnabled'] = bool(self._soundCheckbox.GetValue())
                soundName = self._soundChoice.GetStringSelection()
                if soundName == _kCustomSoundLabel:
                    config['soundPath'] = self._customSoundField.GetValue()
                else:
                    soundPath = _kSoundChoiceDict[soundName]
                    config['soundPath'] = abspathU(soundPath)
                config['soundName'] = soundName

            elif responseName == kFtpResponse:
                if self._hasPaidVersion:
                    config['isEnabled'] = bool(self._ftpCheckbox.GetValue())
                else:
                    config['isEnabled'] = False

            elif responseName == kLocalExportResponse:
                if self._hasPaidVersion:
                    config['isEnabled'] = bool(
                            self._localExportCheckbox.GetValue())
                    config['exportPath'] = self._localExportField.GetValue()
                else:
                    config['isEnabled'] = False

            else:
                assert False, "Unknown response %s" % (responseName)

        self._dataModel.setResponses(responseConfigList)


    ###########################################################
    def OnRecordConfig(self, event):
        """Handle a user request to configure recording.

        @param  event  The event (ignored).
        """
        parent = self.GetTopLevelParent()
        frame = parent.GetParent()
        dlg = OptionsDialog(parent, self._backEndClient, self._dataMgr,
                self._logger, frame.getUIPrefsDataModel())
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnEmailConfig(self, event):
        """Handle a user request to configure email.

        @param  event  The event (ignored).
        """
        emailSettings = self._backEndClient.getEmailSettings()
        responseConfigList = self._dataModel.getResponses()

        responseConfig = None
        for responseName, config in responseConfigList:
            if responseName == kEmailResponse:
                responseConfig = config
                break

        assert responseConfig is not None
        if not responseConfig:
            self._logger.error("Couldn't retrieve email response config");
            return

        dlg = EmailSetupDialog(self.GetTopLevelParent(), emailSettings,
                               responseConfig)
        try:
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                self._backEndClient.setEmailSettings(dlg.getEmailConfig())
                self._dataModel.setResponses(responseConfigList)
        finally:
            dlg.Destroy()


    ###########################################################
    def OnFtpConfig(self, event):
        """Handle a user request to configure FTP.

        @param  The event (ignored).
        """
        ftpSettings = self._backEndClient.getFtpSettings()

        dlg = FtpSetupDialog(self.GetTopLevelParent(), ftpSettings)
        try:
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                self._backEndClient.setFtpSettings(dlg.getFtpConfig())

                # Turn on FTP response, since they hit "OK" from settings
                # (that implies that they wanted FTP)...
                self._ftpCheckbox.SetValue(1)
                self.OnUiChange()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnLocalExportConfig(self, event):
        """Handle a user request to configure local export.

        @param  The event.
        """
        if self._ignoreCustomFieldUpdate or not self._hasPaidVersion:
            return

        promptUserIfRemotePathEvtHandler(event)

        exportPath = self._localExportField.GetValue()

        evtObj = event.GetEventObject()

        if (evtObj.GetValue() == '') or (evtObj.GetValue() != exportPath):
            self._localExportCheckbox.SetValue(False)
            self.OnUiChange(event)

        elif os.path.isdir(exportPath):
            if not self._localExportCheckbox.GetValue():
                self._localExportCheckbox.SetValue(True)
            self.OnUiChange(event)


    ###########################################################
    def _handleModelChange (self, dataModel):
        """Handle a change in our data model.

        @param  event  The event (ignored).
        """
        assert dataModel == self._dataModel

        responseConfigList = self._dataModel.getResponses()
        for responseName, config in responseConfigList:
            if responseName == kRecordResponse:
                self._recordCheckbox.SetValue(config.get('isEnabled', False))

            elif responseName == kPushResponse:
                if self._hasPaidVersion:
                    self._pushCheckbox.SetValue(config.get('isEnabled', False))

            elif responseName == kIftttResponse:
                if self._hasPaidVersion:
                    self._iftttCheckbox.SetValue(config.get('isEnabled', False))

            elif responseName == kWebhookResponse:
                if self._hasPaidVersion:
                    self._webhookCheckbox.SetValue(config.get('isEnabled', False))
                    self._webhookURI = config.get('webhookUri', '')
                    self._webhookContentType = config.get('webhookContentType', '')
                    self._webhookContent = config.get('webhookContent', '')

            elif responseName == kEmailResponse:
                # Set the checkbox; do this after setting the field, since
                # settings the field may cause an event to go which will
                # check the checkbox...
                self._emailCheckbox.SetValue(config.get('isEnabled', False))

            elif responseName == kCommandResponse:
                if self._hasPaidVersion:
                    # Set the field if needed...
                    # ...only if needed to avoid loop (SetValue fires an event)
                    command = config.get(kCommandResponseLookup, '')
                    if self._commandField.GetValue() != command:
                        self._commandField.SetValue(command)

                    # Set the checkbox; do this after setting the field, since
                    # settings the field may cause an event to go which will
                    # check the checkbox...
                    self._commandCheckbox.SetValue(config.get('isEnabled',
                                                              False))


            elif responseName == kSoundResponse:
                self._soundCheckbox.SetValue(config.get('isEnabled', False))
                soundName = config.get('soundName', 'Alert')
                self._soundChoice.SetStringSelection(soundName)
                if soundName == _kCustomSoundLabel:
                    # Note: only update if needed to avoid playing the sound
                    # if it hasn't changed...
                    soundPath = config.get('soundPath', '')
                    if soundPath != self._customSoundField.GetValue():
                        self._customSoundField.SetValue(soundPath)

            elif responseName == kFtpResponse:
                if self._hasPaidVersion:
                    self._ftpCheckbox.SetValue(config.get('isEnabled', False))

            elif responseName == kLocalExportResponse:
                if self._hasPaidVersion:
                    self._localExportCheckbox.SetValue(config.get('isEnabled', False))
                    exportPath = config.get('exportPath', "")
                    if exportPath != self._localExportField.GetValue():
                        self._localExportField.SetValue(exportPath)

            else:
                assert False, "Unknown response %s" % (responseName)

        self._customSoundField.Enable(
                self._soundChoice.GetStringSelection() == _kCustomSoundLabel)


    ###########################################################
    def OnCustomSoundChange(self, event):
        """Handle a change to the custom sound path.

        @param  event  The event (ignored).
        """
        if self._ignoreCustomFieldUpdate:
            return

        promptUserIfRemotePathEvtHandler(event)

        customPath = self._customSoundField.GetValue()

        if os.path.isfile(customPath):
            self.OnUiChange(event)
            wx.CallLater(100, self._playSound)
        elif customPath == '':
            self.OnUiChange(event)


    ###########################################################
    def OnEmailAddrChange(self, event):
        """Handle a change in the email address field.

        We just make sure that the checkbox is checked if the user types in
        an email address.

        @param  event  The event.
        """
        if self._ignoreCustomFieldUpdate:
            return

        emailFieldValue = self._emailField.GetValue()
        if emailFieldValue:
            self._emailCheckbox.SetValue(1)

        self.OnUiChange(event)


    ###########################################################
    def OnCommandChange(self, event):
        """Handle a change in the command field.

        We just make sure that the checkbox is checked if the user types in
        a command.

        @param  event  The event.
        """
        if self._ignoreCustomFieldUpdate:
            return

        if self._commandField.GetValue():
            self._commandCheckbox.SetValue(1)

        self.OnUiChange(event)

    ############################################################
    def OnWebhookEdit(self, event):
        """Test the specified webhook.

        @param  event  The button event.
        """
        dlg = WebhookEditor(self, self._webhookURI, self._webhookContentType, self._webhookContent)
        try:
            if dlg.ShowModal() == wx.OK:
                self._webhookURI = dlg.URI()
                self._webhookContentType = dlg.ContentType()
                self._webhookContent = dlg.Content()
                self.OnUiChange(event)
        finally:
            dlg.Destroy()


    ############################################################
    def OnCommandTest(self, event):
        """Test the specified command.

        @param  event  The button event.
        """
        command = ''
        responseConfigList = self._dataModel.getResponses()
        for responseName, config in responseConfigList:
            if responseName == kCommandResponse:
                # Set the field if needed...
                # ...only do if needed to avoid loop (SetValue fires an event)
                command = config.get(kCommandResponseLookup, '')
                break

        if not command:
            wx.MessageBox("You must enter a command to test.", _kCommandErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        if type(command) == unicode:
            command = command.encode('utf-8')

        # Since shlex.split only supports POSIX parsing, we
        # recreate that function manually here, but setting the
        # posix parameter only if on Mac. Python 2.6 fixes this.
        lex = shlex.shlex(command, posix=(sys.platform=="darwin"))
        lex.whitespace_split = True
        lex.commenters = ''
        commandList = list(lex)

        if not existsInPath(commandList[0], "file"):
            wx.MessageBox(_kCommandNotFoundErrorStr, _kCommandErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        try:
            p = Popen(commandList, stdin=PIPE, stderr=PIPE,
                      stdout=PIPE, close_fds=(sys.platform=='darwin'))
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()
        except Exception:
            wx.MessageBox(_kCommandErrorStr, _kCommandErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())


    ############################################################
    def OnIftttTest(self, event):
        """Test the ifttt response.

        @param  event  The button event.
        """
        camera = self._dataModel.getVideoSource().getLocationName()
        rule = self._dataModel.getName()
        seconds = int(time.time())
        self._backEndClient.sendIftttMessage(camera, rule, seconds)


##############################################################################
def checkResponses(dataModel, backEndClient, topLevelParent):
    """Check to see if the responses are OK.

    NOTE: This will also update responses based on the current triggers.

    We'll display a message to the user if it's not.

    @param  dataModel       The SavedQueryDataModel.
    @param  backEndClient   Client to the back end.
    @param  topLevelParent  We'll use this as the parent for any wx.MessageBox
                            errors we show.
    @return isOk            True if OK, False if not.
    """
    triggers = dataModel.getTriggers()
    responseConfigList = dataModel.getResponses()
    for responseName, config in responseConfigList:
        if (responseName == kRecordResponse):
            # Ensure the preRecord is set correctly.
            prevPreRecord = config['preRecord']
            config['preRecord'] = kDefaultPreRecord
            for trigger in triggers:
                if hasattr(trigger, 'getWantMoreThan'):
                    if trigger.getWantMoreThan():
                        config['preRecord'] = \
                            kDefaultPreRecord+trigger.getMoreThanValue()
            if config['preRecord'] != prevPreRecord:
                dataModel.setResponses(responseConfigList)

        elif (responseName == kPushResponse) and config.get('isEnabled'):
            if hasPaidEdition(backEndClient.getLicenseData()):
                if not backEndClient.enableNotifications():
                    wx.MessageBox(_kPushRegFailedStr, _kPushRegFailedTitleStr,
                                  wx.OK | wx.ICON_ERROR, topLevelParent)
                    return False

        elif (responseName == kIftttResponse) and config.get('isEnabled'):
            pass

        elif (responseName == kWebhookResponse) and config.get('isEnabled'):
            uri = config.get('webhookUri', '')
            content = config.get('webhookContent', '')
            contentType = config.get('webhookContentType', '')
            error = _validateWebhook(uri, contentType, content)
            if error is not None:
                wx.MessageBox(error, "Invalid webhook params", wx.OK | wx.ICON_ERROR, self)
                return False
        elif (responseName == kEmailResponse) and config.get('isEnabled'):
            # Get address, handling old-style rules...
            toAddrs = config.get('toAddrs', None)
            if toAddrs is None:
                # Loaded old-style rule.  Grab from back end settings...
                emailSettings = backEndClient.getEmailSettings()
                toAddrs = emailSettings.get('toAddrs', "")

            try:
                toAddrs = toAddrs.encode('ascii', 'strict')
            except UnicodeEncodeError, e:
                wx.MessageBox(_kBadEmailAddrStr % (e.object[e.start:e.start+1]),
                              _kBadEmailAddrTitleStr,
                              wx.OK | wx.ICON_ERROR, topLevelParent)
                return False

            if not toAddrs:
                wx.MessageBox(_kNoEmailAddrStr, _kNoEmailAddrTitleStr,
                              wx.OK | wx.ICON_ERROR, topLevelParent)
                return False

            # Just check 'fromAddr' to make sure it's configured...
            # ...the EmailSetupDialog should ensure that if fromAddr is there
            # that the rest is OK...
            emailSettings = backEndClient.getEmailSettings()
            if not emailSettings.get('fromAddr'):
                wx.MessageBox(_kNoEmailAccountStr, _kNoEmailAccountTitleStr,
                              wx.OK | wx.ICON_ERROR, topLevelParent)
                return False
        elif (responseName == kCommandResponse) and config.get('isEnabled'):
            command = config.get(kCommandResponseLookup)
            if not command:
                wx.MessageBox(_kNoCommandStr, _kNoCommandTitleStr,
                              wx.OK | wx.ICON_ERROR, topLevelParent)
                return False

        elif (responseName == kFtpResponse) and config.get('isEnabled'):
            # We just check to see whether 'host' is defined.  If it's not,
            # then we've got a problem.  If it is, we know we must be OK since
            # the config dialog won't let you get away with partially configing.
            ftpSettings = backEndClient.getFtpSettings()
            if not ftpSettings.get('host'):
                wx.MessageBox(_kFtpErrorStr, _kFtpErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, topLevelParent)
                return False

        elif (responseName == kLocalExportResponse) and config.get('isEnabled'):
            # Ensure a valid path is defined.
            if not config.get('exportPath') or \
               not os.path.isdir(config.get('exportPath')):
                wx.MessageBox(_kLocalExportErrorLabel, _kLocalExportErrorTitle,
                              wx.OK | wx.ICON_ERROR, topLevelParent)
                return False

    return True


##############################################################################
def hasResponses(dataModel):
    """Check to see if any responses are configured.

    @param  dataModel     The SavedQueryDataModel.
    @return hasResponses  True if any responses are configured.
    """
    responseConfigList = dataModel.getResponses()
    for _, config in responseConfigList:
        if config.get('isEnabled'):
            return True

    return False


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
