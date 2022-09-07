#!/usr/bin/env python

#*****************************************************************************
#
# FixedGenBitmapButton.py
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
from   wx.lib import buttons as wxbuttons

class FixedGenBitmapButton(wxbuttons.GenBitmapButton):
    """A version of GenBitmapButton with some fixes."""


    ###########################################################
    def __init__(self, parent, bmp, bmpSelected=None, bmpDisabled=None,
                 delta=0, wantHighlight=False):
        """Initializer for FixedGenBitmapButton

        @param  parent         The parent window
        @param  bmp            The image to show when the button is enabled
        @param  bmpSelected    The image to show when the button is selected
        @param  bmpDisabled    The image to show when the button is disabled
        @param  delta          The offset at which to draw the button when it
                               is being clicked.
        @param  wantHighlight  True if the area around a button should be
                               highlighted when it is selected
        """
        wxbuttons.GenBitmapButton.__init__(self, parent, bitmap=bmp,
                                           style=wx.BORDER_NONE,
                                           size=bmp.GetSize())

        if bmpSelected:
            self.SetBitmapSelected(bmpSelected)
        if bmpDisabled:
            self.SetBitmapDisabled(bmpDisabled)

        # labelDelta is a superclass variable
        self.labelDelta = delta

        self._wantHighlight = wantHighlight


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Determines the best size of the button

        @return size  The best size for the control
        """
        return self.GetBitmapLabel().GetSize()


    ###########################################################
    def GetBackgroundBrush(self, dc):
        """Return the background brush

        @param  dc     The active device context
        @return brush  The background brush or None
        """
        if self.up or self._wantHighlight:
            return wxbuttons.GenBitmapButton.GetBackgroundBrush(self, dc)

        return None
