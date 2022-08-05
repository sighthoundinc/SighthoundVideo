#*****************************************************************************
#
# RandomRange.py
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

import random

def randomRange(minVal, maxVal):
    """ Creates an array of random integers, out of a range. Each number is only
    present once. Memory needs to be allocated for the whole range, so large
    ranges will be heavy on the system.

    @param minVal The lowest number.
    @param maxVal The highest number (exclusive).
    """
    result = range(minVal, maxVal)
    i = 0
    c = len(result)
    while i < c:
        ri = random.randint(0, c - 1)
        swap = result[i]
        result[i] = result[ri]
        result[ri] = swap
        i += 1
    return result
