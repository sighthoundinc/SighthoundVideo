#!/usr/bin/env python

#*****************************************************************************
#
# ProcessUtilsWin.py
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
import ctypes.wintypes
import os
import sys

# Maximum size of committed memory (in kB) a process is allowed to consume before
# we shut it down to avoid out-of-memory issues.
# Windows 32-bit processes start experiencing issues at about 1.8GB, so let us restart
# well before that -- at, say, 1.5GB.
if sys.maxint == 2147483647:
    # On 32-bit, keep the limit below 1.5GB
    _kMemoryDieKB = 1500 * 1000
else:
    # On 64-bit, don't go over 4GB, just because we want to stop somewhere
    # Our processes normally should not exceed 500MB
    _kMemoryDieKB = 4000 * 1000

def OB_ASID(a): return a


# Shorthand...
DWORD   = ctypes.wintypes.DWORD
WORD    = ctypes.wintypes.WORD
BOOL    = ctypes.wintypes.BOOL
HANDLE  = ctypes.wintypes.HANDLE
UINT    = ctypes.wintypes.UINT
HMODULE = ctypes.wintypes.HMODULE
PVOID   = ctypes.c_void_p
SIZE_T  = ctypes.c_size_t

MAX_PATH = ctypes.wintypes.MAX_PATH

# Other Windows-related defines...

# ...process constants, from http://msdn.microsoft.com/en-us/library/ms684880(VS.85).aspx
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_TERMINATE = 0x0001


# Priority values, from http://msdn.microsoft.com/en-us/library/windows/desktop/ms686219(v=vs.85).aspx
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
NORMAL_PRIORITY_CLASS = 0x00000020

##############################################################################
class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    """A python adapter for PROCESS_MEMORY_COUNTERS_EX."""
    _fields_ = [
        (OB_ASID("cb"), DWORD),
        (OB_ASID("PageFaultCount"), DWORD),
        (OB_ASID("PeakWorkingSetSize"), SIZE_T),
        (OB_ASID("WorkingSetSize"), SIZE_T),
        (OB_ASID("QuotaPeakPagedPoolUsage"), SIZE_T),
        (OB_ASID("QuotaPagedPoolUsage"), SIZE_T),
        (OB_ASID("QuotaPeakNonPagedPoolUsage"), SIZE_T),
        (OB_ASID("QuotaNonPagedPoolUsage"), SIZE_T),
        (OB_ASID("PagefileUsage"), SIZE_T),
        (OB_ASID("PeakPagefileUsage"), SIZE_T),
        (OB_ASID("PrivateUsage"), SIZE_T),
    ]

##############################################################################
class LANGANDCODEPAGE(ctypes.Structure):
    """A python adapter for LANGANDCODEPAGE."""
    _fields_ = [
        (OB_ASID("language"), WORD),
        (OB_ASID("codePage"), WORD),
    ]


##############################################################################
class VS_FIXEDFILEINFO(ctypes.Structure):
    """A python adapter for VS_FIXEDFILEINFO."""
    _fields_ = [
        (OB_ASID("signature"), DWORD),
        (OB_ASID("strucVersion"), DWORD),
        (OB_ASID("fileVersionMS"), DWORD),
        (OB_ASID("fileVersionLS"), DWORD),
        (OB_ASID("productVersionMS"), DWORD),
        (OB_ASID("productVersionLS"), DWORD),
        (OB_ASID("fileFlagsMask"), DWORD),
        (OB_ASID("fileFlags"), DWORD),
        (OB_ASID("fileOS"), DWORD),
        (OB_ASID("fileType"), DWORD),
        (OB_ASID("fileSubtype"), DWORD),
        (OB_ASID("fileDateMS"), DWORD),
        (OB_ASID("fileDateLS"), DWORD),
    ]


# "import" the calls that we need for easier access below...

# MS docs seem to indicate that some functions moved to kernel32 in Windows 7.
# I don't have Windows 7 to test on, but seems like it's better to be safe...
try:
    enumProcesses = ctypes.windll.psapi.EnumProcesses
    enumProcessModules = ctypes.windll.psapi.EnumProcessModules
    getModuleBaseName = ctypes.windll.psapi.GetModuleBaseNameW
    getModuleFileNameEx = ctypes.windll.psapi.GetModuleFileNameExW
    getProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
