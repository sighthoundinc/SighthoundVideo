#*****************************************************************************
#
# Point.py
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

from math import sqrt
from ctypes import Structure, c_float, c_int

"""
An OpenCV-like Point class. Abstractions are your friend.
Due to laziness, some operations of OpenCV's Point are left as an exercise for the reader.
"""

class Point(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def inRect(self, rect):
        """
        Return true iff this point lies within the given Rect.

        OpenCV convention has that the top left boundaries of a rect are inclusive, while
        the bottom right ones are not.
        """
        if self.x < rect.x or self.x > rect.x + rect.width:
            return False

        if self.y < rect.y or self.y > rect.y + rect.height:
            return False

        return True

    def distanceTo(self, otherPoint):
        """
        Calculate Euclidean distance between two points
        """
        return sqrt((self.x - otherPoint.x) ** 2 + (self.y - otherPoint.y) ** 2)

    def __add__(self, otherPoint):
        """
        Returns a new point that is this one offset by that one.
        """
        return Point(self.x + otherPoint.x, self.y + otherPoint.y)

    def __sub__(self, otherPoint):
        """
        Returns a new point that is this one offset by that one.
        """
        return Point(self.x - otherPoint.x, self.y - otherPoint.y)

    def __iadd__(self, otherPoint):
        """
        Offset this point by that point (mutating this Point)
        """
        self.x += otherPoint.x
        self.y += otherPoint.y

    def __isub__(self, otherPoint):
        """
        Offset this point by that point, negatively (mutating this Point)
        """
        self.x -= otherPoint.x
        self.y -= otherPoint.y

    def __eq__(self, otherPoint):
        return self.x == otherPoint.x and self.y == otherPoint.y

    def __neg__(self):
        return Point(-self.x, -self.y)

    def __div__(self,scalar):
        """
        Divide each coordinate by a scalar value.
        """
        return Point(self.x/scalar, self.y/scalar)

    def __mul__(self,scalar):
        """
        Multiply each coordinate by a scalar value.
        """
        return Point(self.x*scalar, self.y*scalar)

    def __repr__(self):
        """
        Return print string of the landmark points.
        """
        return "(%d, %d)" % (self.x,self.y)

class Pointi(Point,Structure):
    _fields_ = [
        ('x', c_int),
        ('y', c_int)
    ]

    def __init__(self, x, y):
        Structure.__init__(self, x, y)

class Pointf(Point,Structure):
        _fields_ = [
            ('x', c_float),
            ('y', c_float)
        ]

        def __init__(self, x, y):
            Structure.__init__(self, x, y)

def maxPoint(points):
    """
    Returns maximum x and y coordinate from list of points.
    """
    maxPoint = Point(0, 0)
    for point in points:
        maxPoint.x = max(point.x, maxPoint.x)
        maxPoint.y = max(point.y, maxPoint.y)

    return maxPoint

def minPoint(points):
    """
    Return minimum x and y coordinate from list of points.
    """
    minPoint = Point(1000000000000, 1000000000000)
    for point in points:
        minPoint.x = min(point.x, minPoint.x)
        minPoint.y = min(point.y, minPoint.y)

    return minPoint
