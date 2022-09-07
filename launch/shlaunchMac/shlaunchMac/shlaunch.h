/*
#*****************************************************************************
#
# shlaunch.h
#
#
#
#*****************************************************************************
#
 *
 * Copyright 2013-2022 Sighthound, Inc.
 *
 * Licensed under the GNU GPLv3 license found at
 * https://www.gnu.org/licenses/gpl-3.0.txt
 *
 * Alternative licensing available from Sighthound, Inc.
 * by emailing opensource@sighthound.com
 *
 * This file is part of the Sighthound Video project which can be found at
 * https://github.com/sighthoundinc/SighthoundVideo
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; using version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
 *
#
#*****************************************************************************
*/

#ifndef shlaunchMac_shlaunch_h
#define shlaunchMac_shlaunch_h

#include <inttypes.h>
#include <limits.h>
#include <wchar.h>

// The unique key to locate the shared memory (one instance of Exchange).
#define SHARED_MEMORY_KEY  0x278ca2d1

// To mask the launch code (lower 16bit of the launch signal).
#define LAUNCH_MASK     0x0ffff

// Flag to tell via the launch signal that old processes have to be killed
// first. If the actual launch code is zero it will still be effective.
#define LAUNCH_FLAG_KILL_FIRST   0x10000

// Data shared between the service and whatever wants to communicate with it.
// For now this is just the front-end, where we replace the old backend process
// start-and-stop functionality by delegating such work to the service.
struct Exchange {
    uint32_t size;              // size of this structure, in bytes
    uint32_t processId;         // the current service process' identifier
    uint32_t cycles;            // cycle counter, mostly for availability check
    int32_t  status;            // 0 = backend not launched, 1 = launched
    int32_t  launchProcessId;   // ID of the launch issuing process
    int32_t  launch;            // 0 = off or 16bit launch signal plus flags
    int32_t  shutdown;          // 0 = running, 1 = shutdown requested
    char     build[8];          // build version, usually "rNNNNN"
    wchar_t  dataDir[PATH_MAX]; // the global directory (Unicode)
    uint8_t  _pad16[(PATH_MAX * sizeof(int16_t) +
                    8         * sizeof(char) +
                    5         * sizeof(int32_t)) / 16];
} __attribute__((packed));

#endif
