#!/usr/bin/env python

#*****************************************************************************
#
# FontUtils.py
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

# Common 3rd-party imports...
import wx

##############################################################################
def makeFontDefault(*args):
    """Sets the font for the given window according to GetClassDefaultAttributes

    I'm not sure why you need to do this (it seems like the default should be,
    ummmmm, the default?), but it seems to make a difference on the Mac at
    least.  Weird.

    Update: observed behavior was that calling this method on wx.Choice removed
    selection set on that wx.Choice. Adding the code to work around this

    @param  win  The window to set the font for.
    @param  ...  More windows to set the font for...
    """
    for win in args:
        selection = 0
        selectionNeeded = isinstance(win, wx.Choice)
        if selectionNeeded:
            selection = win.GetSelection()
        win.SetFont(win.GetClassDefaultAttributes().font)
        if selectionNeeded and selection >= 0:
            selection = win.SetSelection(selection)


##############################################################################
def makeFontBold(*args):
    """Makes the font bold for the given controls.

    @param  win  The window to set the font for.
    @param  ...  More windows to set the font for...
    """
    for win in args:
        font = win.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        win.SetFont(font)


##############################################################################
def makeFontUnderlined(*args):
    """Makes the font underlined for the given controls.

    @param  win  The window to set the font for.
    @param  ...  More windows to set the font for...
    """
    for win in args:
        font = win.GetFont()
        font.SetUnderlined(True)
        win.SetFont(font)


##############################################################################
def makeFontNotUnderlined(*args):
    """Makes the font underlined for the given controls.

    @param  win  The window to set the font for.
    @param  ...  More windows to set the font for...
    """
    for win in args:
        font = win.GetFont()
        font.SetUnderlined(False)
        win.SetFont(font)


##############################################################################
def adjustPointSize(win, multiplier):
    """Adjust the point size by the given amount.

    Similar to growTitleText(), except never makes things bold.  Can be used
    to shrink text too...

    @param  multiplier  The amount to adjust by.
    """
    font = win.GetFont()
    font.SetPointSize(font.GetPointSize()*multiplier)
    win.SetFont(font)


##############################################################################
def shrinkLargeText(win, newSize=None):
    """Make text in the given control smaller if it is too big

    On osx we often want to shrink the font as the default is fairly large.
    This is a pretty bad hack, but we keep doing it everywhere so we might
    as well centralize it so it's easier to fix up later.

    TODO: Maybe everyone who is calling this should call makeFontDefault()
    instead?

    @param  win      The window containing the text to shrink
    @param  newSize  Optional size for the text to be shrunk to
    """
    font = win.GetFont()
    pointSize = font.GetPointSize()
    if pointSize > 10:
        if newSize:
            font.SetPointSize(newSize)
        else:
            font.SetPointSize(pointSize-2)
        win.SetFont(font)


##############################################################################
def growTitleText(win, multiplier=1.5):
    """Increase the text size of the given window.

    Bolds the text if windows, not necessary on osx.

    @param  win         The window whose font should grow
    @param  multiplier  The multiplier to increase the size by
    """
    font = win.GetFont()
    font.SetPointSize(font.GetPointSize()*multiplier)
    if font.GetPointSize() < 14:
        font.SetWeight(wx.FONTWEIGHT_BOLD)
    win.SetFont(font)



