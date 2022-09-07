#!/usr/bin/env python

#*****************************************************************************
#
# FrontEndLaunchpad.py
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

# This file serves a few purposes:
# - it is the target for the obfuscator--it gets the obfuscator to do both
#   the front end and back end together...  Because of this, it needs to live
#   in the root of the smartvideo directory structure.
# - It is the target for py2exe and routes calls between the front end and
#   the back end...  This is useful so we can have one executable that can
#   launch either the front end or the back end.
# - It handles a handful of things related to being a frozen app on Windows.

# Special imports to support all of our hacks.
# NOTE: Most other imports belong below!
import os
import sys
import traceback, tempfile, time, uuid

_kIsWin = "win32" == sys.platform


def get_utf8_arguments_windows_only():
    # Fix for [SV-194]:
    # <http://bugs.python.org/issue1602>
    #   -- Shows over 7 years worth of developers arguing over this bug.
    # <http://bugs.python.org/issue2128>
    #   -- Provides code workaround for Python 2.X (fixed in Python 3.X).
    # The MSW consoles (CMD and PowerShell) do not support unicode input and
    # output properly. Because of this, the arguments supplied to the
    # interpreter might very well be in unicode, but the interpreter will
    # translate it into ASCII because Microsoft doesn't believe in sanity and
    # standards. To fix this, we get the command line arguments in unicode
    # directly by using win32 API calls. Then we do some small modifications
    # and assign to 'sys.argv' so that it can be available app-wide.

    from ctypes import WINFUNCTYPE, windll, POINTER, byref, c_int
    from ctypes.wintypes import LPWSTR, LPCWSTR
    GetCommandLineW = WINFUNCTYPE(LPWSTR)(("GetCommandLineW", windll.kernel32))
    CommandLineToArgvW = WINFUNCTYPE(POINTER(LPWSTR), LPCWSTR, POINTER(c_int)) \
        (("CommandLineToArgvW", windll.shell32))
    argc = c_int(0)
    argv_unicode = CommandLineToArgvW(GetCommandLineW(), byref(argc))
    argv = [argv_unicode[i].encode('utf-8') for i in xrange(0, argc.value)]

    if not hasattr(sys, 'frozen'):
        # If this is an executable produced by py2exe or bbfreeze, then it will
        # have been invoked directly. Otherwise, unicode_argv[0] is the Python
        # interpreter, so skip that.
        argv = argv[1:]

        # Also skip option arguments to the Python interpreter.
        while len(argv) > 0:
            arg = argv[0]
            if not arg.startswith(u"-") or arg == u"-":
                break
            argv = argv[1:]
            if arg == u'-m':
                # sys.argv[0] should really be the absolute path of the module source,
                # but never mind
                break
            if arg == u'-c':
                argv[0] = u'-c'
                break
    # Make our changes available app-wide...
    sys.argv = argv

if hasattr(sys, 'frozen'):
    if _kIsWin:
        get_utf8_arguments_windows_only()


# TODO: Do we still need this?  All this is doing is forcing linecache.getline
#       to return an emptry string if it's ever used.  According to the python
#       docs, linecache.getline is used to retrieve the line number of source
#       code. However, we don't use this functionality _anywhere_ in our app.
#       I can't think of any reason why we would want this, except that maybe
#       this affects the way tracebacks work (maybe? I don't know). It does no
#       harm keeping it here, but if it's not needed, it should be removed.
# Swiped from py2app's __boot__.py for use when we're launching the backend.
def _disable_linecache():
    import linecache
    def fake_getline(*args, **kwargs):
        return ''
    linecache.orig_getline = linecache.getline
    linecache.getline = fake_getline


# CxFreeze makes the app's working directory start in the "MacOS" directory; We
# change our working directory to the Resources directory so that our bmp's and
# and other resource files can be found and loaded.
# ...we also call _disable_linecache(), which also seems to be done by the
# normal __boot__ script.
if hasattr(sys, 'frozen'):
    if not _kIsWin:
        os.chdir(os.path.join(os.path.dirname(sys.executable), '..', 'Resources'))
    else:
        os.chdir(os.path.dirname(sys.executable))
    _disable_linecache()


from multiprocessing import freeze_support

# Set a handler to catch c crashes in all processes...
from vitaToolbox.loggingUtils.CatchCCrashes import catchCCrashes
catchCCrashes()

errFileTag = "error"

def main():

    try:
        if (len(sys.argv) > 1) and (sys.argv[1] == '--backEnd'):
            errFileTag = "launch"
            from backEnd import BackEndApp
            BackEndApp.main(*sys.argv[2:])
        elif (len(sys.argv) > 1) and (sys.argv[1] == '--quit'):
            errFileTag = "quit"
            from frontEnd.BackEndClient import sendCommand
            sendCommand('quit')
        elif (len(sys.argv) > 1) and (sys.argv[1] == '--sound'):
            errFileTag = "sound"
            from backEnd.responses.SoundResponse import playSound
            playSound(sys.argv[2])
        elif (len(sys.argv) > 1) and (sys.argv[1] == '--upnp'):
            from vitaToolbox.networking import UpnpUiTest
            UpnpUiTest.main()
        elif (len(sys.argv) > 1) and (sys.argv[1] == '--webserver'):
            from backEnd.WebServer import runNginx
            runNginx(*sys.argv[2:-1])
        elif (len(sys.argv) > 1) and (sys.argv[1] == '--xnat'):
            from xnat.xnat import runXNAT
            runXNAT(sys.argv[2], *sys.argv[3:-1])
        elif (len(sys.argv) > 1) and (sys.argv[1] == '--pcap'):
            from backEnd.PacketCaptureStream import doRunPacketCapture
            doRunPacketCapture(*sys.argv[2:])
        else:
            errFileTag = "launch"
            from frontEnd import FrontEndApp
            FrontEndApp.main()
    except:
        try:
            dump = traceback.format_exc()
            dumpFile = "sighthound_%s_%d_%s.log" % (errFileTag,
                int(time.time() * 1000), uuid.uuid4().hex)
            fl = open(os.path.join(tempfile.gettempdir(), dumpFile), "w")
            fl.write(dump)
            fl.close()
        except:
            pass

if __name__ == '__main__':
    # This supports multiprocessing on Windows; seems OK to run on Mac too...
    freeze_support()
    main()
