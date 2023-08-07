#*****************************************************************************
#
# BaseView.py
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
import mmap
import os
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BitmapWindow import BitmapWindow
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.wx.GradientPanel import GradientPanel

# Local imports...
from appCommon.CommonStrings import kFrontEndLogName
from appCommon.CommonStrings import kLiveHeaderSize
from appCommon.DebugPrefs import getDebugPrefAsInt
from frontEnd.FrontEndUtils import getUserLocalDataDir
from vitaToolbox.image.ImageConversion import convertWxBitmapToPil
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8, ensureUnicode

# Status text, to be rendered in the (pre)views.
kStatusTextConnecting = "Connecting..."
kStatusTextCouldNotConnect = "Could not connect"
kStatusTextNoRulesScheduled = "No rules scheduled"
kStatusTextNoActiveRules = "No active rules"
kStatusTextCameraTurnedOff = "Camera turned off"

# Colors for the status screens
kStatusStartColor = (102, 153, 204)
kStatusEndColor = (51, 102, 153)

###############################################################################
class BaseView(GradientPanel):
    """Implements and defines some basic functionality for any view.
    """

    ###########################################################
    def __init__(self, parent, backEndClient, **kwargs):
        """The initializer for BaseView.

        @param  parent         The parent window.
        @param  backEndClient  A connection to the back end app.
        @param  kwargs         Extra arguments, for the gradient panel.
        """
        # Call the base class initializer
        super(BaseView, self).__init__(parent, -1, **kwargs)

        # Get the logger...
        self._logger = getLogger(kFrontEndLogName)

        # Save the passed parameters
        self._backEndClient = backEndClient

        # Track if we're the active view or not.
        self._isActiveView = False

        # Telemetery for memory map access
        self._lastMmapStatsTime = time.time()
        self._mmapStatsInterval = getDebugPrefAsInt("mmapDebug", 3600, getUserLocalDataDir() )
        self._mmapStats = {}


    ###########################################################
    def prepareToClose(self):
        """ Called if the UI is closing. An opportunity to stop activity.
        """
        pass


    ###########################################################
    def deactivateView(self):
        """ Called if the view is to be deactivated.
        """
        self._isActiveView = False


    ###########################################################
    def setActiveView(self, viewParams):
        """ Called if the view is becoming active.

        @param  viewParams  Custom view parameters.
        """
        self._isActiveView = True

    ############################################################
    def OnFocusChanged(self, event):
        """Handle focus changed events and steal focus from our children.

        We'll bind this to all of our children.

        @param  event  The focus event.
        """
        win = event.GetEventObject()

        # If someone else is getting focus that's not the main panel, steal
        # it back in a "call after".  Note that on Windows, doing this breaks
        # choice controls (it makes the choice pop down), so we'll hackily
        # try to steal focus back from them after a choice is made in the
        # function OnAnyChoice().
        if win != self:
            if wx.Platform != '__WXMSW__' or (not isinstance(win, wx.Choice)):
                wx.CallAfter(self._safeSetFocusIgnoringChildren)
        event.Skip()

    ############################################################
    def _safeSetFocusIgnoringChildren(self):
        """A safe version of SetFocusIgnoringChildren that ignores exceptions.

        The most plausable reason we might be getting an exception is if
        we have a 'dead wx object' because we've been destroyed.  This might
        happen if we started a "CallAfter", but were then destroyed before we
        actually got called.
        """
        try:
            self.SetFocusIgnoringChildren()
        except Exception:
            pass




