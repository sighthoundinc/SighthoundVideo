#!/usr/bin/env python

#*****************************************************************************
#
# VideoWindow.py
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
import math
import os.path
import sys

# Common 3rd-party imports...
from   PIL import Image
import wx
from   wx.lib.docview import Command as wxCommand
from   wx.lib.docview import CommandProcessor as CommandProcessorWithExtras

# Toolbox imports...
from vitaToolbox.image.ImageConversion import convertPilToWxBitmap

from vitaToolbox.math.LineSegment import LineSegment
from vitaToolbox.wx.DoubleBufferCompatGc import createDoubleBufferCompatGc
from vitaToolbox.wx.CreateMenuFromData import createMenuFromData

# Local imports...
from backEnd.triggers.TriggerLineSegment import TriggerLineSegment
from backEnd.triggers.TriggerRegion import TriggerRegion


# Constants

# A non-editable region will have an outer pen that's this wide...
_kNormalRegionPenWidth = 1

# An editable region will have an outer pen that's this wide...
_kEditRegionPenWidth = 3

# These are the border and fill colors for a region...
_kRegionTriggerPenColor = (0, 0, 0, 153)
_kRegionTriggerBrushColor = (255, 255, 255, 127)

# The phantom point on a region has these colors...
_kPhantomPointBrushColor = (0xBB, 0xBB, 0xBB, 0xFF)
_kPhantomPointPenColor = (0x63, 0x63, 0x63, 0xFF)

# Line triggers look like this; currently there's no difference between
# edit and non-edit mode...
_kLineTriggerPenWidth = 1
_kLineTriggerSlopDist = 9
_kLineTriggerPenColor = (0xEE, 0xEE, 0, 0xEE)

# Edit circles are this big; they're always black border and white fill for
# now, though that could change in the future...
_kEditCircleRadius = 4
_kEditCircleSloppyRadius = 9
_kEditCirclePreventPhantomRadius = 18

# We need to be this close to a line to show a phantom if we're inside a
# region...
_kPhantomSlopIfInsideRegion = 2.0

# Any mouse movement must be this many pixels before we start tracking.
_kMinMovement = 2

# Default coordinate space of the video window. This can change in the future if
# the video window is ever allowed to scale in the GUI.
_defaultCoordSpace = (320, 240)




# Given three colinear points p, q, r,
# the function checks if point q lies
# on line segment 'pr'
def onSegment(p, q, r):

    if ((q[0] <= max(p[0], r[0])) &
        (q[0] >= min(p[0], r[0])) &
        (q[1] <= max(p[1], r[1])) &
        (q[1] >= min(p[1], r[1]))):
        return True

    return False

# To find orientation of ordered triplet (p, q, r).
# The function returns following values
# 0 --> p, q and r are colinear
# 1 --> Clockwise
# 2 --> Counterclockwise
def orientation(p, q, r):

    val = (((q[1] - p[1]) *
            (r[0] - q[0])) -
        ((q[0] - p[0]) *
            (r[1] - q[1])))

    if val == 0:
        return 0
    if val > 0:
        return 1 # Collinear
    else:
        return 2 # Clock or counterclock

def doIntersect(p1, q1, p2, q2):

    # Find the four orientations needed for
    # general and special cases
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)

    # General case
    if (o1 != o2) and (o3 != o4):
        return True

    # Special Cases
    # p1, q1 and p2 are colinear and
    # p2 lies on segment p1q1
    if (o1 == 0) and (onSegment(p1, p2, q1)):
        return True

    # p1, q1 and p2 are colinear and
    # q2 lies on segment p1q1
    if (o2 == 0) and (onSegment(p1, q2, q1)):
        return True

    # p2, q2 and p1 are colinear and
    # p1 lies on segment p2q2
    if (o3 == 0) and (onSegment(p2, p1, q2)):
        return True

    # p2, q2 and q1 are colinear and
    # q1 lies on segment p2q2
    if (o4 == 0) and (onSegment(p2, q1, q2)):
        return True

    return False

# Returns true if the point p lies
# inside the polygon[] with n vertices
def is_inside_polygon(points, p):
    kIntMax = 1000000
    n = len(points)

    # There must be at least 3 vertices
    # in polygon
    if n < 3:
        return False

    # Create a point for line segment
    # from p to infinite
    extreme = (kIntMax, p[1])
    count = i = 0

    while True:
        next = (i + 1) % n

        # Check if the line segment from 'p' to
        # 'extreme' intersects with the line
        # segment from 'polygon[i]' to 'polygon[next]'
        if (doIntersect(points[i],
                        points[next],
                        p, extreme)):

            # If the point 'p' is colinear with line
            # segment 'i-next', then check if it lies
            # on segment. If it lies, return true, otherwise false
            if orientation(points[i], p,
                        points[next]) == 0:
                return onSegment(points[i], p,
                                points[next])

            count += 1

        i = next

        if (i == 0):
            break

    # Return true if count is odd, false otherwise
    return (count % 2 == 1)



