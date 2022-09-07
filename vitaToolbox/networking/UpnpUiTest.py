#!/usr/bin/env python

#*****************************************************************************
#
# UpnpUiTest.py
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

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...

from Upnp import ControlPointManager

# Constants...

##############################################################################
class UpnpUiTestFrame(wx.Frame):
    """A frame for showing test info for UPNP."""

    ###########################################################
    def __init__(self, controlPointMgr):
        """UpnpUiTestFrame constructor.

        @param  controlPointMgr  The ControlPointManager class to use.
        """
        super(UpnpUiTestFrame, self).__init__(None, size=(600, 500))

        self._controlPointMgr = controlPointMgr

        self._initUiWidgets()

        self.Bind(wx.EVT_IDLE, self.OnIdle)

        self.Show()


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        self._panel = wx.Panel(self)
        self._listBox = wx.ListBox(self._panel, -1)
        self._listBox.SetMinSize((-1, 150))
        makeFontDefault(self._listBox)

        self._detailsLabel = wx.StaticText(self._panel, -1, "",
                                           style=wx.ST_NO_AUTORESIZE)
        makeFontDefault(self._detailsLabel)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self._listBox, 0, wx.EXPAND)
        mainSizer.Add(self._detailsLabel, 1, wx.EXPAND)
        self._panel.SetSizer(mainSizer)

        frameSizer = wx.BoxSizer()
        frameSizer.Add(self._panel, 1, wx.EXPAND)
        self.SetSizer(frameSizer)

        self._listBox.Bind(wx.EVT_LISTBOX, self.OnListBox)


    ###########################################################
    def OnListBox(self, event):
        """Handle listbox events.

        @param  event  The event.
        """
        selection = self._listBox.GetSelection()
        if selection == -1:
            self._detailsLabel.SetLabel("")
        else:
            usn = self._listBox.GetClientData(selection)
            device = self._controlPointMgr.getDevice(usn)

            self._detailsLabel.SetLabel(str(device))


    ###########################################################
    def OnIdle(self, event):
        """Handle idle events.

        @param  event  The idle event.
        """
        event.Skip()

        oldSelection = self._listBox.GetStringSelection()

        changedUsns, goneUsns = self._controlPointMgr.pollForChanges()

        for usn in changedUsns:
            print "%s:\n%s\n%s\n%s\n%s\n\n---\n" % (
                usn,
                self._controlPointMgr.getDevice(usn).getFriendlyName(),
                self._controlPointMgr.getDevice(usn).getPresentationUrl(),
                self._controlPointMgr.getDevice(usn).getModelName(),
                str(self._controlPointMgr.getDevice(usn))
            )

        for usn in goneUsns:
            print "GONE: %s:\n\n---\n" % (usn)

        # Kill the ones that are gone or modified...
        for i in xrange(self._listBox.GetCount()-1, -1, -1):
            usn = self._listBox.GetClientData(i)
            if (usn in goneUsns) or (usn in changedUsns):
                self._listBox.Delete(i)

        # Add in the new ones, in alphabetical order...
        deviceList = [
            (self._controlPointMgr.getDevice(usn).getFriendlyName(True), usn)
            for (usn) in changedUsns
        ]
        deviceList.extend((name, None) for name in self._listBox.GetStrings())
        deviceList.sort(key=lambda x: (x[0].lower(), x[1]))

        for i, (friendlyName, usn) in enumerate(deviceList):
            if usn is not None:
                self._listBox.Insert(friendlyName, i, usn)

        self._listBox.SetStringSelection(oldSelection)



##############################################################################
def main():
    app = wx.App(True)

    controlPointMgr = ControlPointManager()
    frame = UpnpUiTestFrame(controlPointMgr)

    frame.CenterOnParent()

    # Run the main loop, which will close when the frame does.
    app.MainLoop()



if __name__ == '__main__':
    main()
