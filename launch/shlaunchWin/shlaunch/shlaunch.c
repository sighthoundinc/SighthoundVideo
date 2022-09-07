/*
#*****************************************************************************
#
# shlaunch.c
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
#include <tchar.h>
#include <strsafe.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <psapi.h>
#include <aclapi.h>
#include <sddl.h>
#include <shlobj.h>
#include <share.h>
#include <lm.h>
#include <lmaccess.h>

#include "shlaunch.h"

//////////////////////////////////////////////////////////////////////////////

// Set this to simulate the service by calling it from a command prompt,
// of course lacking service control features.
//#define RUN_IN_CONSOLE

// Set this to use runtime logging to a file into the temp dir. Very useful
// during development at least. Could become a registry value one day, maybe.
#define LOG_IT

//////////////////////////////////////////////////////////////////////////////

// Exit code: operation succeeded.
#define EXITCODE_SUCCESS 0
// Exit code: some command line arguments are invalid.
#define EXITCODE_BAD_ARGS 1
// Exit code: general error happened. Details in the logs, if available
#define EXITCODE_ERROR 2
// Exit code: something went wrong interacting with the Win32 service API.
#define EXITCODE_SERVICE_ERROR 3
// Exit code: the service got scheduled for removal, a restart is required.
#define EXITCODE_SERVICE_REMOVAL_PENDING 4
// Exit code: the service already exists (happens on installation bounce).
#define EXITCODE_SERVICE_EXISTS 5
// Exit code: the service does not exist (happens on removal bounce).
#define EXITCODE_SERVICE_MISSING 6
// Exit code: the user data directory pointer cannot be determined or created.
#define EXITCODE_DATADIR_POINTER_ERROR 7

// The name of the service we tell the SCM for management purposes.
#define SERVICE_NAME L"shlaunch"
// The name of the service executable.
#define SERVICE_EXE L"shlaunch.exe"
// The title shown in the Windows services dialog.
#define SERVICE_TITLE L"Sighthound Video Launch"
// Some extra description shown in the Windows services dialog.
#define SERVICE_INFO L"Launches the Sighthound Video backend automatically."

// Name of the backend executable, which has to reside in the same directory
// as the service executable.
#define BACKEND_EXE L"Sighthound Agent.exe"
// Parameter passed to the backend process call. Followed by the global data
// directory.
#define BACKEND_ARG1 L"--backEnd"
// Marker we use to identify all of the Sighthound Video processes. Actually
// only needed under OSX right now, but we'd like to stay compatible.
#define BACKEND_ARG2 L"--sh-2e4fce7e"
// Reserved marker to work around a forking issue. And we use it for the
// current approach to detect backends launched by the service.
#define BACKEND_ARG3 L"--sh-baef77e9"

// Option prefix.
#define ARG_PREFIX L"--"
// Option: the backend should not be started when the service does.
#define ARG_NO_AUTOSTART (ARG_PREFIX L"no-autostart")

// Name of the data directory.
#define DATADIR_NAME L"Sighthound Video"

// Name of the file pointing to a(n original local user's) data directory.
#define DATADIR_POINTER L"data_dir_ptr"

// Polling interval, the time to wait between checking the control memory or
// to wait for the shutdown signal to be picked up.
#define POLL_MILLIS 100

// Time to wait for the backend to pick up the shutdown signal.
#define SHUTDOWN_SIGNAL_TIMOUT_SECS  10

// Time to wait before giving up on the service to stop.
#define STOP_TIMEOUT_SECS  (SHUTDOWN_SIGNAL_TIMOUT_SECS + 5)

// Maximum size of a log file.
#define MAX_LOG_FILE_SIZE  (1024 * 1024)

// How long to wait for a process to terminate.
#define TERMINATE_PROCESS_TIMEOUT  5000

// Maximum number of processes
#define MAX_PROCESSES  0x8000

// Name of the log file written during installation and removal.
#define INSTALL_LOG_FILE  L"shlaunch_install.log"

// INI file name we use to configure the service.
#define CFG_FILE  L"shlaunch.cfg"

// Configuration section: global things.
#define CFG_SECTION_LAUNCH  L"Main"

// Configuration key: whether to launch after boot ("TRUE") or not.
// NOTE: all keys must be lowercase, due to the Python's INI reader
#define CFG_KEY_AUTOSTART  L"autostart"

// Configuration key: whether to do backend starting at all ("TRUE") or not.
#define CFG_KEY_BACKEND  L"backend"

// Name of the application dara directory. Used under XP, since there is no
// official constant available we assume and have to define it ourselves.
#define APPLICATION_DATA  L"Application Data"

//////////////////////////////////////////////////////////////////////////////

// List of all process (executable) names we have to get rid of sometimes.
TCHAR* KILL_CANDIDATES_ALL[] = {
    SERVICE_EXE,                // these two entries must be fixed, see the
    BACKEND_EXE,                // second "list" KILL_CANDIDATES ...
    L"Sighthound Video.exe",
    L"Sighthound USB.exe",
    L"Sighthound Web.exe",
    L"Sighthound XNAT.exe",
    L"SighthoundXNAT.exe",
    NULL };

// List of all of the backend (executable) names.
TCHAR** KILL_CANDIDATES = &KILL_CANDIDATES_ALL[1];

//////////////////////////////////////////////////////////////////////////////

// Service configuration.
struct Config {
    BOOL autoStart;
    BOOL backend;
};

// Service context, basically all the runtime state the service keeps.
struct Context
{
    TCHAR                 cmdln[MAX_PATH * 4];
    PROCESS_INFORMATION   procInfo;
    SERVICE_STATUS_HANDLE ssh;
    DWORD                 chkp;
    struct Exchange*      exchange;
    struct Config         config;
    HANDLE                evtExit;
};

// Global, one and only context. Made public because some functions can't
// take a context pointer.
struct Context* _ctx = NULL;

// The path of the service executable. Global for consistence and convenience.
TCHAR _exeSvc[MAX_PATH + 1] = { 0 };

// Install log file path.
TCHAR _installLog[MAX_PATH + 1] = { 0 };

//////////////////////////////////////////////////////////////////////////////

// Logging things ...

#ifdef LOG_IT
/**
 * Appends a log message into the log file in the user directory. Does not
 * keep the file open.
 *
 * @param msg The log message to write.
 */
