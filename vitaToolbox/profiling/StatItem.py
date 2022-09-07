#*****************************************************************************
#
# StatItem.py
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

##############################################################################
""" Class representing a numerical statistical item, allowing
    to calculate its min/max/average
"""
class StatItem(object):
    ###########################################################
    def __init__(self, name, minF="%d", maxF="%d", avgF="%.1f"):
        self._name = name
        self._minFormat = minF
        self._maxFormat = maxF
        self._avgFormat = avgF
        self._limit = None
        self._reset()


    ###########################################################
    def __str__(self):
        if self._count == 0:
            return self._name+"=n/a"

        minVal = ""
        maxVal = ""
        avgVal = ""
        oorVal = ""
        if self._minFormat is not None:
            minVal = ("min=" + self._minFormat + ",") % self._min
        if self._maxFormat is not None:
            maxVal = ("max=" + self._maxFormat + ",") % self._max
        if self._avgFormat is not None:
            avgVal = ("avg=" + self._avgFormat + ",") % ( self._sum / self._count )
        if self._limit is not None and self._outOfRangeCount > 0:
            oorVal = ("outOfRange=%d,") % self._outOfRangeCount
        return "%s=[%s%s%s%s]" % (self._name, minVal, maxVal, avgVal, oorVal)

    ###########################################################
    def _reset(self):
        self._count = 0
        self._max = 0
        self._min = 0
        self._sum = 0
        self._outOfRangeCount = 0

    ###########################################################
    def reset(self):
        retval = str(self)
        self._reset()
        return retval

    ###########################################################
    def count(self):
        return self._count

    ###########################################################
    def min(self):
        return self._min

    ###########################################################
    def max(self):
        return self._max

    ###########################################################
    def avg(self):
        return self._sum / self._count if self._count > 0 else 0

    ###########################################################
    def setFormat(self, name, value):
        if name == "min":
            self._minFormat = value
        elif name == "max":
            self._maxFormat = value
        elif name == "avg":
            self._avgFormat = value
        else:
            raise Exception("Invalid stats item name")

    ###########################################################
    def setLimit(self, limit):
        self._limit = limit

    ###########################################################
    def report(self, value):
        self._count = self._count + 1
        self._sum = self._sum + value
        if value < self._min:
            self._min = value
        if value > self._max:
            self._max = value
        if self._limit is not None:
            if value < self._limit[0] or value > self._limit[1]:
                self._outOfRangeCount += 1
