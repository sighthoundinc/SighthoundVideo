#! /usr/local/bin/python

#*****************************************************************************
#
# DoubleBufferCompatGc.py
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

# Python imports...

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.sysUtils.PlatformUtils import isWindowsXp


##############################################################################
if isWindowsXp():
    def createDoubleBufferCompatGc(paintDc):
        """Create a GC that is compatible w/ parents that use SetDoubleBuffered.

        There appears to be a bug in Windows XP where SetDoubleBuffered(True)
        doesn't really work very well when any of our children use a
        wx.GraphicsContext to draw themselves.

        Also under Windows XP there is a bug when using this class that text
        with an alpha of 255 will not be drawn correctly.  One lame workaround
        is to set the alpha to 254 before calling gc.SetFont().

        This function will detect XP, then create a wx.GraphicsContext that will
        work properly.  Effectively, we will create a graphics context that
        points to an offscreen buffer.  Then, when you're done, we'll use a
        wx.DC call to blit it onto the real paint DC.

        @return gc        The graphics context.
        @return finishFn  Call this function to finish.
        """
        bitmap = wx.Bitmap.FromRGBA(*paintDc.GetSize())
        dc = wx.MemoryDC()
        dc.SelectObject(bitmap)
        gc = wx.GraphicsContext.Create(dc)

        def finishFn():
            dc.SelectObject(wx.NullBitmap)
            paintDc.DrawBitmap(bitmap, 0, 0, True)

        return gc, finishFn
else:
    def createDoubleBufferCompatGc(paintDc): #PYCHECKER OK: Only define one.
        """Create a GC that is compatible w/ parents that use SetDoubleBuffered.

        There appears to be a bug in Windows XP where SetDoubleBuffered(True)
        doesn't really work very well when any of our children use a
        wx.GraphicsContext to draw themselves.

        This is a dummy version of the function to use on non-XP systems.

        @return gc        The graphics context.
        @return finishFn  Call this function to finish.
        """
        gc = wx.GraphicsContext.Create(paintDc)
        finishFn = lambda: None
        return gc, finishFn
