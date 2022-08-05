#!/usr/bin/env python

#*****************************************************************************
#
# TriggerRegion.py
#     Utility class: Holds a list of points defining a region for use in a trigger
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
import sys

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.math.LineSegment import LineSegment
from vitaToolbox.mvc.AbstractModel import AbstractModel

# Local imports...



##############################################################################
class TriggerRegion(AbstractModel):
    """Holds a list of points defining a region for use in a trigger.

    This is slightly more complicated than just a list of points because
    it has some methods for operating on the region.

    Note: points in the region must be clockwise, and the region must be
    simple (that is, the lines that making it up can't intersect).
    """
    ###########################################################
    def __init__(self, points, coordSpace=None):
        """Create a new trigger region.

        @param  points     A list of points.  Each point is specified as (x, y).
        @param  coordSpace        The coordinate space that this region
                                  exists in, as a two-tuple (width, height).
                                  Can be None if an arbitrary coordinate space
                                  is desired; scaling is disabled if this option
                                  is chosen.
        """
        super(TriggerRegion, self).__init__()

        assert _arePointsClockwise(points), "Points must be clockwise"

        # TODO: Assert that the points make up a simple region (in other words,
        # that no line segments cross each other)...

        self._points = list(points)
        self._proposedPoints = None
        self._coordSpace = coordSpace


    ###########################################################
    def getCoordSpace(self):
        """Get the coordinate space.

        @return  coordSpace  The coordinate space that this region exists
                             in, as a two-tuple (width, height). Can be None
                             if the coordinate space is arbitrary.
        """
        return self._coordSpace


    ###########################################################
    def setCoordSpace(self, coordSpace):
        """Set the coordinate space.

        Note:  If the coordinate space was never set before, (meaning, a call
               to self.getCoordSpace() returns None) the value passed in
               will be the new coordinate space for this region. However,
               if the coordinate space is already set, this region will
               be scaled from the old coordinate space to the new coordinate
               space, and the new coordinate space is kept for this region. This
               is done for several reasons:

               - When the region has no coordinate space, there's no
                 telling what coordinate space it belongs to. In this case,
                 we assume that the region is being told which coordinate
                 space it belongs to. Therefore, the new coordinate space is
                 set, and no scaling is performed.

               - When the region has a coordinate space, then it shouldn't
                 be allowed to be easily changed, since other objects might be
                 listening to changes made to this object. However, a new
                 coordinate space might be desirable if changing aspect ratios.
                 Therefore, when setting a new coordinate space, the internal
                 data is scaled to match the new coordinate space from the old
                 one. Finally, the new coordinate space is kept for this region.

        @param coordSpace  The coordinate space that this region exists
                           in, as a two-tuple (width, height). None is
                           ignored.
        """
        if self._coordSpace is None:
            self._coordSpace = coordSpace
        else:
            oldCoordSpace = self._coordSpace
            self._coordSpace = coordSpace
            self._points = scalePoints(self._points, oldCoordSpace, coordSpace)


    ###########################################################
    def _checkCoordSpace(self, coordSpace):
        """Checks if the coordinate space has been set and if the given
        coordinate space can be used for scaling input or output data.

        @param  coordSpace  The coordinate space that this region exists
                            in, as a two-tuple (width, height). Passing in
                            None will make this function return False.
        @return  bool       True if our coordinate space is already set, and if
                            the given coordinate space can be used for scaling.
        """
        return (self._coordSpace is not None) and (coordSpace is not None)


    ###########################################################
    def proposePointChange(self, i, x, y, fromCoordSpace=None):
        """Set proposed points to original points, but set point i to (x, y).

        This will only accept the proposal if (x, y) is a valid value for
        point i.  If it's not, proposed points will be left alone.

        If the proposed points are changed, will notify any listeners with
        'proposed' as a key.

        @param  i               The index of the point to set.
        @param  x               The x value to set it to.
        @param  y               The y value to set it to.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this region
                                before processing. Can be None if no scaling
                                is desired.
        """
        if self._checkCoordSpace(fromCoordSpace):
            x, y = scalePoint(x, y, fromCoordSpace, self._coordSpace)

        points = self._points
        numPoints = len(points)

        proposedPoints = list(points)
        proposedPoints[i] = (x, y)

        # First, make sure that the change will leave us being a simple
        # region.  We do this by checking to make sure that the two lines
        # that come from the changing point don't intersect with any other
        # lines.  This assumes that the region was previously simple...
        leftI  = (i - 1 + numPoints) % numPoints
        leftX, leftY = points[leftI]
        leftSegment = LineSegment(x, y, leftX, leftY)

        rightI = (i + 1) % numPoints
        rightX, rightY = points[rightI]
        rightSegment = LineSegment(x, y, rightX, rightY)

        for ptNum in xrange(0, numPoints):
            prevPtNum = (ptNum - 1 + numPoints) % numPoints

            if (prevPtNum == i) or (ptNum == i):
                continue

            x1, y1 = points[prevPtNum]
            x2, y2 = points[ptNum]
            lineSegment = LineSegment(x1, y1, x2, y2)

            if ptNum != leftI:
                intersectX, intersectY = lineSegment.findIntersection(leftSegment)
                if intersectX != -1:
                    return
            if prevPtNum != rightI:
                intersectX, intersectY = lineSegment.findIntersection(rightSegment)
                if intersectX != -1:
                    return

        # Next, make sure that the points are still clockwise...
        if not _arePointsClockwise(proposedPoints):
            return

        # If the points changed, do the update...
        if proposedPoints != self._proposedPoints:
            self._proposedPoints = proposedPoints
            self.update('proposed')


    ###########################################################
    def proposeOffset(self, dx, dy, maxWidth, maxHeight, fromCoordSpace=None):
        """Set proposed points to original points + (dx, dy).

        ...this also crops to maxWidth, maxHeight

        If the proposed points are changed, will notify any listeners with
        'proposed' as a key.

        @param  dx              The change in x.
        @param  dy              The change in y.
        @param  maxWidth        The width to crop to.
        @param  maxHeight       The height to crop to.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this region
                                before processing. Can be None if no scaling
                                is desired.
        """

        if self._checkCoordSpace(fromCoordSpace):
            dx, dy = scalePoint(dx, dy, fromCoordSpace, self._coordSpace)
            maxWidth, maxHeight = scalePoint(
                maxWidth, maxHeight, fromCoordSpace, self._coordSpace
            )

        xList = [pt[0] for pt in self._points]
        yList = [pt[1] for pt in self._points]

        # Get a bounding box.
        tlX = min(xList)
        tlY = min(yList)
        width  = (max(xList) - tlX) + 1
        height = (max(yList) - tlY) + 1

        # Crop dx and dy so that the region doesn't go out of bounds.
        if dx < 0:
            if (tlX + dx) < 0:
                dx = -tlX
        else:
            if (tlX + width + dx) > maxWidth:
                dx = maxWidth - (tlX + width)
        if dy < 0:
            if (tlY + dy) < 0:
                dy = -tlY
        else:
            if (tlY + height + dy) > maxHeight:
                dy = maxHeight - (tlY + height)

        # Make a new proposal...
        proposedPoints = [(x + dx, y + dy) for (x, y) in self._points]

        # If the points changed, do the update...
        if proposedPoints != self._proposedPoints:
            self._proposedPoints = proposedPoints
            self.update('proposed')


    ###########################################################
    def getPoints(self, toCoordSpace=None):
        """Return the list of points, ignoring any proposals.

        @param  toCoordSpace  If given, this will be used to scale the output
                              data to the given coordinate space after
                              processing, but before it is returned. Can be None
                              if no scaling is desired.
        @return points        The list of points; a copy so you don't tweak ours.
        """
        if self._checkCoordSpace(toCoordSpace):
            return scalePoints(self._points, self._coordSpace, toCoordSpace)
        return list(self._points)


    ###########################################################
    def getProposedPoints(self, toCoordSpace=None):
        """Return the list of points, returning the proposed ones if they exist.

        @param  toCoordSpace  If given, this will be used to scale the output
                              data to the given coordinate space after
                              processing, but before it is returned. Can be None
                              if no scaling is desired.
        @return points        The list of points; a copy so you don't tweak ours.
        """
        if self._proposedPoints is not None:
            if self._checkCoordSpace(toCoordSpace):
                return scalePoints(self._proposedPoints, self._coordSpace, toCoordSpace)
            return list(self._proposedPoints)
        else:
            if self._checkCoordSpace(toCoordSpace):
                return scalePoints(self._points, self._coordSpace, toCoordSpace)
            return list(self._points)


    ###########################################################
    def setPoints(self, newPoints, fromCoordSpace=None):
        """Set the points as given, deleting any proposals.

        Will notify any listeners with 'points' as a key.

        @param  newPoints       The new value for points.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this region
                                before processing. Can be None if no scaling
                                is desired.
        """
        if self._checkCoordSpace(fromCoordSpace):
            self._points = scalePoints(newPoints, fromCoordSpace, self._coordSpace)
        else:
            self._points = list(newPoints)

        self._proposedPoints = None

        self.update('points')


    ###########################################################
    def rejectProposal(self):
        """Throw away proposed points.

        If the points are updated, will notify any listeners with 'proposed'
        as a key.
        """
        if self._proposedPoints is not None:
            self._proposedPoints = None
            self.update('proposed')


