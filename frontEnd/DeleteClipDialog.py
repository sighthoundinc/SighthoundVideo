#!/usr/bin/env python

#*****************************************************************************
#
# DeleteClipDialog.py
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

# Common 3rd-party imports...
import wx
import time

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...


_kPaddingSize = 4
_kBorderSize = 16
_kDeleteClipProgressText = "Deleting clip %i of %i."
_kTimerQuick = 100
_kTimerSlow = 500


###############################################################
class DeleteClipDialog(wx.Dialog):
    """A dialog for deleting video clips."""
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, clipManager,
                 clipList):
        """Initializer for DeleteClipDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        @param  dataManager    The data manager used by the front end.
        @param  clipManager    The clip manager used by the front end.
        @param  clipList       A list of (location, startTime, stopTime) for
                               each clip to delete.
        """
        wx.Dialog.__init__(self, parent, -1, "Delete clip(s)")

        try:
            self._backEndClient = backEndClient
            self._dataManager = dataManager
            self._clipManager = clipManager
            self._clipList = clipList

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            helpText = wx.StaticText(self, -1, "Choose an option to delete the "
                                     "clip(s) from this list and other searches"
                                     " containing the clip(s).")
            self._quickRadio = wx.RadioButton(self, -1, "Quick delete (remove "
                                              "information used to find the "
                                              "video)", style=wx.RB_GROUP)
            self._quickRadio.SetValue(True)
            self._slowRadio = wx.RadioButton(self, -1, "Permanently delete "
                                             "source video (may take several "
                                             "seconds per clip)")
            warnText = wx.StaticText(self, -1, "This action cannot be undone.")
            makeFontDefault(helpText, self._quickRadio, self._slowRadio,
                            warnText)
            helpText.Wrap(self._slowRadio.GetBestSize()[0])

            sizer.Add(helpText, 0, wx.ALL, _kBorderSize)
            sizer.Add(self._quickRadio, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._slowRadio, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.Add(warnText, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)

            self.FindWindowById(wx.ID_OK, self).SetDefault()
            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)
            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

            self.Fit()
            self.CenterOnParent()

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def OnOk(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        dlg = _DeleteClipsProgDialog(self, self._backEndClient,
                                     self._dataManager, self._clipManager,
                                     self._clipList,
                                     self._quickRadio.GetValue())
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)


_kActionTimeout = 10 # 10 seconds should be more than enough to delete a single clip

###############################################################
class _DeleteClipsProgDialog(wx.Dialog):
    """A progress dialog shown while clips are being deleted."""
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, clipManager,
                 clipList, isQuick):
        """Initializer for _DeleteClipsProgDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        @param  dataManager    The data manager used by the front end.
        @param  clipManager    The clip manager used by the front end.
        @param  clipList       A list of (location, startTime, stopTime) for
                               each clip to delete.
        @param  isQuick        If True perform quick deletes.
        """
        wx.Dialog.__init__(self, parent, -1, "Delete clip(s)",
                           style=wx.CAPTION | wx.SYSTEM_MENU)

        try:
            self._backEndClient = backEndClient
            self._dataManager = dataManager
            self._clipManager = clipManager
            self._clipList = clipList
            self._numClips = len(clipList)
            self._isQuick = isQuick
            self._cancelled = False
            self._curIndex = -1

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            self._label = wx.StaticText(self, -1, _kDeleteClipProgressText %
                                        (1, self._numClips))
            self._gauge = wx.Gauge(self, -1, self._numClips)
            self._gauge.SetMinSize((300, -1))

            sizer.Add(self._label, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)
            sizer.AddSpacer(8)
            sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT |
                      wx.BOTTOM, _kBorderSize)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.BOTTOM | wx.EXPAND, 16)

            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

            self.Fit()
            self.CenterOnParent()

            self._errString = ""
            self._actionStart = None

            # Begin the first delete
            self._deleteNext()

            # Start the update timer
            self._timer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self.OnUpdate, self._timer)
            if isQuick:
                self._timer.Start(_kTimerQuick)
            else:
                self._timer.Start(_kTimerSlow)

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _deleteNext(self):
        """Update the progress dialog with the current status.

        @param  event  The Timer event, ignored.
        """
        # If we're done or the user cancelled stop the timer and exit.
        if self._cancelled or (self._curIndex == self._numClips-1):
            self._timer.Stop()
            if len(self._errString):
                errStr = "Some errors had occurred: \n" + self._errString
                dlg = wx.MessageDialog(self, errStr, "Error", wx.OK | wx.ICON_ERROR)
                try:
                    dlg.ShowModal()
                finally:
                    dlg.Destroy()
            self.EndModal(wx.OK)
            return

        self._actionStart = time.time()

        # Begin to delete next clip.
        self._curIndex += 1
        loc, start, stop = self._clipList[self._curIndex]
        self._backEndClient.deleteVideo(loc, start, stop, self._isQuick)

        # Update the label and gauge.
        self._label.SetLabel(_kDeleteClipProgressText % (self._curIndex+1,
                                                         self._numClips))
        self._gauge.SetValue(self._curIndex)


    ###########################################################
    def OnUpdate(self, event):
        """Update the progress dialog with the current status.

        @param  event  The Timer event, ignored.
        """
        finished = False

        # Check if the current delete has completed.
        cam, start, stop = self._clipList[self._curIndex]
        if self._isQuick:
            self._dataManager.setCameraFilter([cam])
            activeObjects = self._dataManager.getActiveObjectsBetweenTimes(start*1000,
                                                                  stop*1000)
            if not activeObjects:
                finished = True
            elif time.time() - self._actionStart > _kActionTimeout:
                self._errString += "- objects still present between [%d,%d] -> %s\n" % (start, stop, str(activeObjects))
                finished = True
        else:
            checkTime = (start+stop)/2*1000
            files = self._clipManager.getFilesBetween(cam, checkTime, checkTime)
            if not files:
                finished = True
            elif time.time() - self._actionStart > _kActionTimeout:
                self._errString += "- files still present between [%d,%d] -> %s\n" % (start, stop, str(files))
                finished = True

        if finished:
            self._deleteNext()


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self._cancelled = True
        self._label.SetLabel("Canceling...")

