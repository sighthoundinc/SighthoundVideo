#*****************************************************************************
#
# Launch.py
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

import copy
import getpass
import os
import random
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ElementTree

from ctypes import c_void_p
from ctypes import c_int
from ctypes import c_char_p
from ctypes import c_wchar_p

from ConfigParser import ConfigParser

from vitaToolbox.ctypesUtils.LoadLibrary import LoadLibrary


###############################################################################

# Name of the configuration file.
_kConfigFile = "shlaunch.cfg"

# Base name of the shlaunch executable w/o extension.
_kServiceExe = "shlaunch"

# The sudo application we use to run the service with administrative rights.
_kSudoExe = "SighthoundVideoLauncher"

# The (one and only) section in the configuration file.
_kConfigSectionMain = "Main"

# Configuration key: auto-start the backend when the service starts (boolean,
# default is "FALSE"). Mostly important at system boot time.
# NOTE: all keys must be lowercase, the INI reader normalizes like that
kConfigKeyAutoStart = "autostart"

# Configuration key: do start the backend via the service (boolean, default
# is "TRUE"). This is checked by the service and blocks the autostart, but is
# also used in the frontend to know whether to launch the backend ovr the
# service or all by itself.
kConfigKeyBackend = "backend"

# Configuration boolean values (strings).
kConfigValueTrue = "TRUE"
kConfigValueFalse = "FALSE"

# Enable autostart by default on Windows only (since OSX is still plagued by
# network drive issues, so we'd rather let user enable the service explicitly there)
kAutoStartDefault = (sys.platform == 'win32')

_kDefaultSettings = { kConfigKeyAutoStart: kAutoStartDefault,
                      kConfigKeyBackend  : kConfigValueTrue }

# Where to create or expect the service launch registration.
_kDaemonPlistName = "com.sighthound.video.launch"
_kDaemonPlistFile = _kDaemonPlistName + ".plist"
_kDaemonPlistPath = os.path.join(os.path.sep, "Library", "LaunchDaemons",
                                 _kDaemonPlistFile)

# How long to wait for activation to be launched.
_kActivationLaunchTimeout = 20

# Decision about whether to run as a service not not. Made at runtime.
_kServiceAvailable = None

###############################################################################
def serviceAvailable():
    """ Checks whether the service is expected to be present and that we should
    use it, for at least determining the work directory. Whether it does the
    job of launching the back-end is a different decision.

    @return  True if the service is available to us.
    """
    global _kServiceAvailable
    if _kServiceAvailable is None:
        _kServiceAvailable = hasattr(sys, 'frozen')
        if _kServiceAvailable:
            try:
                _kServiceAvailable = 0 == int(os.getenv("SV_NO_SERVICE", "0"))
            except:
                pass
    return _kServiceAvailable


###############################################################################
_libName = 'launch'

_launchlib = LoadLibrary(None, _libName)

_launchlib.launch_open.argtypes = []
_launchlib.launch_open.restype = c_void_p

_launchlib.launch_close.argtypes = [c_void_p]
_launchlib.launch_close.restype = c_int

_launchlib.launch_do.argtypes = [c_void_p, c_int]
_launchlib.launch_do.restype = c_int

_launchlib.launch_pid.argtypes = [c_void_p]
_launchlib.launch_pid.restype = c_int

_launchlib.launch_status.argtypes = [c_void_p]
_launchlib.launch_status.restype = c_int

_launchlib.launch_build.argtypes = [c_void_p]
_launchlib.launch_build.restype = c_char_p

_launchlib.launch_datadir.argtypes = [c_void_p]
_launchlib.launch_datadir.restype = c_wchar_p

_launchlib.launch_shutdown.argtypes = [c_void_p]
_launchlib.launch_shutdown.restype = c_int

###############################################################################

# Extra flag to signal the service that the back-end(s) should be killed, before
# an actual launch (see LAUNCH_FLAG_KILL_FIRST in the service).
_kLaunchFlagKillFirst = 0x10000