void log_it(TCHAR* msg) {
    int needDir;
    FILE* out = NULL;
    SYSTEMTIME st;
    TCHAR log[MAX_PATH];

    if (_installLog[0])
        out = _tfsopen(_installLog, L"at+,ccs=UTF-8", _SH_DENYWR);
    else if (_ctx && _ctx->exchange && _ctx->exchange->dataDir[0]) {
        for (needDir = 0; needDir < 2; needDir++) {
            _tcscpy_s(log, _countof(log), _ctx->exchange->dataDir);
            _tcscat_s(log, _countof(log), L"\\logs");
            if (needDir)
                CreateDirectory(log, NULL);
            _tcscat_s(log, _countof(log), L"\\shlaunch.log");
            if (!needDir) {
                WIN32_FIND_DATA findData;
                HANDLE fnd = FindFirstFile(log, &findData);
                if (INVALID_HANDLE_VALUE != fnd) {
                    FindClose(fnd);
                    if (findData.nFileSizeLow > MAX_LOG_FILE_SIZE ||
                        findData.nFileSizeHigh) {
                        TCHAR log1[MAX_PATH];
                        _tcscpy_s(log1, _countof(log1), log);
                        _tcscat_s(log1, _countof(log1), L".1");
                        DeleteFile(log1);
                        if (!MoveFile(log, log1))
                            DeleteFile(log);
                    }
                }
            }
            out = _tfsopen(log, L"at+,ccs=UTF-8", _SH_DENYWR);
            if (out)
                break;
        }
    }
    if (!out)
        out = stdout;
    GetLocalTime(&st);
    _ftprintf(out, L"%04d-%02d-%02d %02d:%02d:%02d,%03d - %s\n",
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond,
        st.wMilliseconds, msg);
    if (out != stdout)
        fclose(out);
}

#define LOG(msg) log_it(msg);
#else
#define LOG(msg)
#endif


/**
 * Gets a textual representation of an error code (if such is available)
 * and logs it.
 *
 * @param comment  The comment/prefix of the message.
 * @param err      The error code.
 */
void print_error(TCHAR* comment, DWORD err)
{
    TCHAR* msg = NULL;
    TCHAR buf[2048]; // should be big enough, or forget about it

    if (FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER |
        FORMAT_MESSAGE_FROM_SYSTEM     |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        err,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPTSTR)&msg,
        0,
        NULL)) {
        int bufsz = _countof(buf);
        int msglen = _tcslen(msg);
        msg[(2 > msglen ? 2 : msglen) - 2] = '\0';
        _sntprintf_s(buf, bufsz, _TRUNCATE,
            L"%s - error %u (x%x) '%s'", comment, err, err, msg);
        buf[bufsz - 1] = '\0';
        _putts(buf);
        LOG(buf)
        LocalFree(msg);
    }
    else {
        _tprintf(L"%s - error %u (x%x)\n", comment, err, err);
    }
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Enumerates all process IDs we can find and access, gets their executable
 * and then invokes a function on this information.
 *
 * @param handler      Function to call for each process, passing the context,
 *                     the PID, the executable name and (a pointer to) the
 *                     process handle. If the function returns FALSE
 *                     enumeration stops. The handler can set the process
 *                     handler to NULL to prevent it from being closed.
 * @param context      Context pointer to be passed to the handler.
 * @param accessFlags  Extra access flag to allow the handler to do more.
 * @return             Last error, ERROR_SUCCESS if everything worked out.
 */
DWORD enumerate_processes(BOOL(*handler)(void*, DWORD, TCHAR*, HANDLE*),
                          void* context,
                          DWORD accessFlags)
{
    int i, count;
    DWORD result = ERROR_SUCCESS;
    DWORD *processes, size;
    TCHAR log[256];

    // NOTE: alternative would be CreateToolhelp32Snapshot()
    size = MAX_PROCESSES;  // give plenty of space for the even most busiest systems
    processes = (DWORD*)malloc(size);
    if (!processes) {
        SetLastError(ERROR_OUTOFMEMORY);
        goto fail;
    }
    if (!EnumProcesses(processes, size, &size))
        goto fail;
    count = size / sizeof(DWORD);

    // NOTE: we do NOT sort the list to avoid that e.g. the back-end would
    //       restart a just terminated camera process - as a matter of fact the
    //       list returned by Windows already seems to be a walk over the
    //       process dependency tree and the PIDs are not at all predictable,
    //       so by just going through the list we get the desired tear-down of
    //       our processes; however this is an assumption and might change,
    //       ideally there would be a deeper investigation where we'd built the
    //       tree ourselves, yet race conditions make this a tricky task ...

    _stprintf_s(log, _countof(log), L"found %d processes", count);
    LOG(log)
    for (i = 0; i < count; i++) {

        HANDLE process = NULL;
        HMODULE module;
        TCHAR processName[MAX_PATH];
        DWORD pid = processes[i];

        if (0 == pid) // system idle process is not our business
            continue;

        // Nothing is dramatic if we cannot access a process, since it might
        // be of system nature or otherwise protected from prying eyes ...
        process = OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | accessFlags,
            FALSE, pid);
        if (!process) {
            DWORD err = GetLastError();
            if (5 != err) { // 5 means access denied and that usually is a system process
                TCHAR log[128]; // (error 87 usually for processes which are gone, but better log it)
                _stprintf_s(log, _countof(log), L"cannot open process with PID %d", pid);
                print_error(log, GetLastError());
            }
            goto search_loop_cleanup;
        }
        if (!EnumProcessModules(process, &module, sizeof(module), &size)) {
            DWORD err = GetLastError();
            if (299 != err) // 299 happens for 64bit processes (we are of 32bit nature)
                print_error(L"cannot enumerate process modules", err);
            goto search_loop_cleanup;
        }
        if (!GetModuleBaseName(process, module, processName, _countof(processName))) {
            print_error(L"cannot get base name for process", GetLastError());
            goto search_loop_cleanup;
        }
        _stprintf_s(log, _countof(log), L"found process %d '%s'", pid, processName);
        LOG(log)
        if (handler(context, pid, processName, &process))
            result++;
        else
            i = count;

search_loop_cleanup:
        if (process)
            if (!CloseHandle(process))
                goto fail;
    }
    goto cleanup;

fail:
    result = GetLastError();
cleanup:
    free(processes);
    return result;
}

// handler 'class' used in kill_processes()
struct KillContext {
    int kills;
    int errors;
    DWORD noKillPid;
    TCHAR** candidates;
    HANDLE terminatedProcesses[MAX_PROCESSES];
};
BOOL kill_handler(void* context, DWORD pid, TCHAR* exe, HANDLE* process)
{
    struct KillContext* kctx = (struct KillContext*) context;
    TCHAR** candidate;

    if (pid == GetCurrentProcessId() ||
        pid == kctx->noKillPid) {
        return TRUE;
    }

    for (candidate = kctx->candidates; *candidate; candidate++) {
        TCHAR log[128];
        if (_tcsicmp(*candidate, exe))
            continue;
        _stprintf_s(log, _countof(log), L"killing '%s', PID %d ...", exe, pid);
        LOG(log)
        // let the processes terminate with zero (success), so no unwanted
        // warnings will be created ...
        if (TerminateProcess(*process, 0)) {
            kctx->terminatedProcesses[kctx->kills] = *process;
            kctx->kills++;
            *process = NULL;
        }
        else {
            print_error(L"process termination failed", GetLastError());
            kctx->errors++;
        }
    }
    return TRUE;
}


