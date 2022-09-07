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

#ifndef __SHLAUNCH_H
#define __SHLAUNCH_H

// definitions the front-end needs to talk to the launch service ...

// Name of the exchange shared memory map, so the front-end can open it. It's
// a random name to avoid any chance of ever colliding with any another
// product.
#define EXCHANGE_NAME L"Global\\fed45fe4e41b7695"

// Launch flag: kill old processes first.
#define LAUNCH_FLAG_KILL_FIRST   0x10000

// To mask the launch code (lower 16bit of the launch signal).
#define LAUNCH_MASK     0x0ffff

// One instance of this structure is to exchange information and control
// between the service and the front-end, using a memory map.
#pragma pack(push, 1)
struct Exchange {
    LONG  size;               // size of this structure, in bytes
	LONG  cycles;             // cycle counter, to detect shlaunch health
    DWORD processId;          // the current service process' identifier
    LONG  status;             // 0 = backend not launched, 1 = launched
    DWORD launchProcessId;    // ID of the processing issuing the launch
    LONG  launch;             // 0 = off or 16bit launch signal plus flags
    LONG  shutdown;           // 0 = running, 1 = shutdown detected
    TCHAR dataDir[MAX_PATH];  // the global data directory
};
#pragma pack(pop)

#endif
