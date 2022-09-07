#!/usr/bin/env python

#*****************************************************************************
#
# SubmitClipDialog.py
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


import wx
import webbrowser

from vitaToolbox.wx.TextCtrlUtils import addTextCtrlAccelerators
from vitaToolbox.wx.TextCtrlUtils import addTextCtrlPopup


# ...affects the size of our UI controls...
_kControlWidth = 420  # Width of our text fields, etc.
_kTextHeight = 200    # Initial height of our text field
_kConsentHeight = 200 # Height for consent static text

kConsentText = """
<body style="background-color: #dddddd">
<p>
By clicking <b>OK</b>, you agree to provide selected video clips (including any notes) in accordance with the <a href="https://www.sighthound.com/privacy">Sighthound Privacy Policy</a> and <a href="https://www.sighthound.com/terms">Terms of Use</a>.
<br>
<br>
Your data will only be used by Sighthound and not shared with any third parties.
</p>
""".strip()

###############################################################
class SubmitClipConsentDialog(wx.Dialog):
    """A dialog for legally agreeing to send us videos."""
    ###########################################################
    def __init__(self, parent):
        """Initializer for SubmitClipConsentDialog.

        @param  parent         The parent window.
        """
        wx.Dialog.__init__(self, parent, -1, "Submit clip to Sighthound for analysis ...")

        try:
            # Create the main sizer.
            mainSizer = wx.BoxSizer(wx.VERTICAL)

            # Create the controls.
            # consentText = wx.StaticText(self, -1, "Consent text goes here.\n\n"
            #                          "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum" )
            # consentText.SetMinSize((_kControlWidth, -1))
            # consentText.Wrap(_kControlWidth)

            self._consentText = wx.html.HtmlWindow(self, style=wx.TE_READONLY |
                                                wx.TE_MULTILINE | wx.TE_NO_VSCROLL | wx.BORDER_NONE)
            self._consentText.SetPage(kConsentText)
            self._consentText.SetMinSize((_kControlWidth, _kConsentHeight))
            self._consentText.Bind(wx.html.EVT_HTML_LINK_CLICKED, self.onURL)

            self._doNotShowAgain = wx.CheckBox(self, -1,
                                           "Do not show this again")
            self._doNotShowAgain.SetValue(False)


            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            mainSizer.Add(self._consentText, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)
            mainSizer.Add(self._doNotShowAgain, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)


            borderSizer = wx.BoxSizer(wx.VERTICAL)
            borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
            borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

            self.SetSizer(borderSizer)

            self.FindWindowById(wx.ID_CANCEL, self).SetDefault()
            # self.FindWindowById(wx.ID_OK).Bind(wx.EVT_BUTTON, self.OnOk)
            # self.FindWindowById(wx.ID_CANCEL).Bind(wx.EVT_BUTTON, self.OnCancel)

            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise

    ###########################################################
    def onURL(self, evt):
        link = evt.GetLinkInfo()
        webbrowser.open(link.GetHref())

    ###########################################################
    def permanentConsent(self):
        return self._doNotShowAgain.GetValue()

###############################################################
class SubmitClipDetailsDialog(wx.Dialog):
    """A dialog for providing notes along with submitted clip."""
    ###########################################################
    def __init__(self, parent):
        """Initializer for SubmitClipDetailsDialog.

        @param  parent         The parent window.
        """
        wx.Dialog.__init__(self, parent, -1, "Submit clip to Sighthound for analysis ...")

        try:
            # Create the main sizer.
            mainSizer = wx.BoxSizer(wx.VERTICAL)

            self._descField = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE)
            self._descField.SetMinSize((_kControlWidth, _kTextHeight))
            descFieldNote = wx.StaticText(self, -1, "Add a note about this clip (optional)" )
            addTextCtrlAccelerators(self._descField)
            addTextCtrlPopup(self._descField)
            self._descField.SetMinSize((_kControlWidth, _kTextHeight))
            self._descField.SetFocus()
            self._descField.Bind(wx.EVT_KEY_DOWN, self.OnKey)


            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            mainSizer.Add(descFieldNote, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)
            mainSizer.Add(self._descField, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)


            borderSizer = wx.BoxSizer(wx.VERTICAL)
            borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
            borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

            self.SetSizer(borderSizer)

            self.FindWindowById(wx.ID_OK, self).SetDefault()
            # self.FindWindowById(wx.ID_OK).Bind(wx.EVT_BUTTON, self.OnOk)
            # self.FindWindowById(wx.ID_CANCEL).Bind(wx.EVT_BUTTON, self.OnCancel)

            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise

    ###########################################################
    def MoveFocus(self):
        # TODO: Still can't figure out a way to move focus away from TextCtrl
        pass

    ###########################################################
    def OnKey(self, event):
        skip = True
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
            if event.ControlDown():
                evt = wx.PyCommandEvent(wx.EVT_BUTTON.typeId, wx.ID_OK)
                wx.PostEvent(self, evt)
        elif keycode == wx.WXK_TAB:
            self.MoveFocus()
            skip = False


        if skip:
            event.Skip()

    ###########################################################
    def getNote(self):
        return self._descField.GetValue()
