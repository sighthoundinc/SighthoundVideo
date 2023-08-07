#!/usr/bin/env python

#*****************************************************************************
#
# BitmapWindow.py
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

import ctypes
from PIL import Image
import wx

class BitmapWindow(wx.Window):
    """A wx.Window that displays wx.Bitmap objects without flicker."""


    ###########################################################
    def __init__(self, parent, bitmap, size=None, background=(0, 0, 0),
                 scale=False, name="BitmapWindow"):
        """BitmapWindow constructor.

        @param  parent       Our parent UI object.
        @param  bitmap       A wxBitmap object.
        @param  size         Size of the UI window--passed to our wx.Window
                             superclass.  If None, we'll use:
                             - If scale is True:  (1, 1)
                             - If scale is False: bitmap.Size
        @param  background   background color for window, as a r, g, b tuple.
        @param  scale        True if the bitmap should scale with the window.
                             If we're not scaling and the window is bigger
                             than us, we'll be centered.
        @param  name         The name to assign to the control.
        """
        if size:
            winSize = size
            self._bestSize = size
        elif not scale:
            winSize = bitmap.Size
            self._bestSize = None
        else:
            winSize = (1,1)
            self._bestSize = None

        super(BitmapWindow, self).__init__(parent, -1,
                           size=winSize,
                           style=wx.FULL_REPAINT_ON_RESIZE,
                           name=name)
        self.SetBackgroundColour(background)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        # Track if the bitmap should scale and the current scale factor
        self._shouldScale = scale
        self._scale = 1.
        self._offset = (0, 0)

        # Set bitmap
        self._origBitmap = None
        self._bitmap = None
        self.updateBitmap(bitmap)

        # We need to be able to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)


    ############################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Implement DoGetBestSize() to properly apply our bestSize.

        @return bestSize  The actual best size.
        """
        if self._bestSize is not None:
            return self._bestSize

        if self._bitmap is None:
            return super(BitmapWindow, self).DoGetBestSize()
        else:
            return (self._bitmap.GetWidth(), self._bitmap.GetHeight())


    ############################################################
    def GetDesiredFrameSize( self ):
        return self.GetSize()


    ############################################################
    def GetWidthGranularity( self ):
        return 1


    ###########################################################
    def isScaling(self):
        """Check whether the bitmap scales with the window

        @return scales  True if the bitmap scales
        """
        return self._shouldScale


    ###########################################################
    def getScaleFactor(self):
        """Return the current scale factor for the bitmap

        @return scale  The current scale factor
        """
        return self._scale


    ###########################################################
    def getOffset(self):
        """Return the offset of the bitmap.

        @return scale  The current scale factor
        """
        return self._offset


    ###########################################################
    def getBitmap(self):
        """Return the bitmap we're showing.

        @return bitmap  Our bitmap (unmodified, unscaled).
        """
        return self._origBitmap


    ###########################################################
    def updateImageData( self, frame ):
        """Update the bitmap with an RGB ClipFrame

        @param frame  The RGB ClipFrame object to be converted.
        """
        self.UpdateTextureRaw(frame.buffer, frame.width, frame.height)


    ###########################################################
    def updateImageBuffer( self, data, width, height ):
        """Update the bitmap with a string or ctypes buffer.

        @param data     string or ctypes buffer containing RGB image data.
        @param width    Width of the image buffer.
        @param height   Height of the image buffer.
        """
        self.UpdateTextureRaw(data, width, height)


    ###########################################################
    def UpdateTextureRaw( self, data, width, height ):
        """Update the bitmap with a string or ctypes buffer.

        @param data     string or ctypes buffer containing RGB image data.
        @param width    Width of the image buffer.
        @param height   Height of the image buffer.
        """
        # Update the internal bitmap...
        bmp = wx.Bitmap.FromBuffer(width, height, ctypes.string_at(data, width*height*3))
        self.updateBitmap(bmp)


    ###########################################################
    def updateBitmap(self, bitmap):
        """Update the actual bitmap.

        @param  bitmap  A wxBitmap or PIL image.
        """

        if isinstance(bitmap, Image.Image):
            width = bitmap.size[0]
            height = bitmap.size[1]
            asBuffer = bitmap.tobytes('raw', 'RGB')
            bitmap = wx.Bitmap.FromBuffer(width, height, asBuffer)

        # Preserve a clean copy of the original bitmap
        self._origBitmap = bitmap

        self._bitmap = bitmap

        bmpWidth, bmpHeight = bitmap.Size
        winSize = self.GetSize()
        winWidth, winHeight  = winSize
        if not winWidth or not winHeight:
            winWidth, winHeight = bitmap.Size

        self._offset = (0, 0)
        self._scale = 1.

        if winSize != bitmap.Size:
            if self._shouldScale:
                if (winSize[0] == bitmap.Size[0] and
                        bitmap.Size[1] < winSize[1]) or \
                   (winSize[1] == bitmap.Size[1] and
                        bitmap.Size[0] < winSize[0]):
                       # We could let the calculation below do this, it should
                       # assign 1, but best to be explicit and avoid any float error.
                       self._scale = 1

                # If we're scaling, size the bitmap to be as large as possible
                # within the current window dimensions
                elif float(bmpWidth)/winWidth > float(bmpHeight)/winHeight:
                    self._scale = float(bmpWidth)/winWidth
                else:
                    self._scale = float(bmpHeight)/winHeight

                if self._scale != 1:
                    bmpWidth  = int(bmpWidth/self._scale)
                    bmpHeight = int(bmpHeight/self._scale)
                    image = bitmap.ConvertToImage()
                    image = image.Rescale(bmpWidth, bmpHeight)
                    self._bitmap = wx.Bitmap(image)

            if bmpWidth > winWidth or bmpHeight > winHeight:
                # bitmap is too big, so crop it
                left  = int((bmpWidth - winWidth)/2)
                upper = int((bmpHeight - winHeight)/2)
                self._offset = (-left, -upper)
            else:
                # bitmap is smaller than window, so paste it in center
                left  = (winWidth - bmpWidth)/2
                upper = (winHeight - bmpHeight)/2
                self._offset = (left, upper)

        self.Refresh()


    ###########################################################
    def OnSize(self, event):
        """Respond to a change in window size

        @param  event  The size event
        """
        if self._shouldScale:
            self.updateBitmap(self._origBitmap)

        event.Skip()


    ###########################################################
    def SetSize(self, size): #PYCHECKER OK: signature doesn't match
        """Update the window size.

        @param  size  The new size.
        """
        self._bestSize = size
        super(BitmapWindow, self).SetSize(size)


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        Use the same method as PilImageWindow.

        @param  event  The paint event.
        """
        clientWidth, clientHeight = self.GetClientSize()
        width, height = self._bitmap.Size

        # Erase if needed
        if (clientWidth, clientHeight) != (width, height):
            # Get a paint context
            dc = wx.AutoBufferedPaintDC(self)
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.Clear()
        else:
            dc = wx.PaintDC(self)

        # Draw the bitmap...
        x, y = self._offset
        dc.DrawBitmap(self._bitmap, x, y, False)


##############################################################################
def test_main():
    """OB_REDACT
    Our main function, which runs test code
    """
    pass


##############################################################################
if __name__ == '__main__':
    test_main()

