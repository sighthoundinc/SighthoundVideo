#!/usr/bin/env python

#*****************************************************************************
#
# CatchCCrashes.py
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

if sys.platform == 'win32':
    from CatchCCrashesWin import catchCCrashes
    from CatchCCrashesWin import setSilentCrashHandler
else:
    # TODO: Implement for Mac.
    def catchCCrashes():
        pass
    def setSilentCrashHandler():
        pass


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "Registering for crashes..."
    catchCCrashes()
    print "...registered!"

    import ctypes
    pz = ctypes.cast(0x04, ctypes.POINTER(ctypes.c_int))

    print "I'm gonna crash.  Really, I am!"
    print pz.contents
    print "...oh, somehow I didn't crash.  Am I dreaming?"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main(*sys.argv[2:])
    else:
        print "Try calling with 'test' as the argument."
