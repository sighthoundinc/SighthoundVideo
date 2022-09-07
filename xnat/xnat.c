/*
#*****************************************************************************
#
# xnat.c
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

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#ifdef _WIN32
#include <malloc.h>
#else
#include <errno.h>
#include <stdarg.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#define _strdup strdup
#endif

#include <miniupnpc/miniupnpc.h>
#include <miniupnpc/upnpcommands.h>
#include <miniupnpc/upnperrors.h>

#include <natpmp.h>

//////////////////////////////////////////////////////////////////////////////

#define EXIT_SUCCESS        0
#define EXIT_INVALIDARG     1
#define EXIT_OUTOFMEMORY    2
#define EXIT_ERROR          3

// NATPMP response sometimes fail because we encounter invalid payloads coming
// in from unrelated devices, so there needs to be some tolerance and retrying
#define NATPMP_RETRIES   5

// Number of retries for UPnP operations.
#define UPNP_RETRIES   2

// how long ports should be kept open n the router if that value wasn't passed
// in by the caller; one cannot use the value infinite unfortunately ...
#define TTL_DEFAULT 7200

// the protocol scheme codes
enum PROTOCOL {
    P_MIN         = 0,
    P_UPNP        = 0,
    P_NATPMP      = 1,
    P_UPNP_NATPMP = 2,
    P_NATPMP_UPNP = 3,
    P_MAX         = 3
};

#define ACTION_OPEN   "open"
#define ACTION_CLOSE  "close"
#define ACTION_STATUS "status"

// all the keys used to pass in and to be returned, see xnat.py for details
#define KEY_PROTOCOL    "protocol"
#define KEY_TRANSPORT   "transport"
#define KEY_ACTION      "action"
#define KEY_TIMEOUT     "timeout"
#define KEY_ERROR       "error"
#define KEY_RESULT      "result"
#define KEY_LOG         "logs"
#define KEY_REMOTEIP    "remoteIP"
#define KEY_REMOTEPORT  "remotePort"
#define KEY_LOCALPORT   "localPort"
#define KEY_TTL         "ttl"

// we do usually just deal with TCP ports (HTTP, HTTPS)
#define VALUE_TCP   "TCP"

//////////////////////////////////////////////////////////////////////////////

// the global exit code holder, changed by the error code handlers
int _exitcode = EXIT_SUCCESS;

// the parameters read from the command line get stored here
int           _ttl        = -1;
int           _timeout    = 5000;
int           _localPort  = -1;
int           _remotePort = -1;
enum PROTOCOL _protocol   = P_UPNP_NATPMP;
char*         _localIP    = NULL;
char*         _action     = NULL;
char*         _transport  = VALUE_TCP;

//////////////////////////////////////////////////////////////////////////////

// if the output does not go to stdout we put it into a file
char* _outputFile = NULL;
FILE* _outf = NULL;

// open the output (file), this is where the response context gets written out,
// so the caller can then get a dictionary with all of the details of what was
// happening and potentially the news abou the opened port ...
void output_open() {
	if (_outputFile) {
		_outf = fopen(_outputFile, "w");
		if (!_outf) {
			_outf = stderr;
		}
	}
	else {
		_outf = stdout;
	}
	fprintf(_outf, "{");
}
void output_close() {
	fprintf(_outf, "}\n");
	if (stdout != _outf &&
		stderr != _outf) {
		fclose(_outf);
	}
}

// the log functions write to the output file, but the data itself is just part
// of the dictionary and can be retrieved by the caller as one piece of text ...

void log_open () { fprintf(_outf, "'" KEY_LOG "':r\"\"\""); }
void log_close() { fprintf(_outf, "\"\"\","); }

void log_fmt_(char* fmt, va_list args)
{
    time_t tm = time(NULL);
    char* ctm = ctime(&tm);
    ctm[strlen(ctm) - 1] = '\0';
    fprintf(_outf, "%s - ", ctm);
    vfprintf(_outf, fmt, args);
    fputs("\n", _outf);
}

void log_fmt(char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    log_fmt_(fmt, args);
    va_end(args);
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Called to register an error.
 * @param code The error code, which might also become the actual exit code.
 * @param final Set to 1 if the passed in code is the exit code, this gets the
 * actual result be emitted to the output file - no more logging shall be made
 * then after the call.
 * @param fmt The printf-style format string, followed by additional parameters.
 * @return The reflected (exit) code.
 */
