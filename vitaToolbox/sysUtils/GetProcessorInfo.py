#!/usr/bin/env python

#*****************************************************************************
#
# GetProcessorInfo.py
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


import os
import sys


###############################################################
def getProcessorInfo():
    """Return a string describing the system processor."""
    if 'darwin' == sys.platform:
        return _getProcessorInfoMac()
    return _getProcessorInfoWin()


###############################################################
def _getProcessorInfoMac():
    """Return a string describing the system processor."""
    model = os.popen('sysctl -n hw.model').read()
    cpu = os.popen('sysctl -n machdep.cpu.brand_string').read()
    return "%s - %s" % (model.strip(), cpu.strip())


###############################################################
def _getProcessorInfoWin():
    """Return a string describing the system processor."""
    # Strange import to avoid obfuscator warnings on Mac, where this doesn't
    # exist.
    # ...need to also make sure that obfuscator doesn't obfuscate any of the
    # identifiers related to this module.
    _winreg = object()
    exec 'import _winreg'

    identifier = ''
    procName = ''
    numKeys = 0

    try:
        key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                              r'HARDWARE\DESCRIPTION\System\CentralProcessor\0')
        try:
            identifier = _winreg.QueryValueEx(key, 'Identifier')[0]
        except Exception:
            pass
        try:
            procName = _winreg.QueryValueEx(key, 'ProcessorNameString')[0]
        except Exception:
            pass
        try:
            key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                              r'HARDWARE\DESCRIPTION\System\CentralProcessor')
            while True:
                # This will eventually throw an exception when we run out of
                # processor keys.
                _winreg.EnumKey(key, numKeys)
                numKeys += 1
        except Exception:
            pass

    except Exception:
        pass

    return "%s - %s - Num procs: %s" % (identifier, procName, str(numKeys))

