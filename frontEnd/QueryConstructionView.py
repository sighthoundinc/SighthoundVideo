#!/usr/bin/env python

#*****************************************************************************
#
# QueryConstructionView.py
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
import sys
import time

# Common 3rd-party imports...
from PIL import Image
import wx

# Toolbox imports...
from vitaToolbox.path.PathUtils import kInvalidPathChars
from vitaToolbox.path.PathUtils import kInvalidPathCharsDesc
from vitaToolbox.path.PathUtils import normalizePath
from vitaToolbox.wx.GradientEndedLine import GradientEndedLine
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.wx.FontUtils import growTitleText
from vitaToolbox.wx.FixedStaticBitmap import FixedStaticBitmap
from vitaToolbox.wx.HoverButton import HoverButton
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.TranslucentStaticText import TranslucentStaticText
from vitaToolbox.image.ImageConversion import convertWxBitmapToPil
from vitaToolbox.sysUtils.TimeUtils import formatTime

# Local imports...
from appCommon.CommonStrings import kAnyCameraStr
from appCommon.CommonStrings import kImportSuffix
from backEnd.SavedQueryDataModel import SavedQueryDataModel
from frontEnd.CameraSetupWizard import kMaxCameraNameLen
from frontEnd.VideoWindow import VideoWindow

from constructionComponents.ConstructionBlock import drawConstructionBlock

# Construction components
from constructionComponents.CameraConfigPanel import CameraConfigPanel
from constructionComponents.CameraConstructionBlock import CameraConstructionBlock
from constructionComponents.ResponseConfigPanel import ResponseConfigPanel
from constructionComponents.ResponseConstructionBlock import ResponseConstructionBlock
from constructionComponents.TargetConfigPanel import TargetConfigPanel
from constructionComponents.TargetConstructionBlock import TargetConstructionBlock
from constructionComponents.WhereConfigPanel import WhereConfigPanel
from constructionComponents.WhereConstructionBlock import WhereConstructionBlock


# Constants...
_kIconWidth = 42
_kTitleHeight = 32

_kVideoWidth = 320
_kVideoHeight = 240

_kMaxVideoLoadTimerRetries = 50
_kVideoLoadTimerRetryMs = 100

_kBlockTitleHeight = 30

# These are used in the main view...
_kCustomizeNameLabelStr = "Customize name"

# Constants for our gradient line separator...
if wx.Platform == '__WXMSW__':
    _kDividerEdgeColor = (171, 214, 245, 0)
    _kDividerColor = (171, 214, 245, 255)
else:
    _kDividerEdgeColor = (180, 180, 180, 0)
    _kDividerColor = (180, 180, 180, 255)
_kMaxGradientWidth = 98
_kDividerWidth = 2

# Used for selecting which image to look at...
_kImageFromStr = "Image from:"

# Used when looking at imported video...
_kImportedImageFromStr = "Example clip image:"

# Used in the video window...
_kImageNotAvailableStr = "Image not available."


# These are used in the customize name dialog...
_kCustomizeNameTitleStr = "Customize Name"
_kCustomizeNameRadioStr = " Customize name:"
_kAutoNameRadioStr = \
    " Use the following name created automatically for this rule:"

# The maximum allowable rule name length.  This is limited so that we
# can ensure that we can always write out a file with this name, given
# path length limitations in file systems we work with.
_kMaxRuleNameLen = 104

# Spacings...
_kMarginPixels = 15