###############################################################################
class BaseMonitorView(BaseView):
    """Implements extended functionality for monitoring cameras.
    """

    ###########################################################
    def __init__(self, parent, backEndClient, **kwargs):
        """The initializer for BaseMonitorView.

        @param  parent         The parent Window.
        @param  backEndClient  A connection to the back end app.
        @param  kwargs         Extra arguments, for the gradient panel.
        """
        # Call the base class initializer
        super(BaseMonitorView, self).__init__(parent, backEndClient, **kwargs)

        # Information for configured cameras
        self._cameraLocations = []
        self._cameraSettings = {}

        # Memory maps.
        self._mmaps = {}
        self._mmapOpenResults = {}

        # Flag to determine whether we can do OpenGL or not.
        self._bitmapMode = False


    ###########################################################
    def handleLicenseChange(self):
        """ Called if the license situation has changed and thus cameras might
        have been frozen or unfrozen, among other things.
        """
        raise NotImplementedError()


    ###########################################################
    def _openMmap(self, cameraLocation):

        # Attempt to open the mmap.
        if cameraLocation not in self._mmaps:
            fLoc = os.path.join(getUserLocalDataDir(),
                                'live', cameraLocation + '.live')
            f = open(fLoc, 'r+b')
            if f is None:
                self._logger.error("Failed to open mmap at " + ensureUtf8(fLoc))
                return False

            try:
                self._mmaps[cameraLocation] = mmap.mmap(f.fileno(), 0)
                self._mmapOpenResults[cameraLocation] = (0,0,0)
            except:
                self._logger.error("Failed to mmap file at " + ensureUtf8(fLoc))
                return False
            finally:
                f.close()

        # Once we have a mmap we are an 'open camera' once the mmap actually
        # contains valid data.
        header = str(self._mmaps[cameraLocation][:kLiveHeaderSize])
        opened = header != '\x00' * kLiveHeaderSize
        if not opened:
            # We open the file but if before valid data is placed in it the
            # CameraCapture process closes and reopens it we can be stuck
            # with a reference to the old perpetually invalid mmap file.
            # To fix this, as long as the header is empty we should continue to
            # close and reopen our mmap. No worries about being stuck in a
            # perpetual open/close loop remove operations always succeed on
            # macOS. The file will either quickly be gone or contain valid data.
            self._closeMMap(cameraLocation)

        # Report the success or failure of this attempt
        currentTime = time.time()
        failCount, lastFailTime, lastWarnTime = self._mmapOpenResults.get(cameraLocation, (0,0,0))

        # avoid logging failure message more than every 5 minutes
        if opened or currentTime - lastWarnTime > 60*5:
            self._logger.info("open mmap for location '%s' result: %s (%d)" %
                          (cameraLocation, opened, failCount))
            lastWarnTime = currentTime

        if opened:
            self._mmapOpenResults[cameraLocation] = (0,0,0)
        else:
            self._mmapOpenResults[cameraLocation] = (failCount+1, currentTime, lastWarnTime)
        return opened


    ###########################################################
    def _closeMMap(self, cameraLocation):
        """ Removes a memory map from the collection and also closes it. Does
        nothing if the location has no associated map.

        @param cameraLocation  Location for which to close the memory map.
        """
        if cameraLocation in self._mmaps:
            self._mmaps.pop(cameraLocation).close()
            self._mmapOpenResults.pop(cameraLocation)


    ###########################################################
    def _updateVideoControl(self, control, width, height, bmpData):
        """ Puts image data into a control which can handle it.

        @param  control  Either some OpenGL or a bitmap/canvas kind.
        @param  width    The width of the bitmap data.
        @param  height   The height of the bitmap data.
        @param  bmpData  Bitmap data, as received from a camera's memory map.
        """
        if width > 0 and height > 0:
            # There can be an edge case where we have a mixed bag of bitmap and
            # OpenGL controls, hence we need to make sure that we get the type
            # right.
            isBitmapWindow = isinstance(control, BitmapWindow)
            if self._bitmapMode and isBitmapWindow:
                if callable(getattr(control, 'updateImageDataRaw', None)):
                    control.updateImageDataRaw(bmpData, width, height)
                else:
                    bmp = wx.Bitmap.FromBuffer(width, height, bmpData)
                    control.updateBitmap(bmp)
            else:
                control.updateImageBuffer(bmpData, width, height)

    ###########################################################
    def _incMMapAccessStat(self, loc, item):
        if self._mmapStatsInterval is None:
            return
        key = item + "_" + loc
        self._mmapStats[key] = self._mmapStats.get(key, 0) + 1

    ###########################################################
    def _printMmapAccessStats(self):
        if self._mmapStatsInterval is None:
            return
        curTime = time.time()
        if curTime > self._lastMmapStatsTime + self._mmapStatsInterval:
            self._logger.info("mmapAccess: " + str(self._mmapStats))
            self._lastMmapStatsTime = curTime

    ###########################################################
    def _getLiveImage(self, cameraLocation, lastId=-1):
        """ Gets an image from a camera location or its memory map respectively.
        Latter must be available.

        @param  cameraLocation  The camera location from where to collect.
        @param  lastId          Last image identifier, to detect if we're still
                                dealing with the same image.
        @return res             The image data. None if nothing or nothing new
                                is available or if the memory map has signaled
                                that the camera has been turned off.
        @return width           Width of the image.
        @return height          Height of the image.
        @return id              The identifier of the image. Can be passed back
                                into the lastId argument to avoid acquiring an
                                image which we already have. If the identifier
                                is None the camera has been turned off and the
                                caller should detach from it.
        @return requestFps      Request frame rate, what we want.
        @return captureFps      Capture frame rate, what we actually got.
        """

        if not cameraLocation in self._mmaps:
            # Do not update the stats if mmap for this camera hasn't been opened
            return (None, 0, 0, -1, 0, 0)


        res = None
        width = 0
        height = 0
        id = None  # default exit is that we're done
        requestFps = 0
        captureFps = 0

        try:
            # Get the header and the bitmap data.
            mmap = self._mmaps[cameraLocation]
            header = str(mmap[:kLiveHeaderSize])
            # Notice that the bitmap data also includes the footer and the
            # slack region videolib is adding.
            bmpData = mmap[kLiveHeaderSize:]

            # An all-empty header means that videolib has closed the memory
            # map and we're done with things.
            if header != '\x00' * kLiveHeaderSize:

                # Check the ID. If it's the same as the caller has before we're
                # done already. Notice that videolib never issues a -1 or an ID.
                id = int(header[0:9])
                if id == lastId:
                    self._incMMapAccessStat(cameraLocation, "notUpdatedYet")
                    return (None, 0, 0, lastId, 0, 0)

                # Get the image dimension.
                width = int(header[9:13])
                height = int(header[13:17])
                imgSize = width * height * 3

                # Try to get to the footer data. If it doesn't exist we better
                # tell the caller to give up on this memory map right away.
                footerOfs = kLiveHeaderSize + imgSize
                footer = str(mmap[footerOfs:footerOfs + 8])
                if len(footer) != 8:
                    self._incMMapAccessStat(cameraLocation, "noFooter")
                    return (None, 0, 0, None, 0, 0)

                # We can still crash here if the footer data isn't fine, but
                # that is way less likely and can be handled as an exception.
                widthVerify = int(footer[0:4])
                heightVerify = int(footer[4:8])

                # Get the FPS counters.
                requestFps, captureFps = [float(fpsStr) \
                                          for fpsStr in header[17:].split()]

                # Check if the dimension got confirmed by the footer and also
                # that there's enough bitmap data. Better safe than sorry.
                if width > 0 and height > 0 and len(bmpData) >= imgSize and \
                    widthVerify == width and heightVerify == height:
                    res = bmpData
                    self._incMMapAccessStat(cameraLocation, "gotFrame")
                else:
                    # If we don't have good data now it's considered a premature
                    # situation or glitch and we'll tell the caller to try
                    # again.
                    id = lastId
                    self._incMMapAccessStat(cameraLocation, "headerMismatch")

        except:
            # This rare case can happen if we just hit things being written in
            # the middle, so we just ask the caller to repeat its action.
            self._incMMapAccessStat(cameraLocation, "exception")
            id = lastId

        self._printMmapAccessStats()

        return (res, width, height, id, requestFps, captureFps)

