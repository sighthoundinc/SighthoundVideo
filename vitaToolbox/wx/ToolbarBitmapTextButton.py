#!/usr/bin/env python

#*****************************************************************************
#
# ToolbarBitmapTextButton.py
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

import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from TextSizeUtils import makeFontDefault

class ToolbarBitmapTextButton(wx.lib.buttons.GenBitmapTextButton):
    """A transparent toolbar image/text control."""

    ###########################################################
    def __init__(self, parent, ctrlId, bmp, text, bmpOnLeft=True):
        """Initializer for ToolbarBitmapTextButton.

        @param  parent     The parent window.
        @param  ctrlId     The id for the control.
        @param  bmp        The bitmap to use or None.
        @param  text       The text string, or None.
        @param  bmpOnLeft  True if the bitmap should be left of the text.
        """
        wx.lib.buttons.GenBitmapTextButton.__init__(self, parent, ctrlId, bmp,
                text, style=wx.TRANSPARENT_WINDOW | wx.BORDER_NONE)

        self.SetBackgroundStyle(kBackgroundStyle)
        self.labelDelta = 0
        self._bmpOnLeft = bmpOnLeft

        makeFontDefault(self)
        self.SetInitialSize(self.DoGetBestSize())

        # On Windows the toolbar background will not typically redraw, which
        # means that fonts or transparent items will continuously draw on top
        # of one another making a bold/muddy mess. Bind to the triggers for
        # this and force the toolbar to redraw.
        if wx.Platform == "__WXMSW__":

            # When the top window loses/regains focus if this control was
            # selected it will be redrawn. Need to update parent here as well.
            self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
            self.Bind(wx.EVT_KILL_FOCUS, self.OnFocus)

        # We don't get motion events while in the toolbar. This prevents
        # the button from properly toggling state as you drag the mouse. We
        # unfortunatly can't update that, but we *can* cause a button event not
        # to fire on the left-up if we're outside of the button bounds.
        self.Bind(wx.EVT_LEFT_UP, self.OnUp)


    ###########################################################
    def OnUp(self, event):
        """Handle a left up event.

        @param  event  The EVT_LEFT_UP event.
        """
        if not self.HasCapture():
            return

        x, y = event.GetPosition()
        w, h = self.GetClientSize()

        if not (0 <= x < w and 0 <= y < h):
            # If the up is not within our bounds do not allow a button event to
            # be generated.
            self.up = True

        self.Refresh()
        self.GetParent().Refresh()
        event.Skip()


    ###########################################################
    def OnFocus(self, event):
        self.GetParent().Refresh()
        event.Skip()


    ###########################################################
    def GetBackgroundBrush(self, dc):
        """Return the background brush

        @param  dc     The active device context
        @return brush  The background brush or None
        """
        return None


# DrawLabel tweaked from wx.lib.buttons, which has the following copyright
#----------------------------------------------------------------------
# Name:        wx.lib.buttons
# Purpose:     Various kinds of generic buttons, (not native controls but
#              self-drawn.)
#
# Author:      Robin Dunn
#
# Created:     9-Dec-1999
# RCS-ID:      $Id: buttons.py 53288 2008-04-21 15:37:22Z RD $
# Copyright:   (c) 1999 by Total Control Software
# Licence:     wxWindows license
#----------------------------------------------------------------------
# 11/30/2003 - Jeff Grimmett (grimmtooth@softhome.net)
#
# o Updated for wx namespace
# o Tested with updated demo
#
    ###########################################################
    def DrawLabel(self, dc, width, height, dx=0, dy=0):
        # NOTE: This is dependent on wx 2.8 behavior, may need to be updated
        bmp = self.bmpLabel
        if bmp is not None:
            if self.bmpDisabled and not self.IsEnabled():
                bmp = self.bmpDisabled
            if self.bmpFocus and self.hasFocus:
                bmp = self.bmpFocus
            if self.bmpSelected and not self.up:
                bmp = self.bmpSelected
            bw,bh = bmp.GetWidth(), bmp.GetHeight()
            if not self.up:
                dx = dy = self.labelDelta
            hasMask = bmp.GetMask() is not None
        else:
            bw = bh = 0     # no bitmap -> size is zero

        dc.SetFont(self.GetFont())
        if self.IsEnabled():
            dc.SetTextForeground(self.GetForegroundColour())
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        label = self.GetLabel()
        tw, th = dc.GetTextExtent(label)        # size of text
        if not self.up:
            dx = dy = self.labelDelta

        pos_x = (width-bw-tw)/2+dx      # adjust for bitmap and text to centre

        if self._bmpOnLeft:
            if bmp is not None:
                dc.DrawBitmap(bmp, pos_x, (height-bh)/2+dy, hasMask) # draw bitmap if available
                pos_x = pos_x + 2   # extra spacing from bitmap

            dc.DrawText(label, pos_x + dx+bw, (height-th)/2+dy)      # draw the text
        else:
            dc.DrawText(label, pos_x + dx, (height-th)/2+dy)
            pos_x = pos_x+2
            if bmp is not None:
                dc.DrawBitmap(bmp, pos_x + tw, (height-bh)/2+dy, hasMask)
