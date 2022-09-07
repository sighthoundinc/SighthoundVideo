#!/usr/bin/env python

#*****************************************************************************
#
# CommandProcessorWithExtras.py
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
from   wx.lib.docview import CommandProcessor as wxCommandProcessor

# Local imports...


##############################################################################
class CommandProcessorWithExtras(wxCommandProcessor):
    """This is a command processor, but it has a few extra features...

    The features above and beyond the built-in command processor:
    - Get the right default accelerator for "Redo" on Mac.
    - Properly disables the Undo / Redo menu items when there's nothing to
      undo / redo.  This provides a better user experience, though it's
      important that you call SetMenuStrings() if undo becomes possible /
      impossible.
    - Auto-updates menu items at some opportune times, like:
      - After Submit() is called.
      - After Undo() and Redo() are called.
      - When the SetEditMenu() function is called.
    """

    ###########################################################
    def __init__(self, *args, **kwargs):
        """CommandProcessorWithExtras constructor.

        Mostly, this just calls to our superclass.
        """
        super(CommandProcessorWithExtras, self).__init__(*args, **kwargs)

        if wx.Platform == "__WXMAC__":
            self.SetRedoAccelerator("Ctrl+Shift+Z")


    ###########################################################
    def SetMenuStrings(self, *args, **kwargs): #PYCHECKER signature mismatch OK; trying to be generic
        """Tail-patch SetMenuStrings() to disable/enable Undo/Redo items."""
        super(CommandProcessorWithExtras, self).SetMenuStrings(*args, **kwargs)

        editMenu = self.GetEditMenu()
        if editMenu is not None:
            undoMenuItem = editMenu.FindItemById(wx.ID_UNDO)
            undoMenuItem.Enable(self.CanUndo())

            redoMenuItem = editMenu.FindItemById(wx.ID_REDO)
            redoMenuItem.Enable(self.CanRedo())


    ###########################################################
    def Submit(self, *args, **kwargs): #PYCHECKER signature mismatch OK; trying to be generic
        """Tail-patch Submit() to call SetMenuStrings()."""
        super(CommandProcessorWithExtras, self).Submit(*args, **kwargs)
        self.SetMenuStrings()


    ###########################################################
    def Undo(self, *args, **kwargs): #PYCHECKER signature mismatch OK; trying to be generic
        """Tail-patch Undo() to call SetMenuStrings()."""
        result = super(CommandProcessorWithExtras, self).Undo(*args, **kwargs)
        self.SetMenuStrings()
        return result


    ###########################################################
    def Redo(self, *args, **kwargs): #PYCHECKER signature mismatch OK; trying to be generic
        """Tail-patch Redo() to call SetMenuStrings()."""
        result = super(CommandProcessorWithExtras, self).Redo(*args, **kwargs)
        self.SetMenuStrings()
        return result


    ###########################################################
    def SetEditMenu(self, *args, **kwargs): #PYCHECKER signature mismatch OK; trying to be generic
        """Tail-patch SetEditMenu() to call SetMenuStrings()."""
        super(CommandProcessorWithExtras, self).SetEditMenu(*args, **kwargs)
        self.SetMenuStrings()


    ###########################################################
    def ClearCommands(self, *args, **kwargs): #PYCHECKER signature mismatch OK; trying to be generic
        """Tail-patch ClearCommands() to call SetMenuStrings()."""
        super(CommandProcessorWithExtras, self).ClearCommands(*args, **kwargs)
        self.SetMenuStrings()


    ###########################################################
    def GetUndoAccelTuple(self):
        """Return a "tuple" for "Undo", for use in an accelerator table.

        This will look like:
          (flags, keyCode, wx.ID_UNDO)

        @return  accelTuple  The accelerator tuple for undo...
        """
        # Get the accelerator string from our super and convert to an entry...
        undoAccelEntry = \
            wx.GetAccelFromString("\t" + self.GetUndoAccelerator())
        flags = undoAccelEntry.GetFlags()
        keyCode = undoAccelEntry.GetKeyCode()

        # Make sure it uses CMD, not CTRL on Mac.  In my opinion, this is a
        # working around a bug in GetAccelFromString(), since the menu stuff
        # already handles this...
        if (wx.Platform == "__WXMAC__"):
            flags = (flags & ~(wx.ACCEL_CTRL)) | wx.ACCEL_CMD

        return (flags, keyCode, wx.ID_UNDO)


    ###########################################################
    def GetRedoAccelTuple(self):
        """Return a "tuple" for "Redo", for use in an accelerator table.

        This will look like:
          (flags, keyCode, wx.ID_REDO)

        @return  accelTuple  The accelerator tuple for redo...
        """
        # Get the accelerator string from our super and convert to an entry...
        redoAccelEntry = \
            wx.GetAccelFromString("\t" + self.GetRedoAccelerator())
        flags = redoAccelEntry.GetFlags()
        keyCode = redoAccelEntry.GetKeyCode()

        # Make sure it uses CMD, not CTRL on Mac.  In my opinion, this is a
        # working around a bug in GetAccelFromString(), since the menu stuff
        # already handles this...
        if (wx.Platform == "__WXMAC__"):
            flags = (flags & ~(wx.ACCEL_CTRL)) | wx.ACCEL_CMD

        return (flags, keyCode, wx.ID_REDO)



##############################################################################
def test_main():
    """Contains various self-test code."""
    print "NO TESTS"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
