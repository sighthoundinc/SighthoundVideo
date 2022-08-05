#*****************************************************************************
#
# Rect.py
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

from math import sqrt
from Point import Point
from ctypes import Structure, c_float, c_int

"""
Implementation of an OpenCV-like Rect class.
"""
class Rect(object):
    def __init__(self, x, y, width, height):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)

    def tl(self):
        """
        Return the top left corner of the rectangle as a Point.
        """
        return Point(self.x, self.y)

    def br(self):
        """
        Return the bottom right corner of the rectangle as a Point.
        """
        return Point(self.x + self.width, self.y + self.height)

    def center(self):
        """
        Return the center of the rectangle as a Point.
        """
        return Point(self.x + self.width/2.0, self.y + self.height/2.0)

    def area(self):
        """
        Return area of rectangle.
        """
        return self.width * self.height

    def isInside(self, otherRect):
        """
        Return true iff this box is inside the other one.
        """
        return self.tl().inRect(otherRect) and self.br().inRect(otherRect)

    def hasIntersectionWith(self, otherRect):
        """
        Return true iff this box intersects with the other one.
        """
        return self.intersect(otherRect) != RectFromCorners(Point(0, 0), Point(0, 0))

    def containment(self, otherRect):
        """ Return containment of this rect contained in other rectangle.
            Note that it's different from overlap(method='ss') in that it isn't commutative
            (e.g. r1.containment(r2) != r2.containment(r1) )
        """
        intersectRect = self.intersect(otherRect)
        return intersectRect.area()/float(self.area())

    def intersect(self, otherRect):
        """
        Return a Rect representing the intersection of this one with the argument, or
        a rect at (0, 0) of zero size if no intersection exists.
        """
        bottomRight = self.br()
        otherBottomRight = otherRect.br()

        x1 = max(self.x, otherRect.x)
        x2 = min(bottomRight.x, otherBottomRight.x)
        y1 = max(self.y, otherRect.y)
        y2 = min(bottomRight.y, otherBottomRight.y)

        if (x2 < x1) or (y2 < y1):
            return RectFromCorners(Point(0, 0), Point(0, 0))

        return RectFromCorners(Point(x1, y1), Point(x2, y2))

    def adjustBounds(self, otherRect):
        """
        Return part of this rect that is within bounds of the other
        """

        # If this rect intersecting with other rect
        if self.hasIntersectionWith(otherRect):
            # Get intersection rect and adjust this rect based on intersecting box
            intersectRect = self.intersect(otherRect)
            self.x = intersectRect.x
            self.y = intersectRect.y
            self.width = intersectRect.width
            self.height = intersectRect.height

    def overlap(self, otherRect, overlapMethod='jaccard'):
        """
        Compute the Jaccard similarity coefficient (jaccard) or
        Szymkiewicz-Simpson coefficient (ss) of this box with other
        """

        # Compute area of intersection
        intersectArea = self.intersect(otherRect).area()

        denomArea = 0
        if overlapMethod == 'jaccard':
            # If Jaccard, denominator is the union of the areas
            denomArea = self.area() + otherRect.area() - intersectArea
        elif overlapMethod == 'ss':
            # If Szymkiewicz-Simpson, denominator is the min of the areas
            denomArea = min(self.area(), otherRect.area())
        else:
            print "Unknown overlap method."

        # Compute overlap
        overlap = 0
        if denomArea != 0:
            overlap = float(intersectArea) / float(denomArea)

        return overlap

    def boundingBoxWith(self, otherRect):
        """
        Return the smallest Rect that contains both this Rect and the other one.
        """
        bottomRight = self.br()
        otherBottomRight = otherRect.br()

        x1 = min(self.x, otherRect.x)
        x2 = max(bottomRight.x, otherBottomRight.x)
        y1 = min(self.y, otherRect.y)
        y2 = max(bottomRight.y, otherBottomRight.y)

        return RectFromCorners(Point(x1, y1), Point(x2, y2))

    def distanceTo(self, otherRect):
        """
        Return the distance between this box and that one.
        """
        distance = 0

        br = self.br()
        otherBr = otherRect.br()

        if br.x < otherRect.x:
            distance = (otherRect.x - br.x) ** 2
        elif self.x > otherBr.x:
            distance = (self.x - otherBr.x) ** 2

        if br.y < otherRect.y:
            distance += (otherRect.y - br.y) ** 2
        elif self.y > otherBr.y:
            distance += (self.y - otherBr.y) ** 2

        return sqrt(distance)

    def scaleFromTl(self, scaleFactor):
        return RectFromDimensions(self.tl(), self.width * scaleFactor, self.height * scaleFactor)


    def scaleFromCenter(self,scaleFactor):
        """
        Scale bounding box proportionally by scale factor in the both x and y directions.
        """
        center = self.tl() + Point(self.width / 2.0, self.height/2.0)
        shiftX = self.width * scaleFactor / 2.0
        shiftY = self.height * scaleFactor / 2.0
        newTl = center - Point(shiftX, shiftY)

        return RectFromDimensions(newTl, self.width * scaleFactor, self.height * scaleFactor)


    def offset(self, point):
        """
        Get a Rect that is equivalent to this one offset by the given point.
        """
        return RectFromDimensions(self.tl() + point, self.width, self.height)

    def __eq__(self, other):
        return self.x == other.x and \
               self.y == other.y and \
               self.width == other.width and \
               self.height == other.height

    # Because aparently this isn't the default implementation?
    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "(%s, %s, %s, %s)" % (self.x, self.y, self.br().x, self.br().y)

    def __mul__(self,value):
        """
        Multiply by a scalar from right.
        """
        return Rect(self.x*value, self.y*value, self.width*value, self.height*value)

    def __rmul__(self,value):
        """
        Multiply by a scalar from left.
        """
        return self * value


def GetArrayRegion(ndarray, rect):
    """
    Get a rectangular region from an ndArray.

    You can write back to the returned region by doing things like:
    region[:] = 4
    region[:] |= 42
    """
    br = rect.br()
    return ndarray[rect.y:br.y, rect.x:br.x]

def RectFromCorners(tl, br):
    """
    Construct a Rect from a pair of Points (top left and bottom right)
    """
    return Rect(tl.x, tl.y, br.x - tl.x, br.y - tl.y)

def RectFromDimensions(tl, width, height):
    """
    Construct a rect given its top-left, its width, and its height.
    """
    return Rect(tl.x, tl.y, width, height)

def RectFromCenterDimensions(center, width, height):
    """
    Construct a rect given its center, its width, and its height.
    """
    return Rect(center.x-width/2.0, center.y-height/2.0, width, height)

# Mirrors of two native Rect types. You can pass these anywhere a cv-or-sv::Rect of type int or
# float is required. No evil intermediate copying madness required.
# Use these subclasses in cases where you need a Rect to be passable to native code.
class Rectf(Rect, Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
        ('width', c_float),
        ('height', c_float),
    ]

    def __init__(self, x, y, width, height):
        Structure.__init__(self, x, y, width, height)


class Recti(Rect, Structure):
    _fields_ = [
        ('x', c_int),
        ('y', c_int),
        ('width', c_int),
        ('height', c_int),
    ]

    def __init__(self, x, y, width, height):
        Structure.__init__(self, x, y, width, height)