/**
 * To be able to kill processs running under the local system account at
 * uninstall time we need special privileges. It is NOT enough to run as
 * an admin, enabled by the UAC, apparently.
 *
 * @param enable  TRUE to enable debugging, FALSE to give away that right.
 * @return        TRUE if that privilege change attempt worked.
 */
BOOL enable_debugging(BOOL enable)
{
    TOKEN_PRIVILEGES tps;
    LUID luid;
    DWORD err;
    HANDLE process = NULL, token = NULL;
    BOOL result = FALSE;

    process = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, GetCurrentProcessId());
    if (!process) {
        print_error(L"cannot get process token", GetLastError());
        goto cleanup;
    }
    if (!OpenProcessToken(process, TOKEN_ADJUST_PRIVILEGES, &token)) {
        print_error(L"cannot get process token", GetLastError());
        goto cleanup;
    }
    if (!LookupPrivilegeValue(NULL, SE_DEBUG_NAME, &luid)) {
        print_error(L"cannot lookup privilege", GetLastError());
        goto cleanup;
    }
    tps.PrivilegeCount = 1;
    tps.Privileges[0].Luid = luid;
    tps.Privileges[0].Attributes = enable ? SE_PRIVILEGE_ENABLED : 0;
    result = AdjustTokenPrivileges(token, FALSE, &tps, sizeof(TOKEN_PRIVILEGES), NULL, NULL);
    err = GetLastError();
    if (!result || ERROR_NOT_ALL_ASSIGNED == err) {
        print_error(L"cannot adjust privileges", err);
        goto cleanup;
    }
    result = TRUE;
cleanup:
    if (token)
        CloseHandle(token);
    if (process)
        CloseHandle(process);
    return result;
}


/**
 * Gets rid of everything matching a list of process (executable) names.
 *
 * @param  noKillPid  Do not kill the process with this PID.
 * @return            Number of errors occured.
 */
int kill_processes(TCHAR** candidates, DWORD noKillPid)
{
    struct KillContext kctx;
    DWORD result;
    TCHAR log[128];
    BOOL debugging;

    _stprintf_s(log, _countof(log), L"killing processes, excluding %d ...", noKillPid);
    LOG(log)
    debugging = enable_debugging(TRUE);
    ZeroMemory(&kctx, sizeof(kctx));
    kctx.candidates = candidates;
    kctx.noKillPid = noKillPid;
    result = enumerate_processes(kill_handler, &kctx, PROCESS_TERMINATE | SYNCHRONIZE);
    if (kctx.kills) {
        DWORD waitResult;
        int i;
        LOG(L"waiting for terminated processes to end...")
        waitResult = WaitForMultipleObjects(kctx.kills,
                                            kctx.terminatedProcesses,
                                            TRUE,
                                            TERMINATE_PROCESS_TIMEOUT);
        if (waitResult <   WAIT_OBJECT_0 ||
            waitResult >= (WAIT_OBJECT_0 + kctx.kills))
            print_error(L"waiting failed", GetLastError());
        for (i = 0; i < kctx.kills; i++)
            CloseHandle(kctx.terminatedProcesses[i]);
    }
    _stprintf_s(log, _countof(log), L"%d processes killed, %d errors (enum result %u)",
                kctx.kills, kctx.errors, result);
    LOG(log)
    if (debugging)
        enable_debugging(FALSE);
    return kctx.errors;
}


