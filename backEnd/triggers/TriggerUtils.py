#!/usr/bin/env python

#*****************************************************************************
#
# TriggerUtils.py
#     Various trigger-related utility functions
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


from ctypes import POINTER, Structure, c_int

from vitaToolbox.ctypesUtils.LoadLibrary import LoadLibrary


_libName = 'optsearches'
_searchlib = LoadLibrary(None, _libName)


###############################################################
class BBOX(Structure):
    """The bbox format used by the c library."""
    _fields_ = [("x1", c_int),
                ("y1", c_int),
                ("x2", c_int),
                ("y2", c_int)]



_searchlib.is_obj_inside.argtypes = [BBOX, c_int, POINTER(BBOX), c_int]
_searchlib.is_obj_inside.restype = c_int
_searchlib.did_obj_cross.argtypes = [BBOX, BBOX, BBOX, c_int, c_int]
_searchlib.did_obj_cross.restype = c_int

kTrackPointStrToInt = {'center' : 0,
                       'top'    : 1,
                       'bottom' : 2,
                       'left'   : 3,
                       'right'  : 4}

kDirectionStrToInt = {'left'  : 0,
                      'right' : 1,
                      'any'   : 2}


###############################################################
def optimizedDidObjCrossLine(prevBbox, curBbox, boundary, location, direction):
    """Determine whether an object crossed a boundary.

    @param  prevBbox   A BBOX of the bounding box at the previous frame.
    @param  curBbox    A BBOX of the bounding box at the current frame.
    @param  boundary   A BBOX defining the line segment to test.
    @param  location   A value from kTrackPointStrToInt.
    @param  direction  A value from kDirectionStrToInt.
    @return didCross   True if the object tracking point crossed boundary.
    """
    retVal = _searchlib.did_obj_cross(prevBbox, curBbox, boundary, location,
                                      direction)
    if retVal == 1:
        return True
    return False


###############################################################
def optimizedIsPointInside(bbox, trackLocation, cSegments, numSegments):
    """Determine whether a point on an object is inside a region.

    @param  bbox           A BBOX struct of the object's bounding box.
    @param  trackLocation  The location on the point to track, must be a
                           value from kTrackPointStrToInt.
    @param  cSegments      A ctypes Array of segments defining the array.
    @param  numSegments    The number of segments in cSegments.
    @return isInside       True if the point is inside the region, else False.
    """
    retVal = _searchlib.is_obj_inside(bbox, trackLocation, cSegments,
                                      numSegments)
    if retVal == 1:
        return True
    return False


###############################################################
def getBboxTrackingPoint(bbox, location='center'):
    """Return a point on the bbox

    @param  bbox      Coordinates for the top left and bottom right of a rect
    @param  location  The location on the box to track
    @return point     X,Y coordinates of the requested point
    """
    assert location in kTrackPointStrToInt.keys()

    # Remember that (x2, y2) on bbox are _outside_ the object; adjust so they're
    # not for the math below...
    bbox = (bbox[0], bbox[1], bbox[2]-1, bbox[3]-1)

    if location == 'center':
        return ((bbox[2]+bbox[0])/2, (bbox[3]+bbox[1])/2)
    elif location == 'top':
        return ((bbox[2]+bbox[0])/2, bbox[1])
    elif location == 'bottom':
        return ((bbox[2]+bbox[0])/2, bbox[3])
    elif location == 'left':
        return (bbox[0], (bbox[3]+bbox[1])/2)
    elif location == 'right':
        return (bbox[2], (bbox[3]+bbox[1])/2)