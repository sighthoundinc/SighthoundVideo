#!/usr/bin/env python

#*****************************************************************************
#
# LineSegment.py
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
import math
import sys

# Common 3rd-party imports...
# Local imports...

##############################################################################
class LineSegment(object):
    """An object representing a line segment in 2D space.

    You can do several operations on this object, such as:
    - figuring out if (and where) two line segments intersect.
    - find the closest point on the line segment to a given point in space.
    - ...
    """
    ###############################################################
    def __init__(self, x1, y1, x2, y2):
        """LineSegment constructor.

        @param  x1  The x coord of the 1st point.
        @param  y1  The y coord of the 1st point.
        @param  x2  The x coord of the 2nd point.
        @param  y2  The y coord of the 2nd point.
        """
        # Save the segment coordinates
        # ...WARNING: Some of the formulas don't work right with integer math,
        # so it's important to work with floats.
        self._x1 = float(x1)
        self._y1 = float(y1)
        self._x2 = float(x2)
        self._y2 = float(y2)

        self._updateCache()


    ###############################################################
    def _updateCache(self):
        """Updates our 'cache'; called when any point changes."""

        # Keep these around since we'll use them often
        self._x2s1 = self._x2-self._x1
        self._y2s1 = self._y2-self._y1
        self._x1s2 = self._x1-self._x2
        self._y1s2 = self._y1-self._y2
        self._crossProd = self._x1*self._y2-self._x2*self._y1


    ###############################################################
    def copy(self):
        """Return a copy of ourselves.

        @return copy  A new line segment that's a copy.
        """
        return LineSegment(self._x1, self._y1, self._x2, self._y2)


    ###############################################################
    def getPoints(self):
        """Return our points

        @return x1  X of our 1st point.
        @return y1  Y of our 1st point.
        @return x2  X of our 2nd point.
        @return y2  Y of our 2nd point.
        """
        return (self._x1, self._y1, self._x2, self._y2)


    ###############################################################
    def setPoint(self, i, x, y):
        """Set one of the two points that make up the line segment.

        @param  i  Either 0 or 1 to set the 1st or 2nd point.
        @param  x  The new x value.
        @param  y  The new y value.
        """
        assert i in (0, 1), "Can only set point 0 or 1."

        if i == 0:
            self._x1 = float(x)
            self._y1 = float(y)
        else:
            self._x2 = float(x)
            self._y2 = float(y)

        self._updateCache()


    ###############################################################
    def getPointDir(self, x, y):
        """Determines where a given point is in relation to the line.

        NOTE: This function works on the _line_ defined by the two points,
        not the _line segment_.  The difference is that the line continues off
        past the ends of the line segment.

        @param  x    The x coordinate to test
        @param  y    The y coordinate to test
        @return dir  The location of the point - 'left', 'right' or 'on'
        """
        a = self._x2s1*(y-self._y1)
        b = self._y2s1*(x-self._x1)
        if a > b:
            return 'left'
        if a < b:
            return 'right'
        return 'on'


    ###############################################################
    def getClosestPtTo(self, x, y):
        """Get the closest point to (x, y) on this line segment.

        Note: this function will always return something on the actual line
        segment--it will never go off the ends.  Also note that it returns
        a floating point value.

        @param  x         X for a point that might be on or off our line seg.
        @param  y         Y for a point that might be on or off our line seg.
        @return closestX  The closest x to the pt, on the line segment.
        @return closestY  The closest y to the pt, on the line segment.
        @return dist      The distance from (x, y) to (closestX, closestY).
        """
        myLengthSq = (((self._y2 - self._y1) ** 2) +
                      ((self._x2 - self._x1) ** 2)  )

        # The position along our segment.  This is "r" in the
        # comp.graphics.algorithms FAQ.  r = 0 means pt1, r = 1 means pt2
        pos = ((x - self._x1) * self._x2s1 + (y - self._y1) * self._y2s1) / \
              myLengthSq

        if pos <= 0:
            closestX, closestY = self._x1, self._y1
        elif pos >= 1:
            closestX, closestY = self._x2, self._y2
        else:
            closestX = self._x1 + pos * (self._x2s1)
            closestY = self._y1 + pos * (self._y2s1)

        dx = (closestX - x)
        dy = (closestY - y)
        distToClosest = math.sqrt(dx * dx + dy * dy)  #PYCHECKER OK: pychecker confused by module/lib name the same...
        return closestX, closestY, distToClosest


    ###############################################################
    def _calcVectorIntersection(self, otherLine):
        """Calcualte the intersection of this line with another.

             | |x1 y1|   x1-x2  |       | |x1 y1|   y1-y2  |
             | |x2 y2|          |       | |x2 y2|          |
             |                  |       |                  |
             | |x3 y3|   x3-x4  |       | |x3 y3|   y3-y4  |
             | |x4 y4|          |       | |x4 y4|          |
        x = ----------------------  y = ----------------------
             |  x1-x2    y1-y2  |       |  x1-x2    y1-y2  |
             |  x3-x4    y3-y4  |       |  x3-x4    y3-y4  |

        Note: this assumes that both are full lines; not segments.  This is
        a helper function for findIntersection()

        @param  otherLine  The other line to look for an intersection.
        @return pt         The intersecting point; (-1, -1) if parallel.
        """
        x1 = otherLine._x1
        y1 = otherLine._y1
        x2 = otherLine._x2
        y2 = otherLine._y2

        x1s2 = x1-x2
        y1s2 = y1-y2
        crossProd = x1*y2-x2*y1
        denom = x1s2*self._y1s2-self._x1s2*y1s2

        if denom == 0:
            # Lines are parallel, no intersection
            return -1, -1

        x = (crossProd*self._x1s2-self._crossProd*x1s2)/denom
        y = (crossProd*self._y1s2-self._crossProd*y1s2)/denom

        return x, y


    ###############################################################
    def findIntersection(self, otherLineSeg):
        """Find the intersection of this line segment with another.

        @param  otherLineSeg  The other line segment to look for an intersection
        @return pt            The intersecting point; (-1, -1) if they don't
                              intersect.  Will be a floating point.
        """
        # Treat self and other as a full line and calculate intersection
        # first, since that's easier.
        x, y = self._calcVectorIntersection(otherLineSeg)

        if ((otherLineSeg._x1 <= x <= otherLineSeg._x2 or
             otherLineSeg._x2 <= x <= otherLineSeg._x1   ) and
            (self._x1 <= x <= self._x2 or
             self._x2 <= x <= self._x1   )                    ):

            # If the x's of either line segment are equal, we need an
            # additional check to ensure the line was actually crossed.
            for lineSeg in (self, otherLineSeg):
                if (lineSeg._x1 == lineSeg._x2):
                    if not (lineSeg._y2 <= y <= lineSeg._y1) and \
                       not (lineSeg._y1 <= y <= lineSeg._y2):
                        return (-1, -1)

            return (x, y)

        return (-1, -1)


    ###############################################################
    def __eq__(self, other):
        """Support testing for equality between line segments.

        @param  other  The other line segment to test.
        @return eq     True if other is an equal line segment; False otherwise.
        """
        try:
            return ((self._x1 == other._x1) and
                    (self._y1 == other._y1) and
                    (self._x2 == other._x2) and
                    (self._y2 == other._y2)    )
        except Exception:
            return False


    ###############################################################
    def __str__(self):
        """Return a string representation of ourself.

        @return s  A string.
        """
        return "<line segment: (%.1f, %.1f) - (%.1f, %.1f)>" % (
            self._x1, self._y1, self._x2, self._y2
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