###############################################################################
class Launch(object):
    """ To talk to the launch service, mainly to start the back-end and to get
    the data directory. And of course to determine if the service is up.
    """

    ###########################################################
    def __init__(self):
        """ Constructor. Does NOT connect to service.
        """
        super(Launch, self).__init__()
        self._handle = None


    ###########################################################
    def open(self):
        """ Connect to the service.

        @return True if service control is established. False if this did not
                work out, which in most of the cases means that the service is
                not running. There is no recovery for that, it either didn't
                get installed properly or it got shut down by an administrator.
        """
        if self._handle:
            return True
        self._handle = _launchlib.launch_open()
        return self._handle is not None


    ###########################################################
    def close(self):
        """ Detaches from the service.

        @return True if the operation succeeded or if we have been detached
                already. False if an error occurred, retrying is an option, but
                most likely not to succeed. Abandonment of the instance and
                possible restart of the owning process is recommended.
        """
        if not self._handle:
            return True
        if _launchlib.launch_close(self._handle):
            self._handle = None
            return True
        return False


    ###########################################################
    def do(self, signal=None, killFirst=False):
        """ Signals the service to launch the back-end. It is up to the service
        to detect the trigger, which happens asynchronously.

        @param  signal     The launch signal. Anything but zero will trigger a
                           launch operation. You may use a random or sequence
                           number to detect different launch triggers, in the
                           range of 1..65535 (16bit unsigned integer). If the
                           value is None a random number will be generated.
        @param  killFirst  Flag to just kill old back-ends and not launch.
        @return            (oldSignal, newSignal) The old value of the launch
                           signal. If it is zero it means that no trigger was
                           set before. If it is the same as the signal and such
                           has been chosen to be unique it means that the former
                           launch request has not been honored yet. The new one
                           is the signal passed in or the auto-generated value.
                           None if the client is not connected.
        """
        if not self._handle:
            return None
        if signal is None:  # create the signal value if none is given
            signal = random.randint(1,65535)
        signal &= 0xffff    # make sure the signal stays 16bit
        signal |= _kLaunchFlagKillFirst if killFirst else 0
        oldSignal = _launchlib.launch_do(self._handle, signal)
        return oldSignal, signal


    ###########################################################
    def pid(self):
        """ The process identifier of the service. This allows detection of
        service restarts and re-issuing a trigger signal.

        @return Service PID. None if not connected to the service.
        """
        if not self._handle:
            return None
        return _launchlib.launch_pid(self._handle)


    ###########################################################
    def status(self):
        """ To determine if the last back-end process launch succeeded.

        @return  Zero if the launch failed. Last launch signal on success.
                 None if not connected to the service.
        """
        if not self._handle:
            return None
        return _launchlib.launch_status(self._handle)


    ###########################################################
    def shutdown(self):
        """ To check if the service got notified of a system shutdown.

        @return  Zero if no notification. 1 if shutdown got signaled.
                 None if not connected to the service.
        """
        if not self._handle:
            return None
        return _launchlib.launch_shutdown(self._handle)


    ###########################################################
    def build(self):
        """ Determines the build number of the service. This is only needed and
        currently works for OSX. Under Win32 we _always_ return None!

        @return  The build number, same format we use in the app itself. Or
                 None if not connected to the service.
        """
        if not self._handle:
            return None
        build = _launchlib.launch_build(self._handle)
        return copy.deepcopy(build)


    ###########################################################
    def dataDir(self):
        """ Lets the service tell us about the user data directory it chose.
        This directory is system-global and also needs to be prepared to be
        accessible by front-ends of any user, which can only be done by the
        service itself.

        @return  The data directory. Empty if it hasn't been created yet.
                 None if not connected to the service.
        """
        if not self._handle:
            return None
        wstrDataDir = _launchlib.launch_datadir(self._handle)
        return copy.deepcopy(unicode(wstrDataDir))


    ###########################################################
    def setConfig(self, cfg, dataDir=None):
        """ Writes a configuration file which the service picks up at start
        time. The key names are kConfig*. If a key is missing a default value
        will be written.

        @param cfg      Dictionary containing the configuration.
        @param dataDir  Data directory path, so configuration access can happen
                        even w/o a connection to the service, otherwise None.
        @return         True if written successfully, False on error.
        """
        if dataDir is None:
            dataDir = self.dataDir()
            if not dataDir:
                return False
        cfgFile = os.path.join(dataDir, _kConfigFile)
        try:
            h = open(cfgFile, 'w')
            h.write("[%s]\n%s=%s\n%s=%s\n" % (
                    _kConfigSectionMain,
                    kConfigKeyAutoStart,
                    cfg.get(kConfigKeyAutoStart, _kDefaultSettings[kConfigKeyAutoStart]),
                    kConfigKeyBackend,
                    cfg.get(kConfigKeyBackend  , _kDefaultSettings[kConfigKeyBackend])))
            return True
        except:
            return False
        finally:
            try:
                h.close()
            except:
                pass


    ###########################################################
    def getConfig(self, dataDir=None):
        """ Picks up the current configuration.

        @param dataDir  Data directory path, so configuration access can happen
                        even w/o a connection to the service, otherwise None.
        @return         Configuration dictionary. None if n/a.
        """
        if dataDir is None:
            dataDir = self.dataDir()
            if not dataDir:
                return None
        try:
            cfgFile = os.path.join(dataDir, _kConfigFile)
            cp = ConfigParser(_kDefaultSettings)
            cp.read([cfgFile])
            result = {}
            for item in cp.items(_kConfigSectionMain):
                result[item[0]] = item[1]
            return result
        except:
            return None


    ###########################################################
    def getConfigOrDefaults(self, dataDir=None):
        """Return the current config or defaults on error.

        @param dataDir  Data directory path, so configuration access can happen
                        even w/o a connection to the service, otherwise None.
        @return         Configuration dictionary.
        """
        ret = self.getConfig(dataDir)
        if ret is None:
            ret = _kDefaultSettings

        return ret