// handler to detect back-end processes (ones which can be signaled to quit)
BOOL backend_detect_handler(void* context, DWORD pid, TCHAR* exe, HANDLE* process)
{
    int* counter = (int*)context;
    UNREFERENCED_PARAMETER(process);
    UNREFERENCED_PARAMETER(pid);
    *counter += _tcsicmp(BACKEND_EXE, exe) ? 0 : 1;
    return TRUE;
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Reads configuration data from the user directory.
 *
 * @param ctx The fully initialized context, w/o things configurable.
 * @return TRUE if the file was present.
 */
BOOL config_read(struct Context* ctx)
{
    BOOL result = TRUE;
    TCHAR configFile[MAX_PATH];
    TCHAR value[256] = { 0 };

    _tcscpy_s(configFile, _countof(configFile), ctx->exchange->dataDir);
    _tcscat_s(configFile, _countof(configFile), L"\\" CFG_FILE);

    GetPrivateProfileString(CFG_SECTION_LAUNCH,
                            CFG_KEY_AUTOSTART,
                            L"FALSE",
                            value,
                            _countof(value),
                            configFile);
    result &= 2 != errno;
    ctx->config.autoStart = !_tcsicmp(L"TRUE", value);
    if (ctx->config.autoStart)
        LOG(L"auto-start enabled in configuration")

    GetPrivateProfileString(CFG_SECTION_LAUNCH,
                            CFG_KEY_BACKEND,
                            L"TRUE",
                            value,
                            _countof(value),
                            configFile);
    result &= 2 != errno;
    ctx->config.backend = !_tcsicmp(L"TRUE", value);
    if (ctx->config.autoStart)
        LOG(L"backend enabled in configuration")

    return result;
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Gets the attributes of a file (or directory).
 *
 * @param path  The file path to look for.
 * @return      Win32 attributes, -1 if not found or on error.
 */
DWORD get_file_attributes(TCHAR* path)
{
    WIN32_FIND_DATA findData;
    HANDLE findHandle = FindFirstFile(path, &findData);
    if (INVALID_HANDLE_VALUE == findHandle)
        return (DWORD)-1;
    FindClose(findHandle);
    return findData.dwFileAttributes;
}

/**
 * Checks whether a path exists, is accessible and is a directory.
 *
 * @param path  The path to check.
 * @return      TRUE if it's a directory.
 */
BOOL is_dir(TCHAR* path)
{
    DWORD attributes = get_file_attributes(path);
    if ((DWORD)-1 == attributes)
        return FALSE;
    return FILE_ATTRIBUTE_DIRECTORY & attributes;
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Makes sure a directory exists with access righst open to everyone on the
 * local system. This is necessary to operate in the same way as the old SV
 * application did, as well as to support access from frontends in any
 * directory.
 *
 * @param path  The directory's path.
 * @return      Zero on success, error code otherwise.
 */
DWORD ensure_dir_with_user_acl(LPCTSTR path)
{
    DWORD                    result;
    PSID                     sid = NULL;
    PACL                     acl = NULL;
    PSECURITY_DESCRIPTOR     sd = NULL;
// Seems like a GCC bug: http://stackoverflow.com/questions/13746033/how-to-repair-warning-missing-braces-around-initializer
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-braces"
    SID_IDENTIFIER_AUTHORITY auth = SECURITY_WORLD_SID_AUTHORITY;
#pragma GCC diagnostic pop
    SECURITY_ATTRIBUTES      sa;
    EXPLICIT_ACCESS          ea;

    if (!AllocateAndInitializeSid(&auth, 1, SECURITY_WORLD_RID,
                                  0, 0, 0, 0, 0, 0, 0, &sid))
        goto fail;

    ZeroMemory(&ea, sizeof(ea));
    ea.grfAccessMode        = SET_ACCESS;
    ea.grfAccessPermissions = SPECIFIC_RIGHTS_ALL | STANDARD_RIGHTS_ALL;
    ea.grfInheritance       = SUB_CONTAINERS_AND_OBJECTS_INHERIT;
    ea.Trustee.TrusteeType  = TRUSTEE_IS_WELL_KNOWN_GROUP;
    ea.Trustee.TrusteeForm  = TRUSTEE_IS_SID;
    ea.Trustee.ptstrName    = (LPTSTR)sid;

    if (ERROR_SUCCESS != SetEntriesInAcl(1, &ea, NULL, &acl))
        goto fail;
    if (NULL == (sd = (PSECURITY_DESCRIPTOR)LocalAlloc(LPTR, SECURITY_DESCRIPTOR_MIN_LENGTH)))
        goto fail;
    if (!InitializeSecurityDescriptor(sd, SECURITY_DESCRIPTOR_REVISION))
        goto fail;
    if (!SetSecurityDescriptorDacl(sd, TRUE, acl, FALSE))
        goto fail;

    sa.nLength = sizeof(sa);
    sa.lpSecurityDescriptor = sd;
    sa.bInheritHandle = FALSE;

    if (CreateDirectory(path, &sa))
        result = ERROR_SUCCESS;
    else {
        result = GetLastError();
        if (ERROR_ALREADY_EXISTS == result) {
            if (SetFileSecurity(path, DACL_SECURITY_INFORMATION, sd))
                result = ERROR_SUCCESS;
            else {
                result = GetLastError();
                print_error(L"cannot set directory ACL", result);
            }
        }
        else
            print_error(L"cannot create directory with ACL", result);
    }
    goto cleanup;

fail:
    result = GetLastError();

cleanup:
    if (sid)
        FreeSid(sid);
    LocalFree(sd);
    LocalFree(acl);

    return result;
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Determines the data directory. Must only be called during installation
 * where we have a real account for the installing user. At service runtime
 * it will NOT determine anything useful (some global spot we must not care
 * about at all).
 *
 * @param dataDir      Where to put the whole data directory path.
 * @param dataDirSize  Size of the dataDir buffer, in characters.
 * @return             TRUE if the determination was successful. FALSE if not.
 */
BOOL current_user_data_dir(TCHAR* dataDir, size_t dataDirSize)
{
    BOOL found = SHGetSpecialFolderPath(
        NULL, dataDir, CSIDL_LOCAL_APPDATA, FALSE);
    if (!found)
        found = GetEnvironmentVariable(L"LOCALAPPDATA", dataDir, dataDirSize);
    if (!found)
        found = GetEnvironmentVariable(L"APPDATA", dataDir, dataDirSize);
    if (!found) {
        found = GetEnvironmentVariable(L"USERPROFILE", dataDir, dataDirSize);
        if (found) {
            _tcscat_s(dataDir, dataDirSize, L"\\");
            _tcscat_s(dataDir, dataDirSize, APPLICATION_DATA);
            found = is_dir(dataDir);
        }
    }
    if (!found)
        found = GetEnvironmentVariable(L"SYSTEMDRIVE", dataDir, dataDirSize);
    if (!found) {
        return FALSE;
    }
    _tcscat_s(dataDir, dataDirSize, L"\\");
    _tcscat_s(dataDir, dataDirSize, DATADIR_NAME);
    return TRUE;
}


/**
 * Some simple heuritics to check whether a given path might be a legit and
 * former Sighthound Video data directory.
 *
 * @param path  The path to check out.
 * @return      TRUE of the path seems to be what we think it is.
 */
BOOL is_data_dir(TCHAR* path)
{
    TCHAR** svObject;
    TCHAR* svObjects[] = { L"logs", L"license.lic", L"videos", NULL };
    for (svObject = svObjects; *svObject; svObject++) {
        TCHAR svObjectPath[MAX_PATH];
        _tcscpy_s(svObjectPath, _countof(svObjectPath), path);
        _tcscat_s(svObjectPath, _countof(svObjectPath), L"\\");
        _tcscat_s(svObjectPath, _countof(svObjectPath), *svObjects);
        if ((DWORD)-1 != get_file_attributes(svObjectPath))
            break;
    }
    return NULL != *svObject;
}


/**
 * To find the best data directory candidate.
 *
 * @param dataDir      Where to put the whole data directory path.
 * @param dataDirSize  Size of the dataDir buffer, in characters.
 * @return             TRUE if the determination was successful. FALSE if not.
 */
BOOL find_data_dir(TCHAR* dataDir, size_t dataDirSize)
{
    TCHAR path[MAX_PATH + UNLEN];
    TCHAR userName[UNLEN + 1];
    TCHAR *tail, *head;
    DWORD c, total, resume, err;
    LPUSER_INFO_1 userInfo;

    LOG(L"searching for data directory...")
    if (!current_user_data_dir(dataDir, dataDirSize))
        return FALSE;
    LOG(dataDir)
    if (is_data_dir(dataDir)) {
        LOG(L"current user's data directory matches")
        return TRUE;
    }
    c = _countof(userName);
    if (!GetUserName(userName, &c)) {
        print_error(L"cannot get user name", GetLastError());
        return TRUE;
    }
    LOG(userName)
    if (NULL == (tail = _tcsstr(dataDir, userName)))
        return TRUE;
    c = tail - dataDir;
    if (_tcsncpy_s(path, _countof(path), dataDir, c))
        return TRUE;
    head = &path[c];
    tail += _tcslen(userName);
    LOG(L"searching for user names...")
    resume = 0;
    do {
        DWORD i;
        userInfo = NULL;
        err = NetUserEnum(NULL,
                          1,
                          FILTER_NORMAL_ACCOUNT,
                          (LPBYTE*)&userInfo,
                          MAX_PREFERRED_LENGTH,
                          &c,
                          &total,
                          &resume);
        if (NERR_Success == err || err == ERROR_MORE_DATA) {
            for (i = 0; i < c; i++) {
                LOG(userInfo[i].usri1_name)
                _tcscpy_s(head, UNLEN, userInfo[i].usri1_name);
                _tcscat_s(head, UNLEN, tail);
                if (is_data_dir(path)) {
                    LOG(L"found matching data directory")
                    LOG(path)
                    _tcscpy_s(dataDir, dataDirSize, path);
                    err = NERR_Success;
                    break;
                }
            }
        }
        else
            print_error(L"user enumeration failed", err);
        if (userInfo)
            NetApiBufferFree(userInfo);
    }
    while (ERROR_MORE_DATA == err);
    return TRUE;
}


/**
 * Gets the location of the data directory pointer file.
 *
 * @param pointer      Where to put the pointer file path.
 * @param pointerSize  Size of the pointer buffer, in characters.
 * @return             TRUE if the pointer file path could be determined.
 */
BOOL get_data_dir_pointer(TCHAR* pointer, size_t pointerSize)
{
    TCHAR* lastbs;
    _tcscpy_s(pointer, pointerSize, _exeSvc);
    lastbs = _tcsrchr(pointer, '\\');
    if (!lastbs)
        return FALSE;
    *(lastbs + 1) = 0;
    _tcscat_s(pointer, pointerSize, DATADIR_POINTER);
    return TRUE;
}


/**
 * If a pointer (file) to a different data directory got written at
 * installation time we do return its content.
 *
 * @param dataDir      Where to put the whole data directory path.
 * @param dataDirSize  Size of the dataDir buffer, in characters.
 * @return             TRUE if a valid pointer file got discovered.
 *                     FALSE if missing or an error occurred. The dataDir
 *                     buffer won't be altered in such a case.
 */
BOOL get_data_dir_from_pointer(TCHAR* dataDir, size_t dataDirSize)
{
    FILE* f = NULL;
    errno_t err;
    TCHAR* p;
    TCHAR pointer[MAX_PATH];
    TCHAR line[MAX_PATH];

    if (!get_data_dir_pointer(pointer, _countof(pointer)))
        return FALSE;

    err = _wfopen_s(&f, pointer, L"rt+,ccs=UTF-8");
    if (err) {
        print_error(L"cannot open datadir pointer for reading", err);
        return FALSE;
    }
    p = fgetws(line, _countof(line), f);
    fclose(f);

    if (!p)
        return FALSE;
    line[_countof(line) - 1] = '\0';
         if (NULL != (p = _tcschr(line, '\r'))) *p = '\0';
    else if (NULL != (p = _tcschr(line, '\n'))) *p = '\0';

    if (is_dir(line)) {
        _tcscpy_s(dataDir, dataDirSize, line);
        return TRUE;
    }
    return FALSE;
}


/**
 * Called at installation time: if a data directory for the installing
 * user exists then its path will be recorded in a file placed next to
 * the service executable. We will always create the data directory if it
 * isn't there yet.
 *
 * @return  TRUE if the pointer got created successfully.
 */
BOOL create_data_dir_pointer()
{
    FILE* f;
    BOOL writeError;
    errno_t err;
    TCHAR pointer[MAX_PATH];
    TCHAR dataDir[MAX_PATH];

    if (!get_data_dir_pointer(pointer, _countof(pointer)))
        return FALSE;
    if (!find_data_dir(dataDir, _countof(dataDir)))
        return FALSE;
    LOG(dataDir)
    if (ERROR_SUCCESS != (err = ensure_dir_with_user_acl(dataDir))) {
        print_error(L"cannot ensure datadir access", err);
        return FALSE;
    }
    err = _wfopen_s(&f, pointer, L"wt+,ccs=UTF-8");
    if (err) {
        print_error(L"cannot open datadir pointer for writing", err);
        return FALSE;
    }
    writeError = 0 > fputws(dataDir, f) ||
                 0 > fputws(L"\n", f);
    fclose(f);
    if (writeError) {
        LOG(L"datadir pointer cannot be written to!?")
        DeleteFile(pointer);
        return FALSE;
    }
    LOG(L"datadir pointer written")
    return TRUE;
}

//////////////////////////////////////////////////////////////////////////////

// All things service management ...


/**
 * Makes sure that the current service configuration is correct.
 *
 * @param man  Service manager handle. Will not be closed.
 * @return     Exit code, ERROR_SUCCESS if everything's in order.
 */
int service_update(SC_HANDLE man) {

    int result = EXITCODE_ERROR;
    SC_HANDLE svc;

    svc = OpenService(man, SERVICE_NAME, SC_MANAGER_ALL_ACCESS);
    if (!svc) {
        print_error(L"cannot open service for update", GetLastError());
        return EXITCODE_ERROR;
    }
    else if (ChangeServiceConfig(svc,
            SERVICE_WIN32_OWN_PROCESS,
            SERVICE_AUTO_START,
            SERVICE_ERROR_NORMAL,
            _exeSvc,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            SERVICE_TITLE)) {
        LOG(L"service updated")
        result = EXITCODE_SUCCESS;
    }
    else {
        print_error(L"cannot update service config", GetLastError());
    }
    CloseServiceHandle(svc);
    return result;
}


/**
 * Installs the service. Expects the service not to be running and it being in
 * the official spot. If the service is already registered we make sure that
 * its configuration is updated. We also set the data directory pointer.
 *
 * @param  exeSvc  Path of the executable.
 * @return         Exit code. EXITCODE_SUCCESS also if service already exists.
 */
int service_install()
{
    int exitcode;
    SC_HANDLE man, svc;

    man = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (NULL == man) {
         print_error(L"cannot open service manager", GetLastError());
         return EXITCODE_SERVICE_ERROR;
    }

    svc = CreateService(
            man,
            SERVICE_NAME,
            SERVICE_TITLE,
            SERVICE_ALL_ACCESS,
            SERVICE_WIN32_OWN_PROCESS,
            SERVICE_AUTO_START,
            SERVICE_ERROR_NORMAL,
            _exeSvc,
            NULL, NULL, NULL, NULL, NULL);
    if (NULL == svc) {
        DWORD err = GetLastError();
        print_error(L"cannot create service", err);
        switch (err) {
            case ERROR_SERVICE_EXISTS:
                exitcode = service_update(man);
                break;
            case ERROR_SERVICE_MARKED_FOR_DELETE:
                exitcode = EXITCODE_SERVICE_REMOVAL_PENDING;
                break;
            default:
                exitcode = EXITCODE_SERVICE_ERROR;
                break;
        }
    }
    else {
        SERVICE_DESCRIPTION sd;

        ZeroMemory(&sd, sizeof(sd));
        sd.lpDescription = SERVICE_INFO;
        if (!ChangeServiceConfig2(svc, SERVICE_CONFIG_DESCRIPTION, &sd)) {
            print_error(L"cannot change service description", GetLastError());
        }
        CloseServiceHandle(svc);
        exitcode = EXITCODE_SUCCESS;
    }
    CloseServiceHandle(man);

    if (!create_data_dir_pointer())
        exitcode = EXITCODE_DATADIR_POINTER_ERROR;

    return exitcode;
}


/**
 * Opens a connection to the service manager and our service itself.
 *
 * @param man      Where to put the manager handle.
 * @param svc      Where to put the service handle.
 * @param acccess  Service access flags.
 * @return         Exit code, 0 on success.
 */
int service_open(SC_HANDLE* man, SC_HANDLE* svc, DWORD access)
{
    if (NULL == (*man = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS))) {
        print_error(L"cannot open service manager", GetLastError());
        return EXITCODE_SERVICE_ERROR;
    }

    if (NULL == (*svc = OpenService(*man, SERVICE_NAME, access))) {
        DWORD err = GetLastError();
        print_error(L"cannot open service", err);
        CloseServiceHandle(*man);
        return ERROR_SERVICE_DOES_NOT_EXIST == err ? EXITCODE_SERVICE_MISSING :
                                                     EXITCODE_SERVICE_ERROR;
    }

    return EXITCODE_SUCCESS;
}


/**
 * Starts the service. Also reports success if the service is running already.
 * The service will be told not to launch the backend.
 *
 * @return Exit code, 0 on success.
 */
int service_start()
{
    SC_HANDLE man, svc;
    int exitcode;

    if (EXITCODE_SUCCESS == (exitcode = service_open(
            &man, &svc, SC_MANAGER_ALL_ACCESS))) { // TODO: can we go with less rights here?
        const TCHAR* args[] = { SERVICE_NAME, ARG_NO_AUTOSTART };
        if (!StartService(svc, 2, args)) {
            DWORD err = GetLastError();
            if (ERROR_SERVICE_ALREADY_RUNNING == err) {
                exitcode = EXITCODE_SUCCESS;
            }
            else
                print_error(L"cannot start the service", err);
        }
        CloseServiceHandle(svc);
        CloseServiceHandle(man);
    }
    return exitcode;
}


/**
 * Stops the service, makes sure that the back-end is also down. If this works
 * out the (old) executable can be overwritten safely. This avoids having to
 * unregister the service and potentially having to restart the machine.
 *
 * @return EXITCODE_SUCCESS if the shutdown worked.
 */
int service_shutdown()
{
    DWORD result = EXITCODE_SUCCESS;
    SC_HANDLE man, svc;

    if (EXITCODE_SUCCESS == service_open(&man, &svc, SC_MANAGER_ALL_ACCESS)) {
        SERVICE_STATUS ss;
        ZeroMemory(&ss, sizeof(ss));
        if (ControlService(svc, SERVICE_CONTROL_STOP, &ss)) {
            time_t tmout = time(NULL) + STOP_TIMEOUT_SECS;
            LOG(L"waiting for service to stop...")
            for (;;) {
                if (!QueryServiceStatus(svc, &ss)) {
                    print_error(L"cannot query the service", GetLastError());
                    result = EXITCODE_ERROR;
                    break;
                }
                if (ss.dwCurrentState == SERVICE_STOPPED) {
                    LOG(L"service stopped")
                    break;
                }
                if (time(NULL) > tmout) {
                    print_error(L"timeout waiting for the service to stop",
                                GetLastError());
                    result = EXITCODE_ERROR;
                    break;
                }
                Sleep(POLL_MILLIS);
            }
        }
        else {
            DWORD err = GetLastError();
            if (ERROR_SERVICE_NOT_ACTIVE != err) {
                print_error(L"cannot stop the service", err);
                result = EXITCODE_ERROR;
            }
        }
        CloseServiceHandle(svc);
        CloseServiceHandle(man);
    }
    if (kill_processes(KILL_CANDIDATES_ALL, 0))
        result = EXITCODE_ERROR;
    return result;
}


/**
 * Removes the service from the SCM's registry.
 *
 * @return  Exit code, 0 on success.
 */
int service_remove()
{
    SC_HANDLE man, svc;
    int exitcode;

    // FIXME: we also want the service to stop first, no?
    exitcode = service_open(&man, &svc, SC_MANAGER_ALL_ACCESS);
    if (EXITCODE_SUCCESS == exitcode) {
        if (DeleteService(svc)) {
            LOG(L"service removed")
            if (!DeleteService(svc) &&
                ERROR_SERVICE_MARKED_FOR_DELETE == GetLastError()) {
                LOG(L"need to restart detected")
                exitcode = EXITCODE_SERVICE_REMOVAL_PENDING;
            }
        }
        else {
            DWORD err = GetLastError();
            print_error(L"cannot remove service", err);
            switch (err) {
                case ERROR_SERVICE_DOES_NOT_EXIST:
                    LOG(L"service does not exist?!")
                    exitcode = EXITCODE_SUCCESS;
                    break;
                case ERROR_SERVICE_MARKED_FOR_DELETE:
                    LOG(L"service marked for deletion")
                    exitcode = EXITCODE_SERVICE_REMOVAL_PENDING;
                    break;
                default:
                    exitcode = EXITCODE_SERVICE_ERROR;
                    break;
            }
        }
        CloseServiceHandle(svc);
        CloseServiceHandle(man);
    }
    else if (EXITCODE_SERVICE_MISSING == exitcode)
        exitcode = EXITCODE_SUCCESS;
    return exitcode;
}


//////////////////////////////////////////////////////////////////////////////

// Service runtime ...

/**
 * To tell the SCM about the service's current status.
 * @param ctx    The service context. Can be NULL if out of memory.
 * @param state  Current state of the service.
 * @param exit   Exit code.
 * @param hint   Wait hint, if things take longer than expected, or just zero.
 */
void update_status(struct Context* ctx, DWORD state, DWORD exit, DWORD hint)
{
    SERVICE_STATUS ss;

    ZeroMemory(&ss, sizeof(ss));
    ss.dwServiceType      = SERVICE_WIN32_OWN_PROCESS;
    ss.dwCurrentState     = state;
    ss.dwWin32ExitCode    = exit;
    ss.dwWaitHint         = hint;
    ss.dwControlsAccepted = SERVICE_START_PENDING == state ? 0 : SERVICE_ACCEPT_STOP;
    ss.dwControlsAccepted |= SERVICE_ACCEPT_SHUTDOWN;

    if (ctx &&
        SERVICE_RUNNING != state &&
        SERVICE_STOPPED != state) {
        ss.dwCheckPoint = ++ctx->chkp;
    }
#ifdef RUN_IN_CONSOLE
    _tprintf(L"update_status state=%u, exit=%u, hint=%u, chkp=%u\n",
             state, exit, hint, ss.dwCheckPoint);
#else
    if (!SetServiceStatus(ctx->ssh, &ss)) {
        print_error(L"cannot update service status", GetLastError());
    }
#endif
}


#ifdef RUN_IN_CONSOLE

/**
 * Console control handler for testing when not running as a service.
 *
 * @param ctrl  Console control, we're looking for Ctrl+C, so the user can
 *              simulate a service-stop command sent by the SCM.
 */
BOOL WINAPI ctrl_handler(DWORD ctrl) {
    if (ctrl == CTRL_C_EVENT) {
        _putts(L"got hit by Ctrl+C");
        if (_ctx) {
            update_status(_ctx, SERVICE_STOP_PENDING, NO_ERROR, 0);
            SetEvent(_ctx->evtExit);
        }
    }
    return TRUE;
}

#else

/**
 * Handler where the service receives control commands from the SCM.
 *
 * @param ctrl Control command.
 */
VOID WINAPI ctrl_handler(DWORD ctrl)
{
    TCHAR log[64];
    _stprintf_s(log, _countof(log), L"got control command x%x", ctrl);
    LOG(log)
    switch (ctrl) {
        case SERVICE_CONTROL_SHUTDOWN:
        case SERVICE_CONTROL_STOP:
            if (_ctx) {
                update_status(_ctx, SERVICE_STOP_PENDING, NO_ERROR, 0);
                SetEvent(_ctx->evtExit);
            }
            break;
        default:
            break;
   }
}

#endif


/**
 * Launches the Sighthound backend executable.
 *
 * @param ctx  Service context.
 * @return     ERROR_SUCCESS if the launch succeeded, otherwise an error.
 */
DWORD launch_backend(struct Context* ctx)
{
    TCHAR* lastbs = NULL;
    TCHAR currentDir[MAX_PATH] = { 0 };
    STARTUPINFO sinf;

    if (!ctx->config.backend) {
        LOG(L"Not launching the backend due to configuration.")
        return ERROR_ACCESS_DENIED;
    }

    ZeroMemory(&sinf, sizeof(sinf));
    sinf.cb = sizeof(sinf);

    lastbs = _tcsrchr(_exeSvc, '\\');
    if (lastbs) {
        _tcsncpy_s(currentDir, _countof(currentDir),
                   _exeSvc, (size_t)(lastbs - _exeSvc));
    }
    LOG(currentDir)
    LOG(L"Creating process...")

    return CreateProcessW(
            NULL,
            ctx->cmdln,
            NULL,
            NULL,
            FALSE,
            0,
            NULL,
            currentDir,
            &sinf,
            &ctx->procInfo) ? ERROR_SUCCESS : GetLastError();
}


/**
 * The service runtime entry point. When this function returns the service is
 * down and stopped.
 *
 * @param argc  Number of service arguments.
 * @param argv  Service arguments.
 */
VOID WINAPI svc_main(DWORD argc, LPTSTR *argv)
{
    DWORD  err = ERROR_SUCCESS;
    HANDLE exchangeMap = NULL;
    TCHAR* lastbs;
    TCHAR  dataDir[MAX_PATH] = { 0 };
    TCHAR  log[512];
    SECURITY_ATTRIBUTES sa;
    struct Context* ctx = NULL;
    struct Exchange* exchange = NULL;
    int    backendProcessCount;
    time_t tmout;

    ZeroMemory(&sa, sizeof(sa));

    ctx = (struct Context*)calloc(1, sizeof(struct Context));
    if (!ctx) {
        err = ERROR_OUTOFMEMORY;
        goto cleanup;
    }
    _ctx = ctx;
    ctx->chkp = 1;

    sa.nLength = sizeof(sa);
    sa.bInheritHandle = FALSE;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptor(
            L"D:"
            L"(D;OICI;GA;;;BG)"   // no guests
            L"(D;OICI;GA;;;AN)"   // no anonymous users
            L"(A;OICI;GRGW;;;AU)" // read/write for users
            L"(A;OICI;GA;;;BA)",  // all for admin (just because)
            SDDL_REVISION_1,
            &sa.lpSecurityDescriptor,
            0)) {
        DWORD err = GetLastError();
        print_error(L"cannot create security descriptor", err);
        goto cleanup;
    }

    exchangeMap = CreateFileMapping(INVALID_HANDLE_VALUE, &sa, PAGE_READWRITE,
                                    0, sizeof(exchange), EXCHANGE_NAME);
    if (!exchangeMap) {
        print_error(L"cannot create map", err);
        goto cleanup;
    }

    exchange = (struct Exchange*)MapViewOfFile(exchangeMap,
                                               FILE_MAP_READ | FILE_MAP_WRITE,
                                               0, 0, 0);
    if (!exchange) {
        err = GetLastError();
        print_error(L"cannot map view", err);
        goto cleanup;
    }
    ZeroMemory(exchange, sizeof(*exchange));
    exchange->processId = GetCurrentProcessId();
    ctx->exchange = exchange;

#ifdef RUN_IN_CONSOLE
    SetConsoleCtrlHandler(ctrl_handler, TRUE);
#else
    LOG(L"registering service handler")
    if (0 == (ctx->ssh = RegisterServiceCtrlHandler(SERVICE_NAME, ctrl_handler))) {
        err = GetLastError();
        print_error(L"cannot register control handler", err);
        goto cleanup;
    }
    LOG(L"control handler registered")
#endif

    update_status(ctx, SERVICE_START_PENDING, NO_ERROR, 5000);
    LOG(L"status is now pending")

    ctx->cmdln[0] = '"';
    _tcscpy_s(&ctx->cmdln[1], _countof(ctx->cmdln) - 1, _exeSvc);
    lastbs = _tcsrchr(ctx->cmdln, '\\');
    if (lastbs)
        lastbs[1] = '\0';

    if (!get_data_dir_from_pointer(dataDir, _countof(dataDir))) {
        LOG(L"datadir pointer N/A");
        goto cleanup;
    }

    // can't hurt to refresh the ACL every time, just in case something changed it
    if (ERROR_SUCCESS != (err = ensure_dir_with_user_acl(dataDir))) {
        print_error(L"ensuring datadir failed", err);
        goto cleanup;
    }
    _tcscpy_s(exchange->dataDir, _countof(exchange->dataDir), dataDir);
    LOG(dataDir)

    exchange->size = sizeof(*exchange);  // signal that the exchange is now valid

    if (!config_read(ctx))
        LOG(L"initial configuration loading failed")

    if (2 == argc && !_tcscmp(ARG_NO_AUTOSTART, argv[1])) {
        ctx->config.autoStart = FALSE;
        LOG(L"auto-start disabled via command line argument")
    }

    LOG(L"creating event")
    ctx->evtExit = CreateEvent(NULL, FALSE, FALSE, NULL);
    if (!ctx->evtExit) {
        DWORD err = GetLastError();
        print_error(L"cannot create event", err);
        goto cleanup;
    }

    _tcscat_s(ctx->cmdln, _countof(ctx->cmdln), BACKEND_EXE);
    _tcscat_s(ctx->cmdln, _countof(ctx->cmdln), L"\" " BACKEND_ARG1 L" \"");
    _tcscat_s(ctx->cmdln, _countof(ctx->cmdln), dataDir);
    _tcscat_s(ctx->cmdln, _countof(ctx->cmdln), L"\" " BACKEND_ARG2 L" " BACKEND_ARG3 L"");
    LOG(ctx->cmdln)

    update_status(ctx, SERVICE_RUNNING, NO_ERROR, 0);
    LOG(L"service running")

    exchange->launch = ctx->config.autoStart ? 0xffff : 0;
    if (exchange->launch)
        LOG(L"initial launch set")

    for (;;) {
        LONG launch = InterlockedExchange(&exchange->launch, 0);
        LONG status = 0;
        InterlockedIncrement(&exchange->cycles);
        if (launch) {
            if (!config_read(ctx))
                LOG(L"error reloading configuration");
            _sntprintf_s(log, _countof(log), _TRUNCATE,
                         L"got launch signal x%08x (cycles=%d)",
                         launch, exchange->cycles);
            LOG(log)
            if (LAUNCH_FLAG_KILL_FIRST & launch)
                kill_processes(KILL_CANDIDATES, exchange->launchProcessId);
            if (LAUNCH_MASK & launch) {
                err = launch_backend(ctx);
                if (err)
                    print_error(L"cannot launch the EXE", err);
                else
                    LOG(L"backend launched")
            }
            status = launch;
        }
        InterlockedExchange(&exchange->status, status);

        if (WAIT_TIMEOUT != WaitForSingleObject(ctx->evtExit, POLL_MILLIS))
            break;
    }

    // we signal the back-end (if there) and give it some time to pick this up
    backendProcessCount = 0;
    enumerate_processes(backend_detect_handler, &backendProcessCount, 0);
    if (0 == backendProcessCount)
        LOG(L"no backend processes running")
    else {
        LOG(L"setting shutdown flag ...")
        _ctx->exchange->shutdown = 1;
        tmout = time(NULL) + SHUTDOWN_SIGNAL_TIMOUT_SECS;
        while (_ctx->exchange->shutdown) {
            if (time(NULL) > tmout) {
                LOG(L"backend did not pick up shutdown flag in time")
                break;
            }
            Sleep(POLL_MILLIS);
        }
    }

    LOG(L"exiting...")

    err = ERROR_SUCCESS;

cleanup:
    if (_ctx) {
        _ctx->exchange = NULL;
        _ctx = NULL;
    }

    if (exchange)
        UnmapViewOfFile(exchange);
    if (exchangeMap)
        CloseHandle(exchangeMap);

    update_status(ctx, SERVICE_STOPPED, err, 0);

    LocalFree(sa.lpSecurityDescriptor);
    free(ctx);
}


/**
 * Where the service registers its runtime entry point and starts the dispatcher.
 *
 * @return Exit code, 0 on success.
 */
int service_execute(int argc, _TCHAR* argv[])
{
#ifdef RUN_IN_CONSOLE
    svc_main(argc, argv);
    return EXITCODE_SUCCESS;
#else
    SERVICE_TABLE_ENTRY dtab[] = {
        { SERVICE_NAME, (LPSERVICE_MAIN_FUNCTION) svc_main },
        { NULL, NULL }
    };
    argc = 0;
    argv = NULL;

    if (StartServiceCtrlDispatcher(dtab)) {
        LOG(L"dispatcher done");
        return EXITCODE_SUCCESS;
    }
    else {
        print_error(L"dispatcher could not be started", GetLastError());
        return EXITCODE_ERROR;
    }
#endif
}

//////////////////////////////////////////////////////////////////////////////

// (minidumps only in release, so in dev we can catch things in the debugger)
#ifndef _DEBUG
//extern void minidump_init(TCHAR* prefix, UINT exitOnCrash, UINT maxDumps);
#endif

/**
 * Application entry point. Called both in the command prompt to remove,
 * disable and install the service, as well as by the SCM to simply run it.
 *
 * @param argc  Number of command line arguments.
 * @param argv  Command line arguments.
 * @return      Exit code.
 */
int _tmain(int argc, _TCHAR* argv[])
{
#ifndef _DEBUG
//    minidump_init(SERVICE_NAME, 0xbaadc0de, (UINT)-1);
#endif

    if (!GetModuleFileName(NULL, _exeSvc, _countof(_exeSvc))) {
        print_error(L"cannot get EXE path", GetLastError());
        return EXITCODE_ERROR;
    }

    if (1 < argc) {
        int i;
        int exitcode = EXITCODE_SUCCESS;

        GetTempPath(MAX_PATH, _installLog); // separate logs just for installation things
        _tcscat_s(_installLog, _countof(_installLog), L"\\");
        _tcscat_s(_installLog, _countof(_installLog), INSTALL_LOG_FILE);

        for (i = 1; i < argc && !exitcode; i++) {
            TCHAR log[256];
            TCHAR* cmd = argv[i];

            if (!_tcsncmp(ARG_PREFIX, cmd, _tcslen(ARG_PREFIX)))
                continue;
            LOG(cmd)
                 if (!_tcscmp(L"remove"  , cmd)) exitcode = service_remove();
            else if (!_tcscmp(L"shutdown", cmd)) exitcode = service_shutdown();
            else if (!_tcscmp(L"install" , cmd)) exitcode = service_install();
            else if (!_tcscmp(L"start"   , cmd)) exitcode = service_start();
            else {
                _sntprintf_s(log, _countof(log), _TRUNCATE, L"unknown command '%s'", cmd);
                LOG(log);
                exitcode = EXITCODE_BAD_ARGS;
                break;
            }
        }
        return exitcode;
    }
    return service_execute(argc, argv);
}
