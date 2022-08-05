#! /usr/local/bin/python

#*****************************************************************************
#
# ExportClipsDialog.py
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
import datetime

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.path.PathUtils import abspathU
from vitaToolbox.sysUtils.TimeUtils import getTimeAsString, dateToMs
from vitaToolbox.wx.FileBrowseButtonFixed import DirBrowseButton
from vitaToolbox.wx.FileBrowseButtonFixed import FileBrowseButton
from vitaToolbox.wx.VitaDatePickerCtrl import VitaDatePickerCtrl
from vitaToolbox.wx.TranslucentStaticText import TranslucentStaticText
from vitaToolbox.wx.FixedTimeCtrl import FixedTimeCtrl
from vitaToolbox.strUtils.EnsureUnicode import ensureUnicode

# Local imports...


_kPaddingSize = 4
_kBorderSize = 16
_kSizes = [ 1440, 1080, 800, 720, 640, 480, 320, 160 ]

kUseFpsLimit = 1
kUseSizeLimit = 2
kDefaultTypeValue = "mp4"

###############################################################################
class ExportSingleClipDialog(wx.Dialog):
    """A dialog for exporting a single clip."""


    ###########################################################
    def __init__(self, parent, title=wx.EmptyString,
                 message=wx.FileSelectorPromptStr, defaultDir=wx.EmptyString,
                 defaultFile=wx.EmptyString,
                 types=None,
                 flags=0,
                 style=wx.DEFAULT_DIALOG_STYLE,  pos=wx.DefaultPosition,
                 size=(440, -1)):
        """Initializer for ExportSingleClipDialog

        @param  parent          The parent window.
        @param  title           Title of this dialog instance.
        @param  message         Message to be displayed in the FileDialog or
                                DirDialog.
        @param  defaultDir      The default export folder path.
        @param  defaultFile     The default filename for the exported file.
        @param  types           list of types we'll allow to save as
        @param  fpsCtrlValue    current value for fps, of None if control should be hidden
        @param  sizeLimitValue  current value for maximum size
        @param  style           wxPython style flag for this dialog.
        @param  pos             Position of this window relatiave to its parent.
        @param  size            Size of this window.
        """
        super(ExportSingleClipDialog, self).__init__(
            parent, -1, title, pos, size, style
        )

        self._title = title
        self._defaultFile = defaultFile
        self._defaultDir = defaultDir

        try:
            # Create the controls.
            if types is not None:
                self._saveAsType = wx.Choice(self, -1, choices=types)
                self._saveAsType.Bind( wx.EVT_CHOICE, self.OnTypeChoiceSelection )
                self._saveAsType.SetSelection(0)
            else:
                self._saveAsType = None

            savepathLabel = wx.StaticText(self, wx.ID_ANY, message)
            self._savepathField = self.CreateBrowseButton(
                '', message, defaultDir, self._defaultFile, "*.*", wx.FD_SAVE )
            self._savepathField.SetValue(os.path.join(defaultDir, defaultFile))

            self.OnTypeChoiceSelection()

            self._timestampOverlayCheckBox = wx.CheckBox(
                self, wx.ID_ANY, "Add timestamp overlay" )
            self._boundingBoxesCheckBox = wx.CheckBox(
                self, wx.ID_ANY, "Add bounding boxes" )
            if (flags & kUseFpsLimit) != 0:
                self._limitFpsCheckBox = wx.CheckBox(self, wx.ID_ANY, "Limit FPS to" )
                self._limitFpsCheckBox.Bind(wx.EVT_CHECKBOX, self.OnFpsCheck)
                self._fpsCtrl = wx.SpinCtrl(self, -1, "", size=(80,-1))
                self._fpsCtrl.SetRange(1, 60)
                self.FPSLimit = -1
            else:
                self._limitFpsCheckBox = None
                self._fpsCtrl = None
            if (flags & kUseSizeLimit) != 0:
                self._sizeCheckBox = wx.CheckBox(self, wx.ID_ANY, "Limit dimensions to" )
                self._sizeCtrl = wx.Choice(self, -1, choices=[ str(x)+"p" for x in _kSizes ])
                self._sizeCheckBox.Bind(wx.EVT_CHECKBOX, self.OnSizeCheck)
                self.SizeLimit = -1
            else:
                self._sizeCheckBox = None
                self._sizeCtrl = None

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)


            horizSizer = wx.BoxSizer(wx.HORIZONTAL)
            horizSizer.Add( savepathLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.TOP, _kBorderSize )
            if self._saveAsType is not None:
                horizSizer.Add( self._saveAsType, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP, _kBorderSize )
            sizer.Add(horizSizer)

            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._savepathField, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kBorderSize )
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._timestampOverlayCheckBox, 0, wx.LEFT | wx.RIGHT, _kBorderSize )
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add( self._boundingBoxesCheckBox, 0, wx.LEFT | wx.RIGHT, _kBorderSize )
            sizer.AddSpacer(_kPaddingSize)
            if self._limitFpsCheckBox is not None:
                horizSizer = wx.BoxSizer(wx.HORIZONTAL)
                horizSizer.Add( self._limitFpsCheckBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kBorderSize )
                horizSizer.Add( self._fpsCtrl, 0, wx.EXPAND | wx.RIGHT, _kBorderSize )
                sizer.Add(horizSizer)
                sizer.AddSpacer(_kPaddingSize)
            if self._sizeCheckBox is not None:
                horizSizer = wx.BoxSizer(wx.HORIZONTAL)
                horizSizer.Add( self._sizeCheckBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kBorderSize )
                horizSizer.Add( self._sizeCtrl, 0, wx.EXPAND | wx.RIGHT, _kBorderSize )
                sizer.Add(horizSizer)
                sizer.AddSpacer(_kPaddingSize)

            self._addExtendedControls()

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kBorderSize)
            saveButton = self.FindWindowById(wx.ID_OK, self)
            saveButton.SetLabel("Save")
            sizer.AddSpacer(_kPaddingSize*2)

            saveButton.Bind(wx.EVT_BUTTON, self.OnSave)
            self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

            self.Fit()
            self.CenterOnParent()
            self.SetSize(size)

            self._savepathField.SetFocus()
            self._setLocCursorToZero()

        except:
            # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise

    ###########################################################
    def _addExtendedControls(self):
        pass

    ###########################################################
    def OnFpsCheck(self, event=None):
        self._fpsCtrl.Enable(self._limitFpsCheckBox.GetValue())

    ###########################################################
    def OnSizeCheck(self, event=None):
        self._sizeCtrl.Enable(self._sizeCheckBox.GetValue())

    ###########################################################
    def OnTypeChoiceSelection(self, event=None):
        currentValue = self.SelectedType

        wildcard = "Any file (*.*)|*.*"
        if currentValue == "mp4":
            wildcard = "MP4 file (*.mp4)|*.mp4"
        elif currentValue == "mjpeg":
            wildcard = "MJPG file (*.mjpeg)|*.mjpeg"
        elif currentValue == "jpg":
            wildcard = "JPG file (*.jpg)|*.jpg"
        elif currentValue == "gif":
            wildcard = "GIF file (*.gif)|*.gif"
        self._savepathField.fileType = wildcard
        if self._defaultFile is not None and len(self._defaultFile)>0:
            self._savepathField.SetValue( os.path.join(self._defaultDir, self._defaultFile + "." + currentValue ) )
        else:
            self._savepathField.SetValue( self._defaultDir )



    ###########################################################
    def CreateBrowseButton(self, labelText, dialogTitle, startDirectory,
                           initialValue, fileMask, fileMode):
        """Create and return a FileBrowseButton or DirBrowseButton to be used
        by an instance of this class.

        NOTE:   This method may be overriden to supply a different browse
                button. This method is called by the constructor. This method
                is not intended to be used in any other way.

        @param  labelText       Label for the text control.
        @param  dialogTitle     Title of the dialog.
        @param  startDirectory  The default export folder path.
        @param  initialValue    The default filename for the exported file.
        @param  fileMask        The allowable file types the exported file may
                                be saved as.
        @param  fileMode        Filemode that describes how the wx.FileDialog
                                should be initialized. This is an argument for
                                FileBrowseButton.

        @return browseButton    Must be an instance of FileBrowseButton or
                                DirBrowseButton
        """
        return FileBrowseButton(
            self, -1, labelText=labelText, dialogTitle=dialogTitle,
            startDirectory=startDirectory, initialValue=initialValue,
            fileMask=fileMask, fileMode=fileMode,
        )

    ###########################################################
    @property
    def SizeLimit(self):
        """Get the size limit set by the user

        @return  integer size limit, or -1 if not set
        """
        if self._sizeCtrl is None or not self._sizeCheckBox.GetValue():
            return -1
        return _kSizes[self._sizeCtrl.GetSelection()]

    ###########################################################
    @SizeLimit.setter
    def SizeLimit(self, sizeLimitValue):
        """Set the size limit set by the user
        """
        if self._sizeCheckBox is None:
            return
        self._sizeCheckBox.SetValue(sizeLimitValue != -1)
        if sizeLimitValue not in _kSizes:
            sizeLimitValue = _kSizes[0]
        self._sizeCtrl.SetSelection(_kSizes.index(sizeLimitValue))
        self._sizeCtrl.Enable(self._sizeCheckBox.GetValue())

    ###########################################################
    @property
    def FPSLimit(self):
        """Get the fps limit set by the user

        @return  integer FPS limit, or -1 if not set
        """
        if self._fpsCtrl is None or not self._limitFpsCheckBox.GetValue():
            return -1
        return self._fpsCtrl.GetValue()

    ###########################################################
    @FPSLimit.setter
    def FPSLimit(self, fpsLimit):
        """Set the fps limit set by the user
        """
        if self._fpsCtrl is None:
            return
        self._limitFpsCheckBox.SetValue(fpsLimit != -1)
        if fpsLimit != -1:
            self._fpsCtrl.SetValue(fpsLimit)
        self._fpsCtrl.Enable(self._limitFpsCheckBox.GetValue())

    ###########################################################
    @property
    def SelectedType(self):
        """Get the selected file type

        @return  string selected file type
        """
        if self._saveAsType is None:
            return kDefaultTypeValue
        currentType = self._saveAsType.GetSelection()
        return self._saveAsType.GetString(currentType).lower()

    ###########################################################
    @property
    def WantTimestampOverlay(self):
        """Get the timestamp overlay preference from the checkbox.

        @return  bool   True if the user wants the timestamp overlay, and False
                        otherwise.
        """
        return self._timestampOverlayCheckBox.IsChecked()


    ###########################################################
    @WantTimestampOverlay.setter
    def WantTimestampOverlay(self, shouldCheck):
        """Set the timestamp overlay preference to the checkbox.

        @param  shouldCheck     True if the checkbox should be checked, or False
                                if it should be unchecked.
        """
        self._timestampOverlayCheckBox.SetValue(shouldCheck)


    ###########################################################
    @property
    def WantBoundingBoxes(self):
        """Get the bounding boxes preference from the checkbox.

        @return  bool   True if the user wants to add bounding boxes, and False
                        otherwise.
        """
        return self._boundingBoxesCheckBox.IsChecked()


    ###########################################################
    @WantBoundingBoxes.setter
    def WantBoundingBoxes(self, shouldCheck):
        """Set the bounding boxes preference to the checkbox.

        @param  shouldCheck     True if the checkbox should be checked, or False
                                if it should be unchecked.
        """
        self._boundingBoxesCheckBox.SetValue(shouldCheck)


    ###########################################################
    def GetSavePath(self):
        """Get the save path that was chosen by the user.

        @return  path   The path to export the clip(s).
        """
        value = self._savepathField.GetValue()
        if self._saveAsType is not None:
            currentType = self._saveAsType.GetSelection()
            currentTypeValue = self._saveAsType.GetString(currentType).lower()
            if not value.lower().endswith("."+currentTypeValue):
                value = value + "." + currentTypeValue
        return value



    ###########################################################
    def VerifyUiInput(self):
        """Verify that the UI input data is acceptable for returning to the
        main program. This method may be overloaded. It is called when the user
        clicks the "Save" button.

        @return  isVerified     True if the data is acceptable, False otherwise.
        """
        savePath = self.GetSavePath()

        dirpath = os.path.dirname(savePath)

        if (not savePath) or (not dirpath) or os.path.isdir(savePath):
            # Ensure the directory field is not blank.
            wx.MessageBox("You must provide an export location.", self._title,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return False

        if os.path.isfile(savePath):
            # Check if the file already exists.
            res = wx.MessageBox("The specified file already exists.  Would"
                                " you like to overwrite it?",
                                self._title, wx.YES_NO | wx.YES_DEFAULT
                                | wx.ICON_QUESTION, self.GetTopLevelParent())
            # We can return early since we have a valid save path that the user
            # either wants or does not want to use.
            return res == wx.YES

        if not os.path.isdir(dirpath):
            # Check if the directory exists.
            res = wx.MessageBox("The specified folder does not exist.  Would"
                                " you like to create it now?",
                                self._title, wx.YES_NO | wx.YES_DEFAULT
                                | wx.ICON_QUESTION, self.GetTopLevelParent())
            if res != wx.YES:
                return False

            # Try to create the directory.
            try:
                os.makedirs(dirpath)
            except Exception:
                pass
            if not os.path.isdir(dirpath):
                # If we couldn't create the directory show an error.
                wx.MessageBox("The folder could not be created.  Please "
                              "select a different location.",
                              self._title,
                              wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
                return False

        return True


    ###########################################################
    def _verifyUiInput(self):
        """Verify that the UI input data is acceptable for returning to the
        main program.

        @return  isVerified     True if the data is acceptable, False otherwise.
        """
        savePath = abspathU(self._savepathField.GetValue())
        self._savepathField.SetValue(savePath)

        # For error cases we want to put the focus back on the directory field.
        self._savepathField.SetFocus()
        self._setLocCursorToZero()

        return self.VerifyUiInput()


    ###########################################################
    def _setLocCursorToZero(self):
        """Set the cursor position of the location field to zero."""
        for child in self._savepathField.GetChildren():
            if hasattr(child, "SetInsertionPoint"):
                child.SetInsertionPoint(0)
                child.ShowPosition(0)


    ###########################################################
    def OnSave(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        if self._verifyUiInput():
            self.EndModal(wx.ID_OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)


###############################################################################
class ExportMultipleClipsDialog(ExportSingleClipDialog):
    """A dialog for exporting multiple clips."""


    ###########################################################
    def CreateBrowseButton(self, labelText, dialogTitle, startDirectory,
                           initialValue, fileMask, fileMode):
        """Create and return a FileBrowseButton or DirBrowseButton to be used
        by an instance of this class.

        NOTE:   This method may be overriden to supply a different browse
                button. This method is called by the constructor. This method
                is not intended to be used in any other way.

        @param  labelText       Label for the text control.
        @param  dialogTitle     Title of the dialog.
        @param  startDirectory  The default export folder path.
        @param  initialValue    The default filename for the exported file.
        @param  fileMask        The allowable file types the exported file may
                                be saved as.
        @param  fileMode        Filemode that describes how the wx.FileDialog
                                should be initialized. This is an argument for
                                FileBrowseButton.

        @return browseButton    Must be an instance of FileBrowseButton or
                                DirBrowseButton
        """
        return DirBrowseButton(
            self, -1, labelText=labelText, dialogTitle=dialogTitle,
            startDirectory=startDirectory,
        )


    ###########################################################
    def VerifyUiInput(self):
        """Verify that the UI input data is acceptable for returning to the
        main program. This method may be overloaded. It is called when the user
        clicks the "Save" button.

        @return  isVerified     True if the data is acceptable, False otherwise.
        """
        savePath = self.GetSavePath()

        if not savePath:
            # Ensure the directory field is not blank.
            wx.MessageBox("You must select a folder.", self._title,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return False

        if not os.path.isdir(savePath):
            # Check if the directory exists.
            res = wx.MessageBox("The specified folder does not exist.  Would"
                                " you like to create it now?",
                                self._title, wx.YES_NO | wx.YES_DEFAULT
                                | wx.ICON_QUESTION, self.GetTopLevelParent())
            if res != wx.YES:
                return False

            # Try to create the directory.
            try:
                os.makedirs(savePath)
            except Exception:
                pass
            if not os.path.isdir(savePath):
                # If we couldn't create the directory show an error.
                wx.MessageBox("The folder could not be created.  Please "
                              "select a different location.",
                              self._title,
                              wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
                return False

        return True

###############################################################################
class ExportTimeRangeDialog(ExportSingleClipDialog):
    ###########################################################
    def __init__(self, camList, currentCamera, centerTimeAround, markupModel, *args, **kwargs):
        """Initializer for ExportSingleClipDialog

        @param  parent          The parent window.
        @param  title           Title of this dialog instance.
        @param  message         Message to be displayed in the FileDialog or
                                DirDialog.
        @param  defaultDir      The default export folder path.
        @param  defaultFile     The default filename for the exported file.
        @param  types           list of types we'll allow to save as
        @param  flags           flags controlling dialog behavior
        @param  style           wxPython style flag for this dialog.
        @param  pos             Position of this window relatiave to its parent.
        @param  size            Size of this window.
        """
        self._camList = camList
        self._centerTimeAround = centerTimeAround/1000.0 # convert to seconds
        self._currentCamera = currentCamera
        self._markupModel = markupModel
        super(ExportTimeRangeDialog, self).__init__(*args, **kwargs)

    ###########################################################
    def getCameraLocation(self):
        return self._camListBox.GetString(self._camListBox.GetSelection())

    ###########################################################
    def _getTime(self, dateCtrl, timeCtrl):
        dateInMs = dateToMs(dateCtrl.GetValue())
        timeInMs = timeCtrl.GetValue(as_wxTimeSpan=True).GetMilliseconds()
        res = dateInMs + timeInMs
        return res

    ###########################################################
    def getStartTime(self):
        return self._getTime(self._fromDate, self._fromTime)

    ###########################################################
    def getEndTime(self):
        return self._getTime(self._toDate, self._toTime)

    ###########################################################
    def _addExtendedControls(self):
        _kDefaultPeriodMs = 2*60 # export 2 min by default
        # Append to the main sizer.
        mainSizer = self.GetSizer()
        mainSizer.AddSpacer(_kBorderSize)

        use24Hr = not self._markupModel.get12HrTime()
        useUSDate = self._markupModel.getUSDate()
        startDT = self._centerTimeAround-_kDefaultPeriodMs/2
        startDTTime = datetime.date.fromtimestamp(startDT)
        startDTStr = getTimeAsString(startDT*1000, ":", True, use24Hr)
        endDT = self._centerTimeAround+_kDefaultPeriodMs/2
        endDTTime = datetime.date.fromtimestamp(endDT)
        endDTStr = getTimeAsString(endDT*1000, ":", True, use24Hr)

        fromToSizer = wx.FlexGridSizer(3, 3, _kBorderSize/2, _kBorderSize)

        camListLabel = TranslucentStaticText(self, wx.ID_ANY, "Camera:")
        self._camListBox = wx.Choice(self, choices=self._camList, style=wx.CB_SORT)
        fromToSizer.Add(camListLabel, 0, wx.LEFT, _kBorderSize )
        fromToSizer.Add( self._camListBox )
        fromToSizer.Add( wx.StaticText(self, -1, '') )

        self._fromLabel = TranslucentStaticText(self, -1, "From:")
        self._fromDate = VitaDatePickerCtrl(self,  startDTTime,
                                            datetime.date.fromtimestamp(0),
                                            "today",
                                            None)
        self._fromDate.useUSDateFormat(useUSDate)
        self._fromTime = FixedTimeCtrl(
                    self, -1, value=startDTStr.upper() )
        fromToSizer.Add( self._fromLabel, 0, wx.LEFT, _kBorderSize )
        fromToSizer.Add( self._fromDate )
        fromToSizer.Add( self._fromTime )

        self._toLabel = TranslucentStaticText(self, -1, "To:")
        self._toDate = VitaDatePickerCtrl(self, endDTTime,
                                            datetime.date.fromtimestamp(0),
                                            "today",
                                            None)
        self._toDate.useUSDateFormat(useUSDate)
        self._toTime = FixedTimeCtrl(
                    self, -1, value=endDTStr.upper() )
        fromToSizer.Add( self._toLabel, 0, wx.LEFT, _kBorderSize )
        fromToSizer.Add( self._toDate )
        fromToSizer.Add( self._toTime )

        mainSizer.Add( fromToSizer, 1, wx.ALL, _kBorderSize )

        if self._currentCamera in self._camList:
            self._camListBox.SetSelection(self._camList.index(self._currentCamera))
        else:
            self._camListBox.SetSelection( 0 )


    ###########################################################
    def OnCancel(self, event=None):
        """Cancel the dialog.

        @param  event  The button event.
        """
        self.EndModal(wx.CANCEL)

    ###########################################################
    def OnSave(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        if self._verifyUiInput():
            self.EndModal(wx.ID_OK)

    ###########################################################
    def _verifyUiInput(self):
        if not super(ExportTimeRangeDialog, self)._verifyUiInput():
            return False
        if self.getStartTime() >= self.getEndTime():
            wx.MessageBox("Please enter valid combination of star and end time.", self._title,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return False
        return True