##############################################################################
class VideoWindow(wx.Control):
    """A wx.Window for displaying / marking up video frames.

    This Window was initially created based on PilImageWindow.  We don't use
    PilImageWindow because:
    (*) PilImageWindow is a little bit too generic for our needs here--we don't
        need all of its functionality--we'd rather have speed and have it be
        easier to add our own features.
    (*) PilImageWindow was used by lots of dev apps, so it would have been more
        of a pain to change its interface.

    TODO:
    - I have the concept of "Edit mode" in this code a bunch, but it's not
      really flushed out, since I'm not sure where we'll use it yet.
    - You can add lots of regions and lines at once.  This also isn't used
      yet, but could be in the future.

    NOTES:
    - We currently, the image never scales at all.
    """

    ###########################################################
    def __init__(self, parent,
                 pos=wx.DefaultPosition, size=wx.DefaultSize):
        """VideoWindow constructor.

        @param  parent  Our parent UI object.
        @param  pos     The position to put us at.
        @param  size    Our size.
        """
        # Initialize this early, since we access in destructor...
        self._popupMenu = None

        # Call our super...
        super(VideoWindow, self).__init__(
            parent, -1, pos, size, style=wx.NO_BORDER
        )

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        # The coordinate space of the loaded image.
        self._coordSpace = _defaultCoordSpace

        # We keep track of the original image set by the user, plus bmp version.
        self._origImage = None
        self._origBitmap = None

        # An overlay image that the user can set...
        self._overlayImage = None
        self._overlayBitmap = None

        # This will be a list of different regions to highlight.  Each element
        # in the list is a TriggerRegion.  They should be listed clockwise.
        self._triggerRegions = []

        # This is parallel to self._triggerRegions & is used to unregister
        # for their updates...
        self._triggerRegionRegFns = []

        # Like for regions, for for trigger lines...
        self._triggerLineSegments = []
        self._triggerLineSegmentRegFns = []


        # If True, all lines and regions can be edited...
        self._isInEditMode = True


        # Used during mouse tracking...

        # ...the point that the mouse was clicked on...
        self._mouseDownPt = None
        self._sawMouseMove = False

        # The region/line segment that matched a pen down...
        self._mouseDownObject = None

        # The index of the point in _mouseDownObject, or None.
        self._mouseDownObjectPtIndex = None

        # If we're mousing near a line in a region, we'll draw a phantom point
        # to allow the user to add more points...
        self._phantomPoint = None
        self._phantomPointRegion = None
        self._phantomPointIndex = None

        # When right-clicking, we keep track of which object/point we clicked
        # on so we can delete the point...
        self._deletePointObject = None
        self._deletePointPointIndex = None

        # Make our popup menu; note accelerators won't "just happen" for
        # this menu--we have to manually add them to our accelerator table.
        # ...also note that the accelerator table ignores whether these menu
        # items are enabled / disabled...
        self._deletePointId = wx.NewId()
        menuData = (
            ("&Undo\tCtrl+Z", "", wx.ID_UNDO, self.OnAccelerator),
            ("&Redo\tCtrl+Y", "", wx.ID_REDO, self.OnAccelerator),
            (None, None, None, None),
            ("Rese&t To Default", "", wx.ID_ANY, self.OnReset),
            (None, None, None, None),
            ("&Delete Point", "", self._deletePointId,
             lambda _: self._deletePointInRegion(self._deletePointObject,
                                                 self._deletePointPointIndex)),
        )
        self._popupMenu = createMenuFromData(menuData, self)


        # We will use this to store commands for undoing / redoing...
        self._cmdProcessor = CommandProcessorWithExtras()
        self._cmdProcessor.SetEditMenu(self._popupMenu)

        # Save away cursors...
        self._moveItemCursor = self._makeCursor("Move_Item_Cursor.png")
        self._movePointCursor = wx.Cursor(wx.CURSOR_HAND)

        # We need to be able to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # We need to handle all the mouse stuff...
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)

        # Register for context menu event (usually right-click)...
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)

        # Make escape cancel dragging. This is needed to prevent crashing in
        # Mac where escaping will close the window before handling resources
        # from dragging...
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyUp)

        # Add undo and redo to accelerator table...
        redoAccelEntry = wx.GetAccelFromString("\t" + self._cmdProcessor.GetRedoAccelerator())
        redoFlags = redoAccelEntry.GetFlags()
        redoKeyCode = redoAccelEntry.GetKeyCode()
        undoAccelEntry = wx.GetAccelFromString("\t" + self._cmdProcessor.GetUndoAccelerator())
        undoFlags = undoAccelEntry.GetFlags()
        undoKeyCode = undoAccelEntry.GetKeyCode()
        accelTable = wx.AcceleratorTable([
            (undoFlags, undoKeyCode, wx.ID_UNDO),
            (redoFlags, redoKeyCode, wx.ID_REDO),
        ])
        self.SetAcceleratorTable(accelTable)
        self.Bind(wx.EVT_MENU, self.OnAccelerator)

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    ###########################################################
    def OnDestroy(self, event=None):
        """ Explicitly release mouse capture, if needed
        """
        if self.HasCapture():
            self.ReleaseMouse()

    ###########################################################
    def __del__(self):
        """VideoWindow destructor."""
        if self._popupMenu is not None:
            self._popupMenu.Destroy()
            self._popupMenu = None

    ###########################################################
    def setImage(self, image):
        """Update the actual image.

        @param  image       A Python Imaging Library image.
        @param  coordSpace  The coordinate space that the VideoWindow should
                            draw its objects in. If None, it will use the
                            coordinate space of the image it is given.
        """
        # Keep a clean copy of the original image...
        self._origImage = image

        # Make the bitmap now to make paint faster...
        self._origBitmap = convertPilToWxBitmap(image)

        # Our coordinate space is equivalent to the image size.
        self._coordSpace = self._origImage.size

        # Refresh ourselves...
        self.Refresh()


    ###########################################################
    def setOverlayImage(self, image):
        """Set an image to show on top of everything else.

        @param  image  The overlay image.
        """
        if image != self._overlayImage:
            # Keep a clean copy of the original image...
            self._overlayImage = image

            # Make the bitmap now to make paint faster...
            if image is not None:
                self._overlayBitmap = convertPilToWxBitmap(image)
            else:
                self._overlayBitmap = None

            # Refresh ourselves...
            self.Refresh()


    ###########################################################
    def setTriggerRegions(self, newTriggerRegions):
        """Set a new list of trigger regions.

        @param  newTriggerRegions  A list of regions to highlight.  Each
                                   is a TriggerRegion object.
        """
        # Avoid clearing undo history if nothing changes...
        if newTriggerRegions == self._triggerRegions:
            return

        # Unregister for any old updates...
        for triggerRegion, fn in zip(self._triggerRegions,
                                     self._triggerRegionRegFns):
            triggerRegion.removeListener(fn)

        # Set the new regions, then register...
        self._triggerRegions = newTriggerRegions
        self._triggerRegionRegFns = \
            [triggerRegion.addListener(self._handleTriggerUpdate)
             for triggerRegion in self._triggerRegions]

        # Clear any undo/redo info...
        self._cmdProcessor.ClearCommands()

        self.Refresh()


    ###########################################################
    def setTriggerLineSegments(self, newTriggerLineSegments):
        """Set a new list of trigger line segments.

        @param  newTriggerLineSegments  A list of TriggerLineSegment objects.
        """
        # Avoid clearing undo history if nothing changes...
        if newTriggerLineSegments == self._triggerLineSegments:
            return

        # Unregister for any old updates...
        for triggerLineSegment, fn in zip(self._triggerLineSegments,
                                          self._triggerLineSegmentRegFns):
            triggerLineSegment.removeListener(fn)

        # Set the new line segments, then register...
        self._triggerLineSegments = newTriggerLineSegments
        self._triggerLineSegmentRegFns = \
            [triggerLineSegment.addListener(self._handleTriggerUpdate)
             for triggerLineSegment in self._triggerLineSegments]

        # Clear any undo/redo info...
        self._cmdProcessor.ClearCommands()

        self.Refresh()


    ###########################################################
    def getCommandProcessor(self):
        """Return the command processor associated with this window.

        Our frame calls this to perform Undo/Redo.

        @return commandProcessor  Our command processor.
        """
        return self._cmdProcessor


    ############################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Implement DoGetBestSize() to properly apply our bestSize.

        Our best size is always the size of our image.  If we don't have one,
        we call our super.

        @return  bestSize  The best size for us.
        """
        if self._origImage:
            return self._origImage.size
        else:
            return super(VideoWindow, self).GetBestSize()


    ###########################################################
    def OnReset(self, event):
        """Reset our region/line trigger to defaults.

        Actually just resets the first region or line trigger to defaults,
        which is what we'd expect since we currently only have one line
        or region...  If we need more than one, I guess we'd want to use
        the same region that we found for deletion (_deletePointObject).

        @param  event  The menu event.
        """
        width, height = self._origImage.size

        if self._triggerRegions:
            defaultPoints = [(int(width/4),       int(height/4)),
                             (int((3 * width)/4), int(height/4)),
                             (int((3 * width)/4), int((3 * height)/4)),
                             (int(width/4),       int((3 * height)/4))]

            cmd = _SetPointsInTriggerCommand(self._triggerRegions[0],
                                             defaultPoints, "Reset", self._coordSpace)
            self._cmdProcessor.Submit(cmd)
        elif self._triggerLineSegments:
            defaultPoints = [(int(width/2), int(height/4)),
                             (int(width/2), int((3 * height)/4))]

            cmd = _SetPointsInTriggerCommand(self._triggerLineSegments[0],
                                             defaultPoints, "Reset", self._coordSpace)
            self._cmdProcessor.Submit(cmd)


    ###########################################################
    def OnMouseDown(self, event):
        """Handle mouse down on ourselves.

        @param  event  The event; may be a mouse down or a double-click event.
        """
        # Always take focus...
        self.SetFocus()

        # Bail if we're not editable.  TODO: Should this be trigger-by-trigger?
        if not self._isInEditMode:
            return

        triggerObject, ptIndex = (None, None)

        # Clicking while a phantom point is showing adds that point, then
        # starts dragging with it...
        if self._phantomPoint is not None:
            newPoints = self._phantomPointRegion.getPoints()
            newPoints.insert(self._phantomPointIndex, self._phantomPoint)
            cmd = _SetPointsInTriggerCommand(self._phantomPointRegion,
                                             newPoints, "Add Point", self._coordSpace)
            self._cmdProcessor.Submit(cmd)

            triggerObject = self._phantomPointRegion
            ptIndex = self._phantomPointIndex

        x, y = (event.X, event.Y)

        # Init everything...
        self._sawMouseMove = False
        self._mouseDownPt = (x, y)
        self._mouseDownObject = None
        self._mouseDownObjectPtIndex = None


        # Try first to find an edit point, unless we already have one from the
        # phantom point code.  If we find one, capture and we're done...
        if triggerObject is None:
            triggerObject, ptIndex = self._findTriggerObjectEditPoint(x, y)
        if triggerObject is not None:
            assert ptIndex is not None
            self._mouseDownObject = triggerObject
            self._mouseDownObjectPtIndex = ptIndex
            self.CaptureMouse()
            return

        # Second, try to find a line...
        lineSegment = self._findLineSegment(x, y)
        if lineSegment is not None:
            self._mouseDownObject = lineSegment
            self.CaptureMouse()
            return

        # Finally, try a region...
        region = self._findRegion(x, y)
        if region is not None:
            self._mouseDownObject = region
            self.CaptureMouse()
            return

        event.Skip()


    ###########################################################
    def OnMouseMove(self, event):
        """Handle mouse move on the window.

        @param  event  The event; may be a move event, a mouse up event, or
                       even a double-click event.
        """
        # Bail if we're not editable.  TODO: Should this be object-by-object?
        if not self._isInEditMode:
            event.Skip()
            return

        # Clear our any extra point, and mark us for refresh...
        if self._phantomPoint is not None:
            self._phantomPoint = None
            self.Refresh()

        x, y = event.X, event.Y

        if self.HasCapture():
            # If the user is dragging the mouse, update our objects
            width, height = self._origImage.size

            # Figure out how much we've moved; if enough, record that this
            # wasn't just a click...
            origX, origY = self._mouseDownPt
            dx, dy = (x - origX, y - origY)
            if abs(dx) > _kMinMovement or abs(dy) > _kMinMovement:
                self._sawMouseMove = True

            # If the mouse has moved enough, process the drag...
            if self._sawMouseMove:
                triggerObject = self._mouseDownObject
                if triggerObject is not None:
                    ptIndex = self._mouseDownObjectPtIndex
                    if ptIndex is not None:
                        # Move just one point; keep in bounds...
                        x = min(max(x, 0), width-1)
                        y = min(max(y, 0), height-1)
                        triggerObject.proposePointChange(ptIndex, x, y, self._coordSpace)
                    else:
                        # Move the whole trigger...
                        triggerObject.proposeOffset(dx, dy, width, height, self._coordSpace)
        else:
            # If we have an object but we don't have capture, we somehow lost
            # capture; force mouse up processing...
            if self._mouseDownObject is not None:
                self.OnMouseUp(event)

            # The user's just mousing over things.  Put "phantom points" to
            # allow the user to add more points to the region.
            didPlace = self._tryToPlacePhantomPoint(x, y)

            # Adjust the cursor...
            self._adjustCursor(x, y, didPlace)

        event.Skip()


    ###########################################################
    def _adjustCursor(self, x, y, didPlacePhantom):
        """Adjust the cursor.

        @param  x                The x loc of the mouse.
        @param  y                The y loc of the mouse.
        @param  didPlacePhantom  An optimization--if we know we placed a phantom
                                 point, we'll draw the right cursor for it.
        """
        if didPlacePhantom:
            self.SetCursor(self._movePointCursor)
            return

        triggerObject, _ = self._findTriggerObjectEditPoint(x, y)
        if triggerObject is not None:
            self.SetCursor(self._movePointCursor)
            return

        lineSegment = self._findLineSegment(x, y)
        if lineSegment is not None:
            self.SetCursor(self._moveItemCursor)
            return

        region = self._findRegion(x, y)
        if region is not None:
            self.SetCursor(self._moveItemCursor)
            return

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    ###########################################################
    def _makeCursor(self, cursorFilePath):
        """Make a cursor from the given png file.

        @param  cursorFilePath  The name of the .png file.
        """
        img = wx.Image(os.path.join('frontEnd', 'bmps', cursorFilePath))
        img.ConvertAlphaToMask()
        img.SetOption(wx.IMAGE_OPTION_CUR_HOTSPOT_X, img.GetWidth()/2)
        img.SetOption(wx.IMAGE_OPTION_CUR_HOTSPOT_Y, img.GetHeight()/2)
        return wx.Cursor(img)


    ###########################################################
    def OnMouseUp(self, event):
        """Handle mouse up on the window.

        @param  event  The event; may be a mouse up or a double-click event.
        """
        # When deciding whether we've been editing, check for _mouseDownObject
        # rather than capture, since (on the Mac at least), right-clicking
        # while dragging seems to take away capture without telling us.  This
        # way, we'll detect the mouse up, at least...
        if self._mouseDownObject:
            # Do one more move, then release if we really still have capture.
            if self.HasCapture():
                self.OnMouseMove(event)
                self.ReleaseMouse()

            triggerObject = self._mouseDownObject
            self._mouseDownObject = None

            if self._sawMouseMove:
                if triggerObject is not None:
                    ptIndex = self._mouseDownObjectPtIndex
                    if ptIndex is not None:
                        cmd = _SetPointsInTriggerCommand(triggerObject, None,
                                                         "Move Point", self._coordSpace)
                    else:
                        if isinstance(triggerObject, TriggerLineSegment):
                            triggerType = "Boundary"
                        else:
                            triggerType = "Region"
                        cmd = _SetPointsInTriggerCommand(triggerObject, None,
                                                        "Move %s" % triggerType, self._coordSpace)

                    self._cmdProcessor.Submit(cmd)
            else:
                # A simple "click" on the object, which actually does something
                # in the case of a line segment.
                if (self._mouseDownObjectPtIndex is None) and \
                   isinstance(triggerObject, TriggerLineSegment):
                    self.changeLineTriggerDirection(triggerObject)

            # Reject any proposals that we might have made, now that we've
            # released the pen...
            triggerObject.rejectProposal()


    ###########################################################
    def OnDoubleClick(self, event):
        """Handle a double click.

        We just treat this as a mouse down and mouse up.  Why?  This way if
        a user just sits there clicking on the arrow, it will keep cycling
        directions.

        @param  event  The double-click event.
        """
        self.OnMouseDown(event)
        self.OnMouseUp(event)


    ###########################################################
    def OnLeaveWindow(self, event):
        """Handle mouse leaving the window, so we can delete phantom point.

        @param  event  The event.
        """
        # Clear our any extra point, and mark us for refresh...
        if self._phantomPoint is not None:
            self._phantomPoint = None
            self.Refresh()


    ###########################################################
    def OnShowPopup(self, event):
        """Show a popup menu...

        @param  event  The context menu event.
        """
        # No popup menu if no region and no line segments...
        if not (self._triggerRegions or self._triggerLineSegments):
            event.Skip()
            return

        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)

        # Figure out whether delete point is enabled, which only happens
        # if the mouse is over a valid point...
        x, y = pos
        triggerObject, ptIndex = self._findTriggerObjectEditPoint(x, y)
        canDelete = (triggerObject is not None) and \
                    (len(triggerObject.getPoints()) > 3)
        self._popupMenu.Enable(self._deletePointId, canDelete)

        # Save these so that the popup menu knows what to delete...
        self._deletePointObject = triggerObject
        self._deletePointPointIndex = ptIndex

        # Popup the menu...
        self.PopupMenu(self._popupMenu)


    ###########################################################
    def OnKeyUp(self, event):
        """Handle key-up event.

        ... really, we're just handling an "escape" key-up event. We need to do
        this so that escaping a window in Mac doesn't cause a crash from not
        handling our resources from dragging first. In other words, catch the
        escape key-up event, cancel our dragging by forcing a fake mouse-down
        event, and then continue as normal.

        @param event:  The key-up event.
        """
        keyCode = event.GetKeyCode()

        if keyCode == wx.WXK_ESCAPE:

            # Get the current mouse coordinates in terms of ourselves...
            mouseX, mouseY = self.ScreenToClient(wx.GetMousePosition())

            # Create a fake mouse event with those coordinates.
            class FakeMouseEvent(object):
                pass
            fakeMouseEvent = FakeMouseEvent()
            fakeMouseEvent.X = mouseX
            fakeMouseEvent.Y = mouseY
            fakeMouseEvent.Skip = lambda *args, **kwargs: None

            # Force a mouse-up event to cancel dragging. It's okay to just call
            # this our OnMouseUp method, since it checks if we're currently
            # dragging or not.
            self.OnMouseUp(fakeMouseEvent)

        # Allow other panels or windows to process the key-up event...
        event.Skip()


    ###########################################################
    def OnAccelerator(self, event):
        """Handle undo and redo accelerator events.

        @param  event  The menu event.
        """
        menuId = event.GetId()
        didHandle = False

        if menuId == wx.ID_UNDO:
            didHandle = self._cmdProcessor.Undo()
        elif menuId == wx.ID_REDO:
            didHandle = self._cmdProcessor.Redo()

        if not didHandle:
            event.Skip()


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)
        dc.SetBackground(wx.BLACK_BRUSH)
        dc.Clear()

        gc, finishFn = createDoubleBufferCompatGc(dc)

        # Make a wx.Image from the PIL image...
        # ...TODO: Any more efficient way?
        imageWidth, imageHeight = self._origBitmap.GetSize()

        # Draw the image...
        gc.DrawBitmap(self._origBitmap, 0, 0, imageWidth, imageHeight)

        # Draw all of the regions...
        for triggerRegion in self._triggerRegions:
            self._drawRegion(triggerRegion, gc)

        for triggerLineSegment in self._triggerLineSegments:
            self._drawLineSegment(triggerLineSegment, gc)

        # Draw the overlay, if there is one...
        if self._overlayBitmap is not None:
            overlayWidth, overlayHeight = self._overlayBitmap.GetSize()
            gc.DrawBitmap(self._overlayBitmap,
                          (imageWidth-overlayWidth)/2,
                          (imageHeight-overlayHeight)/2,
                          overlayWidth, overlayHeight)

        finishFn()


    ###########################################################
    def _handleTriggerUpdate(self, triggerObject):
        """Handle changes to one of our trigger regions / line segments.

        @param  triggerObject  The trigger region that changed.
        """
        _ = triggerObject

        # Delete phantom points...
        if self._phantomPoint is not None:
            self._phantomPoint = None

        # Just refresh ourselves...
        self.Refresh()


    ###########################################################
    def _findTriggerObjectEditPoint(self, x, y,
                                    sloppyRadius=_kEditCircleSloppyRadius):
        """Try to find an edit point in a region/line seg for the given x and y.

        This will look first for a dead-on hit, then will look for a sloppy
        hit.

        @param  x              The x of the click.
        @param  y              The y of the click.
        @param  sloppyRadius   The sloppy radius needed.
        @return triggerObject  The region/line segment that was found; or None
                               if none found.
        @return ptIndex        The index of the matching point in the object;
                               or None.
        """
        normalRadiusSq = _kEditCircleRadius * _kEditCircleRadius
        sloppyRadiusSq = sloppyRadius * sloppyRadius

        # Trigger objects are all regions and line segments.  This list is
        # the order in which they are drawn.
        triggerObjects = self._triggerRegions + self._triggerLineSegments

        # Note: we work in reverse so that we pick the point that was drawn
        # "higher" (AKA last) first.  Only do this for exact matches, since
        # those are the only ones that have a real z-ordering (it's obvious
        # which is on "top"...
        for triggerObject in reversed(triggerObjects):
            points = triggerObject.getPoints(self._coordSpace)
            for i, (ptX, ptY) in reversed(list(enumerate(points))):
                dx = (ptX - x)
                dy = (ptY - y)
                if (dx * dx) + (dy * dy) <= normalRadiusSq:
                    return (triggerObject, i)

        # Now look for the best sloppy radius...  Just get point that's
        # closest.
        bestTriggerObject = None
        bestI = None
        bestRadiusSq = sloppyRadiusSq
        for triggerObject in triggerObjects:
            points = triggerObject.getPoints(self._coordSpace)
            for i, (ptX, ptY) in enumerate(points):
                dx = (ptX - x)
                dy = (ptY - y)
                radiusSq = (dx * dx) + (dy * dy)
                if radiusSq <= bestRadiusSq:
                    bestRadiusSq = radiusSq
                    bestTriggerObject = triggerObject
                    bestI = i

        return (bestTriggerObject, bestI)


    ###########################################################
    def _findLineSegment(self, x, y):
        """Try to find a line segment that contains the given x and y.

        @param  x            The x of the click.
        @param  y            The y of the click.
        @return lineSegment  The line segment that the click landed on.
        """
        bestDist = _kLineTriggerSlopDist
        bestTriggerLineSegment = None

        for triggerLineSegment in self._triggerLineSegments:
            # Check for points close to the line segment first...
            lineSegment = triggerLineSegment.getLineSegment(self._coordSpace)
            closestX, closestY, dist = lineSegment.getClosestPtTo(x, y)
            if dist <= bestDist:
                bestTriggerLineSegment = triggerLineSegment
                bestDist = dist

            # Also check to see if they clicked on the actual bitmap...
            rotBmp, rotBmpX, rotBmpY = \
                self._getLineSegmentBitmap(triggerLineSegment)
            bmpRegion = wx.Region(rotBmp, wx.BLACK)
            bmpRegion.Offset(rotBmpX, rotBmpY)
            if bmpRegion.Contains(x, y):
                bestTriggerLineSegment = triggerLineSegment
                bestDist = 0

        return bestTriggerLineSegment


    ###########################################################
    def _findRegion(self, x, y):
        """Try to find a region that contains the given x and y.

        No slop is allowed here (mostly because it would be hard to compute).

        @param  x        The x of the click.
        @param  y        The y of the click.
        @return region   The region that the click landed on.
        """
        for triggerRegion in reversed(self._triggerRegions):
            points = triggerRegion.getPoints(self._coordSpace)
            if is_inside_polygon(points, (x, y)):
                return triggerRegion

        return None


    ###########################################################
    def _tryToPlacePhantomPoint(self, x, y):
        """Place a phantom point, if we're close enough to any region edges.

        This is called by "mouse move" if the mouse isn't down.

        @param  x         The x of the mouse move.
        @param  y         The y of the mouse move.
        @return didPlace  True if we placed a point; False otherwise.
        """
        # Don't add the phantom point if there's an edit point close.
        triggerObject, _ = self._findTriggerObjectEditPoint(x, y,
                                               _kEditCirclePreventPhantomRadius)
        if triggerObject is not None:
            return False

        # Don't add the phantom point if we're on top of a line segment.
        triggerObject = self._findLineSegment(x, y)
        if triggerObject is not None:
            return False

        # Normally, we'll show phantom points for the line closest to us,
        # assuming that it's somewhat close...
        bestDist = _kEditCircleSloppyRadius - 1

        # ...but if we're on top of a region, require it to be _really_ close.
        triggerObject = self._findRegion(x, y)
        if triggerObject is not None:
            bestDist = _kPhantomSlopIfInsideRegion

        # Try to find a line closeby to add the phantom point to.  The line
        # must be closer than _kEditCircleSloppyRadius pixels.
        for triggerRegion in self._triggerRegions:
            points = triggerRegion.getPoints(self._coordSpace)
            numPoints = len(points)
            for i in xrange(numPoints):
                x1, y1 = points[i-1]
                x2, y2 = points[i]
                lineSeg = LineSegment(x1, y1, x2, y2)
                closestX, closestY, dist = lineSeg.getClosestPtTo(x, y)
                closestX = int(round(closestX))
                closestY = int(round(closestY))
                if dist <= bestDist:
                    bestDist = dist
                    # We have a new best place for the phantom point...
                    self._phantomPoint = (closestX, closestY)
                    self._phantomPointRegion = triggerRegion
                    self._phantomPointIndex = i

        if self._phantomPoint is not None:
            self.Refresh()
            return True
        return False


    ###########################################################
    def _drawRegion(self, triggerRegion, gc):
        """Draw the given region on the given GraphicsContext.

        @param  triggerRegion  The trigger region to draw.
        @param  gc             The graphics context
        """
        points = triggerRegion.getProposedPoints(self._coordSpace)

        # Bail if no points
        if not points:
            return

        # Decide whether we're in edit mode.  TODO: Should this be on a
        # region-by-region basis?  Depends on how we use the region...
        isInEditMode = self._isInEditMode

        # Draw the actual region, which we do by using the "path" concept in wx.
        gc.PushState()

        if isInEditMode:
            penWidth = _kEditRegionPenWidth
        else:
            penWidth = _kNormalRegionPenWidth

        gc.SetPen(wx.Pen(_kRegionTriggerPenColor, penWidth))
        gc.SetBrush(wx.Brush(_kRegionTriggerBrushColor))

        # DrawLines draws the region just like we'd expect, but we need to
        # make sure we end where we started...
        gc.DrawLines(points + points[:1])

        gc.PopState()

        # Draw the dots around, if in edit mode...
        if isInEditMode:
            gc.PushState()

            #font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            #gc.SetFont(font)

            gc.SetPen(wx.BLACK_PEN)
            gc.SetBrush(wx.WHITE_BRUSH)
            for i, (x, y) in enumerate(points):
                self._drawEditCircle(gc, x, y)
                #gc.DrawText("%d: (%d, %d)" % (i, x, y), x, y)
            if self._phantomPoint:
                gc.SetPen(wx.Pen(_kPhantomPointPenColor))
                gc.SetBrush(wx.Brush(_kPhantomPointBrushColor))
                x, y = self._phantomPoint
                self._drawEditCircle(gc, x, y)

            gc.PopState()


    ###########################################################
    def _drawEditCircle(self, gc, x, y):
        """Draw an "edit circle" at the given point.

        This is the circle showing that the point can be dragged.

        @param  x  The x coord.
        @param  y  The y coord.
        """
        gc.DrawEllipse(x-_kEditCircleRadius, y-_kEditCircleRadius,
                       2*_kEditCircleRadius, 2*_kEditCircleRadius)


    ###########################################################
    def _getLineSegmentBitmap(self, triggerLineSegment):
        """Return the bitmap to draw on a given line segment, and where.

        @param  triggerLineSegment  The trigger line segment to draw.
        @return bmp                 The rotated bitmap to draw on the line seg.
        @return x                   The x location to draw the bitmap at.
        @return y                   The y location to draw the bitmap at.
        """
        ((x1, y1), (x2, y2)) = triggerLineSegment.getProposedPoints(self._coordSpace)
        dirStr = triggerLineSegment.getDirection()

        dx = x2 - x1
        dy = y2 - y1
        angle = math.atan2(dx, dy)

        # TODO: Not sure this is all right, or whether we'll even continue
        # to use a bitmap for all of this...
        if dirStr == 'right':
            image = wx.Image("frontEnd/bmps/Direction_Left.png")
        elif dirStr == 'left':
            image = wx.Image("frontEnd/bmps/Direction_Left.png")
            angle = math.atan2(-dx, -dy)
        else:
            assert dirStr == 'any'
            image = wx.Image("frontEnd/bmps/Direction_Both.png")

        imageWidth, imageHeight = image.GetWidth(), image.GetHeight()
        rotImage = image.Rotate(angle, (imageWidth/2, imageHeight/2))
        rotBmp = rotImage.ConvertToBitmap()
        rotBmpWidth, rotBmpHeight = rotBmp.GetWidth(), rotBmp.GetHeight()

        x = (x1 + x2 - rotBmpWidth)/2
        y = (y1 + y2 - rotBmpHeight)/2

        # We need to adjust to keep the bitmap on the screen...
        # ...first, calc what we need to adjust x by if we adjust y and
        # what we need to adjust y by if we adjust x.  We'd like to move
        # at a right angle to the other line, which should be (-dx / dy),
        # I think.  ...but we need to watch for divide by 0...
        width, height = self._origImage.size
        if dx == 0:
            xAdjust = 0
        else:
            xAdjust = (-dy / dx)
        if dy == 0:
            yAdjust = 0
        else:
            yAdjust = (-dx / dy)

        if x < 0:
            y += (yAdjust * -x)
            x = 0
        if y < 0:
            x += (xAdjust * -y)
            y = 0
        if (x + rotBmpWidth > width):
            extraWidth = (x + rotBmpWidth) - width
            y -= (yAdjust * extraWidth)
            x -= extraWidth
        if (y + rotBmpHeight > height):
            extraHeight = (y + rotBmpHeight) - height
            x -= (xAdjust * extraHeight)
            y -= extraHeight

        return (rotBmp, x, y)


    ###########################################################
    def _drawLineSegment(self, triggerLineSegment, gc):
        """Draw the given line segment on the given GraphicsContext.

        @param  triggerLineSegment  The trigger line segment to draw.
        @param  gc                  The graphics context
        """
        gc.PushState()

        gc.SetPen(wx.Pen(_kLineTriggerPenColor, _kLineTriggerPenWidth))
        ((x1, y1), (x2, y2)) = triggerLineSegment.getProposedPoints(self._coordSpace)
        gc.StrokeLine(x1, y1, x2, y2)

        gc.SetPen(wx.BLACK_PEN)
        gc.SetBrush(wx.WHITE_BRUSH)
        if self._isInEditMode:
            self._drawEditCircle(gc, x1, y1)
            self._drawEditCircle(gc, x2, y2)

        rotBmp, rotBmpX, rotBmpY = \
            self._getLineSegmentBitmap(triggerLineSegment)
        rotBmpWidth, rotBmpHeight = rotBmp.GetWidth(), rotBmp.GetHeight()
        gc.DrawBitmap(rotBmp, rotBmpX, rotBmpY, rotBmpWidth, rotBmpHeight)

        gc.PopState()


    ###########################################################
    def _deletePointInRegion(self, region, ptIndex):
        """Delete the given point in the given region.

        @param  region   The region to delete the point in.
        @param  ptIndex  The index of the point in the region.
        """
        newPoints = region.getPoints()
        del newPoints[ptIndex]
        cmd = _SetPointsInTriggerCommand(region, newPoints, "Delete Point", self._coordSpace)
        self._cmdProcessor.Submit(cmd)


    ###########################################################
    def changeLineTriggerDirection(self, lineTrigger):
        """Change the direction in the given line trigger.

        @param  lineTrigger  The line trigger to change.
        """
        cmd = _ChangeLineTriggerDirCommand(lineTrigger)
        self._cmdProcessor.Submit(cmd)




##############################################################################
class _SetPointsInTriggerCommand(wxCommand):
    """A "command" to set points in a trigger region / line segment.

    This is part of our undo architecture.
    """
    def __init__(self, triggerObject, newPoints=None, desc="Adjust Points", coordSpace=None):
        """_SetPointsInTriggerCommand constructor.

        @param  triggerObject  The region / line segment we're setting points in
        @param  newPoints      The new points; if None, we'll use the current
                               proposal.
        @param  desc           The description of the change, to use in the undo
                               menu item name.
        @param  coordSpace     The coordinate space of the video window.
        """
        super(_SetPointsInTriggerCommand, self).__init__(
            canUndo=True, name=desc
        )
        self._triggerObject = triggerObject
        if newPoints is None:
            newPoints = triggerObject.getProposedPoints(coordSpace)
        self._newPoints = newPoints
        self._oldPoints = triggerObject.getPoints(coordSpace)
        self._coordSpace = coordSpace


    ###########################################################
    def Do(self):
        """Do the command.

        @return  didItWork  True if the command worked; False otherwise.
        """
        self._triggerObject.setPoints(self._newPoints, self._coordSpace)
        return True


    ###########################################################
    def Undo(self):
        """Do the command.

        @return  didItWork  True if the command worked; False otherwise.
        """
        self._triggerObject.setPoints(self._oldPoints, self._coordSpace)
        return True


##############################################################################
class _ChangeLineTriggerDirCommand(wxCommand):
    """A "command" change the direction of a line trigger.

    This is part of our undo architecture.
    """

    # The order we cycle through directions...
    _kDirOrder = ['any', 'left', 'right']

    def __init__(self, lineTrigger):
        """_ChangeLineTriggerDirCommand constructor.

        @param  lineTrigger  The TriggerLineSegment to change direction on.
        """
        super(_ChangeLineTriggerDirCommand, self).__init__(
            canUndo=True, name="Change Direction"
        )
        self._lineTrigger = lineTrigger


    ###########################################################
    def Do(self):
        """Do the command.

        @return  didItWork  True if the command worked; False otherwise.
        """
        dirStr = self._lineTrigger.getDirection()
        dirIndex = self._kDirOrder.index(dirStr)

        dirStr = self._kDirOrder[(dirIndex + 1) % len(self._kDirOrder)]

        self._lineTrigger.setDirection(dirStr)
        return True


    ###########################################################
    def Undo(self):
        """Do the command.

        @return  didItWork  True if the command worked; False otherwise.
        """
        dirStr = self._lineTrigger.getDirection()
        dirIndex = self._kDirOrder.index(dirStr)

        dirStr = self._kDirOrder[(dirIndex - 1)]

        self._lineTrigger.setDirection(dirStr)
        return True



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    image = Image.open("frontEnd/bmps/fakeVideoWindowBackground.png")

    frame = wx.Frame(None)

    videoWin = VideoWindow(frame)
    videoWin.setImage(image)
    videoWin.setTriggerRegions([
        #TriggerRegion([(10, 20), (87, 30), (70, 190), (2, 180)]),
        TriggerRegion(list(([(10, 20), (80, 20), (80, 190), (10, 190)]))),
    ])
    videoWin.setTriggerLineSegments([
        TriggerLineSegment(LineSegment(200, 200, 200, 100), 'left')
    ])

    # Create a frame sizer, which appears to be needed if we use Fit()
    frameSizer = wx.BoxSizer()
    frameSizer.Add(videoWin, 1, wx.EXPAND)
    frame.SetSizer(frameSizer)

    videoWin.SetFocus()

    # Fit and show...
    frame.Fit()
    frame.Show()

    # Run the main loop, which will close when the frame does.
    app.MainLoop()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
