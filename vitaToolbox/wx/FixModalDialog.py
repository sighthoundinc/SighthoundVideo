#!/usr/bin/env python

#*****************************************************************************
#
# FixModalDialog.py
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

# Common 3rd-party imports...
import wx

##############################################################################
def fixModalDialog(win, exitButtonIds=[wx.ID_OK, wx.ID_CANCEL]):
    """Call this at the beginning of a modal dialog that may have child dialogs.

    This works around problems in the WXMSW port of wxWidgets that exist at
    least through wxPython 2.8.10.1.  The problem is described in this bug:
      http://trac.wxwidgets.org/ticket/11273

    Roughly, we want to prevent dismissing the current dialog until any
    sub-dialogs that were created disappear.  If we don't, we end up with some
    big problems.

    @param  win            The modal dialog.
    @param  exitButtonIds  The IDs of all buttons that could cause this dialog
                           to exit.
    """
    # Nothing to do if not MSW...
    if wx.Platform != '__WXMSW__':
        return

    # Bind to idle and activate looking for top-level children that have us as
    # their parent.  Adjust enable/disable state of buttons accordingly.
    def enableOrDisableButtons(event):
        wantButtonsEnabled = True

        for topWin in wx.GetTopLevelWindows():
            if topWin.GetParent() == win:
                wantButtonsEnabled = False
                break

        for buttonId in exitButtonIds:
            button = win.FindWindowById(buttonId)
            if button:
                button.Enable(wantButtonsEnabled)

        event.Skip()
    win.Bind(wx.EVT_ACTIVATE, enableOrDisableButtons)
    win.Bind(wx.EVT_IDLE, enableOrDisableButtons)

    # Bind to close too to prevent closing (from the X)
    def onClose(event):
        for topWin in wx.GetTopLevelWindows():
            if topWin.GetParent() == win:
                break
        else:
            event.Skip()
    win.Bind(wx.EVT_CLOSE, onClose)


