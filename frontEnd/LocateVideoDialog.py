#!/usr/bin/env python

#*****************************************************************************
#
# LocateVideoDialog.py
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
import os
import shutil
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.wx.FileBrowseButtonFixed import DirBrowseButton

# Local imports...
from appCommon.CommonStrings import kAppName, kVideoFolder
from FrontEndUtils import promptUserIfRemotePathEvtHandler


_kPaddingSize = 4
_kBorderSize = 16


###############################################################
class LocateVideoDialog(wx.Dialog):
    """A dialog for moving video data settings."""
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager):
        """Initializer for MoveVideoDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        @param  dataManager    The data manager used by the front end.
        """
        wx.Dialog.__init__(self, parent, -1, "Video recording")

        try:
            self._backEndClient = backEndClient
            self._dataManager = dataManager

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            label = wx.StaticText(self, -1, "Video files could not be found.")
            errText = wx.StaticText(self, -1, "If you store video on a network "
                                    "or external drive, click Cancel and check "
                                    "your connection.  Or click Browse to "
                                    "select or create the folder to store video"
                                    " recorded by %s." % kAppName)
            makeFontDefault(errText)
            errText.Wrap(350)

            self._newLocField = DirBrowseButton(
                self, -1, labelText='',
                changeCallback=promptUserIfRemotePathEvtHandler
            )
            self._findRadio = wx.RadioButton(self, -1, "Locate my videos (a "
                                             'folder called "%s")' %
                                             kVideoFolder, style=wx.RB_GROUP)
            self._findRadio.SetValue(True)
            self._newRadio = wx.RadioButton(self, -1, "Create a new folder to "
                                            "store video")

            sizer.Add(label, 0, wx.ALL, _kBorderSize)
            sizer.Add(errText, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, _kBorderSize)
            sizer.Add(self._findRadio, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._newRadio, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.Add(self._newLocField, 0, wx.EXPAND | wx.ALL, _kBorderSize)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.BOTTOM | wx.EXPAND, 16)

            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)
            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)
            self.FindWindowById(wx.ID_CANCEL, self).SetDefault()

            self.Fit()
            self.CenterOnParent()

            self._newLocField.SetFocus()

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _setLocCursorToZero(self):
        """Set the cursor position of the location field to zero."""
        for child in self._newLocField.GetChildren():
            if hasattr(child, "SetInsertionPoint"):
                child.SetInsertionPoint(0)
                child.ShowPosition(0)


    ###########################################################
    def OnOk(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        newPath = self._newLocField.GetValue()

        # For error cases we want to put the focus back on the directory field.
        self._newLocField.SetFocus()
        self._setLocCursorToZero()

        startFromScratch = self._newRadio.GetValue()

        if not newPath:
            # Ensure the directory field is not blank.
            wx.MessageBox("You must select a folder.", "Locate Video Files",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        if not startFromScratch and os.path.basename(newPath) != kVideoFolder:
            wx.MessageBox("This does not appear to be a valid video folder."
                          "  The folder that contains video should be named "
                          '"%s."' % kVideoFolder, "Locate Video Files",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        if not os.path.isdir(newPath):
            # Check if the directory exists.
            if not startFromScratch:
                wx.MessageBox("The location you selected does not appear to be "
                              "a folder.", "Locate Video Files",
                              wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
                return
            else:
                res = wx.MessageBox("The location you selected does not appear "
                                    "to be a folder.  Would you like to create "
                                    "one now?", "Locate Video Files",
                                    wx.YES_DEFAULT | wx.ICON_QUESTION |
                                    wx.YES_NO, self.GetTopLevelParent())
                if res != wx.YES:
                    return

                # Try to create the directory.
                try:
                    os.makedirs(newPath)
                except Exception:
                    pass
                if not os.path.isdir(newPath):
                    # If we couldn't create the directory show an error.
                    wx.MessageBox("The folder could not be created.  Please "
                                  "select a different location.",
                                  "Locate Video Files", wx.OK | wx.ICON_ERROR,
                                  self.GetTopLevelParent())
                return

        if startFromScratch:
            newVideoDir = os.path.join(newPath, kVideoFolder)
            if os.path.isdir(newVideoDir):
                # Check if archive folder exists already.
                res = wx.MessageBox('A folder named "%s" already exists at the '
                                    "selected location.  Delete this data and "
                                    "proceed?" % kVideoFolder,
                                    "Locate Video Files", wx.ICON_QUESTION |
                                    wx.YES_NO | wx.NO_DEFAULT,
                                    self.GetTopLevelParent())
                if res != wx.YES:
                    return

                # Attempt to remove the existing directory.
                try:
                    shutil.rmtree(newVideoDir)
                except Exception:
                    pass
                if os.path.isdir(newVideoDir):
                    # If the directory still exists give an error.
                    wx.MessageBox('The folder "%s" could not be deleted.  '
                                  'Manually remove it and try again, or select '
                                  'a different location.' % kVideoFolder,
                                  "Locate Video Files", wx.ICON_ERROR | wx.OK,
                                  self.GetTopLevelParent())
                    return

        if startFromScratch:
            self._backEndClient.setVideoLocation(newPath, False)
        else:
            # We don't want to send the path with _kVideoFolder already in it.
            self._backEndClient.setVideoLocation(os.path.split(newPath)[0],
                                                 False, True)

        dlg = _ChangeLocationProgDialog(self, self._backEndClient)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

        finished = False
        while not finished:
            # If the dialog couldn't be created for some weird reason we still
            # want to wait until the processing is complete.
            finished, success = \
                            self._backEndClient.getVideoLocationChangeStatus()
            time.sleep(.2)

        if success:
            if startFromScratch:
                self._dataManager.setVideoStoragePath(newVideoDir)
            else:
                self._dataManager.setVideoStoragePath(newPath)
        else:
            wx.MessageBox("Unable to change the folder location.  Select a "
                          "different location.", "Locate Video Files",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())

        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)


###############################################################
class _ChangeLocationProgDialog(wx.Dialog):
    """A progress dialog shown while a directory change operation is ongoing."""
    ###########################################################
    def __init__(self, parent, backEndClient):
        """Initializer for _ChangeLocationProgDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        """
        wx.Dialog.__init__(self, parent, -1, "Video recording",
                           style=wx.CAPTION | wx.SYSTEM_MENU)

        try:
            self._backEndClient = backEndClient

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            label = wx.StaticText(self, -1,
                                  "Changing the video storage location.")
            self._gauge = wx.Gauge(self, -1, 100)

            sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)
            sizer.AddSpacer(8)
            sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT |
                      wx.BOTTOM, _kBorderSize)

            self.Fit()
            self.CenterOnParent()

            self._timer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self.OnUpdate, self._timer)
            self._timer.Start(200)

            self.Bind(wx.EVT_CHAR_HOOK, self.OnKey)

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def OnUpdate(self, event):
        """Update the progress dialog and estimated time

        @param  event  The Timer event, ignored.
        """
        finished, _ = self._backEndClient.getVideoLocationChangeStatus()
        if finished:
            self._timer.Stop()
            self.EndModal(wx.OK)
            return

        # Pulse the progress dialog.
        self._gauge.Pulse()


    ###########################################################
    def OnKey(self, event):
        """Ignore escape events.

        @param  event  The EVT_CHAR_HOOK event.
        """
        event.Skip(event.GetKeyCode() != wx.WXK_ESCAPE)