##############################################################################
def scalePoint(x, y, fromCoordSpace, toCoordSpace):
    """Scales the given x and y coordinate from one coordinate space to another.

    @param x:                 The x coordinate.
    @param y:                 The y coordinate.
    @param fromCoordSpace:    The coordinate space to scale from, as a 2-tuple.
    @param toCoordSpace:      The coordinate space to scale to, as a 2-tuple.
    @return x, y:             Scaled coordinates, x and y, as ints.
    """
    # Note: when scaling, we want to scale 319 to 639 to make things even.
    return \
        int(round(x * float(toCoordSpace[0]-1) / (fromCoordSpace[0]-1))), \
        int(round(y * float(toCoordSpace[1]-1) / (fromCoordSpace[1]-1)))


##############################################################################
def scalePoints(points, fromCoordSpace, toCoordSpace):
    """Scales the given region from one coordinate space to another.

    @param points:          The list of points to scale.
    @param fromCoordSpace:  The coordinate space to scale from, as a 2-tuple.
    @param toCoordSpace:    The coordinate space to scale to, as a 2-tuple.
    @return newPoints:      New list of scaled points.
    """
    # Note: when scaling, we want to scale 319 to 639 to make things even.
    scaleX, scaleY = \
        float(toCoordSpace[0]-1) / (fromCoordSpace[0]-1), \
        float(toCoordSpace[1]-1) / (fromCoordSpace[1]-1)
    return [(int(round(scaleX * x)), int(round(scaleY * y)))
            for (x, y) in points
            ]


