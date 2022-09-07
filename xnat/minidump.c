/*
#*****************************************************************************
#
# minidump.c
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

#include <windows.h>
#include <dbghelp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdlib.h>
#include <tchar.h>

// buffer to store the minidump file path; if not overwritten at runtime mini
// dumps will end up in the temporary directory
TCHAR _miniDumpPath[MAX_PATH] = { 0 };

// prefix for the minidump's file name
TCHAR* _miniDumpPrefix = TEXT("default");

// flag to exit the process after a dump file was written
UINT _exitOnCrash = 0;

// Maximum number of dump files to keep.
UINT _maxDumps = 0;

// We load the MiniDumpWriteDump function dynamically, just in case it is not
// available. Hence we need to know the signature of it.
typedef BOOL (WINAPI *MINIDUMPWRITEDUMP)(
    HANDLE, DWORD, HANDLE, MINIDUMP_TYPE,
    PMINIDUMP_EXCEPTION_INFORMATION,
    PMINIDUMP_USER_STREAM_INFORMATION,
    PMINIDUMP_CALLBACK_INFORMATION);

/**
 * The exception filter, called if a crash happened. We try to look up the mini
 * dump function, make a file name based on prefix and a timestamp and then
 * write all of it out, preferrably at a location the application has set.
 *
 * @see http://msdn.microsoft.com/en-us/library/ms681401%28v=vs.85%29.aspx
 */
LONG WINAPI _minidump_filter(struct _EXCEPTION_POINTERS *excPtrs)
{
    BOOL dumped = FALSE;
    HMODULE dll = NULL;
    HANDLE h = INVALID_HANDLE_VALUE;
    HANDLE hf = INVALID_HANDLE_VALUE;
    MINIDUMPWRITEDUMP miniDumpWriteDumpProc;
    MINIDUMP_EXCEPTION_INFORMATION excInfo;
    TCHAR fileName[256];
    WIN32_FIND_DATA wfd;
    SYSTEMTIME stm;

    // load the DBGHLPAPI library and the MiniDumWriteDump() API
    dll = LoadLibrary(TEXT("dbghelp.dll"));
    if (!dll)
        goto cleanup;
    miniDumpWriteDumpProc = (MINIDUMPWRITEDUMP)GetProcAddress(dll, "MiniDumpWriteDump");
    if (!miniDumpWriteDumpProc)
        goto cleanup;

    // if the dump path isn't given use the temporary path
    if (!_miniDumpPath[0])
        if (!GetTempPath(_countof(_miniDumpPath), _miniDumpPath))
            goto cleanup;

    // if we have too many dump files already then get rid of olde ones, if
    // that doesn't work we don't continue (don't want to fill up the disk)
    _tcscpy_s(fileName, _countof(fileName), _miniDumpPath);
    _tcscat_s(fileName, _countof(fileName), TEXT("*"));
    h = FindFirstFile(fileName, &wfd);
    if (INVALID_HANDLE_VALUE == h) {
        if (ERROR_FILE_NOT_FOUND != GetLastError())
            goto cleanup;
    }
    else {
        size_t plen = _tcslen(_miniDumpPrefix);
        size_t n, c = 0;
        for (n = 0;;n++) {
            size_t flen;
            TCHAR bak;
            if (n && !FindNextFile(h, &wfd)) {
                if (ERROR_NO_MORE_FILES != GetLastError())
                    goto cleanup;
                break;
            }
            flen = _tcslen(wfd.cFileName);
            if (flen < plen)
                continue;
            bak = wfd.cFileName[plen];
            wfd.cFileName[plen] = (TCHAR)0;
            if (_tcsicmp(wfd.cFileName, _miniDumpPrefix))
                continue;
            if (++c < _maxDumps)
                continue;
            wfd.cFileName[plen] = bak;
            _tcscpy_s(fileName, _countof(fileName), _miniDumpPath);
            _tcscat_s(fileName, _countof(fileName), wfd.cFileName);
            if (!DeleteFile(fileName))
                goto cleanup;
        }
    }

    // create the dump file path
    GetSystemTime(&stm);
    _sntprintf_s(fileName, _countof(fileName), _TRUNCATE,
                 TEXT("%s_%04d%02d%02d_%02d%02d%02d_%03d.dmp"), _miniDumpPrefix,
                 stm.wYear, stm.wMonth, stm.wDay,
                 stm.wHour, stm.wMinute, stm.wSecond, stm.wMilliseconds);
    _tcscat_s(_miniDumpPath, _countof(fileName), fileName);

    // open the dump file for writing
    h = CreateFile(_miniDumpPath,
                          GENERIC_WRITE,
                          FILE_SHARE_WRITE,
                          NULL,
                          CREATE_ALWAYS,
                          FILE_ATTRIBUTE_NORMAL,
                          NULL);
    if (INVALID_HANDLE_VALUE == h)
        goto cleanup;

    // emit the mini dump to that file
    ZeroMemory(&excInfo, sizeof(excInfo));
    excInfo.ThreadId = GetCurrentThreadId();
    excInfo.ExceptionPointers = excPtrs;

    if (!miniDumpWriteDumpProc(GetCurrentProcess(),
                               GetCurrentProcessId(),
                               h,
                               MiniDumpNormal,
                               &excInfo,
                               NULL, NULL))
        goto cleanup;
    dumped = TRUE;

cleanup:
    CloseHandle(h);
    FindClose(hf);
    FreeLibrary(dll);

    if (_exitOnCrash && dumped) {
        ExitProcess(_exitOnCrash);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

/**
 * To be called in the application to be enabled to catch crashes and write out
 * minidumps.
 *
 * @param prefix       Application name prefix. Constant, up to 64 characters.
 * @param exitOnCrash  Causes the exception handler to end the process and return
 *                     this value as the exit code. To not to exit pass in zero.
 * @param maxDumps     Maximum number of dumps to keep, (UINT)-1 for default.
 */
void minidump_init(TCHAR* prefix, UINT exitOnCrash, UINT maxDumps)
{
    _exitOnCrash = exitOnCrash;
    _miniDumpPrefix = prefix;
    _maxDumps = (UINT)-1 == maxDumps ? 10 : maxDumps;
    SetUnhandledExceptionFilter(_minidump_filter);
}
