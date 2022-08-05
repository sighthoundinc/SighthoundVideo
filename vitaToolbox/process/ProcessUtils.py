#!/usr/bin/env python

#*****************************************************************************
#
# ProcessUtils.py
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
if sys.platform == 'win32':
    from ProcessUtilsWin import listProcesses
    from ProcessUtilsWin import getProcessName
    from ProcessUtilsWin import killProcess
    from ProcessUtilsWin import getMemoryStats
    from ProcessUtilsWin import checkMemoryLimit
    from ProcessUtilsWin import getOpenModuleInfoList
    from ProcessUtilsWin import setPriority
    from ProcessUtilsWin import filteredProcessCommands
    def listChildProcessesOfPID(*args, **kwargs): return []
else:
    from ProcessUtilsUnix import listProcesses
    from ProcessUtilsUnix import getProcessName
    from ProcessUtilsUnix import killProcess
    from ProcessUtilsUnix import getMemoryStats
    from ProcessUtilsUnix import checkMemoryLimit
    from ProcessUtilsUnix import filteredProcessCommands
    from ProcessUtilsUnix import listChildProcessesOfPID
    from os import nice as setPriority
    def getOpenModuleInfoList(_): return []


kPriorityLow = 10
kPriorityNormal = 0
kPriorityHigh = -10


##############################################################################
def getProcessesWithName(toFind):
    """Return the processes that have the given name.

    This is currently built upon platform-dependent code, but could probably
    be made faster using platform-specific code.

    @param  toFind   The name to look for; note that this is case insensitive
                     and should not include the extension (like ".exe")
    @return pidList  A list of process IDs that match.
    """
    processesWithName = []

    toFind = toFind.lower()

    for processId in listProcesses():
        processName = getProcessName(processId)
        if processName:
            if toFind == os.path.splitext(processName)[0].lower():
                processesWithName.append(processId)

    return processesWithName


##############################################################################
def setProcessPriority(priority):
    """Adjust the process priority.

    @param  priority  One of kPriorityLow, kPriorityNormal, or kPriorityHigh.
    """
    setPriority(priority)



##############################################################################
def _test(args):
    """OB_REDACT
       Implement some simple command line tests.

    @param  args  sys.argv[1:]
    """
    # Grab the command off, defaulting to list...
    try:
        cmd = args.pop(0)
    except IndexError:
        cmd = 'list'

    if cmd == 'list':
        processIdList = listProcesses()
        for processId in processIdList:
            processName = getProcessName(processId)
            if processName is None:
                processName = "<unknown>"
            print processId, processName
    elif cmd == 'killall':
        toKill = args[0].lower()

        processIdList = listProcesses()
        for processId in processIdList:
            processName = getProcessName(processId)
            if processName:
                if toKill == os.path.splitext(processName)[0].lower():
                    print "Killing %s (%d)" % (processName, processId)
                    try:
                        killProcess(processId)
                    except Exception:
                        print "...failed!"
    elif cmd == 'mem':
        pidList = getProcessesWithName(args[0])
        for pid in pidList:
            memStats = getMemoryStats(pid)
            memStrs = ["%6.2f (%s)" % (memUsage/1024.0, name) for
                       (name, memUsage) in sorted(memStats.iteritems())]
            print "% 6d %s" % (pid, " ".join(memStrs))
    elif cmd == 'dlls':
        pidList = getProcessesWithName(args[0])
        for pid in pidList:
            openModules = getOpenModuleInfoList(pid)
            print "PID: %d" % pid
            print "\n  ".join([''] + [str(om) for om in openModules])
            print "==="
    else:
        print "Unknown test command"


##############################################################################
if __name__ == '__main__':
    _test(sys.argv[1:])



