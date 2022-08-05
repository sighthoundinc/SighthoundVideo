#!/usr/bin/env python

#*****************************************************************************
#
# FixedTimeCtrl.py
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

"""
## @file
Contains the FixedTimeCtrl class.
"""

import wx
import sys
from wx.lib import masked

EVT_TIMEUPDATE = masked.EVT_TIMEUPDATE


###############################################################################
def DoesThisLocalRequire24HrFmt():

    wxdt = wx.DateTime.FromDMY(1, 0, 1970)
    require24hr = False

    try:
        if wxdt.Format('%p') != 'AM':
            require24hr = True
    except:
        require24hr = True

    return require24hr


###############################################################################
class FixedTimeCtrl(masked.TimeCtrl):
    """A time control that ensures a single field is always selected."""
    def __init__ (self, parent, id=-1, value='00:00:00', pos=wx.DefaultPosition, #PYCHECKER OK: Too many arguments
                  size=wx.DefaultSize, fmt24hr=False, spinButton=None,
                  style=wx.TE_PROCESS_TAB, validator=wx.DefaultValidator,
                  name="time", **kwargs):
        super(FixedTimeCtrl, self).__init__(parent, id, value, pos, size,
                                            fmt24hr, spinButton, style,
                                            validator, name, **kwargs)

        # Catch mouse events so we can ensure a single field is always selected.
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouse)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnMouse)

        if 'darwin' == sys.platform:
            # This is required to make up for buggy TimeCtrl
            # See https://github.com/wxWidgets/Phoenix/issues/639 for more details
            self.Unbind(wx.EVT_CHAR)
            self.Bind(wx.EVT_CHAR_HOOK, self._OnChar)

        self._timer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnTimer)


    ###########################################################
    def OnMouse(self, event):
        """Respond to a mouse event.

        @param  event  The mouse event, ignored.
        """
        event.Skip()
        self._timer.Start(50, True)


    ###########################################################
    def SelectField(self):
        """Ensure a single field is selected."""
        self._OnDoubleClick(None)


    ###########################################################
    def OnTimer(self, event):
        """Respond to a timer event.

        @param  event  The EVT_TIMER event, ignored.
        """
        mouseState = wx.GetMouseState()
        if mouseState.LeftIsDown() or mouseState.RightIsDown():
            self._timer.Start(50, True)
        else:
            self.SelectField()
