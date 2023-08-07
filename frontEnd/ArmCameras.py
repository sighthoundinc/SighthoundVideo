#!/usr/bin/env python

#*****************************************************************************
#
# ArmCameras.py
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
import sys
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FontUtils import adjustPointSize
from vitaToolbox.wx.BindChildren import bindChildren

# Local imports...


# Constants...
_kDialogTitle = "Arm cameras"

_kCaption = "Select which cameras you would like to be On:"

_kDelayCheckStr   = "Delay before turning on cameras:"
_kDelayMinutesStr = "minute(s)"


_kCountdownTitle = "Arming cameras"
_kCountdownCaption = "Cameras will be armed in:"

# Min / max on minute spinner...
_kMinMinutes = 1
_kMaxMinutes = 99

# The min width of the checkbox
_kMinCheckListBoxWidth = 350
_kMinCheckListBoxHeight = 160


# We'll run the timer once a second...
_kDelayTimerMs = 1000


# The width of the delay text...
_kDelayWidth = 350


##############################################################################
def handleArmRequest(parent, backEndClient):
    """Handle a request to "ARM" the cameras.

    This will display UI to the user asking for details, then do the ARM if
    the user actually chose that.

    @param  parent         The UI parent.
    @param  backEndClient  Proxy for talking to the back end.
    """
    # Get info from back end...
    camLocations = sorted(backEndClient.getCameraLocations(),
                          cmp=lambda a, b: cmp(a.lower(), b.lower()))
    armSettings = backEndClient.getArmSettings()

    dlg = _ArmDialog(parent, camLocations, armSettings)
    try:
        result = dlg.ShowModal()
        if result != wx.ID_OK:
            return
        armSettings = dlg.getArmSettings()
    finally:
        dlg.Destroy()

    # Pass settings on...
    backEndClient.setArmSettings(armSettings)

    # Handle delay...
    if armSettings['wantArmDelay']:
        dlg = _ArmDelayDialog(parent, armSettings['armDelayMinutes'])
        try:
            result = dlg.ShowModal()
            if result != wx.ID_OK:
                return
        finally:
            dlg.Destroy()

    # Do the arming!
    camerasNotToArm = set(armSettings['camerasNotToArm'])
    for camLoc in camLocations:
        _, _, enabled, _ = backEndClient.getCameraSettings(camLoc)

        if camLoc in camerasNotToArm:
            if enabled:
                backEndClient.enableCamera(camLoc, False)
        else:
            if not enabled:
                backEndClient.enableCamera(camLoc, True)


##############################################################################
def handleDisarmRequest(parent, backEndClient):
    """Handle a request to "disarm" the cameras (AKA: all cameras off).

    At the moment, we don't display any UI to the user here, but we could in
    the future.

    @param  parent         The UI parent.
    @param  backEndClient  Proxy for talking to the back end.
    """
    # We don't use the UI parent...
    _ = parent

    # Get info from back end...
    camLocations = sorted(backEndClient.getCameraLocations(),
                          cmp=lambda a, b: cmp(a.lower(), b.lower()))

    # Disarm turns off all cameras...
    for camLoc in camLocations:
        _, _, enabled, _ = backEndClient.getCameraSettings(camLoc)
        if enabled:
            backEndClient.enableCamera(camLoc, False)


##############################################################################
class _ArmDialog(wx.Dialog):
    """A dialog for arming the cameras."""

    ###########################################################
    def __init__(self, parent, camLocations, armSettings):
        """_ArmDialog constructor.

        @param  parent        Our parent UI element.
        @param  camLocations  A list of camera locations.
        @param  armSettings   A dict describing arm settings; see
                              BackEndPrefs for details.
        """
        # Call our super
        super(_ArmDialog, self).__init__(
            parent, title=_kDialogTitle, style=wx.DEFAULT_DIALOG_STYLE |
            wx.RESIZE_BORDER
        )

        try:
            self._camLocations = camLocations
            self._armSettings = armSettings

            self._initUiWidgets()
            self.Fit()
            self.SetSizeHints(*self.GetSize())
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        if not isinstance(self._armSettings, dict):
            # General case of screwed up prefs...
            self._armSettings = {}

        wantArmDelay = self._armSettings.get('wantArmDelay', True)
        delayMinutes = self._armSettings.get('armDelayMinutes', 1)
        camerasNotToArm = set(self._armSettings.get('camerasNotToArm', []))

        self._captionLabel = wx.StaticText(self, -1, _kCaption,
                                           style=wx.ST_NO_AUTORESIZE)

        self._camListBox = wx.CheckListBox(self, -1, choices=self._camLocations) #PYCHECKER OK: GetItemHeight not really needed.
        self._camListBox.SetMinSize((_kMinCheckListBoxWidth,
                                     _kMinCheckListBoxHeight))

        for i, camLoc in enumerate(self._camLocations):
            if camLoc not in camerasNotToArm:
                self._camListBox.Check(i)

        self._delayCheckBox = wx.CheckBox(self, -1, _kDelayCheckStr)
        self._delayCheckBox.SetValue(wantArmDelay)

        self._delaySpinner = wx.SpinCtrl(self, -1,
                                         min=_kMinMinutes, max=_kMaxMinutes)
        self._delaySpinner.SetValue(delayMinutes)

        self._minutesLabel = wx.StaticText(self, -1, _kDelayMinutesStr,
                                           style=wx.ST_NO_AUTORESIZE)

        # We use the StdDialogButtonSizer() in case we later want to add more
        # weird buttons...
        buttonSizer = wx.StdDialogButtonSizer()

        self._cancelButton = wx.Button(self, wx.ID_CANCEL)
        self._okButton = wx.Button(self, wx.ID_OK)

        buttonSizer.AddButton(self._cancelButton)
        buttonSizer.AddButton(self._okButton)

        self._okButton.SetDefault()
        self._okButton.SetFocus()
        buttonSizer.Realize()


        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.Add(self._captionLabel, 0, wx.EXPAND | wx.BOTTOM, 10)
        mainSizer.Add(self._camListBox, 1, wx.EXPAND | wx.BOTTOM, 20)

        delaySizer = wx.BoxSizer(wx.HORIZONTAL)
        delaySizer.Add(self._delayCheckBox, 0, wx.ALIGN_CENTER_VERTICAL)
        delaySizer.Add(self._delaySpinner, 0, wx.ALIGN_CENTER_VERTICAL)
        delaySizer.Add(self._minutesLabel, 0, wx.ALIGN_CENTER_VERTICAL)

        mainSizer.Add(delaySizer, 0, wx.EXPAND | wx.BOTTOM, 20)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)

        self.Bind(wx.EVT_BUTTON, self.OnOK, self._okButton)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self._cancelButton)


    ###########################################################
    def getArmSettings(self):
        """Get the settings.

        If the dialog was dismissed with "OK", these are the updated settings
        from the dialog.

        @return armSettings  The settings, updated with the user's changes.
        """
        return self._armSettings


    ###########################################################
    def OnOK(self, event):
        """Respond to the user pressing OK

        @param  event  The button event
        """
        camerasNotToArm = set(self._camLocations) - \
                          set(self._camListBox.GetCheckedStrings())
        self._armSettings['camerasNotToArm'] = list(camerasNotToArm)

        self._armSettings['armDelayMinutes'] = self._delaySpinner.GetValue()
        self._armSettings['wantArmDelay'] = bool(self._delayCheckBox.GetValue())

        self.EndModal(wx.ID_OK)


    ###########################################################
    def OnCancel(self, event):
        """Respond to the user pressing Cancel

        @param  event  The button event
        """
        self.EndModal(wx.ID_CANCEL)



