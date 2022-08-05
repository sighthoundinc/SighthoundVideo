#!/usr/bin/env python

#*****************************************************************************
#
# TextCtrlUtils.py
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
import string

# Toolbox imports...

# Local imports...
from CreateMenuFromData import createMenuFromData

# Constants...
_kLinkColor = (0, 102, 204, 255)
_kLinkHoverColor = (5, 153, 255, 255)


##############################################################################
def addTextCtrlAccelerators(editText):
    """Adds missing "accelerator" keys to a TextCtrl.

    I'm not sure why wx seems to be missing these, but it's annoying.

    @param  editText  The TextControl to add the missing keys to.
    """
    def _onAccelerator(event):
        menuId = event.GetId()

        if menuId == wx.ID_UNDO:
            if editText.CanUndo():
                editText.Undo()
            return
        elif menuId == wx.ID_REDO:
            if editText.CanRedo():
                editText.Redo()
            return
        elif menuId == wx.ID_SELECTALL:
            editText.SetSelection(-1, -1)
            return

        event.Skip()

    # Add accelerator keys
    accelTable = None
    if wx.Platform == "__WXMAC__":
        # I'm not sure why, but Undo wasn't working automatically for Mac.
        accelTable = wx.AcceleratorTable([
            (wx.ACCEL_CMD, ord('Z'), wx.ID_UNDO),
            (wx.ACCEL_CMD | wx.ACCEL_SHIFT, ord('Z'), wx.ID_REDO),
        ])
    elif wx.Platform == "__WXMSW__":
        # ...and select all isn't working on Windows.  Sigh...
        accelTable = wx.AcceleratorTable([
            (wx.ACCEL_CMD, ord('A'), wx.ID_SELECTALL),
        ])

    if accelTable is not None:
        editText.SetAcceleratorTable(accelTable)
        editText.Bind(wx.EVT_MENU, _onAccelerator)


##############################################################################
def addTextCtrlPopup(editText):
    """Adds a popup menu with edit menu commands to a text control.

    @param  editText  The TextControl to add the popup menu to.
    """
    # Different redo accelerator for Mac and Windows...
    if wx.Platform == "__WXMAC__":
        redoText = "&Redo\tShift+Ctrl+Z"
    else:
        redoText = "&Redo\tCtrl+Y"

    def _onShowPopup(event):
        # Create the menu; note that Cut/Copy/Paste names seem to come for
        # free from wx; Undo/Redo/Select All do too, but:
        # - Undo and Redo don't get accelerators (?)
        # - Select All has lower-case "A".
        menuData = (
            ("&Undo\tCtrl+Z", "", wx.ID_UNDO, None),
            (redoText, "", wx.ID_REDO, None),
            (None, None, None, None),
            ("", "", wx.ID_CUT, None),
            ("", "", wx.ID_COPY, None),
            ("", "", wx.ID_PASTE, None),
            (None, None, None, None),
            ("Select &All\tCtrl+A", "", wx.ID_SELECTALL, None),
        )
        popupMenu = createMenuFromData(menuData, editText)

        # Popup the menu...
        editText.PopupMenu(popupMenu)

        popupMenu.Destroy()

    # Register for context menu event (usually right-click)...
    editText.Bind(wx.EVT_CONTEXT_MENU, _onShowPopup)


##############################################################################
def fixSelection(*args):
    """Fix the selection of the passed text fields on Mac.

    For some reasons, Mac text fields don't start out with their whole contents
    selected, which causes weird behavior if you use the tab key to cycle
    through focus.  This fixes that.  Also: it contains a workaround to the
    fact that there is a graphical glitch on Mac if you set the selection on
    a non-focused text field.  Because of this workaround, it ends up giving
    focus to the first item in this list.

    @param  ...  Just pass text fields in, they will all be fixed.
    """
    if wx.Platform == '__WXMAC__':
        # Select all in each text field, then give each one focus.  The giving
        # of focus + taking it away fixes graphical glitches, at least in
        # wx 2.8.9.2...
        for textField in args:
            textField.SelectAll()
            textField.SetFocus()

        # Select the first one again.
        if args:
            args[0].SetFocus()
        else:
            assert False, "fixSelection should be passed at least one item"


##############################################################################
def setHyperlinkColors(hyperlinkCtrl):
    """Set the hyperlink colors on a hyperlink control.

    @param  hyperlinkCtrl The hyperlink control to modify.
    """
    hyperlinkCtrl.SetNormalColour(wx.Colour(*_kLinkColor))
    hyperlinkCtrl.SetHoverColour(wx.Colour(*_kLinkHoverColor))
    hyperlinkCtrl.SetVisitedColour(hyperlinkCtrl.GetNormalColour())


########################################################################
class CharValidator(wx.Validator):
    ''' Validates data as it is entered into the text controls. '''

    kAllowDigits        = 1
    kNoDigits           = 2
    kAllowAlpha         = 4
    kNoAlpha            = 8
    kAllowSpace         = 16
    kNoSpace            = 32
    kAllowPunctuation   = 64
    kNoPunctuation      = 128
    kPermissive         = 256

    #----------------------------------------------------------------------
    def __init__(self, flags, allowedChars="", bannedChars=""):
        wx.Validator.__init__(self)
        self.flags = flags
        self.allowedChars = allowedChars
        self.bannedChars = bannedChars
        self.Bind(wx.EVT_CHAR, self.OnChar)

    #----------------------------------------------------------------------
    def Clone(self):
        '''Required Validator method'''
        return CharValidator(self.flags)

    #----------------------------------------------------------------------
    def Validate(self, win):
        return True

    #----------------------------------------------------------------------
    def TransferToWindow(self):
        return True

    #----------------------------------------------------------------------
    def TransferFromWindow(self):
        return True

    #----------------------------------------------------------------------
    def _processFlag(self, event, flag):
        if (self.flags & flag) != 0:
            # This has been explicitly permitted
            event.Skip()
        elif (self.flags & (flag*2)) != 0:
            # This has been explicitly banned
            pass
        elif (self.flags & CharValidator.kPermissive) != 0:
            # if the validator is marked as permissive, allow this char
            event.Skip()

    #----------------------------------------------------------------------
    def OnChar(self, event):
        keycode = int(event.GetKeyCode())
        if keycode < 256:
            #print keycode
            key = chr(keycode)
            #print key
            # The key had explicitly been banned
            if key in self.bannedChars:
                return
            if key in self.allowedChars:
                event.Skip()
                return
            if key in string.letters:
                self._processFlag(event, CharValidator.kAllowAlpha)
            elif key in string.digits:
                self._processFlag(event, CharValidator.kAllowDigits)
            elif key in string.whitespace:
                self._processFlag(event, CharValidator.kAllowSpace)
            elif key in string.punctuation:
                self._processFlag(event, CharValidator.kAllowPunctuation)
            elif (self.flags & CharValidator.kPermissive) != 0:
                # char isn't any of the known groups; if the validator is marked as permissive, allow it
                event.Skip()

