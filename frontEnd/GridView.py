#!/usr/bin/env python

#*****************************************************************************
#
# GridView.py
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
import time
import traceback
import sys

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BitmapWindow import BitmapWindow
from vitaToolbox.wx.GLCanvasSV import OsCompatibleGLCanvas, GLExceptionSV
from vitaToolbox.wx.GradientPanel import GradientPanel
from vitaToolbox.wx.CreateMenuFromData import createMenuFromData
from vitaToolbox.wx.BindChildren import bindChildren

# Local imports...
import FrontEndEvents
from FrontEndPrefs import getFrontEndPref
from FrontEndPrefs import setFrontEndPref
from FrontEndUtils import determineGridViewCameras
from BaseView import BaseMonitorView
from BaseView import makeVideoStatusBitmap
from BaseView import kStatusTextConnecting
from BaseView import kStatusTextCouldNotConnect
from BaseView import kStatusTextCameraTurnedOff
from BaseView import kStatusStartColor
from BaseView import kStatusEndColor
from appCommon.CommonStrings import kCameraOn
from appCommon.CommonStrings import kCameraOff
from appCommon.CommonStrings import kCameraConnecting
from appCommon.CommonStrings import kCameraFailed

# Constants...

# Some average camera resolution aspect ratio, rough guess.
_kCommonAspectRatio = (1280.0 / 720 + 640.0 / 480) / 2

# How often to log the frame rate, in seconds.
_kFpsLogInterval = 2.0

# How often to synchronize with the camera states.
_kCamerasSyncInterval = 1.0

# How often to try to attach to memory maps if we're supposed to.
_kSyncMmapInterval = .5

# After how many seconds to give up on a camera if it hasn't yielded any new
# frames since the last time we picked up one.
_kCameraTimeout = 5.0

# Gap between the camera views, in pixels.
_kGridGap = 5

# Maximum number of rows supported. Anything higher will be capped.
_kMaxRows = 9

# Maximum number of columns supported. Anything higher will be capped.
_kMaxCols = 9

# Controls menu for which we place a custom menu while the grid view is active.
_kControlsMenuName = "&Controls"

# Do not disable memory map, until the camera has not been visible for this long
_kMmapTimeout = 20

# When mmap for an enabled camera isn't available, delay requests to enable mmap by an increasing value
_kMinMmapRetryTime = 1
_kMaxMmapRetryTime = 32

# To map a camera state to status text which we can then show.
_kStatusTextMap = {
    kCameraOn: None,  # if a camera's on we show its picture
    kCameraOff: kStatusTextCameraTurnedOff,
    kCameraConnecting: kStatusTextConnecting,
    kCameraFailed: kStatusTextCouldNotConnect
}

# Events we listen on to detect changes in the set of cameras.
_kCameraChangeEvents = [
    FrontEndEvents.EVT_CAMERA_ADDED,
    FrontEndEvents.EVT_CAMERA_EDITED,
    FrontEndEvents.EVT_CAMERA_REMOVED ]


##############################################################################
class VisibleCamera:
    """ Stores state for cameras which are visible in the grid view.
    """

    ###########################################################
    def __init__(self, location, enabled, status, reason, lastFrameId, viewControl):
        """
        @param  location     The camera location.
        @param  enabled      Whether the camera is logically enabled. If so
                             we are trying to connect and may have live view
                             data.
        @param  status       Camera status, mostly to be displayed when there is
                             no live view available.
        @param  lastFrameId  The identifier of the last live view frame
                             received, so on the next poll we can detect new
                             ones.
        @param  viewControl  The associated view control, where either live
                             view or status images can be shown at.
        """
        self.location = location
        self.enabled = enabled
        self.status = status
        self.reason = reason
        self.lastFrameId = lastFrameId
        self.viewControl = viewControl
        self.frameCounter = 0
        self.lastFrameTime = time.time()
        self.lastOpenRequestTime = 0
        self.currentRetryTime = _kMinMmapRetryTime