##############################################################################
def _arePointsClockwise(points):
    """Return whether the given points specifying a region are clockwise.

    This works in the wx coordinate system, where (0, 0) is the top-left point.
    In a cartesian coordinate system, the result of this function is opposite.

    This function is based on descriptions in Wikipedia and the
    comp.graphics.algorithms FAQ).  The Wikipedia article can be found (at the
    moment) at:
        http://en.wikipedia.org/wiki/Polygon_area

    Major changes from the classic algorithms:
    - Result is reversed for wx coordinate system.
    - I use the optimization talked about in the comp.graphics.algorithms FAQ,
      so the formula isn't as obvious as the wikipedia one.
    - I use (i-2, i-1, and i) rather than (i-1, i, and i+1).  That ends up
      working well in python, where list[-1] and list[-2] work just perfectly.

    NOTE: If useful, we could exctact the "signed area" part of this function.

    TODO: Move to a more generic place?

    @param  points        The points that make up the simple polygon.
    @return areClockwise  True if the points are clockwise; False otherwise.
    """
    signedArea = 0

    numPoints = len(points)
    for i in xrange(numPoints):
        x1, y1 = points[i-2]
        x2, y2 = points[i-1]
        x3, y3 = points[i]

        signedArea += x2 * (y3 - y1)
    signedArea /= 2

    return signedArea > 0



##############################################################################
def test_main():
    """Contains various self-test code."""
    print "NO TESTS"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
