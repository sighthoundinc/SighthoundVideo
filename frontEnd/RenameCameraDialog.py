#!/usr/bin/env python

#*****************************************************************************
#
# RenameCameraDialog.py
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
import re
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.wx.FixedTimeCtrl import FixedTimeCtrl, EVT_TIMEUPDATE
from vitaToolbox.wx.FixedTimeCtrl import DoesThisLocalRequire24HrFmt
from vitaToolbox.path.PathUtils import kInvalidPathChars
from vitaToolbox.path.PathUtils import kInvalidPathCharsDesc
from vitaToolbox.path.PathUtils import normalizePath
from vitaToolbox.wx.VitaDatePickerCtrl import VitaDatePickerCtrl

# Local imports...
from CameraSetupWizard import addDefaultRule, kMaxCameraNameLen
from CameraSetupWizard import kInvalidCameraNameSuffixes
import FrontEndEvents


_kPaddingSize = 8
_kEditStr = "Edit the location name (the camera has not moved)."
_kNewStr = "Create a new location because I moved my camera on:"


###############################################################
class RenameCameraDialog(wx.Dialog):
    """A dialog for renaming cameras."""
    ###########################################################
    def __init__(self, parent, cameraName, backEndClient, dataManager):
        """Initializer for RenameCameraDialog.

        @param  parent         The parent window.
        @param  cameraName     The camera to rename.
        @param  backEndClient  An object for communicating with the back end.
        @param  dataManager    An interface to the the object database.
        """
        wx.Dialog.__init__(self, parent, -1, "Edit Camera Location")

        try:
            self._backEndClient = backEndClient
            self._origName = cameraName
            self._dataManager = dataManager

            self.SetDoubleBuffered(True)

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            # Create the controls.
            locationLabel = wx.StaticText(self, -1, "Camera location:")
            self._locationCtrl = wx.TextCtrl(self, -1, cameraName,
                                             size=(200, -1))
            self._locationCtrl.SetMaxLength(kMaxCameraNameLen)
            makeFontDefault(locationLabel)

            # Create controls shown when editing.
            self._renameRadio = wx.RadioButton(self, -1, '')
            editLocationText = wx.StaticText(self, -1, _kEditStr)
            self._renameRadio.SetValue(True)
            self._newLocationRadio = wx.RadioButton(self, -1, '')
            newLocationText = wx.StaticText(self, -1, _kNewStr)
            makeFontDefault(editLocationText, newLocationText)
            self._datePicker = VitaDatePickerCtrl(self, None, None, "today")
            if DoesThisLocalRequire24HrFmt():
                fmt = '24HHMM'
            else:
                fmt = 'HHMM'
            self._timeCtrl = FixedTimeCtrl(self, -1, value='08:00:00',
                                           size=wx.DefaultSize, format=fmt)
            self._timeCtrl.SetValue(wx.DateTime.Now())
            _, timeHeight = self._timeCtrl.GetSize()
            timeSpin = wx.SpinButton(self, -1, size=(-1, timeHeight),
                                     style=wx.SP_VERTICAL | wx.SP_WRAP)
            self._timeCtrl.BindSpinButton(timeSpin)
            self._helpText = wx.StaticText(self, -1, "Video recorded before "
                               'then can be found by selecting "%s" from the '
                               "Camera list in the Search view." % cameraName)
            makeFontDefault(self._helpText)
            self._helpText.Wrap(360)
            self._helpText.Hide()

            # Throw everything in sizers.
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(locationLabel, 0, wx.ALIGN_CENTER_VERTICAL)
            hSizer.Add(self._locationCtrl, 0, wx.LEFT |
                       wx.ALIGN_CENTER_VERTICAL, _kPaddingSize)
            sizer.Add(hSizer, 0, wx.LEFT | wx.TOP, 3*_kPaddingSize)

            flexSizer = wx.FlexGridSizer(0, 2, _kPaddingSize, _kPaddingSize)
            flexSizer.AddGrowableCol(1)
            flexSizer.Add(self._renameRadio, 0, wx.ALIGN_CENTER_VERTICAL)
            flexSizer.Add(editLocationText, 0, wx.ALIGN_CENTER_VERTICAL)
            flexSizer.Add(self._newLocationRadio, 0, wx.ALIGN_CENTER_VERTICAL)
            flexSizer.Add(newLocationText, 0, wx.ALIGN_CENTER_VERTICAL)
            flexSizer.AddSpacer(1)
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(self._datePicker, 0, wx.ALIGN_CENTER_VERTICAL)
            hSizer.Add(self._timeCtrl, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
                       2*_kPaddingSize)
            hSizer.Add(timeSpin, 0, wx.ALIGN_CENTER_VERTICAL)
            flexSizer.Add(hSizer, 0, wx.LEFT | wx.EXPAND |
                          wx.ALIGN_CENTER_VERTICAL)
            flexSizer.AddSpacer(1)
            flexSizer.Add(self._helpText, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
            vSizer = wx.BoxSizer(wx.VERTICAL)
            vSizer.Add(flexSizer, 0, wx.LEFT, 2*_kPaddingSize)

            sizer.AddSpacer(2*_kPaddingSize)
            sizer.Add(vSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                      3*_kPaddingSize)

            # Create, place and bind the buttons.
            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.TOP | wx.BOTTOM | wx.RIGHT |
                      wx.EXPAND, 2*_kPaddingSize)

            self.FindWindowById(wx.ID_OK, self).SetDefault()
            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)
            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

            # Bind to controls we want to activate the radio buttons.
            self._renameRadio.Bind(wx.EVT_RADIOBUTTON, self.OnSetEdit)
            self._newLocationRadio.Bind(wx.EVT_RADIOBUTTON, self.OnSetNew)
            editLocationText.Bind(wx.EVT_LEFT_DOWN, self.OnSetEdit)
            editLocationText.Bind(wx.EVT_LEFT_DCLICK, self.OnSetEdit)
            newLocationText.Bind(wx.EVT_LEFT_DOWN, self.OnSetNew)
            newLocationText.Bind(wx.EVT_LEFT_DCLICK, self.OnSetNew)
            self._datePicker.Bind(wx.adv.EVT_DATE_CHANGED, self.OnSetNew)
            self._timeCtrl.Bind(EVT_TIMEUPDATE, self.OnSetNew)

            self.Fit()
            self.CenterOnParent()

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def OnSetEdit(self, event=None):
        """Activate the edit radio.

        @param  event  ignored.
        """
        self._renameRadio.SetValue(True)
        self._helpText.Hide()


    ###########################################################
    def OnSetNew(self, event=None):
        """Activate the new radio.

        @param  event  ignored.
        """
        if self._renameRadio.GetValue() and \
           (self._locationCtrl.GetValue() == self._origName):
            # If the user needs to rename the camera and hasn't yet done so
            # we'll remove the old name.
            self._locationCtrl.SetValue('')

        self._newLocationRadio.SetValue(True)
        self._helpText.Show()


    ###########################################################
    def OnOk(self, event=None): #PYCHECKER OK: Function (OnOk) has too many returns
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        # Normalize the location name so it can be safely saved as a file name
        newLocation = normalizePath(self._locationCtrl.GetValue())
        newLocationLower = newLocation.lower()

        # Validate fields
        if len(newLocation) > kMaxCameraNameLen:
            wx.MessageBox("Location names cannot be more than %d characters." \
                          % kMaxCameraNameLen,
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        if not len(newLocation):
            wx.MessageBox("You must enter a location.", "Error",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        if newLocation.startswith(' ') or newLocation.endswith(' '):
            wx.MessageBox("Location names cannot begin or end with a space.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        if newLocation.endswith('.'):
            wx.MessageBox("Location names cannot end with a period.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        for suffix in kInvalidCameraNameSuffixes:
            if newLocation.endswith(suffix):
                wx.MessageBox('The camera name cannot end with "%s".' % suffix,
                              "Error", wx.OK | wx.ICON_ERROR,
                              self.GetTopLevelParent())
                self._locationCtrl.SetFocus()
                return

        # Make sure the name has been updated.
        if newLocation == self._origName:
            wx.MessageBox("The name for the new location cannot be the same"
                          " as the name of the previous location.", "Error",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        # Prevent invalid location names
        if re.search("[%s]" % kInvalidPathChars, newLocation) is not None:
            wx.MessageBox("The camera name cannot contain any of the following "
                          "characters: %s. Please choose a different name." % \
                          kInvalidPathCharsDesc, "Error",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        # Prevent non-UTF8 characters in location names
        try:
            newLocation.encode('utf-8', 'strict')
        except UnicodeEncodeError, e:
            wx.MessageBox(("The camera name cannot contain the "
                          "character \"%s\". "
                          "Please choose a different name.") %
                           e.object[e.start:e.start+1],
                          "Error",
                           wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            self._locationCtrl.SetFocus()
            return

        # Prevent duplicate camera locations
        locations = [s.lower() for s in
                        self._backEndClient.getCameraLocations()]
        if newLocationLower != self._origName.lower():
            if newLocationLower in locations:
                # Check if another camera is configured with a name differing
                # only by caps.
                wx.MessageBox("Another camera is configured as location \"%s\". "
                              "Please choose another name." \
                              % newLocation, "Error",
                              wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
                self._locationCtrl.SetFocus()
                return

            rules = \
                self._backEndClient.getRuleInfoForLocation(newLocationLower)
            dmNames = [s.lower() for s in
                       self._dataManager.getCameraLocations()]
            if len(rules) > 0 or newLocationLower in dmNames:
                # Check if there are any old rules or video that will be
                # associated with this name, and warn the user.
                res = wx.MessageBox("The name of this camera location already "
                    "exists. Video recorded at that location will be added to "
                    "the video recorded by this camera location.  If this is "
                    "not what you intended, enter a different name.",
                    "Warning", wx.OK | wx.CANCEL | wx.ICON_WARNING,
                    self.GetTopLevelParent())

                if res != wx.OK:
                    self._locationCtrl.SetFocus()
                    return


        # Set the current edit time.
        if self._newLocationRadio.GetValue():
            date = self._datePicker.GetValue()
            dateSec = int(time.mktime(date.timetuple()))
            timeList = self._timeCtrl.GetValue().split(':')
            isAm = timeList[1].endswith('AM')
            hour = int(timeList[0])
            minute = int(timeList[1][:2])
            if isAm and hour == 12:
                hour = 0
            elif not isAm and hour != 12:
                hour += 12

            cameraRenameTime = dateSec + (hour*3600+minute*60)
        else:
            cameraRenameTime = -1

        # Perform the rename operation.
        camType, camUri, wasEnabled, camExtras = \
                    self._backEndClient.getCameraSettings(self._origName)
        self._backEndClient.editCamera(self._origName, newLocation, camType,
                                       camUri, cameraRenameTime, camExtras)
        if cameraRenameTime != -1:
            addDefaultRule(self._backEndClient, newLocation)

        # Present a pulsing progress dialog while we wait for the back end
        # to finish our edit request.
        statusText = "Moving data from %s to %s.  Please wait." \
                     % (self._origName, newLocation)
        dlg = wx.ProgressDialog("Renaming camera...", statusText,
                                parent=self.GetTopLevelParent(),
                                style=wx.PD_APP_MODAL)
        try:
            dlg.Bind(wx.EVT_ACTIVATE, self.OnActivate)
            breakMs = cameraRenameTime*1000+3000
            while True:
                maxMs = self._dataManager.getMostRecentObjectTime(self._origName)
                if maxMs < breakMs:
                    break
                dlg.Pulse()
                time.sleep(.2)

        finally:
            dlg.Unbind(wx.EVT_ACTIVATE)
            dlg.Destroy()

        # This is a workaround for an occurance that can happen if the camera
        # we're renaming was frozen.  It will recieve the pending rename, but
        # in the case were no renaming actually needs to take place (the
        # rename time is now, no videos to split) we will exit our progress
        # dialog before the message is processed, before this camera is
        # enabled.  This will cause a 2 minute delay in the live view before
        # the camera starts recording as the new name, leaving a weird state
        # where it might display status screens about rules or schedules even
        # though things are OK.  Forcing an enable here fixes this.
        if wasEnabled:
            self._backEndClient.enableCamera(newLocation, True)

        # Notify the parent about the edit.
        evt = FrontEndEvents.CameraEditedEvent(self._origName, newLocation)
        self.GetParent().GetEventHandler().ProcessEvent(evt)

        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)


    ###########################################################
    def OnActivate(self, event):
        """Handle an activate event.

        @param  event  The EVT_ACTIVATE event.
        """
        eventObj = event.GetEventObject()
        def safeRaise():
            try:
                eventObj.Raise()
            except Exception:
                pass
        wx.CallAfter(safeRaise)


