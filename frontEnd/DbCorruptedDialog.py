#!/usr/bin/env python

#*****************************************************************************
#
# DbCorruptedDialog.py
#   Dialog to decide what to do when a database corruption happened.
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


import wx

from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors

from appCommon.CommonStrings import kCorruptDataUrl


_kPaddingSize = 4
_kBorderSize = 16

_kTitle = "Data Corruption Detected"

_kHelpText = (
"""One or more critical data files have been damaged. This is likely the """
"""result of hardware failure due to power loss or a dying component. """
"""Please back up any critical data and select one of the following options """
"""to continue:"""
)

_kOptionRecover = \
        "Recover - Preserve as much video and tracking data as possible."
_kOptionReset = (
"""Reset - Delete all video data. """
"""Camera and rule configurations will be saved.""")
_kOptionManual = "Quit - Take no action and exit the application."

_kSupport = "For more information click "
_kSupportLink = "here"
_kSupport1 = "."


###############################################################################
class DbCorruptedDialog(wx.Dialog):
    """A dialog for deleting video clips."""

    ###########################################################
    def __init__(self, parent):
        """Constructor.

        @param parent  The parent window.
        """
        wx.Dialog.__init__(self, parent, -1, _kTitle)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyUP)

        try:
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            textHelp = wx.StaticText(self, -1, _kHelpText)
            textSupport = wx.StaticText(self, -1, _kSupport)
            textSupport1 = wx.StaticText(self, -1, _kSupport1)
            linkSupport = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, _kSupportLink, kCorruptDataUrl)
            setHyperlinkColors(linkSupport)

            sizerSupport = wx.BoxSizer(wx.HORIZONTAL)
            sizerSupport.Add(textSupport)
            sizerSupport.Add(linkSupport)
            sizerSupport.Add(textSupport1)

            self._rbtnRecover = wx.RadioButton(self, -1, _kOptionRecover,
                                               style=wx.RB_GROUP)
            self._rbtnRecover.SetValue(True)
            self._rbtnReset = wx.RadioButton(self, -1, _kOptionReset)
            self._rbtnManual = wx.RadioButton(self, -1, _kOptionManual)

            textHelp.Wrap(max(self._rbtnRecover.GetBestSize()[0],
                              self._rbtnReset.GetBestSize()[0],
                              self._rbtnManual.GetBestSize()[0]))

            sizer.Add(textHelp, 0, wx.ALL, _kBorderSize)
            sizer.Add(self._rbtnRecover, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._rbtnReset, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._rbtnManual, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.Add(sizerSupport, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)

            sizerButtons = self.CreateStdDialogButtonSizer(wx.OK)
            sizer.Add(sizerButtons, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)

            self.FindWindowById(wx.ID_OK, self).SetDefault()
            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)

            self.Fit()
            self.CenterOnParent()

        except:
            self.Destroy()
            raise


    ###########################################################
    def OnKeyUP(self, event):
        """ Called if any key is released. Used to intercept [Esc].

        @param  event  The key event.
        """
        if wx.WXK_ESCAPE == event.GetKeyCode():
            self.EndModal(wx.CANCEL)


    ###########################################################
    def OnClose(self, event=None):
        """ Called if the dialog closes through another way than [OK].

        @param  event  The close event.
        """
        self.EndModal(wx.CANCEL)


    ###########################################################
    def OnOk(self, event=None):
        """ Called if the [OK] button is clicked. The user's decision is read
        from the radio buttons and then translated into a message box result
        (YES=recover, NO=reset, CANCEL=manual).

        @param  event  The button event.
        """
        if self._rbtnRecover.GetValue():
            self.EndModal(wx.YES)
        elif self._rbtnReset.GetValue():
            self.EndModal(wx.NO)
        else:
            self.EndModal(wx.CANCEL)
