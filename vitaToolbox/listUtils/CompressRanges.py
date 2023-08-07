#!/usr/bin/env python

#*****************************************************************************
#
# CompressRanges.py
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


##############################################################################
def compressRanges(rangeList):
    """Take a list of ranges and compress it so there is no overlap.

    Notes:
    - This function assumes the list is already sorted.
    - Does not change the input list.

    >>> compressRanges([(1,4), (2,6), (9,20), (21,23)])
    [(1, 6), (9, 23)]

    >>> compressRanges([(0, 12), (1,4), (2,6), (9,20), (21,23)])
    [(0, 23)]

    >>> compressRanges([(0, 12), (1,4), (2,6), (9,20), (22,23)])
    [(0, 20), (22, 23)]

    >>> compressRanges([(0,0), (1,1), (2,2), (4,4)])
    [(0, 2), (4, 4)]

    >>> l = [(0,0), (1,1), (2,2), (4,4)]
    >>> compressRanges(l)
    [(0, 2), (4, 4)]
    >>> l
    [(0, 0), (1, 1), (2, 2), (4, 4)]

    >>> compressRanges([(0, 992236), (141074, 160208), (206174, 223874), (255708, 289308), (297608, 315674), (325408, 374974), (389608, 418608), (419774, 437941), (440408, 469308), (491674, 513074), (517041, 536908), (552008, 614708), (631141, 648974), (650408, 669141), (755841, 786674), (815908, 834741), (867141, 921141)])
    [(0, 992236)]

    @param  rangeList         A list of ranges to compress.
    @return compressedRanges  A list of compressed ranges, as described above.
    """
    # Handle the empty list...
    if not rangeList:
        return []

    start, end = rangeList[0]
    compressedRanges = [(start, end)]

    for i in xrange(1, len(rangeList)):
        start, end = rangeList[i]
        prevStart, prevEnd = compressedRanges[-1]

        if prevEnd >= start-1:
            compressedRanges[-1] = (prevStart, max(prevEnd, end))
        else:
            compressedRanges.append((start, end))


    return compressedRanges


##############################################################################
def test_main():
    """OB_REDACT
    Our main function, which runs test code
    """
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    test_main()
