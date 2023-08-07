

#*****************************************************************************
#
# MoveVideoDialog.py
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
import os
import shutil
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.path.GetDiskSpaceAvailable import getDiskSpaceAvailable
from vitaToolbox.path.PathUtils import getDirSize, abspathU
from vitaToolbox.path.VolumeUtils import getVolumeNameAndType, kUnknownDiskTypes
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.wx.FileBrowseButtonFixed import DirBrowseButton

# Local imports...
from appCommon.CommonStrings import kVideoFolder
from FrontEndUtils import promptUserIfRemotePathEvtHandler


_kPaddingSize = 4
_kBorderSize = 16
_kFreeSpaceBuffer = 1024*1024*300

_kEstimatedTimeStr = "Estimated time left: %s (%.1f of %s GB copied)"
_kCalculatingStr =   "Calculating... this may take several minutes                   "

###############################################################
class MoveVideoDialog(wx.Dialog):
    """A dialog for moving video data settings."""
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, logger):
        """Initializer for MoveVideoDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        @param  dataManager    The data manager used by the front end.
        @param  logger         Logger instance to use.
        """
        wx.Dialog.__init__(self, parent, -1, "Move video")

        self._logger = logger
        try:
            self._backEndClient = backEndClient
            self._dataManager = dataManager

            self._origStoragePath = abspathU(self._backEndClient.getVideoLocation())
            self._origVolName, self._origVolType = \
                                    getVolumeNameAndType(self._origStoragePath)

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            locLabel = wx.StaticText(self, -1, "Video storage location (click "
                                     "browse to change):")
            self._newLocField = DirBrowseButton(
                self, -1, labelText='',
                changeCallback=promptUserIfRemotePathEvtHandler
            )
            self._newLocField.SetValue(self._origStoragePath)
            self._moveRadio = wx.RadioButton(self, -1,
                                             "Move existing video to the new "
                                             "location", style=wx.RB_GROUP)
            self._moveRadio.SetValue(True)
            self._deleteRadio = wx.RadioButton(self, -1,
                                               "Delete existing video")

            self._usedGb = getDirSize(os.path.join(self._origStoragePath,
                                                   kVideoFolder))
            self._logger.info("size of data to move: %d" % self._usedGb)
            self._usedGb = self._usedGb/1024./1024/1024

            if self._usedGb >= .1:
                sizeStr = "%.1f GB" % self._usedGb
            else:
                sizeStr = "< 100 MB"

            textA = wx.StaticText(self, -1, "Large file transfers can take "
                                  "several hours (you have %s of video)." %
                                  sizeStr)
            textB = wx.StaticText(self, -1, "Do NOT turn off or restart your "
                                  "computer before the transfer is complete.")
            makeFontDefault(textA, textB)

            sizer.Add(locLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._newLocField, 0, wx.EXPAND | wx.LEFT | wx.RIGHT,
                      _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._moveRadio, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._deleteRadio, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.Add(textA, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)
            sizer.Add(textB, 0, wx.LEFT | wx.RIGHT, _kBorderSize)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)

            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)
            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

            self.Fit()
            self.CenterOnParent()

            self._newLocField.SetFocus()
            self._setLocCursorToZero()

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
        newPath = abspathU(self._newLocField.GetValue())
        self._newLocField.SetValue(newPath)

        # For error cases we want to put the focus back on the directory field.
        self._newLocField.SetFocus()
        self._setLocCursorToZero()

        if not newPath:
            # Ensure the directory field is not blank.
            wx.MessageBox("You must select a folder.", "Move Video Files",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        fullOrigPath = os.path.join(self._origStoragePath, kVideoFolder)
        if fullOrigPath == os.path.commonprefix([fullOrigPath, newPath]):
            # Prevent selecting a folder inside the current video folder.
            wx.MessageBox("You cannot select a folder inside the current "
                          "video folder.", "Move Video Files",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        appDir = os.getcwdu()
        if appDir == os.path.commonprefix([appDir, newPath]):
            # Prevent selecting a folder inside the application folder.
            wx.MessageBox("You cannot store your videos in the same "
                          "location as the application.", "Move Video Files",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        if not os.path.isdir(newPath):
            # Check if the directory exists.
            res = wx.MessageBox("The specified folder does not exist.  Would"
                                " you like to create it now?",
                                "Move Video Files", wx.YES_NO | wx.YES_DEFAULT
                                | wx.ICON_QUESTION, self.GetTopLevelParent())
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
                              "select a different location.", "Move Video Files",
                              wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
                return

        if newPath == self._origStoragePath:
            # The directory didn't change.
            wx.MessageBox("You must select a different folder location to move "
                          "videos.", "Move Video Files", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            return

        newVideoDir = os.path.join(newPath, kVideoFolder)
        if os.path.isdir(newVideoDir):
            # Check if archive folder exists already.
            res = wx.MessageBox('A folder named "%s" already exists at the '
                                "selected location.  Delete this data and "
                                "proceed?" % kVideoFolder, "Move Video Files",
                                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
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
                wx.MessageBox('The folder "%s" could not be deleted.  Manually '
                              'remove it and try again, or select a different '
                              'location.' % kVideoFolder, "Move Video Files",
                              wx.ICON_ERROR | wx.OK, self.GetTopLevelParent())
                return

        targetVolName, targetVolType = getVolumeNameAndType(newPath)
        if (targetVolName != self._origVolName or \
           targetVolType in kUnknownDiskTypes) and self._moveRadio.GetValue():
            spaceAvail = getDiskSpaceAvailable(newPath)
            usedBytes = self._usedGb*1024*1024*1024
            if spaceAvail < usedBytes+_kFreeSpaceBuffer:
                # If we're on a different disk ensure we have enough space to
                # copy the files.
                mbAvail = spaceAvail/1024/1024
                mbNeeded = (usedBytes+_kFreeSpaceBuffer)/1024/1024
                wx.MessageBox("You must have %d MB free to copy your existing "
                              "videos.  There is currently only %d MB free.  "
                              "Free some space, select a different location or "
                              'select the "Delete existing video" option.' %
                              (mbNeeded, mbAvail), "Move Video Files", wx.OK |
                              wx.ICON_ERROR, self.GetTopLevelParent())
                return

        # Close any open files to prevent user required cleanup on windows.
        # Save the current video state so that we can re-open the closed
        # file when we're done.
        vidState = self._dataManager.getVideoState()
        self._dataManager.forceCloseVideo()

        # Perform the move.
        self._backEndClient.setVideoLocation(newPath,
                                             self._moveRadio.GetValue())

        isCopying = self._moveRadio.GetValue()
        if isCopying:
            progDlgLabel = "Moving video files from %s (%s) to %s (%s)" % \
                            (self._origVolType, self._origVolName,
                             targetVolType, targetVolName)
        else:
            progDlgLabel = \
                "Removing existing videos and changing the storage location."

        dlg = _MoveVideoProgressDialog(self, self._backEndClient, isCopying,
                                       progDlgLabel, newVideoDir,
                                       self._usedGb*1024*1024*1024)
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
            self._dataManager.setVideoStoragePath(newVideoDir)
        else:
            wx.MessageBox("The relocation failed.", "Move Video Files", wx.OK |
                          wx.ICON_ERROR, self.GetTopLevelParent())

        # Restore the video state, using the file in the new location.
        self._dataManager.restoreVideoState(vidState)

        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)


###############################################################
class _MoveVideoProgressDialog(wx.Dialog):
    """A progress dialog displayed while a move operation is ongoing."""
    ###########################################################
    def __init__(self, parent, backEndClient, copyingData, label, newVideoDir,
                 targetSize):
        """Initializer for _MoveVideoProgressDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        @param  copyingData    True if we're copying data.
        @param  label          The label string for the dialog.
        @param  newVideoDir    Path to the new archive directory.
        @param  targetSize     The size in bytes of data being moved.
        """
        wx.Dialog.__init__(self, parent, -1, "Move video",
                           style=wx.CAPTION | wx.SYSTEM_MENU)

        try:
            self._backEndClient = backEndClient
            self._copying = copyingData
            self._newVideoDir = newVideoDir

            # Prevent divide by zeros.
            self._targetSize = max(targetSize, 1)

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            label = wx.StaticText(self, -1, label)
            self._gauge = wx.Gauge(self, -1, 100)
            self._gauge.SetMinSize((350, -1))

            sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)
            sizer.AddSpacer(8)
            sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT,
                      _kBorderSize)

            if copyingData:
                self._startTime = time.time()

                targetGb = targetSize/1024./1024/1024
                if targetGb < .1:
                    self._targetGbStr = "<.1"
                else:
                    self._targetGbStr = "%.1f" % targetGb

                self._estimatedTime = wx.StaticText(self, -1,
                                                    _kCalculatingStr)
                sizer.AddSpacer(8)
                sizer.Add(self._estimatedTime, 0, wx.BOTTOM | wx.LEFT |
                          wx.RIGHT, _kBorderSize)
            else:
                sizer.AddSpacer(_kBorderSize)

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

        if self._copying:
            # Calculate how much space has been copied and update
            # the progress dialog.
            self._setBytes(getDirSize(self._newVideoDir))
        else:
            # Pulse the progress dialog.
            self._gauge.Pulse()


    ###########################################################
    def _setBytes(self, curBytesCopied):
        """Update the progress bar to reflect the current status

        @param  curBytesCopied  The number of bytes that have been copied.
        """
        if not self._copying:
            return

        now = time.time()
        percent = float(curBytesCopied)/self._targetSize
        percent = min(0.999, percent)
        gb = curBytesCopied/1024./1024/1024

        # Update the gauge
        self._gauge.SetValue(100*percent)

        # Update the estimated time string
        if percent == 0:
            self._estimatedTime.SetLabel(_kCalculatingStr)
            self.Refresh()
            return
        else:
            elapsed = now-self._startTime
            total = elapsed/percent
            remaining = int(total-elapsed)

            if remaining > 60:
                minutes = int(remaining/60)
                timeStr = "%i minutes" % (minutes+1)
            else:
                if remaining > 1:
                    timeStr = "%i seconds" % remaining
                else:
                    # Here we are nearly done, but it might stay for a bit
                    # removing the old data.  We have seen it take 5 minutes
                    # with 10 gigs of files.
                    self._estimatedTime.SetLabel("Finishing...")
                    self.Refresh()
                    return

        self._estimatedTime.SetLabel(_kEstimatedTimeStr % (timeStr, gb,
                                                           self._targetGbStr))
        self.Refresh()


    ###########################################################
    def OnKey(self, event):
        """Ignore escape events.

        @param  event  The EVT_CHAR_HOOK event.
        """
        event.Skip(event.GetKeyCode() != wx.WXK_ESCAPE)

