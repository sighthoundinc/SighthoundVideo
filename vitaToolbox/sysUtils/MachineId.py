#!/usr/bin/env python

#*****************************************************************************
#
# MachineId.py
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

import sys, netifaces, hashlib

###############################################################################

_kMachineID = None

###############################################################################

def _machine_id_osx():
    """ Get the serial number available under OSX through the IOkit service.

    @return The machine identifier, or None if that didn't work out.
    """

    from ctypes import cdll, util, c_void_p, c_char_p, c_int32, c_uint32

    iokit = cdll.LoadLibrary(util.find_library("IOKit"))
    coref = cdll.LoadLibrary(util.find_library("CoreFoundation"))

    iokit.IOServiceGetMatchingService.argtypes = [c_void_p, c_void_p]
    iokit.IOServiceGetMatchingService.restype = c_void_p
    iokit.IOServiceMatching.restype = c_void_p
    mservice = iokit.IOServiceGetMatchingService(c_void_p.in_dll(iokit,
        "kIOMasterPortDefault"),
        iokit.IOServiceMatching("IOPlatformExpertDevice"))

    allocator = c_void_p.in_dll(coref, "kCFAllocatorDefault")

    coref.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_int32]
    coref.CFStringCreateWithCString.restype = c_void_p
    key = coref.CFStringCreateWithCString(allocator,
        "IOPlatformSerialNumber".encode("mac_roman"), 0)

    iokit.IORegistryEntryCreateCFProperty.restype = c_void_p
    iokit.IORegistryEntryCreateCFProperty.argtypes = [c_void_p, c_void_p,
                                                      c_void_p, c_uint32]
    serNum = iokit.IORegistryEntryCreateCFProperty(mservice, key, allocator, 0);

    if serNum:
        coref.CFStringGetCStringPtr.argtypes = [c_void_p, c_uint32]
        coref.CFStringGetCStringPtr.restype = c_char_p
        result = coref.CFStringGetCStringPtr(serNum, 0)

    iokit.IOObjectRelease.argtypes = [c_void_p]
    iokit.IOObjectRelease(mservice)

    return result


###############################################################################
def _machine_id_win():
    """ Get the serial number available under Windows via the registry value
    HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\MachineGuid.

    @return The machine identifier, None if the registry didn't yield anything.
    """
    from _winreg import OpenKey, QueryValueEx, CloseKey
    from _winreg import HKEY_LOCAL_MACHINE, KEY_READ
    try:
        key = OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
          KEY_READ | 0x0100) # _winreg.KEY_WOW64_64KEY is Python 2.7
        return QueryValueEx(key, "MachineGuid")[0]
    finally:
        if key is not None:
            try:
                CloseKey(key)
                pass
            except:
                pass

    return None


###############################################################################
def _machine_id_fallback(logger=None):
    """ Gets the most decent MAC address as the machine ID.

    @param logger To report (unexpected) issues during gathering.
    @return MAC address or None of nothing useful could be found.
    """
    found = []
    try:
        for interfaceName in netifaces.interfaces():
            interfaceAddresses = netifaces.ifaddresses(interfaceName)
            linkAddresses = interfaceAddresses.get(netifaces.AF_LINK, None)
            if linkAddresses is None:
                continue
            macs = []
            for linkAddress in linkAddresses:
                mac = linkAddress.get('addr', None)
                if mac:
                    if 0 == (2 & int(mac[0:2], 16)):
                        macs.append(mac)
            if len(macs) > 0:
                found.append((interfaceName, macs))
    except:
        if logger:
            logger.error("issue looking at MAC addresses (%s)" % sys.exc_info()[1])
    if not found:
        return None
    mac = None
    if "win32" == sys.platform:
        # Win32 interface names (e.g. "{E9286221-C46E-47A2-A25C-B966130BED05}")
        # are not suitable for heuristics, at least not with this method ...
        pass
    else:
        for n in xrange(0,31):
            preferred = "en%d" % n
            for f in found:
                if preferred == f[0]:
                    mac = f[1][0]
                    break
            if mac:
                break
    if not mac:
        mac = found[0][1][0]
    return mac.lower()


###############################################################################
def machineId(force=True,logger=None):
    """ Gets the machine identifier. Detects it once, returns cached copies
    afterwards, unless forced. An attempt will be made every time if no former
    attempt has been successful so far.

    @param force True if the detection should run again.
    @param logger To log error messages to. Can be None.
    @return The machine ID or None if detection failed.
    """
    global _kMachineID
    if force or _kMachineID is None:
        try:
            if "win32" == sys.platform:
                mid = _machine_id_win().lower()
            else:
                mid = _machine_id_osx().lower()
            _kMachineID = hashlib.sha1(mid).hexdigest()
        except:
            if logger is not None:
                import traceback
                logger.error("cannot get machine ID: %s" % sys.exc_info()[1])
                logger.error(traceback.format_exc())
    if not _kMachineID:
        _kMachineID = _machine_id_fallback(logger)
    return _kMachineID


###############################################################################

if __name__ == "__main__":
    import time, logging
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(sh)
    logger = logging.getLogger("main")
    tm = time.time()
    loops = int(sys.argv[1]) if 1 < len(sys.argv) else 10000
    for i in xrange(0, loops):
        mid = machineId(True, logger)
    print "machine ID is '%s', %.2f calls/second" % \
        (mid, loops/max(1, (time.time() - tm)))
        # (got 1800 on OSX and 50K on Win8)