##############################################################################
class _ArmDelayDialog(wx.Dialog):
    """A dialog for showing the time left till arming happens."""

    ###########################################################
    def __init__(self, parent, delayMinutes):
        """_ArmDelayDialog constructor.

        @param  parent        Our parent UI element.
        @param  delayMinutes  The number of minutes to delay.
        """
        # Call our super
        super(_ArmDelayDialog, self).__init__(
            parent, title=_kCountdownTitle
        )

        try:
            self._delayEndsAt = time.time() + (60 * delayMinutes)
            self._initUiWidgets()
            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        self._captionLabel = wx.StaticText(self, -1, _kCountdownCaption,
                                           style=wx.ST_NO_AUTORESIZE)

        self._timeLeftLabel = wx.StaticText(self, -1, "",
                                            style=wx.ST_NO_AUTORESIZE |
                                            wx.ALIGN_CENTER)
        adjustPointSize(self._timeLeftLabel, 2)
        self._timeLeftLabel.SetMinSize((_kDelayWidth, -1))

        # We use the StdDialogButtonSizer() in case we later want to add more
        # weird buttons...
        buttonSizer = wx.StdDialogButtonSizer()

        self._cancelButton = wx.Button(self, wx.ID_CANCEL)

        buttonSizer.AddButton(self._cancelButton)

        self._cancelButton.SetDefault()
        self._cancelButton.SetFocus()
        buttonSizer.Realize()


        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.Add(self._captionLabel, 0, wx.EXPAND | wx.BOTTOM, 10)
        mainSizer.Add(self._timeLeftLabel, 0, wx.EXPAND | wx.BOTTOM, 20)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)

        # Bind to UI stuff...
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self._cancelButton)

        # Update the text...
        self.OnTimer()

        # Make timer and bind to it, and start...
        self._timer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self._timer)
        self._timer.Start(_kDelayTimerMs)


    ###########################################################
    def OnTimer(self, event=None):
        """Update the time left label, and dismiss the dialog if needed.

        @param  event  The event; may be None the first time...
        """
        timeLeft = max(self._delayEndsAt - time.time(), 0)
        timeLeft = int(round(timeLeft))

        minutesLeft, secondsLeft = divmod(timeLeft, 60)
        self._timeLeftLabel.SetLabel("%02d:%02d" % (minutesLeft, secondsLeft))

        # Only allow ending the modal if not called the first time...
        if (event is not None) and (timeLeft == 0):
            self._timer.Stop()
            self.EndModal(wx.ID_OK)


    ###########################################################
    def OnCancel(self, event):
        """Respond to the user pressing Cancel

        @param  event  The button event
        """
        self.EndModal(wx.ID_CANCEL)





##############################################################################
def test_main(whatToTest='arm'):
    """OB_REDACT
       Contains various self-test code.
    """
    # Ugly test code...
    from BackEndClient import BackEndClient
    from appCommon.CommonStrings import kAppName

    app = wx.App(False)
    app.SetAppName(kAppName)

    backEndClient = BackEndClient()
    didConnect = backEndClient.connect()
    assert didConnect

    if whatToTest == 'arm':
        handleArmRequest(None, backEndClient)
    elif whatToTest == 'disarm':
        handleDisarmRequest(None, backEndClient)
    else:
        print "ERROR: Don't know how to test %s" % whatToTest


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main(*sys.argv[2:])
    else:
        print "Try calling with 'test' as the argument."
