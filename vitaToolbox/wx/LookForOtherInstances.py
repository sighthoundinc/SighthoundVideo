#!/usr/bin/env python

#*****************************************************************************
#
# LookForOtherInstances.py
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

# Common 3rd-party imports...
import wx



###########################################################
def lookForOtherInstances(mainWindowName=None):
    """Check of other instances; if they're running, switch 'em to front.

    ...note that switching to front only happens on Windows.  On Mac, we don't
    really have this problem--the OS won't allow you to run the app twice.

    @param  mainWindowName        The window name to bring to the front, if
                                  we're not first.  If none, we'll try the app
                                  name.
    @return singleIntanceChecker  If non-None, keep a reference to this as long
                                  as you're running.  If None, this wasn't the
                                  first instance.
    """
    appName = wx.GetApp().GetAppName()

    if mainWindowName is None:
        mainWindowName = appName

    if type(mainWindowName) == str:
        mainWindowName = mainWindowName.decode('utf-8')

    # Make an object to check for a single instance of apps.  We
    # temporarily disable logs so we never see a "stale lock file" error...
    log = wx.LogNull()
    singleInstanceChecker = \
        wx.SingleInstanceChecker("%s-%s" % (appName, wx.GetUserId()))
    del log

    if singleInstanceChecker.IsAnotherRunning():
        # On Windows, try to bring the other process to the front...
        # ...note that we assume the class is wxWindowClassNR, which we got
        # from:
        #   hwnd = self.GetHandle()
        #   className = ctypes.create_unicode_buffer(1024)
        #   result = ctypes.windll.user32.GetClassNameW(hwnd, className, 1024)
        #   print className.value
        if wx.Platform == '__WXMSW__':
            hwnd = ctypes.windll.user32.FindWindowW(u'wxWindowClassNR', #PYCHECKER OK: No module attribute (windll) found
                                                    mainWindowName)
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd) #PYCHECKER OK: No module attribute (windll) found

        # OK, return None--we weren't first...
        return None

    # Return the checker, for the caller to hold...
    return singleInstanceChecker


