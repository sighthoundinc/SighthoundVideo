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

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include <stdarg.h>
#include <stdbool.h>
#include <errno.h>
#include <unistd.h>
#include <signal.h>
#include <unistd.h>
#include <iconv.h>
#include <pwd.h>
#include <sys/types.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/sysctl.h>
#include <sys/stat.h>
#include <libkern/OSAtomic.h>

extern char **environ;

#include "shlaunch.h"

//
// This file gets auto-generated via the common ./app or make step. So you need
// to run one of these, create our own file containing just the following line:
//
// #define SHLAUNCH_BUILD "r00000"
//
// Replace r00000 with the actual build number if you want the service to work
// with the SV application in development itself.
//
#include "shlaunch_build.h"

///////////////////////////////////////////////////////////////////////////////

// Flag to turn on things useful when running the service in a terminal for
// testing purposes, rather than having it activated by launchd.
//#define RUN_IN_TERMINAL

///////////////////////////////////////////////////////////////////////////////

// Exit code: the service run succeeded.
#define RET_SUCCESS  0
// Exit code: some error occurred.
#define RET_ERROR  1
// Exit code: setting up shared memory didn't work.
#define RET_SHARED_MEMORY_ERROR  2
// Exit code: activation failed.
#define RET_ACTIVATE_ERROR  3
// Exit code: wrong/missing command line argument(s).
#define RET_ARGS_ERROR  4
// Exit code: given build does not match us.
#define RET_BUILD_MISMATCH  5
// Exit code: could not change from root to the actual user ID.
#define RET_SETUID_ERROR  6

// Product name, for user data directoru naming.
#define PRODUCT_NAME  "Sighthound Video"

// Format string for log messages (date, level, text). Compatible to Python
#define LOG_FORMAT  "%s - %s - %d - %s\n"

// Default log file name. The log file is written to the temporary folder first,
// then to the logs directory.
#define LOG_FILE   "shlaunch.log"

// Maximum number of characters of a log message
#define LOG_MAX_LINE     1024

// Log levels.
#define LOG_LEVEL_INFO   "INFO"
#define LOG_LEVEL_ERROR  "ERROR"

// Log file size limit, if reached we roll over, keeping the last generation.
#define LOG_FILE_MAXLEN    (1024 * 1024)

// Extension to add to a rolled log file.
#define LOG_FILE_ROLLEXT    ".1"

// The configuration file (INI format). Written by the frontend to control the
// autostart feature, i.e. launch the backend at system/service start time.
#define CONFIG_FILE   "shlaunch.cfg"

// Configuration data tokens.
#define CONFIG_ASSIGN         "="
#define CONFIG_KEY_AUTOSTART  "autostart"
#define CONFIG_KEY_BACKEND    "backend"
#define CONFIG_VALUE_TRUE     "TRUE"

// Time to wait in the service loop, where we listen for launch signals.
#define IDLE_MILLIS     100
// How long to wait between process kill attempts.
#define KILL_WAIT_MILLIS   250
// How often to try to kill processes.
#define KILL_WAIT_RETRIES  20
// How long to wait for the back-end processes to cease on service termination.
#define SHUTDOWN_WAIT_SECS  10

// Maximum number of Sighthound Video processes to expect.
#define MAX_PROCESSES   256

// The global application data directory.
#define APP_DATA_DIR    "/Library/Application Support/" PRODUCT_NAME

// Name of the SV logs directory, locate in the user data directory.
#define LOGS_DIR  "logs"

// Name of the executable to launch. Due to OSX firewall issue everything
// carries the same name, so this is the backend.
#define SV_EXE  "Sighthound Video"

// Arguments to start the backend process.
#define ARG_FROZEN     "--frozen"
#define ARG_FROZEN2    "macosx_app"
#define ARG_BACKEND    "--backEnd"
#define ARG_MARKER1    "--sh-2e4fce7e"
#define ARG_MARKER2    "--sh-baef77e9"

// Names of processes we have to get rid of. Notice that the service might have
// to kill its own kind, but never itself of course.
char* SIGHTHOUND_PROCESS_NAMES[] = { SV_EXE, "shlaunch", NULL };

///////////////////////////////////////////////////////////////////////////////

