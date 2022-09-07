#!/usr/bin/env python

#*****************************************************************************
#
# FixedMultiSplitterWindow.py
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
from wx.lib.splitter import MultiSplitterWindow

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle

class FixedMultiSplitterWindow(MultiSplitterWindow):
    """This class overrides functions from MultiSplitterWindow. This is needed
    because the original SplitterWindow and MultiSplitterWindow have certain bugs
    that needed to be addressed before it can be used.

    Bugs Fixed:
    - With the original classes, the sash is able to move off screen.
    - The window will cover up the right(bottom)-most window when the sash is to the far
        right(bottom) of the screen, and then having the window resized smaller towards the sash.
    - The size of the sash can't be changed.
    - The sash cannot be made invisible. Windows draws the sash with the background color of the window
        even if the window is set to transparent.

    """


    ###########################################################
    def __init__(self, parent, id=-1,
                 pos = wx.DefaultPosition, size = wx.DefaultSize,
                 style = 0, name="fixedMultiSplitter", sashBmp=None,
                 logger = None):
        """

        @param parent  The parent window.
        @param id      The id of this window.
        @param pos     The position of this window as a 2-tuple (width, height).
        @param size    The size of this window as a 2-tuple (width, height).
        @param style   The window styles.
        @param name    The name of this window.
        @param sashBmp An optional bitmap draw as a sash grab point.
        @param logger  An optional logger object to write extra info to.
        """
        MultiSplitterWindow.__init__(self, parent, id, pos, size, style, name)

        self.SetBackgroundStyle(kBackgroundStyle)

        self._sashGravity = 0
        self._prevSize = (-1, -1)

        self.SetMinimumPaneSize(1)

        self._wasDragging = False

        self._sashBmp = None
        self._sashSize = 12

        self._logger = logger

        if sashBmp:
            self._sashBmp = sashBmp
            self._sashSize = self._sashBmp.GetWidth()

        # Detect sash position changes so that we make sure the child windows'
        # min sizes are being respected.
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self.OnSashPosChange)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.OnSashPosChange)


    ###########################################################
    def SplitVertically(self, window1, window2):
        """Added functionality. Calling this function will add the two windows and
        split the window vertically automatically.  It will also set the minimum sizes of the windows.

        @param window1  The top(left) window of the splitter window.
        @param window2  The bottom(right) window of the splitter window.
        """
        self.SetOrientation(wx.HORIZONTAL)
        window1.SetMinSize(window1.GetEffectiveMinSize())
        window2.SetMinSize(window2.GetEffectiveMinSize())
        self.AppendWindow(window1)
        self.AppendWindow(window2)


    ###########################################################
    def SplitHorizontally(self, window1, window2):
        """Added functionality. Calling this function will add the two windows and
        split the window horizontally automatically.  It will also set the minimum sizes of the windows.

        @param window1  The top(left) window of the splitter window.
        @param window2  The bottom(right) window of the splitter window.
        """
        self.SetOrientation(wx.VERTICAL)
        window1.SetMinSize(window1.GetEffectiveMinSize())
        window2.SetMinSize(window2.GetEffectiveMinSize())
        self.AppendWindow(window1)
        self.AppendWindow(window2)


    ###########################################################
    def SetSashGravity(self, gravity):
        """Added functionality.  This sets the gravity of the sash.
        If the sash gravity is not a number between 0 and 1 inclusive,
        this function will behave as a no-op.

        @param gravity  The gravity of the sash as a number between 0 and 1 inclusive.
        """
        if gravity >= 0 or gravity <= 1:
            self._sashGravity = gravity


    ###########################################################
    def GetSashGravity(self):
        """Added functionality.  This gets the gravity of the sash.

        @return sashGravity  The gravity of the sash as a number between 0 and 1 inclusive.
        """
        return self._sashGravity


    ###########################################################
    def GetAllowableSashPos(self, idx, pos):
        """Checks if the sash at 'idx' can have position 'pos'.

        If the given position is greater than the min/max dimension length, then
        the min/max length will be returned. Otherwise, the given position is
        returned.

        @param  idx    Index of the sash we want to check.
        @param  pos    Position we want to set the sash to.
        @return newpos The allowable position this index can have.
        """

        # If this index is the last sash, return the given position.
        if idx == len(self._windows) - 1:
            return pos

        # Get dimension information
        if self.GetOrientation() == wx.HORIZONTAL:
            # The width value is in position 0 in size objects.
            dimension = 0
        else:
            # The height value is in position 1 in size objects.
            dimension = 1
        minLength = max(self.GetWindow(idx).GetEffectiveMinSize()[dimension], 1)
        maxLength = self.GetClientSize()[dimension] - \
                    max(self.GetWindow(idx+1).GetEffectiveMinSize()[dimension], 1)

        return max(minLength, min(maxLength, pos))


    ###########################################################
    def OnSashPosChange(self, event):
        """Handles the sash position changing and changed event.

        @param  event   The sash changed or changing event.
        """
        event.SetSashPosition(self.GetAllowableSashPos(event.GetSashIdx(),
                                                       event.GetSashPosition())
        )


    ###########################################################
    def _DrawSash(self, dc):
        """Overloaded function. Draw an indicator for the sash.

        NOTE: Currently assuming vertical sash as that's all we use.
              Currently also only draws the first sash.

        @param  dc  The device context to draw to.
        """
        # Return if the user doesn't want a sash.
        if self.HasFlag(wx.SP_NOSASH):
            return

        # Return if we're not split yet.
        if len(self._windows) < 2:
            return

        # Only paint if we're actually painting during a paint event.
        if not isinstance(dc, wx.PaintDC):
            return

        # Below is for experimental purposes ONLY (for now, anyway).
        # This piece of code draws a bitmap for the sash.
        if self._sashBmp:
            sashPos = self.GetSashPosition(0)

            h = self.GetSize()[1]
            dc.DrawBitmap(self._sashBmp,
                          self.GetSashPosition(0),
                          (h-self._sashSize)/2)

        # Below is for experimental purposes ONLY (for now, anyway).
        # This piece of code draws a solid black bar for the sash.
        if False:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.BLACK))

            indicatorPos = self.GetSashPosition(0)
            indicatorSize = self.GetSashSize()
            if self.GetOrientation() == wx.HORIZONTAL:
                x = indicatorPos
                y = 0
                w = indicatorSize
                h = self.GetClientSize().height
            else:
                x = 0
                y = indicatorPos
                w = self.GetClientSize().width
                h = indicatorSize
            dc.DrawRectangle(x, y, w, h)


    ###########################################################
    def _GetSashSize(self):
        """Overloaded function.  This function returns the size of the sash.
        Since this subclass maintains the size of the sash, we need to overload
        this function, and not call the super's equivalent method. The super's method
        returns a constant.

        @return sashSize  The size of the sash as an integer.
        """
        return self._sashSize


    ###########################################################
    def GetSashSize(self):
        """Added functionality.  This function returns the size of the sash.

        @return sashSize  The size of the sash as an integer.
        """
        return self._GetSashSize()


    ###########################################################
    def SetSashSize(self, size):
        """Added functionality.  This function sets the size of the sash.

        Note: if a bitmap was passed into the constructor, this function does
              nothing.

        @param  size  The desired sash size as an integer.
        """
        if self._sashBmp is None:
            self._sashSize = size


    ###########################################################
    def _SizeWindows(self):
        """Overloaded function.  This function was overloaded to force the splitter window
        to respect the minimum sizes of its child windows.  Without this, the splitter window
        can cover up either of the child windows without properly resizing.
        """

        # Only run this if we're physically visible to the user,
        # and if there is more than one window (sash).
        if ((self.GetTopLevelParent().IsShownOnScreen()) and
            (len(self._sashes) > 1)                         ):

            if self._prevSize[0] > 0 and self._prevSize[1] > 0:

                # Get dimension information
                if self.GetOrientation() == wx.HORIZONTAL:
                    prevDimension, _ = self._prevSize
                    curPosition, _, curDimension, _ = self.GetClientRect().Get()
                    minDimension, _ = self._windows[0].GetEffectiveMinSize()
                else:
                    _, prevDimension = self._prevSize
                    _, curPosition, _, curDimension = self.GetClientRect().Get()
                    _, minDimension = self._windows[0].GetEffectiveMinSize()

                # Get the difference in size from resizing.
                diff = curDimension - prevDimension

                # Calculate the amount of gravity for the first and last sash.
                sashGravity = int(self._sashGravity * diff)

                # Adjust the sashes for gravity.
                newSashPos = self.GetAllowableSashPos(
                    0, sashGravity + self._sashes[0]
                )
                self._sashes[0] = newSashPos

                # Make sure the sash is not off screen
                if ((self._sashes[0] > curDimension) or
                    (self._sashes[0] < 1)              ):
                    # This should technically never happen. So if it does,
                    # we'll log it. The only time it's expected to happen
                    # is if the user changes the screen resolution to
                    # something smaller than the app, forcing the app
                    # to resize.
                    if self._logger:
                        msg = 'Sash was off screen. Name = %(name)s, '  \
                              'sash position = %(sashPos)s, '           \
                              'Left/Top = %(leftOrTop)s, '              \
                              'Right/Bottom = %(rightOrBttm)s'
                        values = {'name': self.GetName(),
                                  'sashPos': str(self._sashes[0]),
                                  'leftOrTop': str(curPosition),
                                  'rightOrBttm': str(curDimension)}
                        self._logger.info(msg % values)
                    # The sash is off screen. Set the position to
                    # the minimum width/height of the first window.
                    self._sashes[0] = minDimension

        # Size the windows
        MultiSplitterWindow._SizeWindows(self)

        self._prevSize = self.GetClientSize()