###############################################################
def launchLog(msg):
    """Simple log function which appends to shlaunch.log in the temp folder,
    since we won't have logging enabled at early/service installation time.

    @param msg  The message to log. Timestamp will be prefixed automatically.
    @return     True if logged successfully. False on error.
    """
    try:
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        msg = "%s [LAUNCH] - %s\n" % (tstamp, msg)
        f = open(os.path.join(tempfile.gettempdir(), "shlaunch_usr.log"), "a")
        f.write(msg)
        return True
    except:
        return False
    finally:
        try:
            f.close()
        except:
            pass


###############################################################################
def _loadLaunchPlist(plistFile=_kDaemonPlistPath):
    """ Loads the plist which declares the service for OSX.

    @param plistFile  Location of the file. Default value for release/frozen.
    @return           Tuple (id,exe,rel) with the service registration name,
                      the executable path and the release, as found in the
                      plist. None if the data could not be loaded, either
                      because of the file to be missing or its format not being
                      understood.
    """
    if not os.path.isfile(plistFile):
        launchLog("plist file not found (%s)" % plistFile)
        return None
    try:
        root = ElementTree.parse(plistFile).getroot()
        if "plist" != root.tag:
            launchLog("no <plist> found in '%s'" % plistFile)
            return None
        dct = root.findall("./dict")[0]
        nxt = False
        for c in dct:
            if nxt:
                if c.tag == "string":
                    label = c.text
                    break
                launchLog("unknown label tag <%s>" % c.tag)
                return None
            if c.tag == "key" and c.text == "Label":
                nxt = True
        else:
            launchLog("no label tag found in '%s'" % plistFile)
            return None
        progArgs = dct.findall("./array/string")
        launch  = progArgs[0].text
        release = progArgs[1].text
        return (label, launch, release)
    except:
        launchLog("_loadLaunchPlist - UNCAUGHT ERROR (%s)" % sys.exc_info()[1])
        return None


###############################################################################
def _checkServicePlist(build):
    """Checks if the service is properly registered.

    @param  build  The build number, same as what to expect in the service
                   plist file if installed properly and being recent.
    @return        True the plist looks fine.
    """
    exeDir = os.path.dirname(sys.executable)
    shlaunchPath = os.path.join(exeDir, _kServiceExe)
    lpl = _loadLaunchPlist()
    if lpl is None:
        return False
    if lpl[0] != _kDaemonPlistName:
        launchLog("daemon name mismatch (%s)" % lpl[0])
        return False
    if lpl[1] != shlaunchPath:
        launchLog("daemon path mismatch (%s)" % lpl[1])
        return False
    if lpl[2] != build:
        launchLog("build mismatch (%s)" % lpl[2])
        return False
    return True


###############################################################################
def _activateMac(build, localDataDir):
    """ Service activation call for OSX. Asks the user for credentials run the
    service executable with administrator rights, so it can install the plist
    for the service and create the global user data directory or a symlink to
    to local one if needed. Once done we launch the service one more time under
    the current user's account, same as the OSX service launcher would do, plus
    telling it not to kill this process.

    @param  build         The build number, to ensure the service is compatible.
    @param  localDataDir  Potential legacy local directory to move.
    @return               True if activation worked, False if it failed.
    """
    if type(localDataDir) == unicode:
        localDataDir = localDataDir.encode('utf-8')
    exeDir = os.path.dirname(sys.executable)
    shlaunchPath = os.path.join(exeDir, _kServiceExe)
    params = []
    params.append(os.path.join(exeDir, _kSudoExe))
    params.append("--wait")
    params.append(shlaunchPath)
    params.append(build)
    params.append("--activate")
    params.append(str(os.getpid()))
    params.append(localDataDir)
    params.append(str(os.getuid()))
    params.append(getpass.getuser())
    try:
        launchLog("activating launch %s ..." % str(params))
        p = subprocess.Popen(params,
            stdin =subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True)
        for s in [p.stdin, p.stdout, p.stderr]:
            s.close()
        # there is no other way, we need to wait for the activation to finish,
        # since the user has the right to idle on the admin prompt as long as
        # she wants ...
        exitCode = p.wait()
        if 0 != exitCode:
            launchLog("activation exit code %d" % exitCode)
            return False
        launchLog("activation successful")
    except:
        launchLog("activate error %s (%s)" % (str(params), sys.exc_info()[1]))
        return False

    lpl = _loadLaunchPlist()
    if lpl is None:
        launchLog("activation did not yield the plist?!")
        return False
    params = []
    params.append(lpl[1])
    params.append(lpl[2])
    # NOTE: since we are the parent process of shlaunch we're not in danger of
    #       getting killed by it during the old-process-cleanup stage.
    try:
        launchLog("launching service %s ..." % str(params))
        p = subprocess.Popen(params,
            stdin =subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True)
        for s in [p.stdin, p.stdout, p.stderr]:
            s.close()
        launchLog("launch call issued")
    except:
        launchLog("launch error %s (%s)" % (str(params), sys.exc_info()[1]))
        return False
    return True