except AttributeError:
    enumProcesses = ctypes.windll.kernel32.EnumProcesses
    enumProcessModules = ctypes.windll.kernel32.EnumProcessModules
    getModuleBaseName = ctypes.windll.kernel32.GetModuleBaseNameW
    getModuleFileNameEx = ctypes.windll.kernel32.GetModuleFileNameExW
    getProcessMemoryInfo = ctypes.windll.kernel32.GetProcessMemoryInfo

openProcess = ctypes.windll.kernel32.OpenProcess
closeHandle = ctypes.windll.kernel32.CloseHandle
terminateProcess = ctypes.windll.kernel32.TerminateProcess

getFileVersionInfoSize = ctypes.windll.version.GetFileVersionInfoSizeW
getFileVersionInfo = ctypes.windll.version.GetFileVersionInfoW
verQueryValue = ctypes.windll.version.VerQueryValueW


##############################################################################
def listProcesses():
    """Return a list of all running process IDs.

    Note that this is instantenous--there's no guarantee that a process won't
    have died or have been born by the time you use this list.

    This is based loosely on code from MSDN's "Enumerating All Processes":
      http://msdn.microsoft.com/en-us/library/ms682623(VS.85).aspx

    @return pidList  A list of all running process IDs.
    """
    # We need to pass memory into the kernel for it to fill in.  We start with
    # a really big number, but will grow it as needed...
    tableSize = 1024

    while True:
        processTable = (DWORD * tableSize)()
        processTableBytes = ctypes.sizeof(processTable)
        bytesNeeded = DWORD(0)

        success = enumProcesses(processTable, processTableBytes,
                                ctypes.byref(bytesNeeded)       )
        if not success:
            raise RuntimeError("EnumProcessesFailed")

        if bytesNeeded.value < processTableBytes:
            break
        tableSize *= 2

    numEntries = bytesNeeded.value / ctypes.sizeof(DWORD)
    return processTable[:numEntries]


##############################################################################
def getProcessName(processId):
    """Get the name of the given process.

    Note: this will return None if we don't have access to the name (or run
    into some other sort of trouble).

    This is based loosely on code from MSDN's "Enumerating All Processes":
      http://msdn.microsoft.com/en-us/library/ms682623(VS.85).aspx

    @param  processId  The ID of the process whose name we want.
    @return name       The name of the process, or None.
    """
    processHandle = openProcess(PROCESS_QUERY_INFORMATION |
                                PROCESS_VM_READ, False, processId)
    if processHandle == 0:
        return None

    try:
        moduleHandle = HMODULE(0)
        bytesNeeded = DWORD(0)
        success = enumProcessModules(processHandle, ctypes.byref(moduleHandle),
                                     ctypes.sizeof(moduleHandle),
                                     ctypes.byref(bytesNeeded))
        if not success:
            return None

        processName = ctypes.create_unicode_buffer(MAX_PATH)
        numChars = getModuleBaseName(processHandle, moduleHandle,
                                     processName, MAX_PATH)
        if not numChars:
            return None
        else:
            assert len(processName.value) == numChars
            return processName.value
    finally:
        closeHandle(processHandle)

##############################################################################
def filteredProcessCommands(filterFn):
    """ TODO: implement, if ever needed
    """
    return []

##############################################################################
def killProcess(processId):
    """Kill the given process ID.

    This will throw a RuntimeError if we have problems killing.

    This is based loosely on MSDN sample code.

    @param  processId  The ID of the process we want to kill.
    """
    processHandle = openProcess(PROCESS_QUERY_INFORMATION |
                                PROCESS_TERMINATE |
                                PROCESS_VM_READ, False, processId)
    if processHandle == 0:
        raise RuntimeError("OpenProcess failed")

    try:
        # Kill with code 1 (arbitrary)...
        success = terminateProcess(processHandle, 1)
        if not success:
            raise RuntimeError("TerminateProcess failed")
    finally:
        # Question: is it safe to do this after terminating?
        # ...seems to work...
        closeHandle(processHandle)


