#!/usr/bin/env python

#*****************************************************************************
#
# BindChildren.py
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

"""
## @file
Contains misc. utility functions/classes to make working with wxpython easier.
"""

import wx


##############################################################################
def _bindExistingChildren(win, event, handler):
    """Help bindChildren() by binding on all existing children.

    We want this to be a separate function so that we only do the bind on
    EVT_WINDOW_CREATE for the top window.

    @param  win      The window to bind to.
    @param  event    The event, like wx.EVT_LEFT_DOWN.
    @param  handler  The handler, like self.OnClick()
    """
    win.Bind(event, handler)
    for child in win.GetChildren():
        _bindExistingChildren(child, event, handler)


##############################################################################
def bindChildren(win, event, handler):
    """Bind the given handler to the given window and all of its children.

    This will do a "win.Bind(event, handler)" on the given window, then
    recursively do it on the children.  Then, it will register to find out
    about all new children of the window so it can bind to them, too!

    @param  win      The window to bind to.
    @param  event    The event, like wx.EVT_LEFT_DOWN.
    @param  handler  The handler, like self.OnClick()
    """
    # Get all existing children...
    _bindExistingChildren(win, event, handler)

    # Make sure we get all future children.  They cannot escape...
    def bindNewborns(createEvent):
        newborn = createEvent.GetEventObject()
        newborn.Bind(event, handler)
        createEvent.Skip()

    win.Bind(wx.EVT_WINDOW_CREATE, bindNewborns)


