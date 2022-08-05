#!/usr/bin/env python

#*****************************************************************************
#
# DeferredStatusBar.py
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


##############################################################################
class DeferredStatusBar(wx.StatusBar):
    """A subclass of StatusBar that lets you do faster (but deferred) updates.

    Normally, when you update the status bar, the draw happens right away.
    This subclass of StatusBar allows you to defer the draw until later,
    which can be a speed win (each draw cycle seems to take up some time).
    """

    ###########################################################
    def __init__(self, parent, fieldWidths=None):
        """DeferredStatusBar constructor.

        @param  parent       The parent window.
        @param  fieldWidths  The widths of each field in the status bar.
        """
        super(DeferredStatusBar, self).__init__(parent, -1)

        # If no field width, there's one field that takes up everything...
        if fieldWidths is None:
            fieldWidths = [-1]

        numFields = len(fieldWidths)

         # Set the number of fields and their styles
        self.SetFieldsCount(numFields)
        self.SetStatusStyles([wx.SB_FLAT]*numFields)
        self.SetStatusWidths(fieldWidths)

        self._labels = [wx.StaticText(self) for _ in xrange(numFields)]

        # Register for resizes
        self.Bind(wx.EVT_SIZE, self.OnSize)

        # Setup initial sizes.
        self._reposition()


    ############################################################
    def OnSize(self, event):
        """Handle size events to reposition ourselves.

        @param  event  The size event.
        """
        self._reposition()


    ############################################################
    def SetStatusText(self, text, number=0, deferred=False): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Set the status text in a deferred or non-deferred way.

        It's OK to mix deferred with non-deferred updates. Non-deferred
        updates call Update() immedately but are much slower on the Mac.

        Defaults to the hidden "blank" field for backwards compatibility.
        Does nothing if the field does not contain a visible text box.

        @param  text      The string to set as status text.
        @param  number    The field to update (zero-based)
        @param  deferred  Whether or not to update the UI immediately
        """
        field = self._labels[number]
        field.SetLabel(text)

        # If not deferred, update immediately, else do nothing.  If we do
        # nothing, we'll be updated on the next idle loop
        if not deferred:
            field.Update()

        # Update the positions of the contents of the status bar, since
        # the length of the text probably changed
        self._reposition()


    ############################################################
    def _reposition(self):
        """Reposition our text, given a size change."""

        # Calculate amount off of center to place text boxes, per platform
        if "wxMac" in wx.PlatformInfo:
            fudge = (0, 0)
        else:
            fudge = (2, 1)

        for i, field in enumerate(self._labels):
            rect = self.GetFieldRect(i)
            field.SetPosition((rect.x + fudge[0], rect.y + fudge[1]))
            field.SetSize((rect.width, rect.height))