// Service context, i.e. all things the service has to keep track of at runtime.
struct SHLaunch {
    struct Exchange* exchange;  // shared memory
    char dataDir[PATH_MAX];     // data directory (for service purposes)
    char exeDir[PATH_MAX];      // service executable location
    int sharedMemoryId;         // shared memory ID (for releasing it)
    int terminate;              // service shutdown flag
};

// Service configuration.
struct SHLaunchConfig {
    bool autoStart; // whether to launch the backend at service startup time
    bool backend;   // if the backend is allowed to be launched at all
};
struct SHLaunchConfig _cfgDefault = { false, true };

// The one and only (global) service data instance.
struct SHLaunch* _shl = NULL;

// PID of calling process, which is not supposed to be killed. We also use this
// to detect the general activation situation, causing for instance to launch
// the backend unconditionally.
int _noKillPid = -1;

///////////////////////////////////////////////////////////////////////////////

#define DAEMON_ID   "com.sighthound.video.launch"

#define PLIST_PATH  "/Library/LaunchDaemons/" DAEMON_ID ".plist"
#define PLIST_TEMPLATE \
"<?xml version=\"1.0\" encoding=\"UTF-8\"?>" \
"<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n" \
"<plist version=\"1.0\"><dict>\n" \
"<key>Label</key>\n" \
"<string>" DAEMON_ID "</string>\n" \
"<key>ProgramArguments</key>\n" \
"<array>\n" \
"<string>%s</string>\n" \
"<string>%s</string>\n" \
"</array>\n" \
"<key>RunAtLoad</key>\n" \
"<true/>\n" \
"<key>UserName</key>\n" \
"<string>%s</string>\n" \
"</dict></plist>"

/**
 * Writes out the plist file declaring the service/daemon in the system.
 *
 * @param path      The path to this executable (UTF-8).
 * @param build     Build string, to be saved in the plist.
 * @param userName  User name to tun the service under (UTF-8).
 * @return          Zero on success, error code otherwise.
 */
