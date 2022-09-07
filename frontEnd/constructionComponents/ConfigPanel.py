#!/usr/bin/env python

#*****************************************************************************
#
# ConfigPanel.py
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
import sys

# Common 3rd-party imports...
import wx

# Local imports...

# Constants...


##############################################################################
class ConfigPanel(wx.Panel):
    """The superclass for query construction view configuration panels.

    You won't instantiate one of these directly.

    *IMPORTANT NOTE*: variables starting with underscore ("_") are considered
    only "protected" in this class.  That is, our subclasses may access them.
    """

    ###########################################################
    def __init__(self, parent):
        """ConfigPanel constructor.

        @param  parent                Our parent UI element.
        """
        # Call our super
        super(ConfigPanel, self).__init__(parent)


    ###########################################################
    def getIcon(self):
        """Return the path to the bitmap associated with this panel.

        @return bmpPath  The path to the bitmap.
        """
        raise NotImplementedError


    ###########################################################
    def getTitle(self):
        """Return the title associated with this panel.

        @return title  The title
        """
        raise NotImplementedError


    ###########################################################
    def activate(self):
        """Set this panel as the active one."""
        pass


    ###########################################################
    def deactivate(self):
        """Called before another panel gets activate."""
        pass


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "NO TESTS"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