##############################################################################
class QueryConstructionView(wx.Panel):
    """The main panel holding the query construction UI.

    This will probably be placed in a frame to make the query construction
    frame.
    """

    ###########################################################
    def __init__(self, parent, dataMgr, backEndClient, queryDataModel,
                 existingNames, validLocations):
        """QueryConstructionView constructor.

        @param  parent          Our parent UI element.
        @param  dataMgr         The data manager for the app.
        @param  backEndClient   Client to the back end.  May be None for test
                                code.
        @param  queryDataModel  The data model to edit in the construction view.
                                Should already be a copy if we need to be able
                                to cancel.
        @param  existingNames   Reserved names the user should not be allowed
                                to use; must not include the current query
                                name unless we're not allowed to use that name.
        @param  validLocations  A list of camera locations the query is allowed
                                to be set to.
        """
        # Call our super
        super(QueryConstructionView, self).__init__(parent)
        self.SetBackgroundColour("white")

        # Make sure we're double-buffered so our children draw properly...
        self.SetDoubleBuffered(True)

        # Save parameters...
        self._dataMgr = dataMgr
        self._backEndClient = backEndClient
        self._queryDataModel = queryDataModel
        self._existingNames = existingNames
        self._validLocations = validLocations

        # Keep track of camera block data model separately...
        self._cameraBlockDataModel = queryDataModel.getVideoSource()

        # Make special bitmaps to show in video window...
        self._loadingImage = Image.new('RGB', (_kVideoWidth, _kVideoHeight))
        self._anyCameraImage = self._makeAnyCameraImage()
        self._notAvailableImage = self._makeNotAvailableImage()

        # A list of times to allow the user to look at video from.  The
        # first value is actually the most recent time we have, the last is the
        # earliest time we've found video for.  We also keep an index of where
        # we are at...
        self._videoTimeList = []
        self._videoTimeIndex = None

        # Keep track of info for loading video...
        self._videoLoadTimer = wx.Timer(self, -1)
        self._videoLoadMs = None
        self._videoLoadTimerRetries = 0
        self.Bind(wx.EVT_TIMER, self.OnVideoLoadTimer, self._videoLoadTimer)

        # Create the UI...
        self._initUiWidgets()

        # Listen for changes from the models...
        self._queryDataModel.addListener(self._updateFromModel)
        self._cameraBlockDataModel.addListener(self._handleCameraChange)

        # Update everything...
        self._updateFromModel(self._queryDataModel)
        self._handleCameraChange(self._cameraBlockDataModel)

        # Select whichever componet was last edited...
        # ...this will effectively give an "OnBlockClick()"
        self._selectLastEdited()



    ###########################################################
    def _makeAnyCameraImage(self):
        """Make an image to show as the bitmap for "Any Camera".

        This is supposed to look like the Camera construction block.

        @return img  A PIL image.
        """
        bmp = wx.Bitmap(_kVideoWidth, _kVideoHeight)
        dc = wx.MemoryDC(bmp)
        drawConstructionBlock(dc, (_kVideoWidth, _kVideoHeight), None,
                              " \n \n" + kAnyCameraStr, self.GetFont(),
                              "black", (181,  66,  66))
        dc.SelectObject(wx.NullBitmap)
        return convertWxBitmapToPil(bmp)


    ###########################################################
    def _makeNotAvailableImage(self):
        """Make an image to show when we can't load an image.

        This is supposed to look just like in Monitor View, so we actually
        import from there.

        @return img  A PIL image.
        """
        # Import here to avoid circular dependencies...
        from MonitorView import makeVideoStatusBitmap

        bmp = makeVideoStatusBitmap(_kImageNotAvailableStr, self.GetFont(),
                                    False, None, _kVideoWidth, _kVideoHeight)
        return convertWxBitmapToPil(bmp)


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets..."""
        # Make our flow chart...
        flowChartPanel = self._createFlowChartPanel(self, self._queryDataModel)

        # Make separator line...
        dividingLine = GradientEndedLine(self, _kDividerColor,
                                         _kDividerEdgeColor,
                                         _kDividerWidth,
                                         _kMaxGradientWidth,
                                         wx.LI_VERTICAL)

        # Create the common UI for the config panels elements...
        iconBmp = wx.Bitmap("frontEnd/bmps/questionMark.png")
        self._iconCtrl = FixedStaticBitmap(self, -1, iconBmp)
        self._iconCtrl.SetMinSize((_kIconWidth, -1))
        self._titleLabel = wx.StaticText(self, -1, "",
                                         style=wx.ST_NO_AUTORESIZE)

        self._imageFromLabel = wx.StaticText(self, -1, _kImageFromStr,
                                             style=wx.ALIGN_CENTER |
                                             wx.ST_NO_AUTORESIZE)
        self._prevTimeButton = HoverButton(self, "<<", wantRepeats=True)
        self._timeLabel = wx.StaticText(self, -1, "99-99 pm",
                                        style=wx.ST_NO_AUTORESIZE |
                                        wx.ALIGN_CENTER)
        self._nextTimeButton = HoverButton(self, ">>", wantRepeats=True)

        self._timeControls = [self._imageFromLabel, self._prevTimeButton,
                              self._timeLabel, self._nextTimeButton]
        makeFontDefault(*self._timeControls)
        self._timeLabel.SetMinSize(self._timeLabel.GetBestSize())
        self._timeLabel.SetLabel("")


        # Make a video window, if we have a data manager...
        self._videoWindow = VideoWindow(self)
        self._videoWindow.setImage(self._loadingImage)

        # Create all of our possible config panels...
        self._configPanels = {
            ('videoSource', None):
                CameraConfigPanel(self, self._queryDataModel.getVideoSource(),
                                  self._validLocations),
            ('target', 0):
                TargetConfigPanel(self, self._videoWindow,
                                  self._queryDataModel.getTargets()[0]),
            ('trigger', 0):
                WhereConfigPanel(self, self._videoWindow,
                                 self._queryDataModel.getTriggers()[0],
                                 self._queryDataModel.getTriggers()[1]),
            ('response', 0):
                ResponseConfigPanel(self, self._queryDataModel,
                                    self._backEndClient, self._dataMgr),
        }

        # Throw everything into sizers...
        self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._mainSizer.Add(flowChartPanel, 0, wx.EXPAND)
        self._mainSizer.Add(dividingLine, 0, wx.EXPAND | wx.RIGHT, 10)

        configSizer = wx.BoxSizer(wx.VERTICAL)

        titleSizer = wx.BoxSizer(wx.HORIZONTAL)
        titleSizer.Add(self._iconCtrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        titleSizer.Add(self._titleLabel, 1, wx.ALIGN_CENTER_VERTICAL)
        titleSizer.AddSpacer(1)

        titleSizer.Add(self._imageFromLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        titleSizer.Add(self._prevTimeButton, 0, wx.ALIGN_CENTER_VERTICAL)
        titleSizer.Add(self._timeLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        titleSizer.Add(self._nextTimeButton, 0, wx.ALIGN_CENTER_VERTICAL)

        self._titleSizer = titleSizer

        configSizer.Add(titleSizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        configSizer.Add(self._videoWindow, 0, wx.BOTTOM, 5)

        overlapSizer = OverlapSizer(True)
        for configPanel in self._configPanels.itervalues():
            overlapSizer.Add(configPanel)
        configSizer.Add(overlapSizer, 1, wx.EXPAND)

        self._mainSizer.Add(configSizer, 1, wx.EXPAND | wx.ALL, 8)

        borderSizer = wx.BoxSizer()
        borderSizer.Add(self._mainSizer, 1, wx.EXPAND | wx.ALL, _kMarginPixels)

        # Set our main sizer...
        self.SetSizer(borderSizer)

        ## Give focus to the flow chart panel (?)
        #flowChartPanel.SetFocus()


        # Bind stuff...
        self._prevTimeButton.Bind(wx.EVT_BUTTON, self.OnPrevTime)
        self._nextTimeButton.Bind(wx.EVT_BUTTON, self.OnNextTime)


    ###########################################################
    def _createFlowChartPanel(self, parent, queryDataModel):
        """Create the flow chart panel & bind to the created blocks.

        TODO: Eventually, this may be a separate class.  For now, it's so
        faked up that we'll just do it here...

        @param  parent          The UI parent to use for the panel.
        @param  queryDataModel  The data model to edit in the construction view.
                                Should already be a copy if we need to be able
                                to cancel.
        """
        # This is the background that we'll throw everything on top of.  This
        # is super fake, but means that we don't need to draw the connectors
        # and the titles for now...
        # ...split into 4 parts, since that works better on Windows.
        fakeBitmap1 = \
            wx.Bitmap("frontEnd/bmps/fakeConstructionQueryViewFlowChart1.png")
        fakeBitmap2 = \
            wx.Bitmap("frontEnd/bmps/fakeConstructionQueryViewFlowChart2.png")
        fakeBitmap3 = \
            wx.Bitmap("frontEnd/bmps/fakeConstructionQueryViewFlowChart3.png")
        fakeBitmap4 = \
            wx.Bitmap("frontEnd/bmps/fakeConstructionQueryViewFlowChart4.png")

        # The main panel to put everything in...
        flowChartPanel = wx.Panel(parent)
        flowChartPanel.SetMinSize((400, -1))
        flowChartPanel.SetBackgroundColour("white")

        # Make name info...
        self._nameLabel = TranslucentStaticText(
            flowChartPanel, -1, "", style=wx.ALIGN_CENTER | wx.ST_ELLIPSIZE_END
        )
        growTitleText(self._nameLabel, 1.1)
        self._changeNameButton = HoverButton(flowChartPanel,
                                             _kCustomizeNameLabelStr)
        self._changeNameButton.SetUnderlined(True)

        # Make the static controls holding our backgrounds...
        self._bmpVideoSourceTitle = wx.StaticBitmap(flowChartPanel, -1, fakeBitmap1,
                                     size=fakeBitmap1.GetSize())
        self._bmpTargetTitle = wx.StaticBitmap(flowChartPanel, -1, fakeBitmap2,
                                     size=fakeBitmap2.GetSize())
        self._bmpRegionTitle = wx.StaticBitmap(flowChartPanel, -1, fakeBitmap3,
                                     size=fakeBitmap3.GetSize())
        self._bmpResponseTitle = wx.StaticBitmap(flowChartPanel, -1, fakeBitmap4,
                                     size=fakeBitmap4.GetSize())

        self._bmpVideoSourceTitle.Bind(wx.EVT_LEFT_DOWN, self.OnBlockTitleClick)
        self._bmpTargetTitle.Bind(wx.EVT_LEFT_DOWN, self.OnBlockTitleClick)
        self._bmpRegionTitle.Bind(wx.EVT_LEFT_DOWN, self.OnBlockTitleClick)
        self._bmpResponseTitle.Bind(wx.EVT_LEFT_DOWN, self.OnBlockTitleClick)

        # Make all of our blocks...
        videoSourceBlock = \
            CameraConstructionBlock(flowChartPanel,
                                    queryDataModel.getVideoSource())
        videoSourceBlock.setClientData(('videoSource', None))
        videoSourceBlock.Bind(wx.EVT_BUTTON, self.OnBlockClick)
        self._videoSourceBlock = videoSourceBlock


        targetBlock = \
            TargetConstructionBlock(flowChartPanel,
                                    queryDataModel.getTargets()[0])
        targetBlock.setClientData(('target', 0))
        targetBlock.Bind(wx.EVT_BUTTON, self.OnBlockClick)
        self._targetBlock = targetBlock

        regionBlock = \
            WhereConstructionBlock(flowChartPanel,
                                   queryDataModel.getTriggers()[0],
                                   queryDataModel.getTriggers()[1])
        regionBlock.setClientData(('trigger', 0))
        regionBlock.Bind(wx.EVT_BUTTON, self.OnBlockClick)
        self._regionBlock = regionBlock

        responseBlock = \
            ResponseConstructionBlock(flowChartPanel, queryDataModel)
        responseBlock.setClientData(('response', 0))
        responseBlock.Bind(wx.EVT_BUTTON, self.OnBlockClick)
        self._responseBlock = responseBlock

        # Throw elements into sizers...
        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(self._nameLabel, 0, wx.EXPAND)
        panelSizer.Add(self._changeNameButton, 0, wx.CENTER | wx.TOP, 10)
        panelSizer.Add(self._bmpVideoSourceTitle, 0, wx.CENTER | wx.TOP, 20)
        panelSizer.Add(videoSourceBlock, 0, wx.CENTER)
        panelSizer.Add(self._bmpTargetTitle, 0, wx.CENTER)
        panelSizer.Add(targetBlock, 0, wx.CENTER)
        panelSizer.Add(self._bmpRegionTitle, 0, wx.CENTER)
        panelSizer.Add(regionBlock, 0, wx.CENTER)
        panelSizer.Add(self._bmpResponseTitle, 0, wx.CENTER)
        panelSizer.Add(responseBlock, 0, wx.CENTER)

        # Add an extra border sizer around everything; top and bottom get 20
        # and sides 5...
        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.AddSpacer(20)
        borderSizer.Add(panelSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        borderSizer.AddSpacer(20)

        flowChartPanel.SetSizer(borderSizer)

        # Bind to the UI elements to get their changes...
        self._changeNameButton.Bind(wx.EVT_BUTTON, self.OnNameChange)

        # Return the panel for our parent...
        return flowChartPanel


    ###########################################################
    def _selectLastEdited(self):
        """Select the component that was edited most recently."""

        lastEditedComponent, i = self._queryDataModel.getLastEdited()
        if lastEditedComponent == 'videoSource':
            self._videoSourceBlock.takeHighlight()
        elif lastEditedComponent == 'target':
            self._targetBlock.takeHighlight()
        elif lastEditedComponent == 'trigger':
            self._regionBlock.takeHighlight()
        elif lastEditedComponent == 'response':
            self._responseBlock.takeHighlight()
        else:
            assert False, "Unknown block to select"


    ###########################################################
    def _updateFromModel(self, queryDataModel):
        """Update all of our settings based on our data models.

        @param  queryDataModel  Should be self._queryDataModel.
        """
        assert queryDataModel == self._queryDataModel
        self._nameLabel.SetLabel(self._queryDataModel.getName())


    ###########################################################
    def _handleCameraChange(self, cameraBlockDataModel):
        """Handle a change in the camera choice.

        @param  cameraBlockDataModel  The data model for the camera.
        """
        assert cameraBlockDataModel == self._cameraBlockDataModel

        self._videoLoadTimer.Stop()

        cameraLocation = cameraBlockDataModel.getLocationName()
        if cameraLocation == kAnyCameraStr:
            self._updateVideoImage(self._anyCameraImage)

            # Make sure that we didn't leave this as the string for imported...
            self._imageFromLabel.SetLabel(_kImageFromStr)
            self._timeLabel.Show(True)
            self._titleSizer.Layout()
        else:
            # Update the 'image from' label for imported clips...
            if cameraLocation.endswith(kImportSuffix):
                self._imageFromLabel.SetLabel(_kImportedImageFromStr)
                self._timeLabel.Show(False)
            else:
                self._imageFromLabel.SetLabel(_kImageFromStr)
                self._timeLabel.Show(True)
            self._titleSizer.Layout()

            self._videoLoadMs = int(time.time() * 1000)
            if self._backEndClient is not None:
                self._backEndClient.flushVideo(cameraLocation)

            # NOTE: UI will be updated on first failure, or success...

            self._videoTimeList = []
            self._videoTimeIndex = None

            self._prevTimeButton.Enable(False)
            self._nextTimeButton.Enable(False)

            self._videoLoadTimerRetries = 0
            self._videoLoadTimer.Start(1, True)


    ###########################################################
    def OnVideoLoadTimer(self, event):
        """Attempt to load a video.

        @param  event  The timer event (ignored).
        """
        cameraLocation = self._cameraBlockDataModel.getLocationName()

        dontWaitList = ['off', 'failed']
        if self._backEndClient is None or \
           self._backEndClient.getCameraStatus(cameraLocation) in dontWaitList:
            image, ms = self._getImage(cameraLocation, self._videoLoadMs, None, 'before')
        else:
            # We really want an image from the last few seconds if we're not
            # off...
            image, ms = self._getImage(cameraLocation, self._videoLoadMs, 1000 * 60, 'before')

        if image is None:
            if self._videoLoadTimerRetries < _kMaxVideoLoadTimerRetries:
                # Set the loading image on the first failure...
                if self._videoLoadTimerRetries == 0:
                    self._updateVideoImage(self._loadingImage)

                self._videoLoadTimerRetries += 1
                self._videoLoadTimer.Start(_kVideoLoadTimerRetryMs, True)
                return
            else:
                # One last try to get _anything_ at all...
                image, ms = self._getImage(cameraLocation, self._videoLoadMs, None, 'before')

                # If we still failed, set the "not available" image...
                if image is None:
                    self._updateVideoImage(self._notAvailableImage)
                    return

        self._updateVideoImage(image, ms)
        self._imageFromLabel.Enable(True)

        self._videoTimeList = [ms]
        self._videoTimeIndex = 0

        self._addPrevTime(ms)

        self._prevTimeButton.Enable(self._videoTimeIndex <
                                    len(self._videoTimeList) - 1)


    ###########################################################
    def _updateVideoImage(self, image, ms=None):
        """Set the video image.

        This also sets the time above the image; and if you pass ms as None,
        it will disable all time-related controls (it won't re-enable them
        if you pass ms as non-None, though)

        @param  image  A PIL image to show in the video window.
        @param  ms     The ms of the image, or None if none.
        """
        # We only want to set the coordinate space for the data model if we are
        # drawing for an image we actually want to use.  It's ok to change the
        # coordinate space of the data model because we're here to edit it in
        # the first place.
        if ((image is not self._anyCameraImage) and
            (image is not self._notAvailableImage) and
            (image is not self._loadingImage)):
            self._queryDataModel.setCoordSpace(image.size)

        self._videoWindow.setImage(image)
        if ms is None:
            self._timeLabel.SetLabel("")
            for control in self._timeControls:
                control.Enable(False)
        else:
            msPlusHour = ms + (1000 * 60 * 60)
            time1Str = formatTime('%I', time.localtime(ms/1000))
            if time1Str[0] == '0':
                time1Str = time1Str[1:]
            time2Str = formatTime('%I %p', time.localtime(msPlusHour/1000)).swapcase()
            if time2Str[0] == '0':
                time2Str = time2Str[1:]

            self._timeLabel.SetLabel("%s-%s" % (time1Str, time2Str))
            self._timeLabel.Enable(True)


    ###########################################################
    def _addPrevTime(self, ms):
        """Append the time prior to the given ms to self._videoTimeList.

        The previous time is the one that we should go to if the user hits
        the left arrow on the video window.

        @param  ms  The time we want the previous time for.
        """
        _kMsPerHour = (1000 * 60 * 60)

        cameraLocation = self._cameraBlockDataModel.getLocationName()

        # Take away at least one hour...
        newMs = ms - _kMsPerHour

        prevImage, prevMs = self._getImage(cameraLocation, newMs, None, 'before')
        if prevImage is not None:
            self._videoTimeList.append(prevMs)

    ###########################################################
    def _getImage(self, cameraLocation, ms, tolerance, direction='any'):
        ''' Get image at it's original size, then resize to best fit the control, while
            maintaining the aspect ratio
        '''
        image, ms = self._dataMgr.getImageAt(cameraLocation, ms, tolerance, direction, (0,0))
        if image is not None:
            oldsize = image.size
            maxsize = (_kVideoWidth, _kVideoHeight)
            ratio = min(maxsize[0]/float(oldsize[0]), maxsize[1]/float(oldsize[1]))
            newsize = (int(oldsize[0]*ratio), int(oldsize[1]*ratio))
            image = image.resize(newsize, Image.ANTIALIAS)
        return image, ms


    ###########################################################
    def OnPrevTime(self, event=None):
        """Handle button press to switch video window to previous time.

        @param  event  The event (ignored).
        """
        cameraLocation = self._cameraBlockDataModel.getLocationName()

        assert (self._videoTimeIndex + 1) <= (len(self._videoTimeList) - 1), \
               "Prev button should be disabled if no more video"

        self._videoTimeIndex = min(self._videoTimeIndex + 1,
                                   len(self._videoTimeList) - 1)
        toLoadMs = self._videoTimeList[self._videoTimeIndex]

        image, ms = self._getImage(cameraLocation, toLoadMs, 0)
        assert ms == toLoadMs
        if not image:
            # Could happen if deleted videos.  ...or disk cleaner?
            image = self._notAvailableImage

        self._updateVideoImage(image, ms)

        # If we're at the first time, prime the pump.  This allows us to
        # show the proper "enabled" state for the "<<" button.
        if self._videoTimeIndex == len(self._videoTimeList)-1:
            self._addPrevTime(toLoadMs)

        self._prevTimeButton.Enable(self._videoTimeIndex <
                                    len(self._videoTimeList) - 1)
        self._nextTimeButton.Enable(self._videoTimeIndex != 0)


    ###########################################################
    def OnNextTime(self, event=None):
        """Handle button press to switch video window to next time.

        @param  event  The event (ignored).
        """
        cameraLocation = self._cameraBlockDataModel.getLocationName()

        assert self._videoTimeIndex > 0, \
               "Prev button should be disabled if no more video"

        self._videoTimeIndex = max(self._videoTimeIndex - 1, 0)
        toLoadMs = self._videoTimeList[self._videoTimeIndex]

        image, ms = self._getImage(cameraLocation, toLoadMs, 0)
        assert ms == toLoadMs
        if not image:
            # Could happen if deleted videos.  ...or disk cleaner?
            image = self._notAvailableImage

        self._updateVideoImage(image, ms)

        self._prevTimeButton.Enable(self._videoTimeIndex <
                                    len(self._videoTimeList) - 1)
        self._nextTimeButton.Enable(self._videoTimeIndex != 0)


    ###########################################################
    def OnNameChange(self, event=None):
        """Handle a click on the "Customize Name" button.

        @param  event  The event (ignored)
        """
        dlg = _CustomizeNameDialog(self.GetTopLevelParent(),
                                   self._queryDataModel,
                                   self._existingNames)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnBlockTitleClick(self, event):
        """Select the block object associate with this title.

        @param  event  The left down event.
        """
        titleObj = event.GetEventObject()

        # Since most of these bitmaps currently include some of the line for
        # the flowchart, we check to see that the click was actually inside
        # the title portion of the image.
        if titleObj.Size[1]-event.GetPosition()[1] <= _kBlockTitleHeight:
            if titleObj == self._bmpVideoSourceTitle:
                self._videoSourceBlock.takeHighlight()
            if titleObj == self._bmpTargetTitle:
                self._targetBlock.takeHighlight()
            if titleObj == self._bmpRegionTitle:
                self._regionBlock.takeHighlight()
            if titleObj == self._bmpResponseTitle:
                self._responseBlock.takeHighlight()


    ###########################################################
    def OnBlockClick(self, event):
        """Handles clicks on any of our construction blocks.

        When this happens, we'll replace the config panel.

        @param  event  The construction block event.
        """
        block = event.GetEventObject()

        # We store the component type / index in the block's client data...
        # ...get it out, and then save...
        lastEditedComponent, i = block.getClientData()
        self._queryDataModel.setLastEdited(lastEditedComponent, i)

        # Hide / deactivate the old panel.
        for panelTuple, configPanel in self._configPanels.iteritems():
            isActive = (panelTuple == (lastEditedComponent, i))
            if (not isActive) and (configPanel.IsShown()):
                configPanel.Show(False)
                configPanel.deactivate()

        activeConfigPanel = self._configPanels[(lastEditedComponent, i)]
        activeConfigPanel.activate()
        activeConfigPanel.Show(True)
        wx.CallAfter(activeConfigPanel.SetFocus)

        self._titleLabel.SetLabel(activeConfigPanel.getTitle() + ":")
        self._iconCtrl.SetBitmap(wx.Bitmap(activeConfigPanel.getIcon()))


##############################################################################
class _CustomizeNameDialog(wx.Dialog):
    """A dialog that lets you customize the name of the query."""

    ###########################################################
    def __init__(self, parent, queryDataModel, existingNames):
        """_CustomizeNameDialog constructor.

        @param  parent          Our parent UI element.
        @param  queryDataModel  The data model to edit.
        @param  existingNames   Reserved names the user should not be allowed
                                to use.
        """
        # Call our super
        super(_CustomizeNameDialog, self).__init__(
            parent, title=_kCustomizeNameTitleStr
        )

        try:
            self._doInit(queryDataModel, existingNames)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _doInit(self, queryDataModel, existingNames):
        """Actual init code; see __init__() for details.

        This function exists so we can put a "try" around it easily...
        """
        # Save parameters...
        self._queryDataModel = queryDataModel
        self._existingNames = existingNames

        # Create the UI...
        self._customizeNameButton = \
            wx.RadioButton(self, -1, _kCustomizeNameRadioStr)
        self._customNameField = wx.TextCtrl(self, -1)
        self._customNameField.SetMaxLength(_kMaxRuleNameLen)
        self._autoNameButton = \
            wx.RadioButton(self, -1, _kAutoNameRadioStr)

        # Windows radio button controls do not support newlines in their labels
        # so we must create a static text for the second line
        autoNameLabel = wx.StaticText(self, -1, '      "%s"' % (
                                      queryDataModel.getAutoName()))

        # Update from model...
        if queryDataModel.isAutoNamed():
            self._autoNameButton.SetValue(1)
        else:
            self._customizeNameButton.SetValue(1)
            self._customNameField.SetValue(queryDataModel.getName())
            wx.CallAfter(self._customNameField.SetSelection, -1, -1)

        # Add stuff to sizers...
        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(10)
        customizeSizer = wx.BoxSizer(wx.HORIZONTAL)
        customizeSizer.Add(self._customizeNameButton, 0, wx.RIGHT |
                           wx.ALIGN_CENTER_VERTICAL, 10)
        customizeSizer.Add(self._customNameField, 1, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(customizeSizer, 0, wx.EXPAND | wx.BOTTOM, 8)
        sizer.Add(self._autoNameButton, 0, wx.EXPAND | wx.RIGHT, 15)
        sizer.Add(autoNameLabel, 0, wx.EXPAND | wx.TOP, 5)
        sizer.AddSpacer(60)
        sizer.Add(buttonSizer, 0, wx.EXPAND)

        borderSizer = wx.BoxSizer()
        borderSizer.Add(sizer, 1, wx.EXPAND | wx.ALL, 15)

        self.SetSizer(borderSizer)

        self.Fit()
        self.CenterOnParent()

        # Give focus to the text field so user can just start typing...
        self._customNameField.SetFocus()

        # Bind to various events...
        self._customizeNameButton.Bind(wx.EVT_RADIOBUTTON, self.OnCustomRadio)
        self._customNameField.Bind(wx.EVT_TEXT, self.OnCustomName)
        self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOK)


    ###########################################################
    def OnCustomName(self, event):
        """Handle text events on the custom name field.

        When we get this, we'll select the radio button, since the user
        probably wanted to do that.

        @param  event  The event.
        """
        self._customizeNameButton.SetValue(1)
        event.Skip()


    ###########################################################
    def OnCustomRadio(self, event):
        """Handle selections of the radio button so we can focus the field.

        @param  event  The event.
        """
        self._customNameField.SetFocus()
        self._customNameField.SetSelection(-1, -1)
        event.Skip()


    ###########################################################
    def OnOK(self, event):
        """Respond to the user pressing OK

        @param  event  The button event
        """
        if self._autoNameButton.GetValue():
            # Don't bother checking for conflicts; we'll do that when leaving
            # the dialog...
            self._queryDataModel.setName("")
        else:
            queryName = self._customNameField.GetValue().strip()
            # Normalize the query name so it can be safely saved as a file name.
            # Windows supports saving both NFC and NFD Unicode file names, but they
            # are treated as *different* files, so we need to always use NFC.
            queryName = normalizePath(queryName)

            cameraName = self._queryDataModel.getVideoSource().getLocationName()
            isOk = checkQueryName(queryName, cameraName, self._existingNames,
                                  self)
            if not isOk:
                return

            self._queryDataModel.setName(queryName)

        self.EndModal(wx.ID_OK)


##############################################################################
def checkQueryName(queryName, cameraName, existingNames, topLevelParent,
                   isAutoNamed=False):
    """Check to see if the given query name is OK.

    We'll display a message to the user if it's not.

    @param  queryName       The name of the query to check.
    @param  cameraName      The camera name for this query
    @param  existingNames   Reserved names the user should not be allowed
                            to use; should be all lowercase.
    @param  topLevelParent  We'll use this as the parent for any wx.MessageBox
                            errors we show.
    @param  isAutoNamed     If True, the query was auto-named; this can affect
                            the error message we give the user.
    @return isOk            True if OK, False if not.
    """
    if not queryName:
        wx.MessageBox("You must enter a name for this rule.", "Error",
                      wx.OK | wx.ICON_ERROR, topLevelParent)
        return False
    if re.search("[%s]" % kInvalidPathChars, queryName) is not None:
        if isAutoNamed:
            wx.MessageBox("Your region name cannot contain any of the "
                          "following characters: %s "
                          "if you are using an automatically-generated name.  "
                          "Please choose a different region name." % \
                          kInvalidPathCharsDesc, "Error",
                           wx.OK | wx.ICON_ERROR, topLevelParent)
        else:
            wx.MessageBox("The rule name cannot contain any of the following"
                          " characters: %s. "
                          "Please choose a different name." % \
                          kInvalidPathCharsDesc, "Error",
                           wx.OK | wx.ICON_ERROR, topLevelParent)
        return False
    if queryName.lower() in existingNames:
        wx.MessageBox('There is already a rule named "%s".  Please '
                       'choose a different name.' % queryName, "Error",
                       wx.OK | wx.ICON_ERROR, topLevelParent)
        return False

    # Prevent non-UTF8 characters in rule names
    try:
        queryName.encode('utf-8', 'strict')
    except UnicodeEncodeError, e:
        if isAutoNamed:
            wx.MessageBox(("Your region name cannot contain the "
                          "character \"%s\". "
                          "Please choose a different region name.") %
                           e.object[e.start:e.start+1],
                          "Error",
                           wx.OK | wx.ICON_ERROR, topLevelParent)
        else:
            wx.MessageBox(("The rule name cannot contain the character \"%s\". "
                          "Please choose a different name.") %
                           e.object[e.start:e.start+1],
                          "Error",
                           wx.OK | wx.ICON_ERROR, topLevelParent)
        return False

    # Validate the length of the rule name
    if isAutoNamed:
        # Validate the rule name length assuming a max length camera name
        currMaxAllowed = _kMaxRuleNameLen - kMaxCameraNameLen + len(cameraName)
        if len(queryName) > currMaxAllowed:
            wx.MessageBox('The automatically generated rule name is longer '
                       'than %d characters because the region name you have '
                       'chosen is too long. Please use a shorter region '
                       'name.' % currMaxAllowed,
                       "Error", wx.OK | wx.ICON_ERROR, topLevelParent)
            return False
    else:
        if len(queryName) > _kMaxRuleNameLen:
            wx.MessageBox('The rule name can be no longer than %d characters. '
                       'Please choose a shorter name.' % _kMaxRuleNameLen,
                       "Error", wx.OK | wx.ICON_ERROR, topLevelParent)
            return False

    return True


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "Please use QueryEditorDialog test code"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