##############################################################################
def _splitLines(gc, maxWidth, text):
    lines = text.split("\n")

    newLines = []
    for line in lines:
        textWidth, _ = gc.GetTextExtent(line)
        if maxWidth <= textWidth:
            words = line.split(" ")
            newLine = ""
            for word in words:
                newLineWidth, _ = gc.GetTextExtent(newLine+word)
                if newLineWidth < maxWidth or newLine == "":
                    # With the addition of this word we still fit
                    # (or the word is too long, but we don't care then)
                    newLine = newLine + word + " "
                else:
                    # This word puts the line over, create a new line
                    newLines.append(newLine)
                    newLine = word + " "
            if newLine != "":
                newLines.append(newLine)
        else:
            newLines.append(line)
    return newLines


##############################################################################
def makeVideoStatusBitmap(statusText, font, startColor, endColor,
                          needPil, icon, width, height):
    """Make a wx.Bitmap to show camera status.

    @param  statusText  The text to display.
    @param  font        The font to use.
    @param  startColor  Start color for gradient.
    @param  endColor    End color for gradient.
    @param  icon        An wx.Bitmap to show in the status window.
    @param  width       The width to make the window.
    @param  height      The height to make the window.
    @return bmp         An image to show when we have an error, as a wx.Bitmap.
    """
    # TODO: Seems like it would be safer to use DC completely, since it can
    # do gradients and XP has some weird issues with drawing text on
    # GraphicsContexts...

    bmp = wx.Bitmap.FromRGBA(width, height)
    memDC = wx.MemoryDC()
    memDC.SelectObject(bmp)
    gc = wx.GraphicsContext.Create(memDC)
    gradientBrush = gc.CreateLinearGradientBrush(width, height, 0, 0,
                                                 startColor, endColor)
    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.SetBrush(gradientBrush)
    gc.DrawRectangle(0, 0, width, height)
    gc.SetFont(font, wx.WHITE)

    kSpace = 5
    lines = _splitLines(gc, width, statusText)
    linesCount = len(lines)

    # Determine total required height of the text
    _, textHeight = gc.GetTextExtent(statusText)
    totalHeight = linesCount*textHeight + (linesCount-1)*kSpace
    if icon is not None:
        totalHeight += icon.GetHeight() + kSpace

    # Determine the top position
    top = kSpace if totalHeight > height else (height - totalHeight) / 2
    offset = top

    # Draw icon at the top, if appicable
    if icon is not None:
        iconW = icon.GetWidth()
        iconH = icon.GetHeight()
        gc.DrawBitmap(icon, width / 2 - iconW / 2, offset, iconW, iconH)
        offset += iconH + kSpace

    for line in lines:
        textWidth, textHeight = gc.GetTextExtent(line)
        gc.DrawText(line, width / 2 - textWidth / 2, offset)
        offset += textHeight + kSpace

    memDC.SelectObject(wx.NullBitmap)

    if needPil:
        return convertWxBitmapToPil(bmp)

    return bmp