###########################################################
def getMemoryStats(processId):
    """Return memory statistics for the given process.

    TODO: Make this more consistent across platforms, somehow?  Allow client
    to specify what things he/she wants.

    @param  processId    The process ID to get memory stats for.
    @return memoryStats  A dictionary of "interesting" memory statistics.
                         Right now, this is "rss" and "vsz" from the "ps"
                         command on Mac.  It's the "private" bytes on windows.
                         Always returns kilobytes.  Returns {} on error.
    """
    memoryStats = {}
    processHandle = openProcess(PROCESS_QUERY_INFORMATION |
                                PROCESS_VM_READ, False, processId)
    if processHandle == 0:
        return memoryStats

    try:
        processMemoryCounters = PROCESS_MEMORY_COUNTERS_EX()
        success = getProcessMemoryInfo(processHandle,
                                       ctypes.byref(processMemoryCounters),
                                       ctypes.sizeof(processMemoryCounters))
        if not success:
            return memoryStats

        # I don't know how to easily get virtual used for a process other than
        # the one calling this fuction (using GlobalMemoryStatusEx), so just
        # return private bytes...
        memoryStats['priv'] = \
            int(round(processMemoryCounters.PrivateUsage / 1024.0))
    finally:
        closeHandle(processHandle)

    return memoryStats

###########################################################
def checkMemoryLimit(processId):
    """ Return false if the process exceeds defined memory limit
    """

    result = True
    memoryStats = None
    try:
        memoryStats = getMemoryStats(processId)
        if memoryStats['priv'] >= _kMemoryDieKB:
            result = False
    except:
        result = False
    return result, memoryStats


###########################################################
def getOpenModuleInfoList(processId):
    """Get a list of information dictionaries about open 'modules'.

    Here, module is kinda a generic term that Windows seems to use, but
    essentially this is getting info about the currently loaded DLLs.

    @param  processId       The process ID that we're querying about.
    @return moduleInfoList  A list of dictionaries, containing at least the
                            keys:
                              path    - The path to the module.
                              size    - The size (in bytes) of the file.
                              version - The version of the file

                            ...for each module.  Any errors are skipped
                            silently, so if this module completely fails it
                            returns the empty list.
    """
    openModules = []
    processHandle = openProcess(PROCESS_QUERY_INFORMATION |
                                PROCESS_VM_READ, False, processId)
    if processHandle == 0:
        return openModules

    try:
        # We need to pass memory into the kernel for it to fill in.  We start with
        # a really big number, but will grow it as needed...
        tableSize = 1024

        while True:
            moduleHandles = (HMODULE * tableSize)()
            bytesNeeded = DWORD(0)
            success = enumProcessModules(processHandle, moduleHandles,
                                         ctypes.sizeof(moduleHandles),
                                         ctypes.byref(bytesNeeded))
            if not success:
                return openModules

            if bytesNeeded.value < ctypes.sizeof(moduleHandles):
                break
            tableSize *= 2

        # Loop over all of them, getting information...
        for i in xrange(bytesNeeded.value / ctypes.sizeof(HMODULE)):
            fileName = ctypes.create_unicode_buffer(MAX_PATH)

            numChars = getModuleFileNameEx(processHandle, moduleHandles[i],
                                           fileName, MAX_PATH)
            if not numChars:
                continue
            else:
                assert len(fileName.value) == numChars

                # Got the path...
                path = fileName.value

                # Try to get the size...
                size = -1
                try:
                    size = os.stat(path).st_size
                except Exception:
                    pass

                # Try to get version information...
                verInfo = _getFileVersionInfoDict(path, [u'FileVersion'])


                openModules.append({
                    'path': path,
                    'size': size,
                    'version': verInfo.get('FileVersion', "")
                })
    finally:
        closeHandle(processHandle)

    return openModules


# Hardcode MS predefined things to query in _getFileVersionInfoDict...
_kVersionAttrNames = [
    u'Comments',
    u'InternalName',
    u'ProductName',
    u'CompanyName',
    u'LegalCopyright',
    u'ProductVersion',
    u'FileDescription',
    u'LegalTrademarks',
    u'PrivateBuild',
    u'FileVersion',
    u'OriginalFilename',
    u'SpecialBuild',
]

