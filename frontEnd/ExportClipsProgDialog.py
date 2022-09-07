#!/usr/bin/env python

#*****************************************************************************
#
# ExportClipsProgDialog.py
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
import os
import time
import threading
import traceback
from copy import deepcopy

# Common 3rd-party imports...
import wx

# Toolbox imports...

# Local imports...
from frontEnd.FrontEndUtils import getUserLocalDataDir

_kPaddingSize = 4
_kBorderSize = 16
_kExportClipProgressText = "Exporting clip %i of %i."
_kTimerQuick = 100
_kTimerSlow = 500


###############################################################
class ExportClipsProgDialog(wx.Dialog):
    """A progress dialog shown while clips are being exported."""
    ###########################################################
    def __init__(self, parent, dataManager, clipManager,
                 savePath, clipList, extras={}):
        """Initializer for _ExportClipsProgDialog.

        @param  parent            The parent window.
        @param  logger            An instance of a VitaLogger to use.
        @param  objDbPath         Path to the object database.
        @param  clipDbPath        Path to the clip manager.
        @param  videoStoragePath  Path to the directory videos are stored.
        @param  savePath          Path to save/export the clips.
        @param  clipList          A list of clips, each of which is
                                  a MatchingClipInfo object.
        @param  extras            A dictionary of extra options and settings
                                  that further specify how clips should be
                                  saved/exported.
        """
        wx.Dialog.__init__(self, parent, -1, "Export clips",
                           style=wx.CAPTION | wx.SYSTEM_MENU)

        try:
            self._dataManager = dataManager
            self._clipManager = clipManager

            self._savePath = savePath

            self._clipList = clipList
            self._numClips = len(clipList)
            self._cancelled = False
            self._curIndex = -1

            self._extras = extras

            self._curExportComplete = False
            self._failedToExport = False

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            self._label = wx.StaticText(self, -1, _kExportClipProgressText %
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

            # Begin the first export
            self._exportNext()

            # Start the update timer
            self._timer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self.OnUpdate, self._timer)

            self._timer.Start(_kTimerSlow)

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _exportNext(self):
        """Exports the next clip in the given cliplist.
        """
        # If we're done or the user cancelled stop the timer and exit.
        if self._cancelled or (self._curIndex == self._numClips-1):
            self._timer.Stop()
            self.EndModal(wx.ID_CANCEL)
            return

        extras = deepcopy(self._extras)

        # Begin to export next clip.
        self._curIndex += 1
        curClip = self._clipList[self._curIndex]

        startTime, stopTime = self._dataManager.openMarkedVideo(
            curClip.camLoc, curClip.startTime, curClip.stopTime,
            curClip.playStart, curClip.objList, (0, 0)
        )

        # TODO: Support for names of imported clips if we ever release an
        #       analysis version.

        baseName = curClip.camLoc
        timeStr = time.asctime(time.localtime(startTime/1000))
        defName = baseName + ' - ' + timeStr.replace(':', '-') + '.mp4'

        savePath = os.path.join(self._savePath, defName)
        success = self._dataManager.saveCurrentClip(
            savePath, startTime, stopTime, getUserLocalDataDir(), extras
        )

        if not success:
            wx.MessageBox("There was an error exporting the clip.",
                          "Error", wx.ICON_ERROR | wx.OK,
                          self.GetTopLevelParent())
            self._timer.Stop()
            self.EndModal(wx.ID_ABORT)
            return

        # Update the label and gauge.
        self._label.SetLabel(_kExportClipProgressText % (self._curIndex+1,
                                                         self._numClips))
        self._gauge.SetValue(self._curIndex)

        self._curExportComplete = True

    ###########################################################
    def OnUpdate(self, event):
        """Update the progress dialog with the current status.

        @param  event  The Timer event, ignored.
        """
        # Check if the current export has completed.
        if self._curExportComplete:
            self._curExportComplete = False
            self._exportNext()


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self._cancelled = True
        self._label.SetLabel("Canceling...")


