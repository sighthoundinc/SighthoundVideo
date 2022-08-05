#!/usr/bin/env python

#*****************************************************************************
#
# PlatformUtils.py
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

# NOTE: This file exists because the "platform" library that ships with
# python 2.5 is flaky on Windows.  Specifically, the builtin "platform"
# library tries to use win32 APIs (which we don't ship), relies on some command
# line programs, and also tries to parse lots of strings w/ heurstics.

# Python imports...
import sys

try:
    # Use this to figure out info about Windows.  From looking at platform
    # code and python docs, this returns:
    # - major
    #    4 = 95, 98, ME
    #    5 = 2000, XP, 2003 Server
    #    6 = Vista / Windows 7
    # - minor (shown with the major before the period)
    #    4.0 = 95
    #    4.10 = 98
    #    4.90 = ME
    #    5.0 = 2000
    #    5.1 = XP
    #    5.2 = 2003 Server
    #    6.0 = Vista
    #    6.1 = Windows 7
    # - build
    #    6001 on my Vista box
    #    2600 on Engineering XP box
    # - platform
    #    0 = Windows 3.1
    #    1 = 95, 98, ME
    #    2 = NT, 2000, XP, Vista, ...
    #    3 = CE
    # - text
    #    'Service Pack 1' on my Vista box
    #    'Service Pack 3' on Engineering XP box

    _windowsVersion = sys.getwindowsversion() #PYCHECKER OK on Mac--Windows only.
except AttributeError:
    # NON-WINDOWS
    # ===========
    import platform

    ###############################################################
    def getPlatformDesc():
        """Return a string describing the platform.

        @return platformDesc  The string describing the platform.
        """
        infoToReturn = [
            platform.platform()
        ]

        # mac_ver() works just fine on windows (and probably Linux?), but
        # returns empty strings...
        release, (version, devStage, nonReleaseVersion), machine = \
            platform.mac_ver()

        if (not version) and (not devStage) and (not nonReleaseVersion):
            if release and machine:
                # Normal Mac
                infoToReturn.append("%s, %s" % (release, machine))
            else:
                # Non-mac?
                pass
        else:
            # Mac w/ extra info...
            infoToReturn.append("%s, (%s, %s, %s), %s" % (
                release, version, devStage, nonReleaseVersion, machine
            ))

        return ', '.join(infoToReturn)


    ###############################################################
    def isWindowsXp():
        """Return True if we're on XP or earlier.

        Technically, this will return True for the following:
        - Windows 2003 Server
        - Windows XP
        - Windows 2000
        ...and anything older.  It won't return True for Vista or later, or any
        non-windows platform.

        @return isWindowsXp  True if we're on XP; False otherwise.
        """
        # We're not on Windows, so no, we're not on XP.
        return False


else:
    # WINDOWS
    # =======

    ###############################################################
    def getPlatformDesc(): #PYCHECKER is confused by top-level if/else
        """Return a string describing the platform.

        @return platformDesc  The string describing the platform.
        """
        major, minor, build, platform, text = _windowsVersion

        return "Windows %d.%d.%d (platform %d), %s" % (
            major, minor, build, platform, text
        )


    ###############################################################
    def isWindowsXp(): #PYCHECKER is confused by top-level if/else
        """Return True if we're on XP or earlier.

        Technically, this will return True for the following:
        - Windows 2003 Server
        - Windows XP
        - Windows 2000
        ...and anything older.  It won't return True for Vista or later, or any
        non-windows platform.

        @return isWindowsXp  True if we're on XP; False otherwise.
        """
        major, _, _, platform, _ = _windowsVersion
        return (platform <= 1) or ((platform == 2) and (major <= 5))

