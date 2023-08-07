#!/usr/bin/env python

#*****************************************************************************
#
# winUtils.py
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

# Python imports...
import ctypes
import sys


##############################################################################
def registerForForcedQuitEvents(closeFunc=None):
    """Register for messages about ctrl+c, logout, etc...

    @param  closeFunc  A function to be called when an event is received.
    @return callbackFunc  The callback created callback function. The caller
                          must maintain a reference to this function or it
                          will go out of scope and no notification will occur.
    """
    if sys.platform == 'darwin':
        # This issue only applies to Vista (and maybe 7?)
        return

    # Create a function that will be our callback handler.
    def f(msgCode):
        _ = msgCode

        try:
            if closeFunc is not None:
                # Call the specified close function if one was provided.
                closeFunc()
        except Exception:
            pass

        # The magic is to return one, claiming we handled this event.
        return 1

    # Create a winfunc and register it as a handler.
    callback = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong)(f) #PYCHECKER OK on Mac--Windows only.
    ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, 1)      #PYCHECKER OK on Mac--Windows only.

    return callback


