/*
#*****************************************************************************
#
# launch.c
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
 * https://github.url/thing
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


#define EXCHG_TMOUT_SECS   10


#ifdef _WIN32
    #define LAUNCH_EXPORT __declspec(dllexport)
#else
    #define LAUNCH_EXPORT __attribute__ ((visibility ("default")))
#endif

#ifdef _WIN32

#include <Windows.h>
#include <time.h>

#include "./shlaunchWin/shlaunch/shlaunch.h"

struct LaunchHandle {
    struct Exchange* exchange;
    HANDLE           fileMapping;
    DWORD            processId;
};

LAUNCH_EXPORT int launch_close(struct LaunchHandle* handle)
{
    int result = 1;
    if (handle) {
        if (handle->exchange)
            result &= UnmapViewOfFile(handle->exchange);
        if (handle->fileMapping)
            result &= CloseHandle(handle->fileMapping);
        free(handle);
    }
    return result;
}

LAUNCH_EXPORT struct LaunchHandle* launch_open()
{
    time_t tmout;
    LONG cycles;
    struct LaunchHandle *result = calloc(1, sizeof(*result));

    if (!result)
        goto fail;

    result->processId = GetCurrentProcessId();
    result->fileMapping = OpenFileMapping(FILE_MAP_WRITE | FILE_MAP_READ,
                                          FALSE, EXCHANGE_NAME);
    if (!result->fileMapping)
        goto fail;

    result->exchange = MapViewOfFile(result->fileMapping,
                                     FILE_MAP_READ | FILE_MAP_WRITE, 0, 0, 0);
    if (!result->exchange)
        goto fail;

    cycles = result->exchange->cycles;
    tmout = time(NULL) + EXCHG_TMOUT_SECS;
    while (result->exchange->size != sizeof(struct Exchange) &&
           cycles == result->exchange->cycles) {
        if (time(NULL) > tmout)
            goto fail;
        Sleep(1);
    }

    return result;

fail:
    launch_close(result);
    return NULL;
}

LAUNCH_EXPORT LONG launch_do(struct LaunchHandle* handle, LONG signal)
{
    handle->exchange->launchProcessId = handle->processId;
    return InterlockedExchange(&handle->exchange->launch, signal);
}

LAUNCH_EXPORT DWORD launch_pid(struct LaunchHandle* handle)
{
    return handle->exchange->processId;
}

LAUNCH_EXPORT LONG launch_status(struct LaunchHandle* handle)
{
    return handle->exchange->status;
}

LAUNCH_EXPORT TCHAR* launch_datadir(struct LaunchHandle* handle)
{
    return handle->exchange->dataDir;
}

LAUNCH_EXPORT char* launch_build(struct LaunchHandle* handle)
{
    return NULL;
}

LAUNCH_EXPORT LONG launch_shutdown(struct LaunchHandle* handle)
{
    return handle->exchange->shutdown;
}

#else

#include <string.h>
#include <stdlib.h>
#include <sys/shm.h>
#include <errno.h>
#include <unistd.h>
#include <libkern/OSAtomic.h>

#include "./shlaunchMac/shlaunchMac/shlaunch.h"



struct LaunchHandle {
    struct Exchange* exchange;
    int              sharedMemoryId;
    int              processId;
};

LAUNCH_EXPORT int launch_close(void* handle)
{
    struct LaunchHandle *lh = handle;
    int result = 1;

    if (lh->exchange)
        if (shmdt(lh->exchange))
            result = 0;
    free(lh);
    return result;
}

LAUNCH_EXPORT void* launch_open()
{
    int   smid;
    void* smem;
    uint32_t cycles;
    time_t tmout;
    struct LaunchHandle *result;

    result = calloc(1, sizeof(*result));
    if (!result)
        goto fail;
    result->processId = getpid();
    result->sharedMemoryId = -1;
    smid = shmget(SHARED_MEMORY_KEY, sizeof(struct Exchange), 0);
    if (smid < 0) {
        int err = errno;
        if (err)
            goto fail;
    }
    smem = shmat(smid, NULL, 0);
    if ((void*)-1 == smem) {
        goto fail;
    }

    result->exchange = (struct Exchange*)smem;

    cycles = result->exchange->cycles; // must change, to prove activity
    tmout = time(NULL) + EXCHG_TMOUT_SECS;
    while (result->exchange->size != sizeof(struct Exchange) &&
           cycles == result->exchange->cycles) {
        if (time(NULL) > tmout)
            goto fail;
        usleep(1);
    }

    result->sharedMemoryId = smid;
    return result;
fail:
    launch_close(result);
    return NULL;
}

LAUNCH_EXPORT int32_t launch_do(void* handle, int32_t signal)
{
    struct LaunchHandle *lh = handle;
    lh->exchange->launchProcessId = lh->processId;
    return __sync_swap(&lh->exchange->launch, signal);
}

LAUNCH_EXPORT uint32_t launch_pid(void* handle)
{
    struct LaunchHandle *lh = handle;
    return __sync_fetch_and_xor(&lh->exchange->processId, 0);
}

LAUNCH_EXPORT int32_t launch_status(void* handle)
{
    struct LaunchHandle *lh = handle;
    return __sync_fetch_and_xor(&lh->exchange->status, 0);
}

LAUNCH_EXPORT wchar_t* launch_datadir(void* handle)
{
    struct LaunchHandle *lh = handle;
    return lh->exchange->dataDir;
}

LAUNCH_EXPORT char* launch_build(void* handle)
{
    struct LaunchHandle *lh = handle;
    return lh->exchange->build;
}

LAUNCH_EXPORT int32_t launch_shutdown(void* handle)
{
    struct LaunchHandle *lh = handle;
    return __sync_fetch_and_xor(&lh->exchange->shutdown, 0);
}

#endif
