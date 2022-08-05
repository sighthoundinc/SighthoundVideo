#!/usr/bin/env python

#*****************************************************************************
#
# FixedStaticBitmap.py
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


# Common 3rd-party imports...
import wx


# Nupic imports...


# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle

# Local imports...


# Constants


##############################################################################
class FixedStaticBitmap(wx.Window):
    """A StaticBitmap class that displays our about box logo properly.

    I'm not sure why the builtin one doesn't.  ...it just puts a gray halo
    around things on Windows.  Some bug in the alpha channel stuff?
    """

    ###########################################################
    def __init__(self, parent, id, label,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0, name="staticBitmap"):
        """The initializer for FixedStaticBitmap.

        @param  parent       The parent Window.
        @param  id           The ID
        @param  label        The label (AKA the wx.Bitmap object).
        @param  pos          UI pos.
        @param  size         UI size.
        @param  style        UI style.
        @param  name         UI name.
        """
        # Make sure it's transparent, even if client doesn't set it...
        style |= wx.TRANSPARENT_WINDOW

        # Call the base class initializer
        super(FixedStaticBitmap, self).__init__(parent, id, pos, size,
                                                    style, name)

        # Save our best size as the one passed in, with is (-1, -1) by default
        self._bestSize = size

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Save params...
        self._label = label

        # Bind to paint events
        self.Bind(wx.EVT_PAINT, self.OnPaint)


    ###########################################################
    def SetBitmap(self, label):
        """Set a new bitmap.

        @param  label  The new bitmap.
        """
        self._label = label
        self.Refresh()


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        @return  bestSize  Our best size.
        """
        # If a size was specified, use that; else use the text size.
        bestWidth, bestHeight = self._bestSize
        bitmapWidth = self._label.GetWidth()
        bitmapHeight = self._label.GetHeight()

        if bestWidth == -1:
            bestWidth = bitmapWidth
        if bestHeight == -1:
            bestHeight = bitmapHeight

        return (bestWidth, bestHeight)


    ###########################################################
    def OnPaint(self, event):
        """Draw the gradient line.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self._label, 0, 0, True)


