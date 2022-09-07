#!/usr/bin/env python

#*****************************************************************************
#
# OverlapSizer.py
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

# Common 3rd-party imports...
import wx

# Toolbox imports...

# Local imports...

# Constants...


##############################################################################
class OverlapSizer(wx.Sizer):
    """A sizer that puts all of its children right on top of one another.

    This sizer effectively lets you have your children overlap each other.
    Every child that you add to this sizer will be assigned the exact same
    location and size: all the full size of the sizer.

    This could be handy for dynamic UI (where the set of UI elements change
    depending on what is showing) or just for allowing you to have an object
    that is centered and another that is right aligned.

    Note: the min size of this sizer is the combination of the largest width
    of any child and the largest height of any child.

    Note that the flags / proportions of all children are ignored.  All children
    are set to full size.  No borders are looked at.  No centering.  No nothing.
    """
    ###########################################################
    def __init__(self, shouldCountHidden=False):
        """OverlapSizer constructor.

        @param  shouldCountHidden  If True, hidden children still count in
                                   our min size.
        """
        super(OverlapSizer, self).__init__()
        self._shouldCountHidden = shouldCountHidden

    ###########################################################
    def CalcMin(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Calculate the minimum space that this sizer needs.

        This _must_ be called before RecalcSizes(), since we cache values here
        and assume they're up to date in RecalcSizes().

        @return size  The minimum size.
        """
        minWidth, minHeight = (-1, -1)

        # Get our children...  Return immediately if there are none...
        allChildren = self.GetChildren()
        if self._shouldCountHidden:
            children = allChildren
        else:
            children = [child for child in allChildren if child.IsShown()]
        if not children:
            return (-1, -1)

        # Calculate mins
        mins = [x.CalcMin() for x in children]
        minWidths  = [x[0] for x in mins if x[0] != -1]
        minHeights = [x[1] for x in mins if x[1] != -1]

        return (max(minWidths), max(minHeights))


    ###########################################################
    def RecalcSizes(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Size up all of our children.

        This is called whenever we need to size our children, and is the
        guts of the sizer.
        """
        # Get our full size...
        p = self.GetPosition()
        s = self.GetSize()

        # Set all the children
        for child in self.GetChildren():
            child.SetDimension(p, s)


