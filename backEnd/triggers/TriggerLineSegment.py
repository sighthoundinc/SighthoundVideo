#!/usr/bin/env python

#*****************************************************************************
#
# TriggerLineSegment.py
#     Utility class: Holds a line segment for use in defining a line trigger.
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
import sys

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.math.LineSegment import LineSegment
from vitaToolbox.mvc.AbstractModel import AbstractModel

# Local imports...



##############################################################################
class TriggerLineSegment(AbstractModel):
    """Holds a line segment for use in defining a line trigger.

    This is a little more complicated than just a line trigger, since it holds
    direction and has some methods for operating on the region.
    """
    ###########################################################
    def __init__(self, lineSegment, triggerDirection, coordSpace=None):
        """Create a new trigger line segment.

        @param  lineSegment       The line segment.  Should be a LineSegment.
                                  We'll make a copy so we don't corrupt yours.
        @param  triggerDirection  The direction of the trigger.  Should be
                                  'any', 'left', or 'right'.
        @param  coordSpace        The coordinate space that this line segment
                                  exists in, as a two-tuple (width, height).
                                  Can be None if an arbitrary coordinate space
                                  is desired; scaling is disabled if this option
                                  is chosen.
        """
        super(TriggerLineSegment, self).__init__()

        assert triggerDirection in ('any', 'left', 'right')

        self._lineSegment = lineSegment.copy()
        self._proposedLineSegment = None
        self._triggerDirection = triggerDirection
        self._coordSpace = coordSpace


    ###########################################################
    def getCoordSpace(self):
        """Get the coordinate space.

        @return  coordSpace  The coordinate space that this line segment exists
                             in, as a two-tuple (width, height). Can be None
                             if the coordinate space is arbitrary.
        """
        return self._coordSpace


    ###########################################################
    def setCoordSpace(self, coordSpace):
        """Set the coordinate space.

        Note:  If the coordinate space was never set before, (meaning, a call
               to self.getCoordSpace() returns None) the value passed in
               will be the new coordinate space for this line segment. However,
               if the coordinate space is already set, this line segment will
               be scaled from the old coordinate space to the new coordinate
               space, and the new coordinate space is kept for this line
               segment. This is done for several reasons:

               - When the line segment has no coordinate space, there's no
                 telling what coordinate space it belongs to. In this case,
                 we assume that the line segment is being told which coordinate
                 space it belongs to. Therefore, the new coordinate space is
                 set, and no scaling is performed.

               - When the line segment has a coordinate space, then it shouldn't
                 be allowed to be easily changed, since other objects might be
                 listening to changes made to this object. However, a new
                 coordinate space might be desirable if changing aspect ratios.
                 Therefore, when setting a new coordinate space, the internal
                 data is scaled to match the new coordinate space from the old
                 one. Finally, the new coordinate space is kept for this line
                 segment.

        @param coordSpace  The coordinate space that this line segment exists
                           in, as a two-tuple (width, height). None is
                           ignored.
        """
        if coordSpace is None:
            return
        if self._coordSpace is None:
            self._coordSpace = coordSpace
        else:
            oldCoordSpace = self._coordSpace
            self._coordSpace = coordSpace
            self._lineSegment = \
                scaleLineSegment(self._lineSegment, oldCoordSpace, coordSpace)


    ###########################################################
    def _checkCoordSpace(self, coordSpace):
        """Checks if the coordinate space has been set and if the given
        coordinate space can be used for scaling input or output data.

        @param  coordSpace  The coordinate space that this line segment exists
                            in, as a two-tuple (width, height). Passing in
                            None will make this function return False.
        @return  bool       True if our coordinate space is already set, and if
                            the given coordinate space can be used for scaling.
        """
        return (self._coordSpace is not None) and (coordSpace is not None)


    ###########################################################
    def setDirection(self, triggerDirection):
        """Set the direction.

        Will send out an update with 'direction'.

        @param  triggerDirection  The new direction.
        """
        assert triggerDirection in ('any', 'left', 'right')
        self._triggerDirection = triggerDirection
        self.update('direction')


    ###########################################################
    def getDirection(self):
        """Get the direction.

        @return triggerDirection  The direction.
        """
        return self._triggerDirection

    ###########################################################
    def proposePointChange(self, i, x, y, fromCoordSpace=None):
        """Set proposed segment to original segment, but set point i to (x, y).

        This will accept any value for (x, y).

        Will notify any listeners with 'proposed' as a key.

        @param  i               The index of the point to set.  Must be 0 or 1.
        @param  x               The x value to set it to.
        @param  y               The y value to set it to.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this line
                                segment before processing. Can be None if no
                                scaling is desired.
        """
        assert i in (0, 1), "Can only set point 0 or 1."

        if self._checkCoordSpace(fromCoordSpace):
            x, y = scalePoint(x, y, fromCoordSpace, self._coordSpace)

        self._proposedLineSegment = self._lineSegment.copy()
        self._proposedLineSegment.setPoint(i, x, y)

        self.update('proposed')


    ###########################################################
    def proposeOffset(self, dx, dy, maxWidth, maxHeight, fromCoordSpace=None):
        """Set proposed segment to original segment + (dx, dy).

        ...this also crops to maxWidth, maxHeight

        If the proposed segment is changed, will notify any listeners with
        'proposed' as a key.

        @param  dx              The change in x.
        @param  dy              The change in y.
        @param  maxWidth        The width to crop to.
        @param  maxHeight       The height to crop to.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this line
                                segment before processing. Can be None if no
                                scaling is desired.
        """
        if self._checkCoordSpace(fromCoordSpace):
            dx, dy = scalePoint(dx, dy, fromCoordSpace, self._coordSpace)
            maxWidth, maxHeight = scalePoint(
                maxWidth, maxHeight, fromCoordSpace, self._coordSpace
            )

        # Compute a bounding box...
        x1, y1, x2, y2 = self._lineSegment.getPoints()
        tlX = min(x1, x2)
        tlY = min(y1, y2)
        brX = max(x1, x2)
        brY = max(y1, y2)

        width = (brX - tlX) + 1
        height = (brY - tlY) + 1

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
        proposedLineSegment = LineSegment(x1 + dx, y1 + dy, x2 + dx, y2 + dy)

        # If the segment changed, do the update...
        if proposedLineSegment != self._proposedLineSegment:
            self._proposedLineSegment = proposedLineSegment
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
        x1, y1, x2, y2 = self._lineSegment.getPoints()

        if self._checkCoordSpace(toCoordSpace):
            x1, y1, x2, y2 = scaleRawLineSegment(
                x1, y1, x2, y2, self._coordSpace, toCoordSpace
            )

        return [(x1, y1), (x2, y2)]


    ###########################################################
    def getProposedPoints(self, toCoordSpace=None):
        """Return the list of points, returning the proposed ones if they exist.

        @param  toCoordSpace  If given, this will be used to scale the output
                              data to the given coordinate space after
                              processing, but before it is returned. Can be None
                              if no scaling is desired.
        @return points        The list of points; a copy so you don't tweak ours.
        """
        if self._proposedLineSegment is not None:
            x1, y1, x2, y2 = self._proposedLineSegment.getPoints()
        else:
            x1, y1, x2, y2 = self._lineSegment.getPoints()

        if self._checkCoordSpace(toCoordSpace):
            x1, y1, x2, y2 = scaleRawLineSegment(
                x1, y1, x2, y2, self._coordSpace, toCoordSpace
            )

        return [(x1, y1), (x2, y2)]


    ###########################################################
    def setPoints(self, newPoints, fromCoordSpace=None):
        """Set the points as given, deleting any proposals.

        Will notify any listeners with 'points' as a key.

        @param  newPoints       The new value for points.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this line
                                segment before processing. Can be None if no
                                scaling is desired.
        """
        ((x1, y1), (x2, y2)) = newPoints

        if self._checkCoordSpace(fromCoordSpace):
            x1, y1, x2, y2 = scaleRawLineSegment(
                x1, y1, x2, y2, fromCoordSpace, self._coordSpace
            )

        self._lineSegment = LineSegment(x1, y1, x2, y2)
        self._proposedLineSegment = None

        self.update('points')


    ###########################################################
    def rejectProposal(self):
        """Throw away proposed line segment.

        If this changes anything, will notify any listeners with 'proposed'
        as a key.
        """
        if self._proposedLineSegment is not None:
            self._proposedLineSegment = None
            self.update('proposed')


    ###########################################################
    def getLineSegment(self, toCoordSpace=None):
        """Return the line segment, ignoring any proposals.

        @param  toCoordSpace  If given, this will be used to scale the output
                              data to the given coordinate space after
                              processing, but before it is returned. Can be None
                              if no scaling is desired.
        @return lineSegment   The current line segment; a copy.
        """
        if self._checkCoordSpace(toCoordSpace):
            return scaleLineSegment(
                self._lineSegment, self._coordSpace, toCoordSpace
            )
        else:
            return self._lineSegment.copy()


    ###########################################################
    def getProposedLineSegment(self, toCoordSpace=None):
        """Return the line segment, returning the proposed one if it exists.

        @param  toCoordSpace  If given, this will be used to scale the output
                              data to the given coordinate space after
                              processing, but before it is returned. Can be None
                              if no scaling is desired.
        @return lineSegemnt   The line segment; a copy.
        """
        if self._proposedLineSegment is not None:
            lineSegment = self._proposedLineSegment
        else:
            lineSegment = self._lineSegment

        if self._checkCoordSpace(toCoordSpace):
            return scaleLineSegment(
                lineSegment, self._coordSpace, toCoordSpace
            )
        else:
            return lineSegment.copy()


    ###########################################################
    def setLineSegment(self, newLineSegment, fromCoordSpace=None):
        """Set the line segment as given, deleting any proposals.

        Will notify any listeners with 'points' as a key.

        @param  newPoints       The new value for points.
        @param  fromCoordSpace  If given, this will be used to scale the input
                                data to the coordinate space of this line
                                segment before processing. Can be None if no
                                scaling is desired.
        """
        if self._checkCoordSpace(fromCoordSpace):
            self._lineSegment = scaleLineSegment(
                newLineSegment, fromCoordSpace, self._coordSpace
            )
        else:
            self._lineSegment = newLineSegment.copy()

        self._proposedLineSegment = None

        self.update('points')


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
def scaleRawLineSegment(x1, y1, x2, y2, fromCoordSpace, toCoordSpace):
    """Scales the given line segment coordinates from one coordinate space to another.

    @param x1:              The x coordinate of the first point in the line segment.
    @param y1:              The y coordinate of the first point in the line segment.
    @param x2:              The x coordinate of the second point in the line segment.
    @param y2:              The y coordinate of the second point in the line segment.
    @param fromCoordSpace:  The coordinate space to scale from, as a 2-tuple.
    @param toCoordSpace:    The coordinate space to scale to, as a 2-tuple.
    @return x1, y1, x2, y2: The scaled coordinates as ints.
    """
    # Note: when scaling, we want to scale 319 to 639 to make things even.
    return \
        int(round(x1 * float(toCoordSpace[0]-1) / (fromCoordSpace[0]-1))), \
        int(round(y1 * float(toCoordSpace[1]-1) / (fromCoordSpace[1]-1))), \
        int(round(x2 * float(toCoordSpace[0]-1) / (fromCoordSpace[0]-1))), \
        int(round(y2 * float(toCoordSpace[1]-1) / (fromCoordSpace[1]-1)))


##############################################################################
def scaleLineSegment(lineSegment, fromCoordSpace, toCoordSpace):
    """Scales the given line segment from one coordinate space to another.

    @param lineSegment:     The TriggerLineSegment object to scale.
    @param fromCoordSpace:  The coordinate space to scale from, as a 2-tuple.
    @param toCoordSpace:    The coordinate space to scale to, as a 2-tuple.
    @return lineSegment:    New scaled TriggerLineSegment.
    """
    x1, y1, x2, y2 = lineSegment.getPoints()
    return LineSegment(
        *scaleRawLineSegment(x1, y1, x2, y2, fromCoordSpace, toCoordSpace)
    )


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
