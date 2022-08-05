#!/usr/bin/env python

#*****************************************************************************
#
# RemoveCameraDialog.py
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
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...
from appCommon.CommonStrings import kImportSuffix, kImportDisplaySuffix

# Globals...
_kPaddingSize = 8
_kWrappingSize = 350
_kCheckboxPaddingSize = 2


###############################################################
def removeCamera(parent, cameraName, dataManager, backEndClient):
    """Remove a camera.

    @param  parent         The window that should be parent to any dialogs.
    @param  cameraName     The name of the camera to remove.
    @param  dataManager    A data manager instance.
    @param  backEndClient  A BackEndClient instance.
    @return removed        True if the camera was removed, False if canceled.
    """
    removeData = False
    dlg = RemoveCameraDialog(parent, cameraName, backEndClient)
    try:
        response = dlg.ShowModal()
        removeData = dlg.deleteData
    finally:
        dlg.Destroy()

    if response == wx.CANCEL:
        return False

    backEndClient.removeCamera(cameraName, removeData)

    if removeData:
        statusText = "Removing data associated with %s, please wait." % (
            cameraName.replace(kImportSuffix, kImportDisplaySuffix)
        )
        dlg = wx.ProgressDialog("Removing camera...", statusText,
                                style=wx.PD_APP_MODAL)
        while True:
            # Force the use of the object database, as we're waiting for objects,
            # not clips to be deleted.
            if cameraName not in dataManager.getCameraLocations(True):
                break
            dlg.Pulse()
            time.sleep(.2)

        dlg.Destroy()

    return True


###############################################################
class RemoveCameraDialog(wx.Dialog):
    """A remove camera dialog prompt."""
    ###########################################################
    def __init__(self, parent, cameraName, backEndClient):
        """Initializer for RemoveCameraDialog.

        @param  parent         The parent window.
        @param  cameraName     The name of the camera being removed.
        @param  backEndClient  An object for communicating with the back end.
        """
        wx.Dialog.__init__(self, parent, -1, "Remove camera", size=(400, -1))

        try:
            self._doInit(cameraName, backEndClient)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _doInit(self, cameraName, backEndClient):
        """Actual init code; see __init__() for details.

        This function exists so we can put a "try" around it easily...
        """
        self._backEndClient = backEndClient

        self.deleteData = False

        self._activeCamera = \
                cameraName in self._backEndClient.getCameraLocations()

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(mainSizer)

        if self._activeCamera:
            questionText = wx.StaticText(self, -1, 'Do you want to remove "%s"'
                                         ' from your list of camera locations?'
                                         % cameraName)
            self.deleteCheck = wx.CheckBox(self, -1)

            helpText = wx.StaticText(
                self, -1,
                "Also delete all videos recorded at this location and rules "
                "used\nby this location\n\n(If you do not check this box, the "
                "camera location will continue to appear in the Search view as "
                "long as the video clips remain.)"
            )
            helpText.Bind(wx.EVT_LEFT_DOWN, self.OnToggleCheck)
            helpText.Bind(wx.EVT_LEFT_DCLICK, self.OnToggleCheck)
            makeFontDefault(self.deleteCheck, helpText, questionText)
            helpText.Wrap(_kWrappingSize)
            questionText.Wrap(_kWrappingSize)

            # Put things in sizers
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(self.deleteCheck, 0, wx.TOP, _kPaddingSize)
            if wx.Platform == "__WXMSW__":
                # On Windows, we need to push the text box a little to the
                # right of the checkbox. Otherwise, it's too close.
                sizer.AddSpacer(_kCheckboxPaddingSize)
            vSizer = wx.BoxSizer(wx.VERTICAL)
            if wx.Platform == "__WXMAC__":
                # We put a little padding above the text box to make it level
                # with the checkbox. Otherwise, it's too high.
                vSizer.AddSpacer(_kCheckboxPaddingSize)
            vSizer.Add(helpText, 0, wx.RIGHT | wx.BOTTOM | wx.TOP, _kPaddingSize)
            sizer.Add(vSizer, 0)

            mainSizer.Add(questionText, 0, wx.ALL, _kPaddingSize)
            mainSizer.Add(sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          _kPaddingSize)
        else:
            self.deleteData = True
            questionText = wx.StaticText(
                self, -1, 'Do you want to remove "%s" and all video and rules '
                'associated with this location?' %
                cameraName.replace(kImportSuffix, kImportDisplaySuffix)
            )
            questionText.Wrap(_kWrappingSize)
            mainSizer.AddSpacer(_kPaddingSize)
            mainSizer.Add(questionText, 0, wx.ALL, 2*_kPaddingSize)
            mainSizer.AddSpacer(_kPaddingSize)

        # Add the OK and Cancel buttons
        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOK)
        self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)
        mainSizer.Add(buttonSizer, 0, wx.ALL | wx.EXPAND, _kPaddingSize)

        self.FindWindowById(wx.ID_OK, self).SetLabel('Remove')

        self.Bind(wx.EVT_CLOSE, self.OnCancel)

        self.Fit()
        self.CenterOnParent()


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)


    ###########################################################
    def OnOK(self, event=None):
        """Respond to the OK selection

        @param  event  The button event.
        """
        self.EndModal(wx.OK)
        if self._activeCamera:
            self.deleteData = self.deleteCheck.GetValue()


    ###########################################################
    def OnToggleCheck(self, event=None):
        """Toggle the check box.

        @param  event  The click event, ignored.
        """
        self.deleteCheck.SetValue(not self.deleteCheck.GetValue())
        self.deleteCheck.SetFocus()