###################################################################
progressUpdateEvent = wx.NewEventType()
EVT_PROGRESS = wx.PyEventBinder(progressUpdateEvent, 1)

class ProgressEvent(wx.PyCommandEvent):
    def __init__(self, evtType, id, pct):
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.percentage = pct

class ExportProgressDialog(wx.Dialog):
    ###########################################################
    def __init__(self, parent, fileList, savePath, startTime, endTime, dataDir, extras, logger, progressFn):
        wx.Dialog.__init__(self, parent, -1, "Exporting ...", style=wx.CAPTION | wx.SYSTEM_MENU)
        self._fileList = fileList
        self._savePath = savePath
        self._startTime = startTime
        self._endTime = endTime
        self._dataDir = dataDir
        self._extras = extras
        self._logger = logger
        self._progressFn = progressFn
        self._result = None
        self._cancelled = False

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Create the controls.
        self._label = wx.StaticText(self, -1, "Exporting - 0% done" )
        self._gauge = wx.Gauge(self, -1, 100)
        self._gauge.SetMinSize((300, -1))

        sizer.Add(self._label, 0, wx.LEFT | wx.RIGHT | wx.TOP, _kBorderSize)
        sizer.AddSpacer(8)
        sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, _kBorderSize)

        buttonSizer = self.CreateStdDialogButtonSizer(wx.CANCEL)
        sizer.Add(buttonSizer, 0, wx.BOTTOM | wx.EXPAND, 16)

        self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)
        self.Bind(wx.EVT_INIT_DIALOG, self.OnInit)
        self.Bind(EVT_PROGRESS, self.OnProgress)

        self.Fit()
        self.CenterOnParent()

        self._thread = ExportRunner(self)
        self._lastPercentage = 0

    ###########################################################
    def _endThread(self):
        if self._thread is not None:
            if self._thread.isAlive():
                self._result = -1

                # Definitely not normal, we expect 2 min files, and copying should not take this long
                self._logger.debug("Terminating clip creation thread...")
                self._thread.join()
                self._logger.debug("... done")
            self._thread = None

    ###########################################################
    def OnInit(self, event=None):
        self._thread.start()

    ###########################################################
    def OnCancel(self, event=None):
        self._cancelled = True
        self._endThread()
        self.EndModal(wx.OK)

    ###########################################################
    def OnProgress(self, event=None):
        percentage = event.percentage

        if percentage > 100:
            self._logger.info("Export completed " + str(percentage) + " -- closing the dialog. Res=" + str(self._result))
            button = self.FindWindowById(wx.ID_CANCEL, self)
            evt = wx.PyCommandEvent(wx.EVT_BUTTON.typeId, button.GetId())
            wx.PostEvent(self, evt)
        else:
            self._gauge.SetValue(percentage)
            self._label.SetLabel("Exporting - %d%% done" % percentage)

    ###########################################################
    def Success(self):
        return self._result >= 0 or self._cancelled

    ###########################################################
    def SetPercentageDone(self, percentage):
        if self._result is not None and percentage <= 100:
            self._logger.error("Progress callback, but result already set. Res=" + str(self._result))
            return -1

        if percentage > self._lastPercentage:
            evt = ProgressEvent(progressUpdateEvent, -1, percentage)
            wx.PostEvent(self, evt)
        return 0

###################################################################
class ExportRunner(threading.Thread):
    """ Internal class for running export processing, while UI is busy
        showing a progress bar
    """
    ###########################################################
    def __init__(self, owner):
        threading.Thread.__init__(self)
        self._owner = owner

    ###########################################################
    def run(self):
        try:
            from videoLib2.python.ClipUtils import remuxClip  # Lazy--loaded on first need
            self._owner._result = remuxClip(self._owner._fileList,
                                self._owner._savePath,
                                self._owner._startTime,
                                self._owner._endTime,
                                self._owner._dataDir,
                                self._owner._extras,
                                self._owner._logger.getCLogFn(),
                                self._owner._progressFn)
        except:
            self._owner._logger.error("remuxClip: exception " + traceback.format_exc())
            self._result = -1
        self._owner.SetPercentageDone(101)