###############################################################
def launchCheckWin():
    """Checks if the service is running, under Windows. Need to do much less
    diligence here, since everything is based on the installer to get things
    correctly set up.

    @return  True if we have contact, False if anything is not right.
    """
    try:
        l = Launch()
        return l.open()
    except:
        return False
    finally:
        try:
            l.close()
        except:
            pass


###############################################################
def launchCheckMac(build, localDataDir, timeout):
    """Checks if the service is running. If not it will try to activate it.
    Also takes care about moving the data directory from a legacy location to
    the global spot.

    @param  build         The current build number, so we can detect mismatched
                          service instance being present.
    @param  localDataDir  Legacy data directory, for possible migration needed.
    @param  timeout       Number of seconds to wait for service to be ready.
    @return               True if things are in order and the service is ready
                          for being accessed via the Launch API. False if not.
    """
    activated = False
    if not _checkServicePlist(build):
        launchLog("service plist conflict, activating...")
        if not _activateMac(build, localDataDir):
            return False
        activated = True
    end = time.time() + timeout
    while time.time() < end:
        l = Launch()
        # check and see if the service is available
        try:
            if l.open():
                # is it the right build?
                lbuild = l.build()
                if build == lbuild:
                    # all good, we're up and ready
                    launchLog("launch build %s verified" % build)
                    return True
                launchLog("build is %s, expected %s" % (lbuild, build))
        finally:
            try:
                l.close()
            except:
                pass
        # do one activation attempt, the service executable will run with
        # admin privileges and try to set things straight and be up and
        # ready for us
        if not activated:
            launchLog("service n/a, activating...")
            tm = time.time()
            if not _activateMac(build, localDataDir):
                return False
            end += time.time() - tm
            activated = True
        # don't poll too quickly, process re-launch etc does take some time
        time.sleep(.5)
    return False


###############################################################################

# testing, both exercising all functions as well as checking to see if polling
# for the shutdown flag is feasible ...

def _testLaunch():
    launch = Launch()
    if not launch.open():
        print "cannot open"
        sys.exit(1)
    print "opened"
    print "data directory is '%s'" % launch.dataDir()
    print "pid: %s" % launch.pid()
    print "status: %s" % launch.status()
    print "shutdown: %s" % launch.shutdown()
    print "launch result: %s" % str(launch.do(killFirst=True))
    time.sleep(1)
    print "status: %s" % launch.status()
    result = launch.close()
    if not result:
        print "cannot close (%d)" % result
        sys.exit(1)
    print "closed"

def _testLaunchPerf():
    now = startedAt = time.time()
    stopAt = now + 5
    polls = 0
    while now < stopAt:
        for _ in xrange(10):
            launch = Launch()
            if not launch.open():
                print "CANNOT OPEN!"
                sys.exit(1)
            if launch.shutdown():
                print "SHUTDOWN?!"
                sys.exit(1)
            if not launch.close():
                print "CANNOT CLOSE!"
                sys.exit(1)
            polls += 1
        now = time.time()
    print "%.3f poll(s) per second" % (polls / (now - startedAt), )

def _testConfig():
    launch = Launch()
    if not launch.open():
        print "open error"
        sys.exit(1)
    cfg = launch.getConfig()
    print "config >>> %s" % (str(cfg))
    if not launch.setConfig({ kConfigKeyAutoStart: kConfigValueTrue }):
        print "cannot set config"
    print "config >>> %s" % (str(launch.getConfig()))
    if not launch.close():
        print "close error"
        sys.exit(1)

if __name__ == '__main__':
    _testLaunch()
    _testLaunchPerf()  # measured 46K polls in a Windows 8.1 VM
    _testConfig()