##############################################################################
class GridView(BaseMonitorView):
    """ Simple view of all cameras, with a subset of them shown actively,
    determined by the grid's dimension and what the starting index in the
    camera list is. The driving mechanism is straightforward: on a timer tick
    we collect all of the frames from memory maps of the active cameras and
    put them into view controls (either OpenGL or, if we can't, of the bitmap
    kind). This high frequency timer keeps up with the desired frame rate, but
    also occasionally checks whether the camera's status has changed or if a
    new memory map is available. Navigation happens through keyboard hits.
    """

    ###########################################################
    def __init__(self, parent, backEndClient, fullScreenMode=False, camerasToShow=None):
        """
        @param  parent         The parent window.
        @param  backendClient  To talk to the backend or camera processes.
        @param  fullScreenMode Show grid view in full screen mode (no associated menubar or menu items)
        @param  camerasToShow  Restrict cameras shown to the provided list
        """
        super(GridView, self).__init__(parent, backEndClient,
                                       startColor=(0, 0, 0), endColor=(0, 0, 0))

        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer)

        self._viewControls = []
        self._visibleCameras = {}
        self._accessTime = {}
        self._statusBitmaps = {}

        self._nextMmapSync = None
        self._nextCamerasSync = None

        self._busy = False
        self._lastFpsLog = None
        self._zoomLevel = 0

        self._bitmapMode = False

        self._liveViewStatus = {}

        self._camerasToShow = camerasToShow
        self._fullScreenMode = fullScreenMode
        self._creationTime = time.time()

        if fullScreenMode:
            self._actionDClick = self._closeParent
            self._actionClick = self._closeParent
        else:
            self._actionDClick = self.OnDoubleClickFullScreen
            self._actionClick = None

        self._initUI()


    ###########################################################
    def Destroy(self):
        """
        @see wx.Panel.Destroy()
        """
        if self._otherControlsMenu is None:
            self.self._controlsMenu.Destroy()
        super(self, GridView).Destroy()


    ###########################################################
    def _createViewControl(self):
        """ Create a view control, where we can show live view images or
        just status information.

        @return  The view control, either fast OpenGL or legacy bitmap windows.
        """
        # The strategy is to always try to get an OpenGL canvas, since we
        # observed occasional failures to do so. Only if we determine for sure
        # that it will never work out for us we set a flag to prevent further
        # futile attempts - this flag however might be then set back temporarily
        # due to the preferences, so we'll fail again, just once though.
        if not self._bitmapMode:
            try:
                result = OsCompatibleGLCanvas(self)
                return result
            except GLExceptionSV, e:
                if e.version.startswith("1"):
                    self._logger.error("no compatible OpenGL available")
                    # Don't ever try to create GL controls again
                    self._bitmapMode = True
                else:
                    self._logger.error("OpenGL canvas creation error: %s" %
                                       traceback.format_exc())
            except:
                self._logger.error("general OpenGL canvas creation error: %s" %
                                   traceback.format_exc())
        emptyBitmapRes = (32, 32)
        emptyBitmap = wx.Bitmap(*emptyBitmapRes)
        return BitmapWindow(self, emptyBitmap, emptyBitmapRes, scale=True)


    ###########################################################
    def _createMenu(self):
        """ Creates the menu we use both on top, as well as in popup style.

        @return  New menu instance.
        """
        if self._fullScreenMode:
            return

        items = (
            ("Back\tLeft", "", self._menuIdBack, self._controlBack),
            ("Forward\tRight", "", self._menuIdForward, self._controlForward),
            (None, None, None, None),
            ("Zoom In\tUp", "", self._menuIdZoomIn, self._controlZoomIn),
            ("Zoom Out\tDown", "", self._menuIdZoomOut, self._controlZoomOut),
            )

        menu = createMenuFromData(items, self.GetTopLevelParent())


        # Create an accelerator table
        self._accelTable = wx.AcceleratorTable([(wx.ACCEL_CTRL, wx.WXK_LEFT,  self._menuIdBack),
                                                (0,             wx.WXK_LEFT,  self._menuIdBack),
                                                (wx.ACCEL_CTRL, wx.WXK_RIGHT, self._menuIdForward),
                                                (0,             wx.WXK_RIGHT, self._menuIdForward),
                                                (wx.ACCEL_CTRL, ord('+'),     self._menuIdZoomIn),
                                                (0,             ord('+'),     self._menuIdZoomIn),
                                                (wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('='),     self._menuIdZoomIn),
                                                (wx.ACCEL_SHIFT,ord('='),     self._menuIdZoomIn),
                                                (wx.ACCEL_CTRL, ord('='),     self._menuIdZoomIn),
                                                (0,             ord('='),     self._menuIdZoomIn),
                                                (0,             wx.WXK_UP,    self._menuIdZoomIn),
                                                (wx.ACCEL_CTRL, ord('-'),     self._menuIdZoomOut),
                                                (0,             ord('-'),     self._menuIdZoomOut),
                                                (0,             wx.WXK_DOWN,  self._menuIdZoomOut),
                                             ])
        self.SetAcceleratorTable(self._accelTable)
        return menu



    ###########################################################
    def _initUI(self):
        """ Set up basic UI things, like the grid sizer.
        """
        # Create the menu, ready to replace the default one on activation.
        self._menuIdBack = wx.NewId()
        self._menuIdForward = wx.NewId()
        self._menuIdZoomIn = wx.NewId()
        self._menuIdZoomOut = wx.NewId()
        self._controlsMenuPos = wx.NOT_FOUND
        self._controlsMenu = self._createMenu()
        self._otherControlsMenu = None

        # Listen to keyboard input we care about.
        self._gridSizer = wx.GridSizer(1, 1, _kGridGap, _kGridGap)

        if not self._fullScreenMode:
            # Attach a context menu.
            self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
            self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)

        self.Bind(wx.EVT_LEFT_DCLICK, self._actionDClick)
        if self._actionClick is not None:
            self.Bind(wx.EVT_LEFT_UP, self._actionClick)

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnWindowDestroy)

        # Create the basic sizers.
        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(self._gridSizer, 1, wx.EXPAND)
        self.SetSizer(borderSizer)
        self.Layout()


    ###########################################################
    def OnWindowDestroy(self, event):
        if event.GetWindow() == self:
            self._timer.Stop()
            self._timer = None

    ###########################################################
    def _enableControlsMenu(self, enable=True):
        """ To enable or disable the controls menu, i.e. replacing or restoring
        the original one other views do use.

        @param  enable  True/False to enable/disable the view's control menu.
        """
        if self._fullScreenMode:
            return

        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()
        if enable:
            if wx.NOT_FOUND != self._controlsMenuPos:
                return
            pos = menuBar.FindMenu(_kControlsMenuName)
            if wx.NOT_FOUND == pos:
                return
            self._controlsMenuPos = pos
            self._otherControlsMenu = menuBar.Replace(
                pos, self._controlsMenu, _kControlsMenuName)
        else:
            if wx.NOT_FOUND == self._controlsMenuPos:
                return
            menuBar.Replace(self._controlsMenuPos, self._otherControlsMenu,
                            _kControlsMenuName)
            self._otherControlsMenu = None
            self._controlsMenuPos = -1


    ###########################################################
    def _syncCameraLocations(self, excludeFrozen=True):
        """ Update ordered list of camera locations we will be showing

        @param  excludeFrozen  Do not return frozen cameras.
        """
        if self._camerasToShow is None:
            allCameraLocations = self._backEndClient.getCameraLocations()
        else:
            allCameraLocations = self._camerasToShow

        cameraLocations = []
        cameraStatus = {}
        for cameraLocation in allCameraLocations:
            _, _, enabled, extra = self._backEndClient.getCameraSettings(
                cameraLocation)
            if not excludeFrozen or not extra.get('frozen', False):
                cameraLocations.append(cameraLocation)
                cameraStatus[cameraLocation] = enabled

        order = getFrontEndPref("gridViewOrder")
        sortedCameraLocations = determineGridViewCameras(cameraLocations, order)

        showInactiveMode = getFrontEndPref("gridViewShowInactive")
        if showInactiveMode == 0:
            # Don't show inactive cameras at all
            newCameraLocations = []
            for cameraLocation in sortedCameraLocations:
                if cameraStatus[cameraLocation]:
                    newCameraLocations.append(cameraLocation)
            self._cameraLocations = newCameraLocations
        elif showInactiveMode == 2:
            # Show inactive cameras, but push them to the end of the list
            newCameraLocations = []
            inactiveCameraLocations = []
            for cameraLocation in sortedCameraLocations:
                if cameraStatus[cameraLocation]:
                    newCameraLocations.append(cameraLocation)
                else:
                    inactiveCameraLocations.append(cameraLocation)
            self._cameraLocations = newCameraLocations + inactiveCameraLocations
        else:
            self._cameraLocations = sortedCameraLocations


    ###########################################################
    def _getGridViewStart(self):
        if self._fullScreenMode:
            return 0
        return getFrontEndPref("gridViewStart")

    ###########################################################
    def _setGridViewStart(self, start):
        """ Set grid view preferences, unless in full screen mode
        """
        if not self._fullScreenMode:
            self._gridDebug("Setting grid view start to " + str(start) + " of " + str(len(self._cameraLocations)))
            setFrontEndPref("gridViewStart", start, False)

    ###########################################################
    def __sync(self):
        """ Synchronizes all of the current cameras and the grid view
        configuration, so we have the right layout, the right number of
        view controls (means potentially tossing out old ones).
        """

        # Get the latest camera( location)s.
        self._syncCameraLocations()
        self._gridDebug("%d camera locations" % len(self._cameraLocations))

        # Change the grid's dimension if necessary.
        cols = max(1, min(_kMaxCols, getFrontEndPref("gridViewCols")))
        rows = max(1, min(_kMaxRows, getFrontEndPref("gridViewRows")))

        cols, rows = self._applyZoom(cols, rows)

        start = self._getGridViewStart()

        # Make sure the start offset is in range and that we try as best as
        # possible not to have any unnecessary slack at the end.
        newStart = start
        start = min(len(self._cameraLocations) - 1, start)
        start = max(0, min(start, len(self._cameraLocations) - cols * rows))
        self._gridDebug("sync @ %d (%dx%d) ..." % (start, cols, rows))
        self._setGridViewStart(start)

        # Update the menu(s) based on where we're at now.
        if not self._fullScreenMode:
            isFullScreen = False
            canBack = newStart > 0 and not isFullScreen
            canForward = len(self._cameraLocations) - newStart > cols * rows and not isFullScreen
            canZoomIn = cols > 1 or rows > 1 and not isFullScreen
            canZoomOut = cols * rows < len(self._cameraLocations) and not isFullScreen
            self._controlsMenu.Enable(self._menuIdBack, canBack)
            self._controlsMenu.Enable(self._menuIdForward, canForward)
            self._controlsMenu.Enable(self._menuIdZoomIn, canZoomIn)
            self._controlsMenu.Enable(self._menuIdZoomOut, canZoomOut)

        # Adjust the grid sizer's dimensions.
        if self._gridSizer.GetCols() != cols:
            self._gridSizer.SetCols(cols)
        if self._gridSizer.GetRows() != rows:
            self._gridSizer.SetRows(rows)

        # Add or remove view controls.
        viewControlCount = min(cols * rows, len(self._cameraLocations) - start)
        self._gridDebug("%d view controls needed" % viewControlCount)
        delta = viewControlCount - len(self._viewControls)

        if 0 > delta:
            for _ in xrange(0, -delta):
                viewControl = self._viewControls.pop()
                self._gridSizer.Detach(viewControl)
                viewControl.Destroy()
        else:
            for _ in xrange(0, delta):
                viewControl = self._createViewControl()
                self._viewControls.append(viewControl)
                self._gridSizer.Add(viewControl, 1, wx.EXPAND)
            self.Layout()

        if self._fullScreenMode:
            bindChildren(self, wx.EVT_CHAR, self.OnFullScreenKeyboard)
        else:
            if wx.Platform == '__WXMSW__':
                bindChildren(self, wx.EVT_SET_FOCUS, self.OnFocusChanged)

        bindChildren(self, wx.EVT_LEFT_DCLICK, self._actionDClick)
        if self._actionClick is not None:
            bindChildren(self, wx.EVT_LEFT_UP, self._actionClick)

        # Clear the status bitmaps, will be regenerated when needed.
        self._statusBitmaps = {}

        # Synchronize the cameras' status.
        self._visibleCameras = {}

        # Time to update the memory maps and status.
        self._nextMmapSync = 0
        self._nextCamerasSync = 0

    ###########################################################
    def OnFullScreenKeyboard(self, event=None):
        if event is None:
            return
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_ESCAPE or keycode == wx.WXK_RETURN:
            self._closeParent(event)



    ###########################################################
    def _closeParent(self, event=None):
        _kMinimumFullscreenLifespan = 0.5 # Don't close fullscreen window too soon!

        if time.time() < self._creationTime + _kMinimumFullscreenLifespan:
            return
        parent = self.GetParent()
        if parent is not None:
            wx.CallAfter(parent.Close)

    ###########################################################
    def _syncCameras(self):
        """ Makes sure that we have the right status determined and set for the
        currently visible cameras. This also means that we turn live views on
        or off, depending what a camera's state is.
        """

        if self._nextCamerasSync is None or self._nextCamerasSync > time.time():
            return

        start = self._getGridViewStart()
        count = len(self._viewControls)
        currentTime = time.time()

        # Check cameras which are visible in the view, called visible cameras.
        fps = getFrontEndPref("gridViewFps")

        for i in xrange(start, start + count):
            cameraLocation = self._cameraLocations[i]

            # Get a visible camera status and whether it's enabled.
            status, reason, enabled = \
                self._backEndClient.getCameraStatusEnabledAndReason(cameraLocation)

            # Add a record if we haven't done so, and set its new status.
            visibleCamera = self._visibleCameras.get(cameraLocation, None)
            if visibleCamera is None:
                visibleCamera = VisibleCamera(
                    cameraLocation, enabled, status, reason, -1,
                    self._viewControls[i - start])
                self._visibleCameras[cameraLocation] = visibleCamera
                self._gridDebug("added visible camera '%s'" % cameraLocation)
            else:
                visibleCamera.enabled = enabled
                visibleCamera.status = status
                visibleCamera.reason = reason

            # If the camera can yield a live view i.e. it's enabled we need to
            # request this, potentially multiple times, no harm in doing that.
            if visibleCamera.enabled:
                if not cameraLocation in self._mmaps:
                    self._enableLiveView(visibleCamera, fps)
                else:
                    # Reset the retry timeout, so we use minimal possible
                    # value next time this camera disconnects
                    visibleCamera.currentRetryTime = _kMinMmapRetryTime
            else:
                # Otherwise ensure that we have it turned off.
                self._disableLiveView(cameraLocation)

            # If we haven't latched into a memory map there needs to be a status
            # bitmap shown instead.
            if not cameraLocation in self._mmaps:
                image = self.getStatusBitmap(visibleCamera)
                visibleCamera.viewControl.updateBitmap(image)

        # Ensure that live views for non-visible cameras are turned off.
        for cameraLocation in self._cameraLocations:
            if not cameraLocation in self._visibleCameras:
                lastAccessTime = self._accessTime.get(cameraLocation, None)
                if lastAccessTime is None or \
                   lastAccessTime + _kMmapTimeout < currentTime:
                    # only disable live view when it times out, not immediately after becoming invisible
                    self._disableLiveView(cameraLocation)
            else:
                self._accessTime[cameraLocation] = currentTime

        # Schedule the next time for us to sync.
        self._nextCamerasSync = currentTime + _kCamerasSyncInterval

    ###########################################################
    def _enableLiveView(self, visibleCamera, fps):
        cameraLocation = visibleCamera.location
        self._liveViewStatus[cameraLocation] = True
        # do not bombard backend with requests to open live view more than once per second
        currentTime = time.time()
        if currentTime - visibleCamera.lastOpenRequestTime < visibleCamera.currentRetryTime:
            return
        # Set mmap parameters before enabling large view ...
        # Doing things in reverse order will cause the server side to reopen
        # mmap file, potentially leaving the client with a dead handle, if it
        # is acquired between the open and configure operations
        visibleCamera.lastOpenRequestTime = currentTime

        # Make sure we do not bombard the backEnd by requests to enable
        # live view, when the camera may be struggling to connect
        visibleCamera.currentRetryTime = min(visibleCamera.currentRetryTime*2, _kMaxMmapRetryTime)
        self._backEndClient.setLiveViewParams(cameraLocation, 0, 0, 0, fps)
        self._backEndClient.enableLiveView(cameraLocation, True)
        self._gridDebug("requested live view for camera '%s'" %
                          cameraLocation)

    ###########################################################
    def _disableLiveView(self, cameraLocation):
        """ Turn off the live view for a particular camera.

        @param  cameraLocation  Location for which live viewing ceased.
        """
        self._accessTime.pop(cameraLocation, None)

        # Close the memory map (if we had one).
        if not self._liveViewStatus.get(cameraLocation, True):
            return

        self._closeMMap(cameraLocation)

        # Tell the backend that we're not interested in live viewing anymore.
        self._backEndClient.enableLiveView(cameraLocation, False)
        self._liveViewStatus[cameraLocation] = False
        self._gridDebug("disabled live view for '%s'" % cameraLocation)


    ###########################################################
    def _sync(self):
        """ Synchronizes the view while freezing the whole window.
        """
        if not self._isActiveView:
            return
        self.Freeze()
        try:
            self.__sync()
            self.Layout()
        finally:
            self.Thaw()


    ###########################################################
    def _navigate(self, offset):
        """ To navigate through the grid.

        @param  offset  Navigation offset, negative to navigate backwards.
        """
        start = self._getGridViewStart()
        newStart = min(len(self._cameraLocations) - 1, start)
        newStart = max(0, start + offset)
        self._setGridViewStart(newStart)
        self._gridDebug("navigating, start set to %d ..." % newStart)
        self._sync()


    ###########################################################
    def _applyZoom(self, cols, rows):
        """ Apply the current zoom level at the most meaningful way. If the
        level is overshooting when zooming out we cap it here.

        @param   rows   The configured, original number of rows.
        @param   cols   The configured, original number of columns.
        @return         Zoomed number of columns.
        @return         Zoomed number of rows.
        """
        viewAspectRatio = self._gridSizer.GetSize()
        viewAspectRatio = float(viewAspectRatio[0]) / max(1, viewAspectRatio[1])
        zoom = self._zoomLevel
        camCount = len(self._cameraLocations)

        # Make sure grid settings make sense with the amount of cameras we have
        while cols > 1 or rows > 1:
            canDropCols = cols > 1 and (cols - 1)*rows >= camCount
            canDropRows = rows > 1 and cols*(rows - 1) >= camCount
            if canDropCols:
                if cols >= rows or not canDropRows:
                    cols -= 1
                else:
                    rows -= 1
            elif canDropRows:
                if rows >= cols or not canDropCols:
                    rows -= 1
                else:
                    cols -= 1
            else:
                break

        if zoom > 0:  # zoom out
            while (cols < _kMaxCols or rows < _kMaxRows) and zoom > 0:
                if cols * rows >= camCount:
                    self._zoomLevel -= zoom
                    break
                if cols >= _kMaxCols:
                    rows += 1
                elif rows >= _kMaxRows:
                    cols += 1
                elif (viewAspectRatio * rows) / cols > _kCommonAspectRatio:
                    cols += 1
                else:
                    rows += 1
                zoom -= 1
        else:  # zoom in
            while (cols > 1 or rows > 1) and zoom < 0:
                if cols <= 1:
                    rows -= 1
                elif rows <= 1:
                    cols -= 1
                elif (viewAspectRatio * rows) / cols > _kCommonAspectRatio:
                    cols -= 1
                else:
                    rows -= 1
                zoom += 1
        return (cols, rows)


    ###########################################################
    def _zoom(self, inc):
        """ Increases or decreases the zoom level.

        @param  inc  Increment as an integer, usually either -1 or 1.
        """
        cols = self._gridSizer.GetCols()
        rows = self._gridSizer.GetRows()
        if inc > 0 and _kMaxCols <= cols and _kMaxRows <= rows:
            return
        if inc < 0 and 1 >= cols and 1 >= rows:
            return
        self._zoomLevel += inc

        self.Freeze()
        try:
            self.__sync()
            self.Layout()
            self._syncCameras()
            self.Layout()
            for _, visibleCamera in self._visibleCameras.iteritems():
                self._updateLiveViewImage(visibleCamera)
        finally:
            self.Thaw()


    ###########################################################
    def handleLicenseChange(self):
        """
        @see  BaseMonitorView.handleLicenseChange
        """
        # Get back in sync with reality, if we must.
        self._sync()


    ###########################################################
    def prepareToClose(self):
        """
        @see  BaseView.prepareToClose
        """
        # Stopping the timer is sufficient to avoid all side effects.
        self._timer.Stop()
        self._isActiveView = False


    ###########################################################
    def deactivateView(self):
        """
        @see BaseView.deactivateView
        """
        super(GridView, self).deactivateView()
        self._enableControlsMenu(False)

        # Make the timer stop.
        self._timer.Stop()

        # Detach from events
        for event in _kCameraChangeEvents:
            self.GetParent().Unbind(event)

        # Turn off the live view for all visible cameras
        for cameraLocation in self._cameraLocations:
            self._disableLiveView(cameraLocation)


    ###########################################################
    def setActiveView(self, viewParams={}):
        """
        @see BaseView.setActiveView
        """
        super(GridView, self).setActiveView(viewParams)
        self._enableControlsMenu()

        # Honor zoom level wishes.
        self._zoomLevel = viewParams.get("zoomLevel", self._zoomLevel)

        # Make sure the view is configured right, dimensions, view controls
        # being generated etc.
        self._sync()

        # Prepare FPS recording.
        self._lastFpsLog = time.time()

        # Camera changes should cause use to synchronize with reality.
        for evt in _kCameraChangeEvents:
            self.GetParent().Bind(FrontEndEvents.EVT_CAMERA_ADDED, self._sync)

        # Launch the timer, where we do the other (sync) work.
        fps = getFrontEndPref("gridViewFps")
        if fps == 0:
            # Set an arbitrary high refresh value for 'unlimited' fps
            fps = 100

        self._timer.Start(1000 / fps, False)


    ###########################################################
    def _syncMmap(self):
        """ Makes sure that we have memory maps or live view data respectively
        for all enabled cameras. Since there is no clear status saying "we're
        on, we have frames" there can be only attempts to open the right mmap.
        """
        # Only synchronize when the time is right.
        now = time.time()
        if self._nextMmapSync is None or self._nextMmapSync > now:
             return
        for _, visibleCamera in self._visibleCameras.iteritems():
            if not visibleCamera.enabled:
                continue
            if not visibleCamera.location in self._mmaps:
                # Open memory maps if we haven't so yet.
                try:
                    if self._openMmap(visibleCamera.location):
                        visibleCamera.lastFrameTime = now
                except IOError:
                    pass
        self._nextMmapSync = now + _kSyncMmapInterval


    ###########################################################
    def _updateLiveViewImage(self, visibleCamera):
        """ Tries to get and show the next live view image. Also counts the
        frames it actually received.

        @param  visibleCamera  The camera to update.
        """
        # Do not update image for cameras that have not been enabled
        if not visibleCamera.enabled:
            return

        # Pointless to try and read the frame after timeout
        if not visibleCamera.location in self._mmaps:
            return

        # Try to acquire an image.
        image, width, height, id, _, _ = self._getLiveImage(\
            visibleCamera.location, visibleCamera.lastFrameId)
        now = time.time()

        if id is None or \
           image is None or \
           visibleCamera.lastFrameId == id:
            # If we haven't gotten a new frame in a reasonable amount of time
            # we declare the live viewing to be over for now.
            if visibleCamera.lastFrameTime + _kCameraTimeout < now:
                self._closeMMap(visibleCamera.location)
                self._logger.warning("mmap image timeout for " + visibleCamera.location)
            return

        visibleCamera.lastFrameTime = now
        visibleCamera.lastFrameId = id
        visibleCamera.frameCounter += 1
        self._updateVideoControl(visibleCamera.viewControl,
                                 width, height, image)


    ###########################################################
    def _onTimer(self, event=None):
        """ Grid view timer function, where everything periodic happens. Gets
        called with a high(er) frequency, some things do not happen on every
        cycle though.

        @param  event  Timer event, not used.
        """

        # Try to open the memory maps which we are supposed to use.
        self._syncMmap()

        # Ensure that all of the camera's states are in sync. This is were we
        # also might update status images, in case there is no live view
        # available.
        self._syncCameras()

        # Every time the timer ticks we go through all visible cameras and
        # check if there are new frames to show. If it's time we also log the
        # frame rates. However if nothing's moving we skip it.
        now = time.time()
        fpsLogSkip = True
        fpsLog = "" if now - self._lastFpsLog >= _kFpsLogInterval else None

        for _, visibleCamera in self._visibleCameras.iteritems():

            self._updateLiveViewImage(visibleCamera)

            if not fpsLog is None:
                fpsTime = time.time() - self._lastFpsLog
                fps = visibleCamera.frameCounter / fpsTime
                fpsLog += "%s%s: %.2f" % \
                    (", " if fpsLog else "", visibleCamera.location, fps)
                visibleCamera.frameCounter = 0
                fpsLogSkip |= 0 == fps

        if not fpsLog is None and not fpsLogSkip:
            self._gridDebug("[FPS] " + fpsLog)
            self._lastFpsLog = time.time()


    ###########################################################
    def getStatusBitmap(self, visibleCamera):
        """ Gets a bitmap which can be painted into the view of a visible
        camera, where usually the live view frames are shown.

        @param  visibleCamera  The camera for which to render the image.
        """

        # Most of the time we already have the rendered image in the cache,
        # only initially or after a refresh latter is empty.
        status = visibleCamera.status
        location = visibleCamera.location
        reason = visibleCamera.reason
        frozen = hasattr(sys, "frozen")
        key = status + location
        if reason is not None:
            key = key + reason

        result = self._statusBitmaps.get(key, None)
        if result is None:
            statusText = _kStatusTextMap.get(status, None)

            # This will happen when we have a connected camera, but no mmap
            if statusText is None:
                statusText = "Please wait ..."

            statusText = statusText + "\n[" + location + "]"
            if reason is not None:
                statusText = statusText + "\n" + reason

            size = self._viewControls[0].GetSize()

            # The OpenGL view port does not seem to allow widths which are not
            # a multiple of four, hence we need to adjust for this.
            width = size[0] & ~3
            height = size[1]

            # Use the default font of the window, size it reasonably.
            fontSize = min(20, max(10, min(height, width) / 10))
            font = self.GetFont()
            font.SetPointSize(fontSize)
            self._gridDebug("creating %dx%d bitmap for status '%s' ..." %
                              (width, height, status))
            result = makeVideoStatusBitmap(statusText, font,
                kStatusStartColor, kStatusEndColor, True, None,
                width, height)
            self._statusBitmaps[key] = result

        return result


    ###########################################################
    """ Control handler: zoom in. """
    def _controlZoomIn(self, event=None):
        self._zoom(-1)


    ###########################################################
    """ Control handler: zoom out. """
    def _controlZoomOut(self, event=None):
        self._zoom(1)


    ###########################################################
    """ Control handler: back (one page). """
    def _controlBack(self, event=None):
        pageStep = self._gridSizer.GetCols() * self._gridSizer.GetRows()
        self._navigate(-pageStep)


    ###########################################################
    """ Control handler: forward (one page). """
    def _controlForward(self, event=None):
        pageStep = self._gridSizer.GetCols() * self._gridSizer.GetRows()
        self._navigate(pageStep)

    ###########################################################
    def OnSize(self, event):
        """
        @see  GradientPanel.OnSize
        """
        super(GridView, self).OnSize(event)

        # Apparently we can be called one more time during a shutdown.
        if not self._isActiveView:
            return

        # If we got resized then all status bitmaps need to be rendered again,
        # we do that on demand, so just getting rid of the old ones is enough.
        self._statusBitmaps = {}

        # Synchronize and update in a locked fashion, to avoid flicker.
        self.Freeze()
        try:
            self.__sync()
            self._syncCameras()
            for _, visibleCamera in self._visibleCameras.iteritems():
                self._updateLiveViewImage(visibleCamera)
        finally:
            self.Thaw()

    ###########################################################
    def _doMouseWheel(self, deta, rotation):
        if rotation != 0:
            self._zoom(rotation/20+rotation/abs(rotation))

    ###########################################################
    def _gridDebug(self, msg):
        """ Utility method for a centralized log outlet for grid view
        """
        self._logger.debug(msg)

    ###########################################################
    def OnMouseWheel(self, event=None):
        if event is not None:
            delta = event.GetWheelDelta()
            rotation = event.GetWheelRotation()
            # Handling this event may result in destruction of the window
            # directly under the mouse cursor. Make sure it happens after the handling
            # of the event had been completed, to prevent a crash
            wx.CallAfter(self._doMouseWheel, delta, rotation)

    ###########################################################
    def _getCameraFromXY(self, x, y):
        cols = self._gridSizer.GetCols()
        rows = self._gridSizer.GetRows()
        start = self._getGridViewStart()
        width, height = self.GetClientSize()
        colWidth = width / float (cols)
        rowHeight = height / float(rows)
        col = int ( x / colWidth )
        row = int ( y / rowHeight )
        pos = start + row * cols + col
        if pos < len(self._cameraLocations):
            loc = self._cameraLocations[pos]
        else:
            loc = None
            pos = None
        self._gridDebug("x=" + str(x) + " y=" + str(y) + " col=" + str(col) + " row=" + str(row) + " loc=" + loc)
        return pos, loc

    ###########################################################
    def _getCameraFromMouseEvent(self, event):
        win = event.GetEventObject()
        winX, winY = event.GetPosition()
        scrX, scrY = win.ClientToScreen( winX, winY )
        x, y = self.ScreenToClient( scrX, scrY )
        return self._getCameraFromXY(x,y)

    ###########################################################
    def _doFullScreen(self, position, location):
        dlg = FullScreenView(self, self._backEndClient, location)
        try:
            dlg.ShowModal()
        finally:
            dlg.ShowFullScreen(False)
            dlg.Destroy()

    ###########################################################
    def OnDoubleClickFullScreen(self, event=None):
        position, location = self._getCameraFromMouseEvent(event)
        wx.CallAfter(self._doFullScreen, position, location )

    ###########################################################
    def _doShowPopup(self, pos):
        menu = self._createMenu()
        for menuId in [self._menuIdBack, self._menuIdForward,
                       self._menuIdZoomIn, self._menuIdZoomOut]:
            menu.Enable(menuId, self._controlsMenu.IsEnabled(menuId))
        self.PopupMenu(menu, pos)
        menu.Destroy()

    ###########################################################
    def OnContextMenu(self, event=None):
        """ Context menu event handler, pops up the same item structure which
        is available on the main menu, including its current enabled states.
        """
        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)

        # Some events from context menu may result in destruction of the window
        # directly under the menu. Make sure it happens after the handling
        # of the event had been completed, to prevent a crash
        wx.CallAfter(self._doShowPopup, pos)


##############################################################################
class FullScreenView(wx.Dialog):
    ###########################################################
    def __init__(self, parent, backEndClient, location):
        super(FullScreenView, self).__init__(parent, -1, "Full Screen")
        self._cameraPanel = GridView(self, backEndClient, True, [location])
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self._cameraPanel, 1, wx.EXPAND)
        self._cameraPanel.setActiveView()
        self._cameraPanel.Show(True)
        self.SetSizer(mainSizer)
        self.ShowFullScreen(True)