int on_error(int code, int final, char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    if (final) {
        log_close();
        fprintf(_outf, "'" KEY_RESULT "':%d,'" KEY_ERROR "':\"\"\"", code);
        vfprintf(_outf, fmt, args);
        fprintf(_outf, "\"\"\"");
        _exitcode = code;
    }
    else {
        log_fmt_(fmt, args);
    }
    va_end(args);
    return code;
}

/**
 * Called to store the result of a successful port opening. After this call no
 * more log output must be made.
 * @param remoteIP The remote IP received from the IGD.
 * @param remotePort The remote port received from the IGD.
 * @param localsPort The associated local port.
 * @param ttl The TTL value negotiated (in seconds).
 * @param protocol The protocol used on the opened port.
 * @return Always EXIT_SUCCESS (0).
 */
int on_success(char* remoteIP, int remotePort, int localPort, int ttl, int protocol)
{
    log_close();
    fprintf(_outf,
    	   "'" KEY_RESULT     "':%d,"
    	   "'" KEY_REMOTEIP   "':'%s',"
           "'" KEY_REMOTEPORT "':%d,"
           "'" KEY_LOCALPORT  "':%d,"
           "'" KEY_PROTOCOL   "':%d,"
           "'" KEY_TTL        "':%d",
           EXIT_SUCCESS, remoteIP, remotePort, localPort, protocol, ttl);
    return (_exitcode = EXIT_SUCCESS);
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Attempts to open or close the port via NATPMP.
 * @param final Set to 1 to write out the error result.
 * @param ttl The TTL (in seconds). Zero means to close the port.
 * @return Success or error (exit) code.
 */
int natpmp(int final, int ttl)
{
    char*          remoteIP = NULL;
    int            res, ret, err, retry, tp;
    natpmp_t       natpmp;
    fd_set         fds;
    natpmpresp_t   rsp;
    struct timeval timeout;

    log_fmt("initializing NAT-PMP...");
    if (0 != (res = initnatpmp(&natpmp, 0, 0))) {
        return on_error(EXIT_ERROR, final, "initializing NAT/PMP failed (%d)", res);
    }
    log_fmt("sending NAT-PMP address request...");
    if (2 != (res = sendpublicaddressrequest(&natpmp))) {
        closenatpmp(&natpmp);
        return on_error(EXIT_ERROR, final, "NAT/PMP address request error (%d)", res);
    }
    retry = NATPMP_RETRIES;
    do {
        FD_ZERO(&fds);
        FD_SET(natpmp.s, &fds);
        getnatpmprequesttimeout(&natpmp, &timeout);
        res = select(FD_SETSIZE, &fds, NULL, NULL, &timeout);
        if (-1 == res) {
            closenatpmp(&natpmp);
            return on_error(EXIT_ERROR, final, "select error!?");
        }
        res = readnatpmpresponseorretry(&natpmp, &rsp);
        err = errno;
        if (0 > res && res != NATPMP_TRYAGAIN) {
            closenatpmp(&natpmp);
            return on_error(EXIT_ERROR, final,
            	"read NAT response failed, error %d (%s)", err, strerror(err));
        }
    }
    while (NATPMP_TRYAGAIN == res && 0 < --retry);
    if (0 == retry) {
        closenatpmp(&natpmp);
        return on_error(EXIT_ERROR, final, "maximum number of read NAT request retries reached");
    }
    remoteIP = inet_ntoa(rsp.pnu.publicaddress.addr);
    remoteIP = _strdup(remoteIP);
    log_fmt("determined external IP (%s), epoch is %u", remoteIP, rsp.epoch);
    tp = strcmp(_transport, "tcp") ? NATPMP_PROTOCOL_UDP :
                                     NATPMP_PROTOCOL_TCP;
    log_fmt("sending NAT-PMP request for '%s' %d->%d (ttl=%d)", _transport, _remotePort, _localPort, ttl);
    if (0 > (res = sendnewportmappingrequest(&natpmp, tp, _localPort, _remotePort, ttl))) {
        closenatpmp(&natpmp);
        return on_error(EXIT_ERROR, final, "new port mapping request failed (%d)", res);
    }
    retry = NATPMP_RETRIES;
    do {
        FD_ZERO(&fds);
        FD_SET(natpmp.s, &fds);
        getnatpmprequesttimeout(&natpmp, &timeout);
        select(FD_SETSIZE, &fds, NULL, NULL, &timeout);
        res = readnatpmpresponseorretry(&natpmp, &rsp);
        log_fmt("read NAT response is %d", res);
    }
    while (NATPMP_TRYAGAIN == res && 0 < --retry);
    if (0 == retry) {
        ret = on_error(EXIT_ERROR, final,
        		"maximum number of read NAT response retries reached");
    }
    else if (0 > res) {
        ret = on_error(EXIT_ERROR, final, "read NAT response failed");
    }
    else if (ttl) {
        ret = on_success(remoteIP,
				rsp.pnu.newportmapping.mappedpublicport,
				rsp.pnu.newportmapping.privateport,
				rsp.pnu.newportmapping.lifetime,
				P_NATPMP);
    }
    else {
        ret = on_success(remoteIP, _remotePort, -1, -1, P_NATPMP);
    }
    closenatpmp(&natpmp);
    free(remoteIP);
    return ret;
}

/**
 * Tries to open the port via NATPMP.
 * @param final Set to 1 to write out the error result.
 * @return Success or error (exit) code.
 */
int open_natpmp(int final)
{
    return natpmp(final, -1 == _ttl ? TTL_DEFAULT : _ttl);
}

/**
 * Close a port formerly opened (or just assumed to be open) via NATPMP.
 * @param final Set to 1 to write out the error result.
 * @return Success or error (exit) code.
 */
int close_natpmp(int final)
{
    return natpmp(final, 0);
}

//////////////////////////////////////////////////////////////////////////////

/**
 * Tries to open the port via UPnP.
 * @param final Set to 1 to write out the error result.
 * @return Success or error (exit) code.
 */
int open_upnp(int final)
{
    struct UPNPDev  *devlst = NULL, *dl;
    struct UPNPUrls urls;
    struct IGDdatas datas;
    int             retry, res;
    char            rmtAddr[64] = { 0 };
    char            lclAddr[64] = { 0 };
    char            rmtPort[32], lclPort[32], ttl[32];
    char            desc[128];

    for (retry = 0; retry < UPNP_RETRIES; retry++) {
		if (NULL == (devlst = upnpDiscover(_timeout, NULL, NULL, 0, 0, 2, &res))) {
			return on_error(EXIT_ERROR, final, "UPnP discovery failed (%d)", res);
		}
		dl = devlst;
		while (dl) {
			log_fmt("found device at %s", dl->descURL);
			dl = dl->pNext;
		}
		res = UPNP_GetValidIGD(devlst, &urls, &datas, lclAddr, sizeof(lclAddr));
		if (!res) {
			return on_error(EXIT_ERROR, final, "cannot get valid IGD (%d)", errno);
		}
		freeUPNPDevlist(devlst);
		log_fmt("UPnP device type %d at %s (local address: %s)", res, urls.controlURL, lclAddr);
		res = UPNP_GetExternalIPAddress(urls.controlURL, datas.first.servicetype, rmtAddr);
		if (res) {
			if (!retry && res == 401) {
				// we've seen this problem in the wild and should not ignore it:
				// sometimes the discovered devices or their URLs respectively
				// are not complete (packet duplication?) and the actual IGD one
				// is not showing up - hence it makes sense to retry this one
				// more time - the particular device at the time was a
				// TL-WR1043N router for which like every 50th attempt failed
				log_fmt("external IP address fetch failed with error 401, retrying...");
				continue;
			}
			return on_error(EXIT_ERROR, final, "cannot get external IP address (%d)", res);
		}
		else {
			break;
		}
    }
    sprintf(rmtPort, "%d", _remotePort);
    sprintf(lclPort, "%d", _localPort);
    sprintf(ttl    , "%d", _ttl);
    sprintf(desc, "SighthoundXNAT %s (%d,%d)", _transport, _remotePort, _localPort);
    log_fmt("adding port mapping %s->%s:%s for '%s'", rmtPort, lclAddr, lclPort, _transport);
    for (retry = 0; retry < UPNP_RETRIES; retry++) {
		res = UPNP_AddPortMapping(
			urls.controlURL,
			datas.first.servicetype,
			rmtPort,
			lclPort,
			lclAddr,
			desc,
			_transport,
			NULL,
			(-1 == _ttl || retry) ? NULL : ttl);
    	if (725 == res && !retry) {
    	    log_fmt("retrying with permanent lease...");
    	    continue;
    	}
    	break;
    }
    if (res) {
        return on_error(EXIT_ERROR, final,
            "port mapping addition failed, error %d (%s)",
            res, strupnperror(res));
    }
    return on_success(rmtAddr, _remotePort, _localPort, _ttl, P_UPNP);
}

/**
 * Close a port formerly opened (or just assumed to be open) via UPnP.
 * @param final Set to 1 to write out the error result.
 * @return Success or error (exit) code.
 */
int close_upnp(int final)
{
    struct UPNPDev* devlst = NULL;
    struct UPNPUrls urls;
    struct IGDdatas datas;
    int             res;
    char            lclAddr[64] = { 0 };
    char            rmtPort[32];

    if (NULL == (devlst = upnpDiscover(_timeout, NULL, NULL, 0, 0, 2, &res))) {
        return on_error(EXIT_ERROR, final, "UPnP discovery failed (%d)", res);
    }
    res = UPNP_GetValidIGD(devlst, &urls, &datas, lclAddr, sizeof(lclAddr));
    if (!res) {
        return on_error(EXIT_ERROR, final, "cannot get valid IGD (%d)", errno);
    }
    log_fmt("UPnP device type %d at %s (local address: %s)", res, urls.controlURL, lclAddr);
    freeUPNPDevlist(devlst);
    sprintf(rmtPort, "%d", _remotePort);
    log_fmt("deleting port mapping %s for '%s'", rmtPort, _transport);
    res = UPNP_DeletePortMapping(
        urls.controlURL,
        datas.first.servicetype,
        rmtPort,
        _transport,
        0);
    if (res) {
        return on_error(EXIT_ERROR, final,
            "port mapping deletion failed, error %d (%s)", res, strupnperror(res));
    }
    return on_success("", _remotePort, -1, -1, P_UPNP);
}

//////////////////////////////////////////////////////////////////////////////

// action handlers ...

void action_open()
{
    if (-1 == _localPort ) {
    	on_error(EXIT_INVALIDARG, 1, "missing local port");
    	return;
    }
    if (-1 == _remotePort) {
    	on_error(EXIT_INVALIDARG, 1, "missing remote port");
    	return;
    }
    switch(_protocol) {
        case P_NATPMP     :      open_natpmp(1); break;
        case P_NATPMP_UPNP: if (!open_natpmp(0)) return;
                                 open_upnp  (1); break;
        case P_UPNP       :      open_upnp  (1); break;
        case P_UPNP_NATPMP: if (!open_upnp  (0)) return;
                                 open_natpmp(1); break;
    }
}

void action_close()
{
    switch(_protocol) {
        case P_NATPMP     :      close_natpmp(1); break;
        case P_NATPMP_UPNP: if (!close_natpmp(0)) return;
                                 close_upnp  (1); break;
        case P_UPNP       :      close_upnp  (1); break;
        case P_UPNP_NATPMP: if (!close_upnp  (0)) return;
                                 close_natpmp(1); break;
    }
}

//////////////////////////////////////////////////////////////////////////////

// argument parsers ...

char* arg_value(char* argv)
{
    char* equ = strchr(argv, '=');
    if (!equ) {
        on_error(EXIT_INVALIDARG, 1, "invalid argument '%s'", argv);
    }
    *equ = '\0';
    return 1 + equ;
}

int parse_int(char* expr)
{
    int result = -1;
    if (1 != sscanf(expr, "%d", &result) ? 1 : 0) {
        on_error(EXIT_INVALIDARG, 1, "invalid number '%s'", expr);
    }
    return result;
}

enum PROTOCOL parse_protocol(char* expr)
{
    int p = parse_int(expr);
    if (p < P_MIN || p > P_MAX) {
        on_error(EXIT_INVALIDARG, 1, "invalid protocol '%s'", expr);
    }
    return (enum PROTOCOL)p;
}

//////////////////////////////////////////////////////////////////////////////

#if defined(WIN32) && !defined(_DEBUG)
extern void minidump_init(TCHAR*, UINT, UINT);
#endif

#ifdef __XNAT_DYLIB
extern char ***_NSGetArgv(void);
extern int *_NSGetArgc(void);
#endif

int main(int argc, char** argv)
{
#if defined(WIN32) && !defined(_DEBUG)
    minidump_init(TEXT("sv_xnat"), 0xbaadc0de, 3);
#endif

#ifdef __XNAT_DYLIB
    {
		int i, c = *_NSGetArgc();
		char** nsargs = *_NSGetArgv();
		for (i = 0; i < c; i++) {
			char* nsarg = nsargs[i];
			if (nsarg && !strcmp(nsarg, "--sh-2e4fce7e")) {
				strcpy(nsarg, "--sh-1194711f");
				break;
			}
		}
    }
#endif
    output_open();
    log_open();
#ifdef WIN32
    {
        WSADATA wsaData;
        int result = WSAStartup(MAKEWORD(2,2), &wsaData);
        if (NO_ERROR != result)
            on_error(EXIT_INVALIDARG, 1, "socket library initialization failed (%d)", result);
    }
#endif
    while (*++argv && !_exitcode) {
        char* name = *argv;
        char* value = arg_value(name);
             if (!strcmp(name, KEY_TTL       )) { _ttl        = parse_int     (value); }
        else if (!strcmp(name, KEY_LOCALPORT )) { _localPort  = parse_int     (value); }
        else if (!strcmp(name, KEY_REMOTEPORT)) { _remotePort = parse_int     (value); }
        else if (!strcmp(name, KEY_TIMEOUT   )) { _timeout    = parse_int     (value); }
        else if (!strcmp(name, KEY_PROTOCOL  )) { _protocol   = parse_protocol(value); }
        else if (!strcmp(name, KEY_TRANSPORT )) { _transport  = value; }
        else if (!strcmp(name, KEY_ACTION    )) { _action     = value; }
        else {
            on_error(EXIT_INVALIDARG, 1, "unknown argument '%s'", name);
        }
    }
    if (!_exitcode) {
		if (!_action) {
			on_error(EXIT_INVALIDARG, 1, "missing action");
		}
		else {
				 if (!strcmp(_action, ACTION_OPEN )) action_open();
			else if (!strcmp(_action, ACTION_CLOSE)) action_close();
			else on_error(EXIT_INVALIDARG, 1, "unknown action '%s'", _action);
		}
    }
    output_close();
#ifdef WIN32
    WSACleanup();
#endif
    return _exitcode;
}

//////////////////////////////////////////////////////////////////////////////

#ifdef __XNAT_DYLIB
int dylibMain(char* outputFile, int argc, char** argv) {
	_outputFile = outputFile;
	return main(argc, argv);
}
#endif
