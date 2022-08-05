#*****************************************************************************
#
# xnat.py
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

import os, sys, subprocess, time, ctypes, uuid, signal, traceback

from subprocess import Popen, PIPE

from appCommon.CommonStrings import kXNATMarkerArg

from vitaToolbox.ctypesUtils.LoadLibrary import LoadLibrary

###############################################################################



# name of the shared library (OSX only right now)
_kSharedLib   = "xnat.dylib"
# whether we're running under Windows or not
_kIsWin = "win32" == sys.platform

###############################################################################
def sharedLibrary():
    """ Returns the name of the shared library to run XNAT from.
    @return The XNAT shared library or None for a separate executable.
    """
    if _kIsWin:
        return None
    if hasattr(sys, "frozen"):
        return os.path.join(os.path.dirname(sys.executable), _kSharedLib)
    else:
        return os.path.join(os.getenv("SV_DEVEL_LIB_FOLDER_LOCAL"), _kSharedLib)


###############################################################################
def runXNAT(outp, *args):
    """ To run XNAT via a shared library. This is called by a forked process
    (usually the webserver) and will effectively become an XNAT instance.

    @param outp  The output file's path.
    @param args  The arguments passed to xnat's main(), which will then be made
                 available to it via the common argc,argv parameters.
    """
    exitcode = -1
    try:
        cdll = ctypes.CDLL(sharedLibrary())
        argv = (ctypes.c_char_p * (len(args) + 1))()
        argv[:-1] = args
        argv[-1] = None
        exitcode = cdll.dylibMain(ctypes.c_char_p(outp), len(args), argv)
    except:
        f = None
        try:
            f = open("/tmp/sighthound_xnat_status", "w")
            f.write("exception: " + traceback.format_exc())
        except:
            pass
        finally:
            if f is not None:
                f.close()
    sys.exit(exitcode)