int create_daemon_plist(char* path, char* build, char* userName)
{
    char doc[sizeof(PLIST_TEMPLATE) + PATH_MAX + 256];
    int n, result;
    size_t c;
    FILE* f;

    n = snprintf(doc, sizeof(doc), PLIST_TEMPLATE, path, build, userName);
    if (n >= sizeof(doc) ||
        n <  sizeof(PLIST_TEMPLATE))
        return E2BIG;

    if (NULL == (f = fopen(PLIST_PATH, "wb")))
        return errno ? errno : EPERM;

    result = 0;
    c = strlen(doc);
    if (c != fwrite(doc, sizeof(char), c, f))
        result = ferror(f);

    if (fclose(f))
        result = ferror(f);

    if (!result && chmod(PLIST_PATH, 0644))
        result = errno;

    if (!result) {
        // cheap way to get around issuing a lot of ACL API calls - if for
        // whatever reason this fails the only consequence is that the plist
        // file cannot be deleted when the service detects that its executable
        // is gone and terminates itself ...
        char cmd[256 + 32 + PATH_MAX];
        if (sizeof (cmd) > snprintf(cmd, sizeof(cmd),
            "chmod +a \"%s allow delete\" \"%s\"", userName, PLIST_PATH))
            system(cmd);
    }

    if (result)
        unlink(PLIST_PATH);

    return result;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Creates a directory with the attribute 0777 (all access).
 *
 * @param dir  The directory to create.
 * @return     Result, see mkdir().
 */
int mkdir_0777(char* dir) {
    mode_t umsk = umask(0);
    int result = mkdir(dir, 0777);
    umask(umsk);
    return result;
}

/**
 * Sleeps for a certain amount of time. Interruptible by POSIX signals.
 *
 * @param millis  The number of milliseconds to idle.
 */
void msleep(int millis)
{
    usleep(1000 * millis);
}

/**
 * Converts a UTF-8 string to Unicode.
 *
 * @param utf8     The UTF-8 string to convert.
 * @param unicode  Where to put the Unicode string. MUST have the right size,
 *                 which is the length plus the terminating zero, times two.
 * @return         Pointer to the Unicode string, or NULL on error.
 */
wchar_t* utf8_to_unicode(char* utf8, wchar_t* unicode)
{
    iconv_t ih = (iconv_t)-1;
    size_t len = strlen(utf8);
    size_t szUtf8 = len;
    size_t szUnicode = len * sizeof(wchar_t);

    ih = iconv_open("UCS-4-INTERNAL", "UTF-8");
    if ((iconv_t)-1 == ih)
        goto fail;
    if ((size_t)-1 == iconv(ih, &utf8, &szUtf8, (char**)&unicode, &szUnicode))
        goto fail;
    unicode[len] = 0;
    goto cleanup;
fail:
    unicode = NULL;
cleanup:
    if ((iconv_t)-1 != ih)
        iconv_close(ih);
    return unicode;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Log function. Writes data to a log file, either/initially in the temporary
 * directory (once available).
 *
 * @param lvl  The log level. See LOG_LEVEL_*.
 * @param msg  Message to write out.
*/
void _log(char* lvl, char* msg)
{
    char logPath[PATH_MAX];
    int retry;
    char tstamp[128];
    FILE * f;
    struct timeval tm;

    gettimeofday(&tm, NULL);
    strftime(tstamp, sizeof(tstamp), "%F %T", localtime(&tm.tv_sec));
    sprintf(&tstamp[strlen(tstamp)], ",%03d", tm.tv_usec / 1000);

#ifdef RUN_IN_TERMINAL
    printf(LOG_FORMAT, tstamp, lvl, getpid(), msg);
#endif
    for (retry = 0; retry < 2; retry++) {
        if (!retry && _shl && _shl->dataDir[0]) {
            if (access(_shl->dataDir, R_OK))
                continue;
            strcpy(logPath, _shl->dataDir);
            strcat(logPath, LOGS_DIR);
            if (access(logPath, R_OK))
                continue;
            strcat(logPath, "/");
        }
        else {
            char* tmpDir = getenv("TMPDIR");
            if (!tmpDir) {
                tmpDir = "/tmp/";
            }
            strcpy(logPath, tmpDir);
            retry = 1;
        }
        strcat(logPath, LOG_FILE);
        {
            char logPath1[PATH_MAX];
            struct stat st;
            if (!stat(logPath, &st) && st.st_size > LOG_FILE_MAXLEN) {
                strcpy(logPath1, logPath);
                strncat(logPath1, LOG_FILE_ROLLEXT,
                        sizeof(logPath1) - strlen(logPath1) - 1);
                logPath1[sizeof(logPath1) - 1] = '\0';
                remove(logPath1);
                if (-1 == rename(logPath, logPath1))
                    remove(logPath);
            }
        }
        f = fopen(logPath, "a");
        if (!f) {
            continue;
        }
        fprintf(f, LOG_FORMAT, tstamp, lvl, getpid(), msg);
        fclose(f);
        break;
    }
}

/**
 * Log a formatted message.
 *
 * @param lvl   The log level. See LOG_LEVEL_*.
 * @param fmt   Format string, printf-compatible.
 * @param args  Zero or more arguments.
 */
void _logf(char* lvl, char* fmt, va_list args)
{
    char ln[LOG_MAX_LINE];
    vsnprintf(ln, sizeof(ln), fmt, args);
    ln[sizeof(ln) - 1] = 0;
    _log(lvl, ln);
}

/**
 * Log a formatted message with INFO level.
 *
 * @param fmt   Format string, printf-compatible.
 * @param args  Zero or more arguments.
 */
void _logf_i(char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    _logf(LOG_LEVEL_INFO, fmt, args);
    va_end (args);
}

/**
 * Log a formatted message with error level.
 *
 * @param fmt   Format string, printf-compatible.
 * @param args  Zero or more arguments.
 */
void _logf_e(char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    _logf(LOG_LEVEL_ERROR, fmt, args);
    va_end (args);
}

/**
 * Logs (most of) the shared memory exchange structure.
 *
 * @param exchg  The exchange data to log.
 */
void _log_exchange(struct Exchange* exchg)
{
    _logf_i("sz=%d, cycl=%d, pid=%d, stat=%d, lpid=%d, lnch=x%x, "
            "shutd=%d, bld=%s, ddir[0]=%d, pad[0]=%d",
            exchg->size,
            exchg->cycles,
            exchg->processId,
            exchg->status,
            exchg->launchProcessId,
            exchg->launch,
            exchg->shutdown,
            exchg->build,
            exchg->dataDir[0],
            exchg->_pad16[0]);
}

///////////////////////////////////////////////////////////////////////////////

char _homeDir[PATH_MAX] = { 0 };

/**
 * Gets the home directory. Determines (and caches) it, if needed.
 *
 * @return  The user's home directory.
 */
char* home_dir()
{
    if (!_homeDir[0]) {
        int uid = getuid();
        struct passwd *pw = getpwuid(uid);
        if (pw && pw->pw_dir && pw->pw_dir[0]) {
            strcpy(_homeDir, pw->pw_dir);
            _logf_i("home directory is '%s'", _homeDir);
            return _homeDir;
        }
        strcpy(_homeDir, uid ? "/tmp" : "/var/root");
        _logf_e("cannot determine home directory, set to '%s'", _homeDir);
    }
    return _homeDir;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Tries to to get rid of formerly created shared memory.
 *
 * @return  Zero on successful removal or if there is not such a leftover.
 */
int exchange_reset()
{
    int smid = shmget(SHARED_MEMORY_KEY, 32, 0);
    if (smid < 0 || errno == ENOENT)
        return 0;
    if (shmctl(smid, IPC_RMID, 0))
        return errno;
    return 0;
}


/**
 * Creates the shared memory for exchanging control information. If it already
 * exists the resource will be re-created. Notice that the shared memory will
 * be r/w accessible by every other process.
 *
 * @param shl  The service context.
 * @return     Zero on success, error code otherwise.
 */
int exchange_open(struct SHLaunch* shl)
{
    int smid = -1, attempt;
    void* smem;

    for (attempt = 0; attempt < 2; attempt++) {
        smid = shmget(SHARED_MEMORY_KEY, sizeof(struct Exchange),
                      IPC_CREAT | IPC_EXCL | 0666);
        if (smid < 0) {
            if (!attempt &&
                (errno == EEXIST ||
                 errno == EINVAL)) {
                _logf_e("shared memory exists already, removing it... ");
                int err = exchange_reset();
                if (err)
                    _logf_e("removal failed (error %d)", err);
                else
                    continue;
            }
            _logf_e("shmget returned %d (error %d)", smid, errno);
            return RET_SHARED_MEMORY_ERROR;
        }
        break;
    }
    smem = shmat(smid, NULL, 0);
    if ((void*)-1 == smem) {
        _logf_e("shmat failed (error %d), ", errno);
        shmctl(smid, IPC_RMID, 0);
        return RET_SHARED_MEMORY_ERROR;
    }
    shl->exchange = (struct Exchange*)smem;
    shl->sharedMemoryId = smid;

    return RET_SUCCESS;
}

/**
 * Closes the shared memory used for exchanging control information. Notice that
 * this really invalidates the memory behind it, meaning any client accessing it
 * afterwards will crash with an access violation!
 *
 * @param shl  The service context.
 * @return     Zero on success, error code otherwise.
 */
int exchange_close(struct SHLaunch* shl)
{
    _logf_i("cleaning up shared memory...");
    if (shl->exchange) {
        if (shmdt((void*)shl->exchange)) {
            _logf_e("shdt failed (error %d), ", errno);
        }
        if (-1 == shmctl(shl->sharedMemoryId, IPC_RMID, 0)) {
            _logf_e("shctl failed (error %d), ", errno);
        }
        shl->exchange = NULL;
        shl->sharedMemoryId = -1;
    }
    return RET_SUCCESS;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Loads the service configuration, using defaults on error/missing items.
 *
 * @param shl  The service context. The data directory needs to be available.
 * @param cfg  Where to store the configuration.
 * @return     True if the file was present and all items were found.
 */
bool cfg_load(struct SHLaunch* shl, struct SHLaunchConfig* cfg)
{
    static char* tokenAutoStart = CONFIG_KEY_AUTOSTART CONFIG_ASSIGN;
    static char* tokenBackend = CONFIG_KEY_BACKEND CONFIG_ASSIGN;

    FILE* f;
    char cfgFile[PATH_MAX];
    int found = 0;

    *cfg = _cfgDefault;
    strcpy(cfgFile, shl->dataDir);
    strcat(cfgFile, CONFIG_FILE);
    f = fopen(cfgFile, "r");
    if (!f) {
        _logf_e("cannot read config file (error %d)", errno);
    }
    else {
        char ln[256];
        while (fgets(ln, sizeof(ln), f)) {
            int tokenLength;
            tokenLength = strlen(tokenAutoStart);
            if (0 == strncmp(ln, tokenAutoStart, tokenLength)) {
                cfg->autoStart = !strncmp(&ln[tokenLength],
                                          CONFIG_VALUE_TRUE,
                                          strlen(CONFIG_VALUE_TRUE));
                found |= 1;
                continue;
            }
            tokenLength = strlen(tokenBackend);
            if (0 == strncmp(ln, tokenBackend, tokenLength)) {
                cfg->backend = !strncmp(&ln[tokenLength],
                                        CONFIG_VALUE_TRUE,
                                        strlen(CONFIG_VALUE_TRUE));
                found |= 2;
            }
        }
        fclose(f);
    }
    _logf_i("configuration loaded (found=%d, autostart=%d, backend=%d)", found,
            cfg->autoStart, cfg->backend);
    return 3 == found;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * If necessary, create the global user data directory.
 *
 * @return  Zero on success, error code otherwise.
 */
int prepare_data_dir()
{
    if (access(APP_DATA_DIR, R_OK)) {
        if (ENOENT == errno) {
            if (mkdir_0777(APP_DATA_DIR)) {
                _logf_e("cannot create data directory (error %d)", errno);
                return RET_ERROR;
            }
            _logf_i("data directory created");
        }
        else {
            _logf_e("cannot access data directory (error %d)", errno);
            return RET_ERROR;
        }
    }
    return RET_SUCCESS;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Enumerate all processes.
 *
 * @param handler  Handler (data, user ID, process ID, parent process ID,
 *                 process command) to be called for every process detected.
 *                 If it returns anything than zero the enumeration stops and
 *                 that result is returned by the function.
 * @param ctx      Arbitrary data pointer to be passed to each callback.
 * @return         Zero on fulll enumeration, otherwise -1 on error code or the
 *                 handler result which caused the interruption.
 */
int enum_processes(int(*handler)(void*, int uid, int pid, int ppid, char* comm),
                   void* ctx)
{
    struct kinfo_proc* kips = NULL;
    int names[] = { CTL_KERN, KERN_PROC, KERN_PROC_ALL, 0 };
    int retry, res = -1;
    size_t sz = -1, c, i;

    res = sysctl(names, 3, NULL, &sz, NULL, 0);
    if (res)
        goto fail;
    for (retry = 0; retry < 10; retry++) {
        kips = malloc(sz);
        if (!kips) {
            res = ENOMEM;
            goto fail;
        }
        res = sysctl(names, 3, kips, &sz, NULL, 0);
        if (res) {
            free(kips);
            kips = NULL;
            continue;
        }
        break;
    }
    if (!kips)
        goto fail;
    c = sz / sizeof(struct kinfo_proc);
    for (i = 0; i < c; i++) {
        uid_t uid  = kips[i].kp_eproc.e_ucred.cr_uid;
        int   ppid = kips[i].kp_eproc.e_ppid;
        int   pid  = kips[i].kp_proc.p_pid;
        char* comm = kips[i].kp_proc.p_comm;
        res = handler(ctx, uid, pid, ppid, comm);
        if (res)
            break;
    }
fail:
    free(kips);
    return res;
}

/**
 * Checks if a process is of SV nature.
 * @param comm  The process command.
 * @return      Zero if it's not a SV thing.
 */
int is_sv_process(char* comm) {
    char** spn = SIGHTHOUND_PROCESS_NAMES;
    while (*spn) {
        if (!strcmp(*spn++, comm))
            return 1;
    }
    return 0;
}

// Handler to count Sighthound Video processes. Context is a simple int* - does
// not count the calling process or this instance.
int count_handler(void* ctx, int uid, int pid, int ppid, char* comm) {
    if (is_sv_process(comm)) {
        int* count = (int*)ctx;
        _logf_i("found SV process pid=%d, uid=%d, comm=%s", pid, uid, comm);
        if (pid != _noKillPid &&
            pid != getpid())
            *count += 1;
    }
    return 0;
}

// Data used by find_handler().
struct FindProcessesContext {
    int pids[MAX_PROCESSES]; // PIDs of Sighthound Video processes.
    int count;               // Number of SV processes found so far.
};

// Process enumeration handler to find Sighthound processes.
int find_handler(void* ctx, int uid, int pid, int ppid, char* comm)
{
    struct FindProcessesContext* fpctx = ctx;

    if (is_sv_process(comm)) {
        _logf_i("found process (uid=%d,pid=%d,ppid=%d,comm=%s)",
                uid, pid, ppid, comm);
        if (fpctx->count < MAX_PROCESSES)
            fpctx->pids[fpctx->count++] = pid;
        else
            return -2;  // too many processes!?
    }
    return 0;
}

// Integer comparator, to be used with qsort().
int cmp_int(const void* i1, const void* i2)
{
    return *(int*)i1 - *(int*)i2;
}

/**
 * Kill all Sighthound Video processes. Identification is done by name. Parent
 * process will never be killed either.
 *
 * @param  noKillPid  PID of process not to kill.
 * @return            Number of SV processs which got a SIGTERM from us.
 */
int kill_old_processes(int noKillPid)
{
    int err, i, killed, result, ownPid = getpid(), parentPid = getppid();
    struct FindProcessesContext fpctx;

    memset(&fpctx, 0, sizeof(fpctx));
    err = enum_processes(find_handler, &fpctx);
    if (err)
        _logf_e("process enumeration failed (%d)", err);

    qsort(fpctx.pids, fpctx.count, sizeof(int), cmp_int);

    killed = 0;
    result = fpctx.count;
    for (i = 0; i < fpctx.count; i++) {
        int pid = fpctx.pids[i];
        if (ownPid == pid || parentPid == pid || _noKillPid == pid ||
            noKillPid == pid) {
            result--;
            continue;
        }
        if (kill(pid, SIGKILL)) {
            _logf_e("cannot kill process %d (%d)", pid, errno);
        }
        else {
            killed++;
        }
    }

    _logf_i("sent SIGKILL to %d processes", killed);
    return result;
}

/**
 * Does a multiple-round attempt to get rid of old Sighthound Video processes.
 * Identified processes get a SIGTERM, the enumeration then gets repeated until
 * no more processes are found, or we do time out.
 *
 * @param  noKillPid  PID of process not to kill.
 * @return            Zero on success, error code otherwise.
 */
int kill_old_processes_and_wait(int noKillPid)
{
    int retries = KILL_WAIT_RETRIES;
    while (kill_old_processes(noKillPid)) {
        int ignored;
        waitpid((pid_t)-1, &ignored, WNOHANG);
        _logf_i("waiting for processes to end (%d retries left) ...", retries);
        msleep(KILL_WAIT_MILLIS);
        if (--retries <= 0) {
            return RET_ERROR;
        }
    }
    return RET_SUCCESS;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Activates the service, meaning creating the plist declaring the service in
 * the system and terminating all other former processes. This requires admin
 * privileges.
 *
 * @param servicePath   Full path to this executable.
 * @param localDataDir  Potential local data directory, for which a symlink might
 *                      need to be created.
 * @param uid           The user ID to run the service under.
 * @param userName      Matching name for the user ID.
 * @return              Zero on success, error code otherwise.
 */
int activate(char* servicePath, char* localDataDir, int uid, char* userName)
{
    int err;

    err = create_daemon_plist(servicePath, SHLAUNCH_BUILD, userName);
    if (err) {
        _logf_e("error creating plist (%d)", err);
        return RET_ACTIVATE_ERROR;
    }
    err = kill_old_processes_and_wait(0);
    if (err) {
        _logf_e("error killing old processes on activation (%d)", err);
        return RET_ACTIVATE_ERROR;
    }
    err = exchange_reset();
    if (err) {
        _logf_e("cannot reset old exchange (%d)", err);
        return RET_ACTIVATE_ERROR;
    }
    if (access(localDataDir, R_OK)) {
        _logf_i("local data (%s) directory not found (%d), preparing global...",
                localDataDir, errno);
        return prepare_data_dir();
    }
    if (0 == access(APP_DATA_DIR, R_OK)) {
        _logf_i("global data directory spot present, not linking local one");
        return 0;
    }
    if (0 == symlink(localDataDir, APP_DATA_DIR)) {
        int chmodResult = chmod(localDataDir, 0777);
        _logf_i("link to local data directory (%s) created (%d)",
                localDataDir, chmodResult);
    }
    else
        _logf_e("creating link to local data directory (%s) failed (%d)",
                localDataDir, errno);
    // we give up on the local data directory, since it won't be lost we might
    // give the user some advice to move it to the right spot manually
    // TODO: properly surface this issue to the UI?
    return 0;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Launch the backend.
 *
 * @param shl  The service context. Gets the PID of the new process.
 * @return     Zero on success, error otherwise.
 */
int launch_backend(struct SHLaunch* shl)
{
    pid_t child;
    int result = RET_ERROR;
    char exe[PATH_MAX];
    char* args[] = { exe, ARG_BACKEND, shl->dataDir,
                     ARG_MARKER1, ARG_MARKER2, NULL };
    char homeDir[PATH_MAX];
    char **env2 = NULL;
    char **env = environ;
    int envLen = 0;

    // TODO: we might not need the HOME environment variable to be set anymore
    while (*env++)
        envLen++;
    env2 = malloc(sizeof(*env) * (envLen + 2));
    if (!env2)
        goto cleanup;
    memcpy(env2, environ, sizeof(*env) * envLen);
    snprintf(homeDir, PATH_MAX, "HOME=%s", home_dir());
    env2[envLen + 0] = homeDir;
    env2[envLen + 1] = NULL;

    strcpy(exe, shl->exeDir);
    strcat(exe, SV_EXE);
    _logf_i("\"%s\" %s \"%s\" %s %s",
            args[0], args[1], args[2], args[3], args[4]);
    child = fork();
    if (0 < child) {
        _logf_i("backend process started (PID=%d)", child);
        result = RET_SUCCESS;
    }
    else if (0 == child) {
        int ret = execve(exe, args, env2);
        _logf_e("execve() returned %d (error %d)", ret, errno);
        exit(0);
    }
    else {
        _logf_e("fork returned %d (error %d)", child, errno);
    }

cleanup:
    free(env2);
    return RET_SUCCESS;
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Waits for all backend processes to exit.
 *
 * @param shl       The service context. Gets the PID of the new process.
 * @param waitSecs  Number of seconds to roughly wait for.
 */
void wait_for_backend_exit(struct SHLaunch* shl, int waitSecs)
{
    int processesLeft;
    time_t tmout = time(NULL) + waitSecs;
    for (;;) {
        int eres, ignored;
        processesLeft = 0;
        eres = enum_processes(count_handler, &processesLeft);
        if (eres) {
            _logf_e("process count enumeration failed!? (%d)", eres);
            return;
        }
        if (0 >= processesLeft)
            break;
        if (time(NULL) >= tmout)
            break;
        _logf_i("%d backend processes left, waiting...", processesLeft);
        waitpid((pid_t)-1, &ignored, WNOHANG);
        msleep(2000);
    }
    if (processesLeft)
        _logf_e("%d backend processes still running", processesLeft);
}

///////////////////////////////////////////////////////////////////////////////

/**
 * Signal handler, to be invoked on SIGTERM (and SIGINT).
 *
 * @param signal  The signal (SIGTERM, SIGINT).
 */
void on_terminate(int signal)
{
    if (_shl) {
        _logf_i("received termination signal %d", signal);
        _shl->terminate = 1;
    }
}

///////////////////////////////////////////////////////////////////////////////

int main(int argc, char** argv)
{
    char* p;
    int ret, uid = -1;
    int launch, kill, ignored, shutdown;
    int32_t exchgLaunch, status, srcPid;
    struct SHLaunch* shl = NULL;
    struct Exchange exchgLast;
    struct SHLaunchConfig cfg;

    memset(&exchgLast, 0, sizeof(exchgLast));

    if (argc < 2) {
#ifdef RUN_IN_TERMINAL
        fputs("RUN_IN_TERMINAL ENABLED", stderr);
#endif
        fputs("usage: shlaunch " SHLAUNCH_BUILD \
              " {--activate nokillpid localdatadir uid username}\n", stderr);
        return RET_ARGS_ERROR;
    }

    if (strcmp(argv[1], SHLAUNCH_BUILD))
        return RET_BUILD_MISMATCH;

    signal(SIGTERM, on_terminate);
#ifdef RUN_IN_TERMINAL
    signal(SIGINT, on_terminate);
#endif

    if (argc >= 6 && 0 == strcmp("--activate", argv[2])) {
        _noKillPid = atoi(argv[3]);
        uid = atoi(argv[5]);
        _logf_i("activating...");
        ret = activate(argv[0], argv[4], uid, argv[6]);
        goto cleanup;
    }
    ret = RET_ERROR;

    kill_old_processes_and_wait(_noKillPid);

    shl = calloc(sizeof(*shl), 1);
    if (!shl) {
        goto cleanup;
    }
    strcpy(shl->exeDir, argv[0]);
    p = strrchr(shl->exeDir, '/');
    if (p)
        *(p + 1) = 0;

    if (-1 != uid) {
        if (setuid(uid)) {
            _logf_e("setuid failed (%d)", errno);
            return RET_SETUID_ERROR;
        }
        _logf_i("setuid(%d) successful", uid);
    }

    ret = exchange_open(shl);
    if (ret)
        goto cleanup;

    strcpy(shl->dataDir, APP_DATA_DIR "/");
    if (!utf8_to_unicode(shl->dataDir, shl->exchange->dataDir)) {
        _logf_e("data directory string conversion failed!?");
        goto cleanup;
    }
    strncpy(shl->exchange->build, SHLAUNCH_BUILD, sizeof(shl->exchange->build));
    shl->exchange->build[sizeof(shl->exchange->build) - 1] = '\0';
    shl->exchange->processId = getpid();
    shl->exchange->size = sizeof(struct Exchange); // = "initialization done"
    _shl = shl;

    srcPid = 0;
    kill = LAUNCH_FLAG_KILL_FIRST;

    // If we got launched by the UI or the configuration tells us so we have to
    // launch the backend right away.
    cfg_load(shl, &cfg);
    launch = (-1 != _noKillPid) || (cfg.autoStart && cfg.backend);
    _logf_i("starting (%d)...", launch);

    while (!shl->terminate) {

        struct Exchange exchgSnapshot;

        shl->exchange->cycles++;

        exchgSnapshot = *shl->exchange;
        exchgLast.cycles = exchgSnapshot.cycles;
        if (memcmp(&exchgLast, &exchgSnapshot, sizeof(exchgSnapshot))) {
            exchgLast = exchgSnapshot;
            _log_exchange(&exchgSnapshot);
        }

        if (access(argv[0], F_OK)) {
            _logf_e("EXECUTABLE GONE: %s", argv[0]);
            unlink(PLIST_PATH);
            break;
        }

        if (kill) {
            _logf_i("killing old processes (src-pid=%d) ...", srcPid);
            kill_old_processes_and_wait(srcPid);
            __sync_fetch_and_and(&shl->exchange->launch,
                                 ~LAUNCH_FLAG_KILL_FIRST);
        }

        if (launch) {
            cfg_load(shl, &cfg);
            if (cfg.backend) {
                _logf_i("launching (x%x)...", launch);
                status = launch_backend(shl);
                __sync_swap(&shl->exchange->status, status ? 0 : 1);
            }
            else
                _logf_e("launch signal (x%x) blocked by configuration", launch);
            __sync_fetch_and_and(&shl->exchange->launch, ~LAUNCH_MASK);
        }

        msleep(IDLE_MILLIS);
        waitpid((pid_t)-1, &ignored, WNOHANG);

        srcPid      = shl->exchange->launchProcessId;
        exchgLaunch = shl->exchange->launch;
        launch = exchgLaunch & LAUNCH_MASK;
        kill   = exchgLaunch & LAUNCH_FLAG_KILL_FIRST;
    }

    shutdown = __sync_swap(&shl->exchange->shutdown, 1);
    _logf_i("service going down (%d), back-end signaled (%d)",
            shl->terminate, shutdown);

    wait_for_backend_exit(shl, SHUTDOWN_WAIT_SECS);

    ret = RET_SUCCESS;

cleanup:
    if (shl) {
        exchange_close(shl);
        _shl = NULL;
        free(shl);
    }
    return ret;
}