###########################################################
def _getFileVersionInfoDict(path, attrNames=_kVersionAttrNames):
    """Return an dictionary with version info about the passed file.

    TODO: Separate this out into someplace more logical?

    @param  path             The file to query.
    @param  attrNames        A list of attributes to query.
    @return versionInfoDict  Info about this file, as a dict.  Keys are
                             various strings defined by Microsoft.  Upon
                             failure, this will just be an empty dict.
    """
    verInfoDict = {}

    # Get info about the version structure...
    bogus = DWORD(0)
    verInfoSize = getFileVersionInfoSize(path, ctypes.byref(bogus))
    if not verInfoSize:
        return verInfoDict

    # Get the version info into the verInfo buffer...
    verInfo = ctypes.create_string_buffer(verInfoSize)
    success = getFileVersionInfo(path, 0, verInfoSize, verInfo)
    if not success:
        return verInfoDict


    # TODO: Query VS_FIXEDFILEINFO?

    # Figure out what languages / codepages are supported...
    # ...this will return lcpArray, which will be a pointer into verInfo...
    lcpArray = ctypes.POINTER(LANGANDCODEPAGE)()
    lcpNumBytes = DWORD(0)
    success = verQueryValue(verInfo, u"\\VarFileInfo\\Translation",
                            ctypes.byref(lcpArray), ctypes.byref(lcpNumBytes))
    if not success:
        return verInfoDict

    # Query for each code page supported...
    # NOTE: We don't really know what to do if more than one, so this loop
    # will actually only run once (!?!?)
    for i in xrange(lcpNumBytes.value / ctypes.sizeof(lcpArray[0])):
        # Get current language and code page...
        lcp = lcpArray[i]


        # Walk through and query each...
        for attrName in attrNames:
            # Build the query...
            queryString = u"\\StringFileInfo\\%04x%04x\\%s" % (
                lcp.language, lcp.codePage, attrName
            )

            # Do the query...
            s = ctypes.wintypes.c_wchar_p()
            sBytes = DWORD(0)
            success = verQueryValue(verInfo, queryString, ctypes.byref(s),
                                    ctypes.byref(sBytes))
            if not success:
                continue

            # Store it
            verInfoDict[attrName] = s.value

        # TODO: Don't know what to do about other languages--we'll just
        # break out after the first one (?!?)
        break

    return verInfoDict


##############################################################################
def setPriority(priority):
    """Set the process priority.

    @param  priority  0 for normal, positive for low, negative for high.
    """
    flag = NORMAL_PRIORITY_CLASS
    if priority < 0:
        flag = ABOVE_NORMAL_PRIORITY_CLASS
    elif priority > 0:
        flag = BELOW_NORMAL_PRIORITY_CLASS

    ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(), flag)


# A few notes about trying to figure out if there are virus scanners...

#http://stackoverflow.com/questions/1331887/detect-antivirus-on-windows-using-c

#import win32com.client
#strComputer = "."
#objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator")
#objSWbemServices = objWMIService.ConnectServer(strComputer,"root\cimv2")
#colItems = objSWbemServices.ExecQuery("Select * from Win32_Environment")
#for objItem in colItems:{
#    print "Caption: ", objItem.Caption
#    print "Description: ", objItem.Description
#    print "Install Date: ", objItem.InstallDate
#    print "Name: ", objItem.Name
#    print "Status: ", objItem.Status
#    print "System Variable: ", objItem.SystemVariable
#    print "User Name: ", objItem.UserName
#    print "Variable Value: ", objItem.VariableValue
#}

#Set oWMI = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\SecurityCenter")
#Set colItems = oWMI.ExecQuery("Select * from AntiVirusProduct")
#For Each objAntiVirusProduct In colItems
#msg = msg & "companyName: " & objAntiVirusProduct.companyName & vbCrLf
#msg = msg & "displayName: " & objAntiVirusProduct.displayName & vbCrLf
#msg = msg & "instanceGuid: " & objAntiVirusProduct.instanceGuid & vbCrLf
#msg = msg & "onAccessScanningEnabled: " & objAntiVirusProduct.onAccessScanningEnabled & vbCrLf
#msg = msg & "productUptoDate: " & objAntiVirusProduct.productUptoDate & vbCrLf
#msg = msg & "versionNumber: " & objAntiVirusProduct.versionNumber & vbCrLf
#msg = msg & vbCrLf
#Next
#
#WScript.Echo msg
