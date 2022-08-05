#!/usr/bin/env python

#*****************************************************************************
#
# CatchCCrashesWin.py
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

# Python imports...
import ctypes
import os
import sys
import traceback


# Crash marker: only handle a crash once, otherwise we risk a loop.
_crashed = False

##############################################################################
def catchCCrashes():
    """Catch crashes that happen in C code and print out debugging info.

    All we do here is register ourselves as a handler for crashes.
    """
    ctypes.windll.kernel32.SetUnhandledExceptionFilter(
        _cUnhandledExceptionFilter
    )


##############################################################################
def setSilentCrashHandler():
    """Catch crashes that happen in C code and print a message and exit the app silently.

    All we do here is register ourselves as a noop handler for crashes.
    """
    def silentUnhandledExceptionFilter(exceptionInfo):
        global _crashed
        if not _crashed:
            _crashed = True
            print >>sys.stderr, "Silent crash handler executed: Unhandled exception!"
            traceback.print_exc()
        os._exit(0)
    TOPLEVEL_EXCEPTION_FILTER_FN = ctypes.WINFUNCTYPE(None, ctypes.c_void_p)
    cSilentUnhandledExceptionFilter = \
        TOPLEVEL_EXCEPTION_FILTER_FN(silentUnhandledExceptionFilter)
    ctypes.windll.kernel32.SetUnhandledExceptionFilter(
        cSilentUnhandledExceptionFilter
    )


##############################################################################
def _unhandledExceptionFilter(exceptionInfo):
    """Our actual handler for crashes.

    We print a traceback here.  This assumes that someone is logging stderr
    to someplace reasonable...
    """
    # TODO: Get more info out of exceptionInfo by looking at the contents...
    #       http://msdn.microsoft.com/en-us/library/ms680634%28VS.85%29.aspx
    #
    # TODO: Really legit to do this if we're called from a different thread,
    #       especially if python doesn't know anything about it (like if it's
    #       created by pthreads?)
    #
    # TODO: it might be better to have all of this in C, but then we cannot
    #       really get to the callstack, unless we use native Python functions
    #       and some structured exception handling for further protection ...
    global _crashed
    if not _crashed:
        _crashed = True
        print >>sys.stderr, "Unhandled exception!"
        traceback.print_exc()
        raise
    #return 1

# Make a CTypes-wrapped pointer to our exception handler...
TOPLEVEL_EXCEPTION_FILTER_FN = ctypes.WINFUNCTYPE(None, ctypes.c_void_p)
_cUnhandledExceptionFilter = \
    TOPLEVEL_EXCEPTION_FILTER_FN(_unhandledExceptionFilter)