###############################################################################
class XNAT:

    RSP_REMOTEIP   = "remoteIP"   # remote/external/public IP, told by the IGD
    RSP_REMOTEPORT = "remotePort" # remote port opened
    RSP_LOCALPORT  = "localPort"  # local port mapped to
    RSP_TTL        = "ttl"        # accepted TTL, in seconds
    RSP_RESULT     = "result"     # result code, 0 for success
    RSP_ERROR      = "error"      # error text, set if result is not zero
    RSP_LOGS       = "logs"       # log output, text with line breaks
    RSP_PROTOCOL   = "protocol"   # the protocol for which an action succeed

    RES_NOEXEC     = -100
    RES_SUCCESS     = 0
    RES_INVALIDARG  = 1
    RES_OUTOFMEMORY = 2
    RES_ERROR       = 3

    PROTOCOL_UPNP        = 0
    PROTOCOL_NATPMP      = 1
    PROTOCOL_UPNP_NATPMP = 2
    PROTOCOL_NATPMP_UPNP = 3

    TRANSPORT_TCP = "TCP"
    TRANSPORT_UDP = "UDP"

    ###########################################################################
    def __init__(self, timeout, logger, workdir):
        """ Creates a new instance which can perform NAT actions repeatedly.
        @param timeout Timeout base for a single action, in seconds.
        @param logger The common logger to use.
        @param workdir Path to a directory where transient things are written.
        """
        self._timeout = timeout;
        self._logger = logger
        self._workdir = workdir
        exe = "SighthoundXNAT" + (".exe" if _kIsWin else "")
        if hasattr(sys, "frozen"):
            self._exe = os.path.join(os.path.dirname(sys.executable), exe)
        else:
            self._exe = os.path.join(os.getenv("SV_DEVEL_LIB_FOLDER_LOCAL"), "..", "bin", exe)


    ###########################################################################
    def open(self, localPort, remotePort, ttl = None,
             protocol = PROTOCOL_UPNP_NATPMP, transport = TRANSPORT_TCP):
        """ Tries to open a port or add a NAT port mapping respectively.
        @param localPort: The local port to map to.
        @param remotePort: The remote/external/public port.
        @param ttl: The lease time in seconds, or None for default.
        @param protocol: The protocol(s) to use (in sequence).
        @param transport: The IP transport, either "UDP" or "TCP".
        @return: Response dictionary.
        """
        cmd = [self._exe,
               "action=open",
               "localPort="  + str(localPort),
               "remotePort=" + str(remotePort),
               "protocol="   + str(protocol),
               "transport="  + transport]
        if ttl is not None:
            cmd.append("ttl=" + str(ttl))
        return self._execute(cmd)


    ###########################################################################
    def close(self, remotePort,
              protocol = PROTOCOL_UPNP_NATPMP, transport = TRANSPORT_TCP):
        """ Tries to open a port or add a NAT port mapping respectively.
        @param remotePort: The remote/external/public port.
        @param protocol: The protocol(s) to use (in sequence).
        @param transport: The IP transport, either "UDP" or "TCP".
        @return: Response dictionary.
        """
        return self._execute([self._exe,
               "action=close",
               "remotePort=" + str(remotePort),
               "protocol="   + str(protocol),
               "transport="  + transport])


    ###########################################################################
    def _execute(self, cmd):
        """ Executes an instance of XNAT and collects its results.

        @param cmd  The command line.
        @return     Result dictionary, ready to be passed up.
        """
        # the total timeout computes as the base timeout 2x for UPnP (because
        # of potential discovery retry_ and 1x for NAT-PMP), plus another unit
        # for safety, covering the actual talking to the devices ...
        timeout = self._timeout * 4
        outp = ""
        libName = sharedLibrary()
        if libName is not None:
            self._logger.info("launching XNAT via %s ..." % libName)
            if (hasattr(sys, "frozen")):
                args = [sys.executable]
            else:
                args = [sys.executable, "FrontEndLaunchpad.py"]
            outpFile = os.path.join(self._workdir, "xnat.%s" % uuid.uuid4())
            args += ["--xnat", outpFile] + cmd + [kXNATMarkerArg]
            self._logger.info(str(args))
            p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                      close_fds=(sys.platform=='darwin'))
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()
            self._logger.info("waiting for process %d to exit..." % p.pid)
            end = time.time() + timeout
            while p.poll() == None and end > time.time():
                time.sleep(.05)
            exitcode = p.returncode
            if exitcode is None:
                self._logger.error("timeout, killing PID %d..." % p.pid)
                try:
                    os.kill(p.pid, signal.SIGKILL)
                    p.join(1)
                    if p.is_alive():
                        self._logger.error("process is still alive")
                except:
                    self._logger.error("kill failed (%s)" % sys.exc_info()[1])
            try:
                of = open(outpFile, "r")
                outp = of.read(0x10000)
            except:
                self._logger.error("cannot read %s (%s)" %
                                   (outpFile, sys.exc_info()[1]))
            finally:
                try: of.close()
                except: pass
            try:
                if os.path.exists(outpFile):
                    os.remove(outpFile)
            except:
                self._logger.error("cannot remove %s (%s)" %
                                   (outpFile, sys.exc_info()[1]))
        else:
            self._logger.info(str(cmd))
            if _kIsWin:
                sinf = subprocess.STARTUPINFO()
                sinf.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                proc = subprocess.Popen(cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    startupinfo=sinf)
            else:
                proc = subprocess.Popen(cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            end = time.time() + timeout
            while True:
                if end < time.time():
                    self._logger.error("timeout, killing PID %d..." % proc.pid)
                    try:
                        os.kill(proc.pid, signal.SIGKILL)
                        proc.join(1)
                        end = time.time() + 5
                        while proc.poll() is None:
                            if time.time() > end:
                                self._logger.warn("process is still active")
                                break
                            time.sleep(.1)
                        if proc.is_alive():
                            self._logger.error("process is still alive")
                    except:
                        self._logger.error("failed: %s" % sys.exc_info()[1])
                        break
                exitcode = proc.poll()
                if exitcode is not None:
                    break
                time.sleep(.1)
            for ln in proc.stdout:
                self._logger.debug(">>> " + ln.rstrip())
                outp += ln
        if exitcode is None:
            return { XNAT.RSP_RESULT: XNAT.RES_ERROR,
                     XNAT.RSP_ERROR: "execution timeout" }
        self._logger.info("exit code is %d" % exitcode)
        try:
            # Windows line breaks mess up eval(uation) apparently
            outp = outp.replace('\r', '')
            return eval(outp)
        except:
            self._logger.error("result eval failed (%s)" % sys.exc_info()[1])
            return { XNAT.RSP_RESULT: XNAT.RES_ERROR,
                     XNAT.RSP_ERROR: "result evaluation failure" }
