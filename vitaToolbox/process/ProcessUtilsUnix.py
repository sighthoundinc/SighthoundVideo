#!/usr/bin/env python

#*****************************************************************************
#
# ProcessUtilsUnix.py
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
import os
import sys
import traceback


# This is in signal on the Mac.  ...but it's not on Windows and that confuses
# the obfuscator...
SIGKILL = 9  # signal.SIGKILL

# Maximum size of committed memory (in kB) a process is allowed to consume before
# we shut it down to avoid out-of-memory issues.
# OSX/Linux 32-bit processes can access 4GB memory space,
# but on older systems it may be as low as 3GB
# Lets set the limit to 2.8GB to be sure (still much higher than we expect any of our
# processes to consume)
if sys.maxint == 2147483647:
    # On 32-bit, keep the limit below 3GB
    _kMemoryDieKB = 2800 * 1000
else:
    # On 64-bit, don't go over 4GB, just because we want to stop somewhere
    # Our processes normally should not exceed 500MB
    _kMemoryDieKB = 4000 * 1000


##############################################################################
def listProcesses():
    """Return a list of all running process IDs.

    Note that this is instantaneous--there's no guarantee that a process won't
    have died or have been born by the time you use this list.

    @return pidList  A list of all running process IDs.
    """
    # We're just going to depend on the system having "ps"; this isn't elegant
    # but is easy and portable...
    # NOTE: we list all processes, not just the user's ones
    return map(int, os.popen('ps ax -o pid').readlines()[1:])


##############################################################################
def listChildProcessesOfPID(processId):
    """Return a list of all running child process IDs spawned from processId.

    Note that this is instantaneous--there's no guarantee that a process won't
    have died or have been born by the time you use this list.

    @param   processId  The process ID you wish to find children processes of.
    @return  pidList    A list of all running child process IDs spawned from
                        processId.
    """
    # We're just going to depend on the system having "ps"; this isn't elegant
    # but is easy and portable...
    return [
        procId for [ppid, procId]
        in map(
            lambda (x): map(int, str.split(x)),
            os.popen('ps ax -o ppid,pid').readlines()[1:]
        )
        if ppid == int(processId)
    ]


##############################################################################
def getProcessName(processId):
    """Get the name of the given process.

    Note: this will return None if we don't have access to the name (or run
    into some other sort of trouble).

    We use the 'ucomm' as the name, which seems the most reliable (really OK?)

    @param  processId  The ID of the process whose name we want.
    @return name       The name of the process, or None.
    """
    # We're just going to depend on the system having "ps"; this isn't elegant
    # but is easy and portable...
    return os.popen('ps -p %d -o ucomm' % processId).readlines()[-1].strip()

##############################################################################
def filteredProcessCommands(filterFn):
    """ Runs a filter over the command line of all running processes, only
    returns the IDs of the ones which were matched by a given filter.

    @param filterFn The filter function, gets a process' ID (integer) and full
    command (string) returning a boolean whether to include this process or not.
    @return List of IDs of matched processes.
    """
    pids = []
    for ln in os.popen('ps ax -o pid,command').readlines()[1:]:
        ln = ln.strip()
        idx = ln.find(' ')
        if -1 == idx:
            continue
        pid = int(ln[0:idx])
        if filterFn(pid, ln[idx+1:]):
            pids.append(pid)
    return pids

##############################################################################
def killProcess(processId):
    """Kill the given process ID.

    @param  processId  The ID of the process we want to kill.
    """
    os.kill(processId, SIGKILL)


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
    try:
        psOutput = os.popen('ps -p %d -o rss,vsz' % processId).readlines()[1]
        psInts = [int(memStat) for memStat in psOutput.split()]

        memoryStats['real'], memoryStats['virt'] = psInts
    except Exception:
        memoryStats['error'] = traceback.format_exc()

    return memoryStats

###########################################################
def checkMemoryLimit(processId):
    """ Return false if the process exceeds defined memory limit
    """

    result = True
    memoryStats = None
    try:
        memoryStats = getMemoryStats(processId)
        if memoryStats['real'] >= _kMemoryDieKB:
            result = False
    except:
        memoryStats['error'] = traceback.format_exc()
        result = False
    return result, memoryStats


