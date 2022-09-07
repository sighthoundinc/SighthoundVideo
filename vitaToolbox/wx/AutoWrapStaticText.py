#! /usr/local/bin/python

#*****************************************************************************
#
# AutoWrapStaticText.py
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

# Common 3rd-party imports...
import wx


class AutoWrapStaticText(wx.Control):
    def __init__(self, parent, id=-1, label="", pos=wx.DefaultPosition, size=wx.DefaultSize, style=0, name="wrapStatText"):
        wx.Control.__init__(self, parent, id, pos, size, wx.NO_BORDER, wx.DefaultValidator, name)
        self.st = wx.StaticText(self, -1, label, style=style)
        self._label = label # save the unwrapped text
        self._Rewrap()
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def SetLabel(self, label):
        self._label = label
        self._Rewrap()
    def GetLabel(self):
        return self._label

    def SetFont(self, font):
        self.st.SetFont(font)
        self._Rewrap()
    def GetFont(self):
        return self.st.GetFont()

    def OnSize(self, evt):
        self.st.SetSize(self.GetSize())
        self._Rewrap()

    def _Rewrap(self):
        self.st.Freeze()
        self.st.SetLabel(self._label)
        self.st.Wrap(self.GetSize().width)
        self.st.Thaw()

    def DoGetBestSize(self):
        # this should return something meaningful for what the best
        # size of the widget is, but what that size should be while we
        # still don't know the actual width is still an open
        # question... Just return a dummy value for now.
        return wx.Size(100,100)

