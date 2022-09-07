#!/usr/bin/env python

#*****************************************************************************
#
# FileBrowseButtonFixed.py
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

import os

import wx
from   wx.lib import filebrowsebutton as filebrowse

# We need this because wxPython uses "." as the default starting directory for
# all of its file and directory dialog browsers. On Mac, this works fine, but
# on Windows, it makes the dialog box look ugly and sparse. Since "." equates to
# "current directory", we just call os.getcwd() for Windows as the default
# starting directory.
if wx.Platform == '__WXMSW__':
    _kDefaultStartDirectory = os.getcwd()
else:
    _kDefaultStartDirectory = '.'


##############################################################################
class FileBrowseButton(filebrowse.FileBrowseButton):
    """A version of FileBrowseButton with some fixes.

    Here we just make sure that the default starting directory is set to
    _kDefaultStartDirectory. See comments above _kDefaultStartDirectory for
    details...
    """
    ###########################################################
    def __init__(self, *args, **kwargs):

        if (len(args) < 10) and kwargs.get('startDirectory', None) is None:
            kwargs['startDirectory'] = _kDefaultStartDirectory

        super(FileBrowseButton, self).__init__(*args, **kwargs)


##############################################################################
class DirBrowseButton(filebrowse.DirBrowseButton):
    """A version of DirBrowseButton with some fixes.

    Here we just make sure that the default starting directory is set to
    _kDefaultStartDirectory. See comments above _kDefaultStartDirectory for
    details...
    """
    ###########################################################
    def __init__(self, *args, **kwargs):

        if (len(args) < 10) and kwargs.get('startDirectory', None) is None:
            kwargs['startDirectory'] = _kDefaultStartDirectory

        super(DirBrowseButton, self).__init__(*args, **kwargs)


##############################################################################
class FileBrowseButtonWithHistory(filebrowse.FileBrowseButtonWithHistory):
    """A version of FileBrowseButtonWithHistory with some fixes.

    Here we just make sure that the default starting directory is set to
    _kDefaultStartDirectory. See comments above _kDefaultStartDirectory for
    details...

    ...And to make sure that the change callback gets called after
    you hit the "Browse" button...
    """
    ###########################################################
    def __init__(self, *args, **kwargs):

        if (len(args) < 10) and kwargs.get('startDirectory', None) is None:
            kwargs['startDirectory'] = _kDefaultStartDirectory

        super(FileBrowseButtonWithHistory, self).__init__(*args, **kwargs)


    ###########################################################
    def SetValue(self, value, callBack=1):
        """Sets text control, making sure we fire off an event.

        NOTE: this function is based off the one shipped with wxPython (AKA
        it's a copy of that one).
        The one that comes with wxPython was only for MSW--apparently they
        didn't realize that Mac needs it too!

        ...the original one was licensed under the wxWindows license.

        @param  value     The value to set the string to.
        @param  callBack  If true, we'll make the callback...
        """
        save = self.callCallback
        self.callCallback = callBack
        self.textControl.SetValue(value)
        self.callCallback =  save

        # Hack to call an event handler
        class LocalEvent:
            def __init__(self, string):
                self._string=string
            def GetString(self):
                return self._string
        if callBack==1:
            # The callback wasn't being called when SetValue was used ??
            # So added this explicit call to it
            self.changeCallback(LocalEvent(value))


##############################################################################
class DirBrowseButtonWithHistory(FileBrowseButtonWithHistory):
    """Like FileBrowseButtonWithHistory, but for directories.

    This class, at least as of 2.8.8.1, doesn't even exist in wx.Python.
    However, it's a pretty simple extension.  Since I subclass the
    class above, we should get all of its fixes too.

    If eventually wx adds its own version of this class, we should probably
    subclass from it.
    """
    ###########################################################
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition, #PYCHECKER Too many args OK--wx function
                 size=wx.DefaultSize, style=wx.TAB_TRAVERSAL,
                 labelText="Select a directory:",
                 buttonText="Browse...",
                 toolTip="Type directory name or browse to select",
                 dialogTitle="",
                 startDirectory=_kDefaultStartDirectory,
                 initialValue="",
                 changeCallback=lambda x:x,
                 history=None,
                 dialogClass=wx.DirDialog,
                 newDirectory=False):
        """DirBrowseButtonWithHistory constructor.

        Note: the parameter list may not be 100% complete.  If you need an
        extra parameter, you can add it and just pass it onto our superclass.

        @param  id              wxPython ID
        @param  pos             Initial position.  It's suggested that you leave
                                this default and use "CenterOnParent".
        @param  size            Initial size.
        @param  style           Window style.  See super.
        @param  labelText       Text for the label on the left side of the ctrl.
        @param  buttonText      Text for the browse button.
        @param  toolTip         Tooltip for the control.
        @param  dialogTitle     Title for the dialog.
        @param  startDirectory  Initial directory to start showing the user,
                                unless the history contains something valid.
        @param  initialValue    Initial value to show in the combo box.
        @param  changeCallback  Called when the value changes.
        @param  histroy         Optional history to show.
        @param  dialogClass     The type of dialog; defaults to wx.DirDialog.
        @param  newDirectory    If True, the user is creating the directory.
        """
        # Only include history in extra args if it evaluates to True.  This
        # works around a bit of a logic flaw in the superclass, where it only
        # deletes 'history' from the named args if it evaulates to True.
        extraArgs = {}
        if history:
            extraArgs['history'] = history

        super(DirBrowseButtonWithHistory, self).__init__(
            parent, id, pos=pos, size=size, style=style, labelText=labelText,
            buttonText=buttonText, toolTip=toolTip, dialogTitle=dialogTitle,
            startDirectory=startDirectory, initialValue=initialValue,
            changeCallback=changeCallback,
            **extraArgs
        )

        self._dialogClass = dialogClass
        self._newDirectory = newDirectory


    ###########################################################
    def OnBrowse(self, event=None):
        """Override super's "OnBrowse" button to browse for dirs, not files.

        This is similar to how the non-history "dir browse button" works.  We
        do a few things different, though.  The main one is that we actually
        use the current directory to start in, if it is valid.  ...well, OK,
        maybe we only do just that one thing different.  ;)

        @param  event  The event (ignored).
        """
        # Start with the directory that the user has shown if it's valid,
        # otherwise start with the directory that was passed into the
        # constructor.
        current = self.GetValue()
        if os.path.isdir(current):
            directory = current
        else:
            directory = self.startDirectory

        # We need a different style if the directory must already exist...
        style = 0
        if not self._newDirectory:
            style |= wx.DD_DIR_MUST_EXIST

        dialog = self._dialogClass(self, message=self.dialogTitle,
                                   defaultPath=directory,
                                   style=style)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                self.SetValue(dialog.GetPath())
        finally:
            dialog.Destroy()



##############################################################################
def test_main():
    """OB_REDACT
    Our main function, which runs test code
    """
    pass


##############################################################################
if __name__ == '__main__':
    test_main()

