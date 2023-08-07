#*****************************************************************************
#
# WebServer.py
#     Controller for the nginx web server.
#     Creates new instances, ensures that they are working and runs a port opener in
#     parallel to support NAT traversal.
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
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

import sys, os, socket, time, subprocess, shutil, hashlib, base64, httplib, re
import traceback, random, pickle, webstuff, MessageIds, uuid
import ctypes
import urllib

from subprocess import Popen, PIPE

from string import Template
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.networking.HttpClient import HttpClient
from vitaToolbox.process.ProcessUtils import getProcessesWithName
from vitaToolbox.process.ProcessUtils import killProcess
from vitaToolbox.process.ProcessUtils import filteredProcessCommands
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8, ensureUnicode, simplifyString

from xnat import xnat
from xnat.xnat import XNAT

from appCommon.CommonStrings import kStatusFile
from appCommon.CommonStrings import kStatusKeyInstance
from appCommon.CommonStrings import kStatusKeyNumber
from appCommon.CommonStrings import kStatusKeyPort
from appCommon.CommonStrings import kStatusKeyVerified
from appCommon.CommonStrings import kStatusKeyCertificateId
from appCommon.CommonStrings import kStatusKeyPortOpenerState
from appCommon.CommonStrings import kStatusKeyRemotePort
from appCommon.CommonStrings import kStatusKeyRemoteAddress
from appCommon.CommonStrings import kWebserverExeName
from appCommon.CommonStrings import kXNATExeName
from appCommon.CommonStrings import kNginxMarkerArg
from appCommon.CommonStrings import kXNATMarkerArg
from logging import LoggerAdapter
from DebugLogManager import DebugLogManager


"""
Controller for the nginx web server. Creates new instances, ensures that they
are working and runs a port opener in parallel to support NAT traversal. For
every new process/run of a server its world or work directory respectively gets
recreated. Only the (access/error) log files get written in the regular
Arden.ai logs folder. Everything else gets removed if an instance is shut
down.

FIXME (01/24/2014):

At least under Windows there is a bug that nginx will not run if its work
directory's path contain's non-ASCII characters. Windows support in general is
considered to be optional and not very well documented. As a matter of fact all
of the Win32 code is not even in the source archive, but you need to get it
from their SCM. We actually have an own repo to build nginx for both OSX and
Windows, located (at the moment of this writing) here:

https://vitamind.kilnhg.com/Code/Vitamin-D-Video/scratch/nginxBuild.git.

After a build attempt all of the Windows specific code can be found in

msvc\nginx_win32_ardenai_build\buildenv\build\nginx\src\os\win32

The Windows support is (or at least appears) messy at some points. For example
files are always opened as Unicode (ngx_open_file), with the cstr expected to
be in UTF-8. However ngx_getcwd() is calling GetCurrentDirectory(), so it gets
whatever the current Windows locale decides to use for the character set, making
its output incompatible for UTF-8-to-Unicode conversion. What the general
strategy (if there is one actually) is remains hard to tell. For example
ngx_open_dir() does pure cstr, while ngx_file_info() converts its paths to
Unicode, again expecting UTF-8 to be the cstr's encoding. This makes it hard to
just fix this one particular issue and not potentially breaking other things.
For years people have been writing about the simple fact that one cannot run the
nginx binary for Windows from a directory containing non-ASCII characters. One
translated (russian) support response simply says not to use russian characters
in the path, period. There seems to be not much affection towards Windows.

The implications resulting from all of this are:

1. We need to provide every path fully qualified in the nginx configuration
file. No relative paths are possible, because if you do nginx uses the current
directory, which then will fail on file opening.

2. The config file we need to be saved as UTF-8. There's no mentioning in the
nginx documents about this fact, but only this way file paths referenced in the
configuration can actually be accessed (if they contain non-ASCII).

3. At this moment we still cannot support people with either having their user
name containing non-ASCII, and/or their Windows having the Arden.ai work
directory contain non-ASCII. Later case comes from the fact that e.g. the folder
"Documents And Settings" is unfortunately translated, and thus can contain
non-ASCII. We have implemented a proof of concept for a workaround though:
by setting the environment variable ARDEN.AI_WEBDIR the 'web' folder, usually
located in the Arden.ai user directory, can be placed in a spot so no
non-ASCII characters will be in the path at all. This seems to work well, thus
the final approach could be that Arden AI creates the web folder
automatically e.g. in C:\ardenaivideo_web and then removes it at shutdown.
We haven't decided yet if we want that patchwork or not. Having a more Windows
empathetical/working nginx would be the actual way to go of course.

To make things worse, regarding non-ASCII path names, the subprocess.Popen
implementation in Python 2.x cannot deal with non-ASCII strings either, or so
the error message goes. Since we have to pass in full file paths to nginx, to
avoid it calling the ngx_getcwd() function, this would be a show stopper.
Fortunately there is a solution: by encoding these parameters with
sys.getfilesystemencoding() - see below. Again, passing in full paths for both
the nginx configuration file (option -c) and the current/work directory (-p)
is a must, at least under Windows.

"""


###############################################################################

# realm, used in the basic auth mechanism
REALM = "Arden.ai"

###############################################################################

_kLogSize         = 1024 * 1024 * 10  # size of WebServer.og
_kMaxLogSize      = 1024 * 1024 * 5   # size of nginx access/error logs
_kMaxLogFiles     = 2    # number of history files(.0,.1,...) per log file
_kRetryStartSecs  = 120  # retry delay if a server start failed
_kRetrySecs       = 5    # retry delay if server verification failed during run
_kVerifySecs      = 30   # how often to verify the server
_kBackendPingSecs = 60   # how often to ping the back-end
_kPortCheckSecs   = 3600 # how often the port opener will do the external check
_kPortCheckTimeout= 10   # timeout for external port checks (in seconds)
_kHtAuthFile      = "htauth"    # the auth file name, containing the credentials
_kConfigName      = "ardenaiweb.conf"    # name of the nginx config file
_kPingFile        = "ping.txt"  # name of ping file, to detect older instances
_kWebServerLog    = "WebServer.log" # name of the log file for this module
_kErrorLog        = "WebServerError.log"    # name of the nginx error log file
_kAccessLog       = "WebServerAccess.log"   # name of the nginx access log file
_kServerName      = "Arden.aiWebServer"   # official name for our nginx server
_kRemoteAppName   = os.path.join("share", "svremoteviewer") # directory where we expect the remote app code

# Template to render the basic auth portion of the nginx config file.
_kAuthBasicTemplate = """
    auth_basic "$realm";
    auth_basic_user_file "$authfile";"""

# To turn off auth for a certain path.
_kAuthBasicOff = """
            auth_basic off;"""

# Template to render the digest auth portion of the nginx config file. We did
# abandon digest auth for a variety of issues we encountered, so this is more
# or less obsolete.
_kAuthDigestTemplate = """
    auth_digest "$realm";
    auth_digest_user_file "$authfile";
    auth_digest_timeout 60s;
    auth_digest_expires 36000s;
    auth_digest_replays 20;"""

# To turn off digest auth for a certain path.
_kAuthDigestOff = """
    auth_digest off;"""

# The URL where the port checker script can be reached.
_kPortOpenerCheckURL = "https://portcheck.ardenai.com/portcheck.php"

# Timeout addition for the port check script. The timeout value communicated to
# it is used on the server for the HTTP fetch attempt. Naturally there is some
# overhead for contacting the portcheck server via SSL, starting the PHP script
# and itself its HTTP client instance etc, so we need to wait a bit longer to
# make sure the script has time to return to us what it got or what not.
_kPortOpenerCheckExtraSecs = 5

# Is this Windows we're running?
_kIsWin = "win32" == sys.platform

# File extensions (for OpenSSL material).
_kFileExtensionKeyPair        = '.key'
_kFileExtensionCertSignReq    = '.csr' # (only used during certificate creation)
_kFileExtensionCertificate    = '.crt'
_kFileExtensionCertificateDER = '.der'
_kFileExtensionCertificateSHA = '.sha'
_kFileExtensionConfig         = '.cnf'

# Base name for key and certificate files.
_kSSLFileBase = 'sv'

# Number of bits for the RSA key to use
_kKeyPairStrength = 2048

# Number of days a self-signed SSL certificate should be valid.
_kCertExpirationDays = 3650

# 'Domain' for the SSL certificates CN field. Appended to the user portion of
# the e-mail address, to represent a somewhat recognizable construct.
_kCommonNameDomain = ".ardenaivideo"

# Name of the environment variable pointing to the OpenSSL configuration file.
_kOpenSSLConfEnvVar = "OPENSSL_CONF"

# Configuration for OpenSSL, just enough to make it run and create what we need.
_kOpenSSLConf = """
[ req ]
distinguished_name = req_distinguished_name

[ req_distinguished_name]
"""

###############################################################################
def runWebServer(msqQ, cmdQ, logDir, mainDir, port, auth, xmlRpcUrl, rmtDir,
                 epo, secure):
    """Create and start a web server start and monitoring process.

    @param msqQ      The message queue where to report back via pinging.
    @param cmdQ      The queue where to receive the control messages from.
    @param logDir    Where to write the log files.
    @param mainDir   The directory where the transient web server stuff goes.
    @param port      The port for the web server to try to open.
    @param auth      The basic/digest authentication information, or None.
    @param xmlRpcUrl The XML/RPC endpoint to which the proxy bridge points to.
    @param rmtDir    The directory where all other remote media goes to.
    @param epo       Enable the port opener (true) or not.
    @param secure    HTTPS certificate info (contact,name), or None for HTTP.
    """
    ws = WebServer(msqQ, cmdQ, logDir, mainDir, port, auth, xmlRpcUrl, rmtDir,
                   epo, secure)
    ws.run()


###############################################################################

# The configuration file template for NGinx.
_kCfgTemplate = """
worker_processes  1;
error_log "$file_errorLog";
error_log "$file_errorLog" notice;
error_log "$file_errorLog" info;
events {
    worker_connections 256;
}
http {
    default_type application/octet-stream;
    access_log "$file_accessLog";
    sendfile on;
    index off;
    keepalive_timeout 65;$auth
    server {
        rewrite ^/$$ /index.html break;
        rewrite ^/mobile/$$ /mobile/index.html break;
        listen $port$ssl_port_extra http2;$ssl_info
        server_name "$server_name";
        error_page 497 @sslr;
        gzip on;
        gzip_proxied any;
        gzip_types text/css text/plain text/xml application/xml application/javascript application/x-javascript text/javascript application/json text/x-json image/x-icon;
        gzip_vary on;
        gzip_comp_level 9;
        gzip_disable "MSIE [1-6]\.";
        location /xmlrpc/ {
            proxy_pass $xmlrpc_url;
            proxy_set_header X-Real-IP $$remote_addr;
            proxy_connect_timeout 20;
        }
        location /remote/ {
            expires off;
            add_header Cache-Control no-cache;
            if_modified_since off;
            mp4;
            alias "$dir_remote";
        }
        location / {
            expires off;
            add_header Cache-Control no-cache;
            root "$dir_remoteApp";
        }
        location /ping {$auth_off
            expires off;
            add_header Cache-Control no-cache;
            if_modified_since off;
            alias "$file_ping";
        }
        location ~ ^/camera/(.*?)/(.*\.jpg)$$ {
            proxy_pass http://127.0.0.1:$$1/$$2$$is_args$$args;
            proxy_set_header X-Real-IP $$remote_addr;
        }$cameraStreams
        location @sslr {
            add_header Cache-Control no-cache;
            rewrite ^/(.*) https://$$http_host/$$1 permanent;
        }
    }$mimeTypes
}"""

# Sub-template in case we enabled HTTPS. Goes into $ssl_info above.
# Notice that SSLv3 gets turned off due to the POODLE attack.
_kCfgTemplateSSLInfo = """
        ssl_certificate     "$ssl_cert";
        ssl_certificate_key "$ssl_key";
        ssl_protocols TLSv1 TLSv1.1 TLSv1.2;"""

# MIME types we render into the Nginx configuration
# NOTE: not all of them are truly needed, but there's no harm in keeping
_kMimeTypes = """
types {
    text/html                             html htm shtml;
    text/css                              css;
    text/xml                              xml;
    image/gif                             gif;
    image/jpeg                            jpeg jpg;
    application/x-javascript              js;
    application/atom+xml                  atom;
    application/rss+xml                   rss;
    text/mathml                           mml;
    text/plain                            txt;
    text/vnd.sun.j2me.app-descriptor      jad;
    text/vnd.wap.wml                      wml;
    text/x-component                      htc;
    image/png                             png;
    image/tiff                            tif tiff;
    image/vnd.wap.wbmp                    wbmp;
    image/x-icon                          ico;
    image/x-jng                           jng;
    image/x-ms-bmp                        bmp;
    image/svg+xml                         svg svgz;
    image/webp                            webp;
    application/java-archive              jar war ear;
    application/mac-binhex40              hqx;
    application/msword                    doc;
    application/pdf                       pdf;
    application/postscript                ps eps ai;
    application/rtf                       rtf;
    application/vnd.ms-excel              xls;
    application/vnd.ms-powerpoint         ppt;
    application/vnd.wap.wmlc              wmlc;
    application/vnd.google-earth.kml+xml  kml;
    application/vnd.google-earth.kmz      kmz;
    application/x-7z-compressed           7z;
    application/x-cocoa                   cco;
    application/x-java-archive-diff       jardiff;
    application/x-java-jnlp-file          jnlp;
    application/x-makeself                run;
    application/x-perl                    pl pm;
    application/x-pilot                   prc pdb;
    application/x-rar-compressed          rar;
    application/x-redhat-package-manager  rpm;
    application/x-sea                     sea;
    application/x-shockwave-flash         swf;
    application/x-stuffit                 sit;
    application/x-tcl                     tcl tk;
    application/x-x509-ca-cert            der pem crt;
    application/x-xpinstall               xpi;
    application/xhtml+xml                 xhtml;
    application/zip                       zip;
    application/octet-stream              bin exe dll;
    application/octet-stream              deb;
    application/octet-stream              dmg;
    application/octet-stream              eot;
    application/octet-stream              iso img;
    application/octet-stream              msi msp msm;
    audio/midi                            mid midi kar;
    audio/mpeg                            mp3;
    audio/ogg                             ogg;
    audio/x-m4a                           m4a;
    audio/x-realaudio                     ra;
    video/3gpp                            3gpp 3gp;
    video/mp4                             mp4;
    video/mpeg                            mpeg mpg;
    video/quicktime                       mov;
    video/webm                            webm;
    video/x-flv                           flv;
    video/x-m4v                           m4v;
    video/x-mng                           mng;
    video/x-ms-asf                        asx asf;
    video/x-ms-wmv                        wmv;
    video/x-msvideo                       avi;
    application/x-mpegurl                 m3u8;
    video/MP2T                            ts;
}"""


###############################################################################
def killWebServerProcesses(logger):
    """Kill all processes which might have been spawned by the web server.

    @param logger  The logger to use.
    @return        True if all processes could be killed, False if none or some.
    """
    result = True
    exes = []
    def killPIDs(pids):
        result = True
        for pid in pids:
            logger.info("killing process %d..." % pid)
            try:
                killProcess(pid)
            except:
                logger.warn("kill failed (%s)" % sys.exc_info()[1])
                result = False
        return result
    # take down the processes which were launched by separate executables
    if webstuff.shared_library() is None: exes.append((kWebserverExeName, 2))
    if xnat.sharedLibrary     () is None: exes.append((kXNATExeName     , 1))
    for exe in exes:
        loop = exe[1]
        while 0 < loop:
            loop -= 1
            pids = sorted(getProcessesWithName(exe[0]))
            if 0 == len(pids): break
            logger.info("%d processes named '%s' exist" % (len(pids), exe[0]))
            result &= killPIDs(pids)
    # now to the ones which are forks calling into shared libraries
    marks = []
    if webstuff.shared_library() is not None: marks.append((kNginxMarkerArg, 2))
    if xnat.sharedLibrary()      is not None: marks.append((kXNATMarkerArg , 1))
    for mark in marks:
        loop = mark[1]
        while 0 < loop:
            loop -= 1
            pids = sorted(filteredProcessCommands(
                lambda _, cmdln: -1 != cmdln.find(mark[0])))
            if 0 == len(pids): break
            logger.info("%d command lines match '%s'" % (len(pids), mark[0]))
            result &= killPIDs(pids)
    return result


###############################################################################
def _createKeyPairAndCertificate(basePath, contact, name, logger):
    """ Create a key pair and a self-signed certificate to enable SSL in Nginx.

    @param basePath   Path where the material gets stored, plus the name of the
                      files. The extensions (.key, .crt) will be appended.
    @param contact    Contact information, to be put into the certificate.
    @param name       Name (of user) or some iD, to be put into the certificate.
    @param logger     Logger instance to use.
    @return           True on success or False if an error occurred.
    """
    def exec_openssl(conf, args, logger):
        cmd = [webstuff.openssl_exe()]
        cmd.extend(args)
        env2 = os.environ.copy()
        env2[_kOpenSSLConfEnvVar] = ensureUtf8(conf)
        if _kIsWin:
            env3 = {}
            for k, v in env2.iteritems():
                try:
                    env3[str(k)] = str(v)  # must _not_ be Unicode apparently
                except:
                    logger.error("Failed to copy env key=" + k.encode('utf-8') + " value=" + v.encode('utf-8'))
            sinf = subprocess.STARTUPINFO()
            sinf.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            proc = subprocess.Popen(cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                startupinfo=sinf, env=env3)
        else:
            proc = subprocess.Popen(cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env2)
        for ln in proc.stdout:
            logger.info(">>> " + ln.rstrip())
        return proc.wait()

    cwdBackup = os.getcwd()
    try:
        os.chdir(os.path.dirname(basePath))

        basePath = os.path.basename(basePath)

        subject = "/C=XX/ST=XX/L=XX/O=%s/OU=%s/CN=%s%s" % \
            (contact, name, name, _kCommonNameDomain)
        key = basePath + _kFileExtensionKeyPair
        csr = basePath + _kFileExtensionCertSignReq
        crt = basePath + _kFileExtensionCertificate
        der = basePath + _kFileExtensionCertificateDER
        sha = basePath + _kFileExtensionCertificateSHA
        cnf = basePath + _kFileExtensionConfig
        for path in [key, csr, crt, cnf, der, sha]:
            if os.path.exists(path):
                os.remove(path)
                logger.info("deleted old SSL file: %s" % path)
        try:
            f = open(cnf, "w+")
            f.write(_kOpenSSLConf)
        finally:
            try: f.close()
            except: pass
        for args in (
            [ 'genrsa', '-out', key, str(_kKeyPairStrength) ],
            [ 'req', '-new', '-key', key, '-out', csr, '-subj', subject ],
            [ 'x509', '-req', '-days', str(_kCertExpirationDays), '-in', csr,
             '-signkey', key, '-out', crt ],
            [ 'x509', '-outform', 'der', '-in', crt, '-out', der]):
            logger.info("running OpenSSL %s ..." % str(args))
            exitCode = exec_openssl(cnf, args, logger)
            if exitCode:
                logger.error("failed, exit code %d" % exitCode)
                return False
        for path in [key, csr, crt]:
            if not os.path.exists(path):
                logger.info("missing file %s" % path)
                return False
        try:
            derFile = open(der, "rb")
            shaFile = open(sha, "w")
            shaFile.write(hashlib.sha1(derFile.read()).hexdigest())
        finally:
            try: derFile.close()
            except: pass
            try: shaFile.close()
            except: pass

        os.remove(csr)
        os.remove(cnf)
        os.remove(der)
        return True
    except:
        logger.error("certificate generation error (%s)" % sys.exc_info()[1])
        return False
    finally:
        os.chdir(cwdBackup)


###############################################################################
def runNginx(*args):
    """ To be run in a forked process, calling the nginx entry point loaded via
    a shared library. This move was necessary to make nginx appear still as the
    common agent process, so the application firewall would not register it as
    a different process, for which too often it wouldn't make it into the
    inclusion table and hence the port would be blocked.

    @param args  The arguments passed to nginx's main(), which will then be made
                 available to it via the common argc,argv parameters.
    """
    cdll = ctypes.CDLL(webstuff.shared_library())
    argv = (ctypes.c_char_p * (len(args) + 1))()
    argv[:-1] = args
    argv[-1] = None
    argc = len(argv) - 1
    nginxExitcode = cdll.main(argc, argv)
    sys.exit(nginxExitcode)


###############################################################################
def _configFilePath(path, isDir):
    """ Makes a (file) path suitable for the nginx configuration.

    @param path   The file path.
    @param isDir  If the path is a directory (True) or a file (False).
    @return       The properly encoded path.
    """
    return ensureUtf8(webstuff.normalize_path(path, isDir))


###############################################################################
class ProblemLogger(LoggerAdapter):
    """ To only allow WARN, ERROR, CRITICAL log messages.
    """
    def info(self, msg, *args, **kwargs):
        pass
    def debug(self, msg, *args, **kwargs):
        pass


###############################################################################
class WebServer(object):
    """ The web server (actually its controller).

    @param msqQ      The message queue where to report back via pinging.
    @param cmdQ      The queue where to receive the control messages from.
    @param logDir    Where to write the log files.
    @param mainDir   The directory where the transient web server stuff goes.
    @param port      The port for the web server to try to open.
    @param auth      The basic/digest authentication information, or None.
    @param xmlRpcUrl The XML/RPC endpoint to which the proxy bridge points to.
    @param rmtDir    The directory where all other remote media goes to.
    @param epo       Enable the port opener (true) or not.
    @param secure    HTTPS certificate info (contact,name), or None for HTTP.
    """
    def __init__(self, msgQ, cmdQ, logDir, mainDir, port, auth, xmlRpcUrl,
                 rmtDir, epo, secure):
        self._secure        = secure
        self._msgQ          = msgQ
        self._cmdQ          = cmdQ
        self._logDir        = logDir
        self._logger        = getLogger("WebServer.log", logDir, _kLogSize)
        self._mainDir       = mainDir
        self._port          = port
        self._auth          = "" if auth is None else auth
        self._xmlRpcUrl     = xmlRpcUrl
        self._remoteDir     = rmtDir
        self._reconfigure   = False
        self._workDir       = None
        self._accessLogFile = None
        self._errorLogFile  = None
        self._configFile    = None
        self._shutdown      = False
        self._nextBEPing    = 0
        self._instance      = None
        self._verified      = False
        self._lastStatus    = {}
        self._certificateId = None
        if hasattr(sys, "frozen"):
            self._remoteAppDir = os.path.join(os.getcwd(), _kRemoteAppName)
        else:
            self._remoteAppDir = os.path.join(os.getenv("SV_DEVEL_LIB_FOLDER_CONAN"), "..", _kRemoteAppName)
        self._logRotater = None
        self._portOpener = None
        self._enablePortOpener(epo)
        self._logger.info("port: %d, opener running: %s, remote-app-dir: %s" %
                          (self._port, epo, self._remoteAppDir))
        self._resetMainDir()
        self._loadCertificateId(True)
        self._cameraLocations={}

        # Set up debug logging
        self._debugLogManager = DebugLogManager("WebServer", os.path.join(mainDir,".."))


    ###########################################################
    def logger(self):
        """ Expose the logger.
        """
        return self._logger


    ###########################################################
    def deleteStatusFile(self):
        """ Removes the status file.
        """
        spath = os.path.join(self._mainDir, kStatusFile)
        try:
            if os.path.exists(spath):
                os.remove(spath)
        except:
            self._logger.error("cannot remove status file %s (%s)" %
                               (spath, sys.exc_info()[1]))

    ###########################################################
    def _loadCertificateId(self, force):
        """Loads the certificate ID from the file emitted during creation time.

        @param  force  True to read it out every time.
        """
        if not force:
            return self._certificateId
        self._certificateId = None # drop the old
        shaFilePath = os.path.join(self._mainDir,
                _kSSLFileBase + _kFileExtensionCertificateSHA)
        try:
            shaFile = open(shaFilePath, "r")
            self._certificateId = shaFile.readline()
        except:
            self._logger.warn("cannot read certificate ID from '%s' (%s)" %
                              (shaFilePath, sys.exc_info()[1]))
        finally:
            try: shaFile.close()
            except: pass


    ###########################################################
    def status(self):
        """ Emit the status file in the main directory.
        """
        s = {}
        if self._portOpener is not None:
            self._portOpener.status(s)
        self._loadCertificateId(False)
        s[kStatusKeyPort] = self._port
        s[kStatusKeyInstance] = self._instance
        s[kStatusKeyVerified] = self._verified
        s[kStatusKeyCertificateId] = self._certificateId
        s[kStatusKeyNumber] = self._lastStatus.get(
            kStatusKeyNumber, random.randint(0, 500000))
        if 0 == cmp(self._lastStatus, s):
            return
        tmpfl = os.path.join(self._mainDir,
            "%s.%04x" % (kStatusFile, random.randint(0, 0xffff)))
        self._logger.info("writing new status file %s..." % tmpfl)
        h = None
        try:
            h = open(tmpfl, "wb")
            pickle.dump(s, h, 0)
            h.close()
        except:
            if h is not None:
                try: h.close()
                except: pass
                try: os.remove(tmpfl)
                except: pass
            self._logger.error("cannot write temporary status file %s (%s)" %
                               (tmpfl, sys.exc_info()[1]))
        attempts = 0
        lastErr = None
        while attempts < 5:
            try:
                spath = os.path.join(self._mainDir, kStatusFile)
                if _kIsWin and os.path.exists(spath):
                    os.remove(spath)
                os.rename(tmpfl, spath)
                s[kStatusKeyNumber] = s[kStatusKeyNumber] + 1
                self._lastStatus = s
                return
            except:
                lastErr = sys.exc_info()[1]
            attempts += 1
            time.sleep(.5)
        try: os.remove(tmpfl)
        except: pass
        self._logger.error("could not rename status file (%s)" % lastErr)


    ###########################################################
    def turnedOn(self):
        """ To check if the web server is logically running.
        """
        return -1 < self._port

    ###########################################################
    def _newCamerasConfig(self):
        res="\n"
        for camera in self._cameraLocations:
            port = self._cameraLocations[camera]
            camUri = simplifyString(camera)
            res += "        location /live/" + camUri + ".jpg {\n" + \
                   "            proxy_pass http://127.0.0.1:" + str(port) + "/image.jpg$is_args$args;\n" + \
                   "            proxy_set_header X-Real-IP $remote_addr;\n" + \
                   "        }\n"
            res += "        location /live/" + camUri + ".m3u8 {\n" + \
                   "            proxy_pass http://127.0.0.1:" + str(port) + "/" + camUri + ".m3u8$is_args$args;\n" + \
                   "            proxy_set_header X-Real-IP $remote_addr;\n" + \
                   "        }\n"
            # location ~ ^/camera/(.*?)/(.*\.jpg)$$ {
            res += "        location ~ ^/live/" + camUri + "-([0-9]+).m3u8$ {\n" + \
                   "            proxy_pass http://127.0.0.1:" + str(port) + "/" + camUri + "-$1.m3u8$is_args$args;\n" + \
                   "            proxy_set_header X-Real-IP $remote_addr;\n" + \
                   "        }\n"
        return res



    ###########################################################
    def _newConfig(self):
        """ Creates a new configuration file in the work directory. Here we
        also write out the ping file, hit by our prober, containing a unique
        identifier to be able to distinguish between different instances. And
        we ensure that SSL things are in order.
        """
        if self._secure:
            base = os.path.join(self._mainDir, _kSSLFileBase)
            missing = False
            for ext in [_kFileExtensionCertificate, _kFileExtensionKeyPair,
                        _kFileExtensionCertificateSHA]:
                path = base + ext
                if not os.path.exists(path):
                    self._logger.warn("missing SSL file '%s'" % path)
                    missing = True
                    break
            if missing:
                if _createKeyPairAndCertificate(base,
                    self._secure[0], self._secure[1], self._logger):
                    self._logger.info("SSL key and certificate (re)created")
                else:
                    self._logger.error("SSL material generation failed")
                    return False
            self._loadCertificateId(True)
            sslPortExtra = " ssl"
            sslCertPath = base + _kFileExtensionCertificate
            sslKeyPath  = base + _kFileExtensionKeyPair
            sslInfo = Template(_kCfgTemplateSSLInfo).substitute(
                ssl_cert = _configFilePath(sslCertPath, False),
                ssl_key  = _configFilePath(sslKeyPath, False))
        else:
            sslPortExtra = ""
            sslInfo = ""
        self._instance = uuid.uuid4().hex
        self._logger.info("new server instance is %s" % self._instance)
        fl = None
        try:
            pingFile = os.path.join(self._workDir, _kPingFile)
            fl = open(pingFile, "w")
            fl.write(self._instance)
        except:
            self._logger.error("cannot write %s: (%s)" %
                               (pingFile, sys.exc_info()[1]))
            return False
        finally:
            if fl is not None:
                try: fl.close()
                except: pass
                fl = None
        pingFile = _configFilePath(pingFile, False)
        if "" != self._auth:
            authFile = os.path.join(self._workDir, _kHtAuthFile)
            try:
                fl = open(authFile, "w")
                fl.write(self._auth)
            except:
                self._logger.error("cannot write %s: %s" %
                                   (authFile, sys.exc_info()[1]))
                return False
            finally:
                if fl is not None:
                    try: fl.close()
                    except: pass
                    fl = None
            if is_basic_auth(self._auth):
                self._logger.info("using HTTP Basic Authentication")
                tmpl = _kAuthBasicTemplate
                authOff = _kAuthBasicOff
            else:
                self._logger.info("using HTTP Digest Authentication")
                tmpl = _kAuthDigestTemplate
                authOff = _kAuthDigestOff
            auth = Template(tmpl).substitute(
                realm    = REALM,
                authfile = _configFilePath(authFile, False))
        else:
            auth = ""
            authOff = ""
        doc = Template(_kCfgTemplate).substitute(
            auth           = auth,
            auth_off       = authOff,
            port           = self._port,
            server_name    = _kServerName,
            xmlrpc_url     = self._xmlRpcUrl,
            mimeTypes      = _kMimeTypes,
            cameraStreams  = self._newCamerasConfig(),
            dir_remote     = _configFilePath(self._remoteDir, True),
            dir_remoteApp  = _configFilePath(self._remoteAppDir, True),
            file_errorLog  = _configFilePath(self._errorLogFile, False),
            file_accessLog = _configFilePath(self._accessLogFile, False),
            file_ping      = pingFile,
            ssl_port_extra = sslPortExtra,
            ssl_info       = sslInfo)
        try:
            self._configFile = os.path.join(self._workDir, _kConfigName)
            fl = open(self._configFile, "w")
            fl.write(doc)
            return True
        except:
            self._logger.error("cannot write %s: %s" %
                               (self._configFile, sys.exc_info()[1]))
            return False
        finally:
            if fl is not None:
                try: fl.close()
                except: pass


    ###########################################################
    def _resetMainDir(self):
        """ Cleans out the whole web server main directory, remove all old
        work directories, status file(s) etc. Minus the OpenSSL stuff.
        """
        if not os.path.exists(self._mainDir):
            try:
                os.makedirs(self._mainDir)
                self._logger.info("main directory %s created" % self._mainDir)
            except:
                self._logger.error("cannot create main directory %s (%s)" %
                                   (self._mainDir, sys.exc_info()[1]))
            return
        objs = os.listdir(self._mainDir)
        self._logger.warn("removing %d object(s) in %s..." %
                          (len(objs), self._mainDir))
        keepers = [ _kSSLFileBase + _kFileExtensionKeyPair,
                    _kSSLFileBase + _kFileExtensionCertificate,
                    _kSSLFileBase + _kFileExtensionCertificateSHA ]
        for obj in objs:
            if obj in keepers:
                continue
            obj = os.path.join(self._mainDir, obj)
            try:
                if os.path.isdir(obj):
                    shutil.rmtree(obj)
                else:
                    os.remove(obj)
            except:
                self._logger.warn("cannot remove %s (%s)" %
                                  (obj, sys.exc_info()[1]))


    ###########################################################
    def _newWorkDir(self):
        """ Creates a new work directory, meaning a directory for which each
        web server instance almost all of its files and directories located.
        Exceptions are the access and error logs, which do get emitted in the
        regular log directory.
        """
        uniq = str(int(time.time() * 1000))
        self._workDir = os.path.join(self._mainDir, uniq)
        self._accessLogFile = os.path.join(self._logDir, _kAccessLog)
        self._errorLogFile  = os.path.join(self._logDir, _kErrorLog)
        try:
            os.makedirs(self._workDir)
            os.mkdir(os.path.join(self._workDir, "temp"))
            os.mkdir(os.path.join(self._workDir, "logs"))
            return True
        except:
            self._logger.error("cannot create work directory: %s" %
                               sys.exc_info()[1])
            return False


    ###########################################################
    def _delWorkDir(self):
        """ Removes the current work directory, preferably after the web
        server instance has been shut down.

        @return  True if the removal was complete and the directory is gone.
        """
        result = True
        if self._workDir is not None:
            self._logger.info("removing work directory %s ..." % self._workDir)
            try:
                shutil.rmtree(self._workDir)
            except:
                self._logger.warn("cannot remove: %s" % sys.exc_info()[1])
                result = False
            self._workDir = None
        return result


    ###########################################################
    def reconfigure(self):
        """ Signals that the web server needs to be configured. The actual
        attempt might now happen right away, but as soon as the next restart
        check point is reached. Delaying factors can be port opening or log
        file rotation for instance. We also clear the verification flag since
        from now on the operational state of the server is unknown to us, even
        if the old instance is still functioning, we don't care about it
        anymore.
        """
        self._reconfigure = True
        self._verified = False


    ###########################################################
    def startServer(self, signal=None):
        """ Starts the web server. Launches a new process. However this also
        supports just signaling a running web server, in such a case the
        existing instance keeps running, just dealing with the signal.

        @param signal  The signal, e.g. "reload" to just bounce the logs.
                       If None is passed the web server truly gets started.
        """
        useSharedLib = webstuff.shared_library() is not None
        exe = sys.argv[0] if useSharedLib else webstuff.server_exe()

        cwdBackup = os.getcwd()
        if useSharedLib:
            # we need to pass the filenames in a OS dependent encoding, because
            # otherwise Popen is going to fail ...
            fsenc = sys.getfilesystemencoding()
            cmd = [exe,
                '-c', ensureUnicode(self._configFile).encode(fsenc),
                '-p', ensureUnicode(self._workDir   ).encode(fsenc)]
        else:
            cmd = [exe, '-c', _kConfigName, '-p', "."]
            os.chdir(self._workDir)

        if signal is None:
            self._logger.info("launching from %s ..." % os.getcwd())
        else:
            self._logger.info("signaling from %s ..." % os.getcwd())
            cmd = cmd + ["-s", signal]

        self._logger.info(str(cmd))
        try:
            if useSharedLib:
                self._logger.info("launching via shared library...")
                args = [sys.executable]
                if not hasattr(sys, "frozen"):
                    args += ["FrontEndLaunchpad.py"]
                args += ["--webserver"] + cmd + [kNginxMarkerArg]
                self._logger.info(str(args))
                subProc = Popen(args,
                    stdin=PIPE, stdout=PIPE, stderr=PIPE,
                    close_fds=(sys.platform=='darwin'))
                subProc.stdin.close()
                subProc.stdout.close()
                subProc.stderr.close()
                subProc.wait()
                exitcode = subProc.returncode
                self._logger.info("launcher exit code is %d" % exitcode)
            else:
                if _kIsWin:
                    sinf = subprocess.STARTUPINFO() # hide the console window(s)
                    sinf.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    proc = subprocess.Popen(cmd,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        cwd=None, startupinfo=sinf)
                    waitForExit = signal is not None
                else:
                    # avoid OpenSSL configuration pickup from the build folder
                    # path, this does not work under Windows somehow (causes
                    # exit code 1)
                    env2 = os.environ.copy()
                    env2[_kOpenSSLConfEnvVar] = ""
                    proc = subprocess.Popen(cmd,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        cwd=None, env=env2)
                    waitForExit = True
                    # NOTE: this block someday can go away if we decide never
                    #       to return to a separate server executable under OSX
                    #       due to the application firewall giving us grief ...
                if waitForExit:
                    for ln in proc.stdout:
                        self._logger.info(">>> " + ln.rstrip())
                    exitcode = proc.wait()
                    self._logger.info("exitcode is %d" % exitcode)
                else:
                    # Nginx's master process does not return under Windows,
                    # hence we wait for a very small period of time (just in
                    # case something really fundamental is broken) and then
                    # assume that the launch was somewhat successful ...
                    pollEnd = time.time() + 1
                    while True:
                        exitcode = proc.poll()
                        if exitcode is not None:
                            break
                        if time.time() > pollEnd:
                            exitcode = 0
                            break
                        time.sleep(.1)
            if self._checkExitcode(exitcode) and signal is None:
                self._enableLogRotater([self._accessLogFile, self._errorLogFile])
                return True
        except:
            self._logger.error("process launch failed: %s" % sys.exc_info()[1])
            self._logger.error(traceback.format_exc())
        finally:
            os.chdir(cwdBackup)

        return False


    ###########################################################
    def _checkExitcode(self, exitcode):
        """ Checks an exit code for a crash, if we find one and haven't seen
        another one yet we log material which might help us determining the
        source of the crash.

        @param exitcode  The exit code to examine.
        @return          True if the exit code indicates a successful server
                         launch.
        """
        crashed = False
        if _kIsWin:
            crashed = -1073741819 == exitcode
        else:
            crashed = -11 == exitcode or -10 == exitcode
        if not crashed:
            return 0 == exitcode

        self._logger.warn("exit code indicates a crash, collecting data...")
        cfgFile = os.path.join(self._workDir, _kConfigName)
        try:
            h = open(cfgFile)
            cfg = h.read()
            self._logger.info("config file content: %s" % ensureUtf8(cfg))
        except:
            self._logger.error("error reading config file %s (%s)" %
                               (cfgFile, sys.exc_info()[1]))
        finally:
            try: h.close()
            except: pass
        return False


    ###########################################################
    def _stopServer(self):
        """ Stops the currently running web server. As a matter of fact it
        actually it tries to kill every web server process out there, no matter
        if it belongs to the current instance or not.
        """
        self._enableLogRotater(None)
        return killWebServerProcesses(self._logger)


    ###########################################################
    def _verifyServer(self, retries=0, retryDelay=1):
        """ Checks if the web server is fully functioning, and also that it is
        actually ours (by using the current credentials and hitting something
        well known).

        @param  retries     Number of attempts.
        @param  retryDelay  Delay in seconds between retries.
        @return             True if a port seems to be open.
        """
        self._verified = False
        if 0 < retries:
            self._logger.info("verifying server...")
        while True:
            hc = HttpClient(5, ProblemLogger(self._logger, {}))
            status, uuid, _ = hc.get("http://localhost:%d/ping" % self._port)
            if status is None:
                self._logger.error("server at port %d not up (%s)" %
                                   (self._port, uuid))
                if 0 < retries:
                    retries -= 1
                    time.sleep(retryDelay)
                    continue
                return False
            # TODO: we actually should do HTTPS if we have SSL turned on,
            #       however by checking for 301 we do verify that the
            #       redirection to HTTPS works, so for now it's acceptable
            if not self._secure and status == 200 and uuid == self._instance:
                self._verified = True
                return True
            if self._secure and status == 301 and uuid:
                self._verified = True
                return True
            self._logger.error("instance mismatch, status=%d, uuid='%s'" %
                               (status, uuid))
            return False


    ###########################################################
    def _idle(self, seconds):
        """ Waits. And much more, this is the spot where all kinds of other
        things (port opening, command queue handling, etc) come to life.

        @param seconds  Number of seconds to 'idle'.
        @param force    True to idle for sure, ignoring the restart flag.
        @return         False if the shutdown signal has been received.
        """
        self._logger.debug("idle for %d seconds..." % seconds)
        stopAt = time.time() + seconds
        while True:
            self.status()
            now = time.time()
            if now > stopAt:
                break
            self._backendPing(now)
            self._processCmdQ()
            if self._shutdown:
                self._logger.info("shutdown detected")
                return False
            self.status()  # because we might (not) have a port opener now
            if self._portOpener is not None:
                self._portOpener.run(self._port, self._workDir)
            if self._reconfigure:
                break
            time.sleep(.1)
        return True


    ###########################################################
    def _backendPing(self, now = time.time()):
        """ Sends a message to the back-end to indicate that this process is
        still functioning, at least on a level where we can process messages
        send to us.

        @param now  Current time.
        """
        if self._msgQ is None:
            return
        if now > self._nextBEPing:
            self._msgQ.put([MessageIds.msgIdWebServerPing])
            self._nextBEPing = now + _kBackendPingSecs


    ###########################################################
    def setPort(self, port):
        """ Sets the port the web server should use. Causes a restart, even if
        the port didn't change.

        @param port  The (new) port to use. -1 to disable the server.
        """
        self._logger.info("port changed from %d to %d" % (self._port, port))
        self._port = port
        self.reconfigure()


    ###########################################################
    def getPort(self):
        """ Returns the currently used port.

        @return  The port the web server is supposed to use. Or -1 if the web
                 server is turned off.
        """
        return self._port


    ###########################################################
    def setAuth(self, auth):
        """ Sets authentication information. The type gets detected by parsing
        the expression, so we can automatically distinguish between the basic
        and the digest type.

        @param auth The auth expression or None to use no authentication.
        """
        self._logger.info("authentication changed")
        self._auth = auth
        self.reconfigure()


    ###########################################################
    def _enablePortOpener(self, enabled):
        """ Turns the port opener on or off. The opener runs in parallel and
            tries to follow the bouncing ball or the web server and its
            instances going up and down on different ports respectively.

        @param enabled  True if the port opening should be running. False
                        to turn it off (this will also close already opened
                        ports in the nearby router).
        """
        if enabled:
            if self._portOpener is None:
                self._portOpener = PortOpener(_kPortOpenerCheckURL,
                                              self._logger,
                                              _kPortCheckTimeout,
                                              _kPortCheckSecs)
                self._logger.info("port opener enabled")
        else:
            if self._portOpener is not None:
                self._portOpener.run(-1, self._workDir)
                self._portOpener = None
                self._logger.info("port opener disabled")


    ###########################################################
    def _enableLogRotater(self, logs):
        """ Enables or disables the log rotater. This is is called in parallel
        with a web server instance's lifetime.

        @param logs  The list of log files to watch and rotate if needed. None
                     does turn off the rotater.
        """
        if logs is not None:
            if self._logRotater is None:
                self._logRotater = LogRotater(
                    logs, _kMaxLogSize, _kMaxLogFiles, self)
        else:
            self._logRotater = None


    ###########################################################
    def _handleMessage(self, msg):
        """ Message dispatcher.

        @param msg  The IPC message just received.
        """
        msgId = msg[0]
        if msgId == MessageIds.msgIdQuit or \
           msgId == MessageIds.msgIdQuitWithResponse:
            self._logger.info("got shutdown message")
            self._shutdown = True
        elif msgId == MessageIds.msgIdWebServerSetPort:
            self.setPort(int(msg[1]))
        elif msgId == MessageIds.msgIdWebServerEnablePortOpener:
            self._enablePortOpener(bool(msg[1]))
        elif msgId == MessageIds.msgIdWebServerSetAuth:
            self.setAuth(msg[1])
        elif msgId == MessageIds.msgIdSetDebugConfig:
            self._debugLogManager.SetLogConfig(msg[1])
        elif msgId == MessageIds.msgIdWsgiPortChanged:
            self._setCameraPort(msg[1], msg[2])
        else:
            self._logger.error("unknown message ID %d" % msgId)
        return

    ###########################################################
    def _softRestart(self):
        self._logger.info("Reconfiguring web server")
        self._newConfig()
        self.startServer("reload")

    ###########################################################
    def _setCameraPort(self, camLocation, wsgiPort):
        needRestart = False
        if wsgiPort is None:
            if camLocation in self._cameraLocations:
                del self._cameraLocations[camLocation]
                needRestart = True
        else:
            if not camLocation in self._cameraLocations or \
                self._cameraLocations[camLocation] != wsgiPort:
                self._cameraLocations[camLocation] = wsgiPort
                needRestart = True

        if needRestart and self.turnedOn():
            self._softRestart()

    ###########################################################
    def _processCmdQ(self):
        """ Command queue (IPC messaging) polling.
        """
        if self._cmdQ is not None:
            limit = 128 # avoid hot looping
            while limit > 0 and not self._cmdQ.empty():
                msg = self._cmdQ.get(block=False)
                self._handleMessage(msg)
                limit -= 1


    ###########################################################
    def newServer(self):
        """ Build the whole next server instance.

        @return False if things didn't work out.
        """
        return self._newWorkDir() and \
               self._newConfig () and \
               self.startServer() and \
               self._verifyServer(5)


    ###########################################################
    def deleteServer(self):
        """ Stops the server and removes its work directory.
        """
        self._stopServer()
        self._delWorkDir()


    ###########################################################
    def run(self):
        """ The main loop of the process.
        """
        try:
            # main retry loop, to attempt starting the server...
            while not self._shutdown:
                # clear the trigger flag for reconfiguration
                self._reconfigure = False
                # retry delay default is long, we do only occasionally come back
                # and see if the server might be able to start again
                retryDelay = _kRetryStartSecs
                # turn off everything first and clean out old things, either
                # because the server is off anyway or to make sure the
                # former instance is really gone ...
                self.deleteServer()
                on = self.turnedOn()
                self._logger.info("server is %s" % ("ON" if on else "OFF"))
                if (on and self.newServer()) or not on:
                    retryDelay = _kRetrySecs
                    doIdle = True
                else:
                    doIdle = False
                # main idle loop if things are going well, meaning web server
                # is up and running or turned off ...
                while doIdle:
                    if not self._idle(_kVerifySecs):
                        # shutdown, we're done
                        self.deleteServer()
                        return
                    # reconfiguration request?
                    if self._reconfigure:
                        break
                    # run log rotation here
                    if self._logRotater is not None:
                        self._logRotater.run()
                    # if the server is running we have to check it now
                    if self.turnedOn():
                        if not self._verifyServer():
                            self._logger.info("server verification failed")
                            # restart, but go with the shorter delay to
                            # avoid hot-looping in cases where the first
                            # verification above worked, but a secondary
                            # always fails...
                            doIdle = False
                # don't retry right away, we need a good portion of idle time;
                # usually things don't fix itself, so it's mostly the user who
                # changes her settings to bring things back to life...
                if not self._reconfigure and not self._idle(retryDelay):
                    # got shutdown, so we're out
                    return
                self._logger.info("going to (re)start server...")
        except:
            self._logger.critical(traceback.format_exc())
        finally:
            # some cleanup
            try:
                self.deleteServer()
            except:
                self._logger.error("final server cleanup failed (%s)" %
                                   sys.exc_info()[1])
            self._enablePortOpener(False)
            self.deleteStatusFile()


###############################################################################
def make_auth(user, passw, realm=None):
    """ Creates an authentication expression which is then used to configure
    the web server.

    @param user   The user name.
    @param pass   The password.
    @param realm  The realm for digest authentication. None to create an
                  expression for basic auth.
    @return       The expression, single line string.
    """
    # user names can contain a ':', which then has to to be escaped into a '::'
    esc = lambda x: x.replace(':', '::')
    if realm is not None:
        ldg = lambda x: hashlib.md5(':'.join(x)).hexdigest()
        return "%s:%s:%s" % (esc(user), esc(realm), ldg((user, realm, passw)))
    else:
        md = hashlib.sha1()
        # TODO: non-ASCII passwords trouble, but there's no official rule either
        md.update(passw)
        return "%s:{SHA}%s" % (esc(user), base64.b64encode(md.digest()))


###############################################################################
def user_from_auth(auth):
    """ Gets the user name from an auth expression.

    @param auth  The auth expression. Either digest or basic.
    @return      The user name or None if parsing failed.
    """
    c = len(auth)
    if 0 == c:
        return ""
    i = 0
    c -= 1
    # we have to "unescape" '::' expressions back into ':', this is done by a
    # look-ahead or in other words "unescape all '::' until you find a truly
    # single ':', that's the end of the user name"
    while i <= c:
        i = auth.find(":", i)
        if -1 == i:
            return ""
        if i < c and ':' == auth[i + 1]:
            i += 2
            continue
        break
    if i > c:
        return ""
    auth = auth[0:i]
    return auth.replace('::', ':')


###############################################################################
def is_basic_auth(auth):
    """ Checks if an auth expression is of the basic type.

    @param auth  the auth expression.
    @return      True if this is an expression used for basic authentication or
                 False if it is something else (digest, if positively thought).
    """
    return auth.find(':{SHA}') == (len(auth) - 6 - 28) # FIXME: can be cheated


###############################################################################
class PortOpenerState:
    """ State definitions for the opener. Things are not trivial, so we keep the
    different areas of logic well separated. Notice that in almost any state the
    deactivation or reconfiguration of the web server can also lead to a
    transition. Different states also have different timer values, meaning the
    delay when they will consider to do any new action. Again, web serve
    changes must cause an immediate reaction for obvious reasons. """

    """ Initial state, web server is turned off.
    """
    WEBSERVER_OFF = 0
    """ Web server is set to be running, but we haven't verified yet that it
    truly is and able to respond to requests.
    """
    WEBSERVER_PROBING = 1
    """ Web server confirmed to be running, but we don't have a port opened for
    it yet or weren't able to during the last run (but try again).
    """
    WEBSERVER_ON = 2
    """ XNAT port has been opened successfully and connectivty has been
    confirmed, from there it's only about occassionally probing it.
    """
    XNAT_ACTIVE = 3
    """ Tunnel been opened successfully and connectivty has been confirmed, we
    will confirm this again occassionally and also try to go back to a NAT port
    if possible.
    """
    TUNNEL_ACTIVE = 4


###############################################################################
def portOpenerStateToStr(state):
    """ Takes a port opener state number and returns a string presentation for
        it, mainly for logging purposes.
    """
    return ["WEBSERVER_OFF",
            "WEBSERVER_PROBING",
            "WEBSERVER_ON",
            "XNAT_ACTIVE",
            "TUNNEL_ACTIVE"][state]


###############################################################################
class PortOpener:
    """ Cares about opening the associated web server's port to the public. This
    can either be done via talking to the IGD directly or using a service to
    route traffic from an outside point-of-entry back to the local system.
    Periodic verification of the port being reachable is also performed, and
    reacted upon if this step fails, meaning attempts for reopening.

    TODO: this is not the prettiest approach, since two opening solutions got
          melted together, could have been much more modular; for now it's good,
          a unit test case ensures that the conditional logic works ...
    """
    DELAY_SHORT  = 1    # short delay (to prevent hot looping)
    DELAY_MEDIUM = 30   # medium delay for relatively quick retries.
    DELAY_LONG   = 3600 # long delay, e.g. for hopeless cases (port n/a etc)

    ###########################################################
    def __init__(self, checkURL, logger, timeout=10, chkIntvl = 60):
        """ Constructor.

        @param checkURL  The URL to an externaly hosted (PHP) script which
                         checks if a port is reachable from the outside.
        @param logger    The logger instance to use.
        @param timeout   General timeout, e.g. for opening a NAT port.
        @param chkIntvl  How often to check if a port is (still) open.
        """
        self._localPort     = -1   # the former web server port we dealt with
        self._remotePort    = -1   # the remote port, either local or tunnel
        self._workDir       = None # the (current) web server work directory
        self._remoteIP      = None # the remote IP (local only)
        self._remoteAddress = None # can be the tunnel host or the local IP
        self._xnatProtocol  = XNAT.PROTOCOL_UPNP_NATPMP # favorite XNAT protocol
        self._xnatTTL       = 24 * 3600 # TTL of a port mapping (1 day for now)
        self._checkURL      = checkURL
        self._timeout       = timeout
        self._logger        = logger
        self._reResult      = re.compile(r"^([A-Z]+) (.*)$", re.M)
        def now(): return time.time()
        self._now      = now      # for time mocking (mainly in test cases)
        self._nextRun  = 0        # run right away, no matter what the time
        self._chkIntvl = chkIntvl
        self._state = PortOpenerState.WEBSERVER_OFF


    ###########################################################
    def _schedule(self, secs):
        """ Schedules the next time the port opening logic should run.

        @param secs  Number of seconds from now when the next run should happen.
                     Activity can happen sooner though, e.g. if a shutdown is
                     happening.
        """
        if secs is None:
            secs = self._chkIntvl
        self._nextRun = self._now() + secs
        if 0 == secs:
            self._logger.debug("scheduled for now")
            self.run(self._localPort, self._workDir)
        else:
            self._logger.debug("scheduled in %d seconds" % secs)


    ###########################################################
    def _setState(self, state):
        """ Sets the new state of the opener.
        """
        self._logger.info("transition from state %s to %s" %
                          (portOpenerStateToStr(self._state),
                           portOpenerStateToStr(state)))
        self._state = state


    ###########################################################
    def run(self, webPort, workDir):
        """ To run a cycle of the port opener. Execution should be fairly quick,
        but can easily be dozens of seconds if lots of things need to be done
        and the participating parties are either slow responders or are n/a in
        general (and we then have to wait for timeouts).

        @param webPort  The port of the web server to open up.
        @param workDir  The current web server work directory.
        """
        # we don't have well-defined events actually to react on, so we need
        # to make our own triggers. One is the change of the associated web
        # server, which will always cause execution, the other the timer a state
        # has recently set to be called back at a certain point in time.
        webServerChanged = self._localPort != webPort
        if self._now() < self._nextRun and not webServerChanged:
            return
        # web server changes must be acknowledged by the different states, so
        # we do keep the new local port, and hence will be able to detect any
        # new change on the next run
        self._localPort = webPort
        # for this round we need the work directory
        self._workDir = workDir
        # from here on the different states decide what's going to happen next
        if PortOpenerState.WEBSERVER_OFF == self._state:
            if not webServerChanged:
                # no need to schedule a timer, only a web server change matters
                return
            if self._localCheck(self._localPort):
                self._setState(PortOpenerState.WEBSERVER_ON)
                self._schedule(0)
                return
            else:
                # web server is not operational yet, so we're going to try again
                self._setState(PortOpenerState.WEBSERVER_PROBING)
                self._schedule(1)
                return
        elif PortOpenerState.WEBSERVER_PROBING == self._state:
            # back to the roots if the web server got turned off
            if -1 == self._localPort:
                self._setState(PortOpenerState.WEBSERVER_OFF)
                return
            # if the web server's port has changed in the meanwhile then it does
            # not matter, since we're already in the right state to deal with
            # that kind of situation
            if self._localCheck(self._localPort):
                self._setState(PortOpenerState.WEBSERVER_ON)
                self._schedule(0)
                return
            else:
                # web server is still not operational yet, hence try again
                # NOTE: we could bail out if this unavailability goes on for
                #       too long, but for now just keep going aggressively
                self._schedule(1)
                return
        elif PortOpenerState.WEBSERVER_ON == self._state:
            # if the web server got turned off then there's little to do here
            if -1 == self._localPort:
                self._setState(PortOpenerState.WEBSERVER_OFF)
                return
            # now if the web server port changed we need to go back and probe
            if webServerChanged:
                self._setState(PortOpenerState.WEBSERVER_PROBING)
                self._schedule(0)
                return
            # try opening the tunnel over XNAT first
            succ, rmip, rmpt = self._openXNATVerify(
                self._localPort, self._localPort)
            if succ:
                # we're good with XNAT, store the information
                self._remoteIP      = rmip
                self._remoteAddress = rmip
                self._remotePort    = rmpt
                self._setState(PortOpenerState.XNAT_ACTIVE)
                self._publish()
                self._schedule(None)
                return
            # how about a tunnel?
            succ, rmhs, rmpt = self._openTunnelVerify()
            if succ:
                self._remoteIP      = None
                self._remoteAddress = rmhs
                self._remotePort    = rmpt
                self._publish()
                self._setState(PortOpenerState.TUNNEL_ACTIVE)
                self._publish()
                self._schedule(None)
                return
            # just in case the web server has issues we should check for it and
            # if there is trouble go back into probing mode ..
            if not self._localCheck(self._localPort):
                self._setState(PortOpenerState.WEBSERVER_PROBING)
                self._schedule(PortOpener.DELAY_SHORT)
                return
            # try all of this again in one hour, we are more counting on
            # the tunnel service to become available again, rather than XNAT to
            # suddendly start working, but you never know what could happen ...
            #
            # FIXME: tunnel is not working right now, so we delay for a longer
            #        time, instead of going wild/loopy on the XNAT side - once
            #        the tunnel functionality is in set this to DELAY_MEDIUM
            #
            self._schedule(PortOpener.DELAY_LONG)
            return
        elif PortOpenerState.XNAT_ACTIVE == self._state:
            # any change in the webserver requires some action here
            if webServerChanged:
                self._closeXNAT(self._remotePort)
                self._remotePort    = -1
                self._remoteIP      = None
                self._remoteAddress = None
                # depending if the server's on or off go different ways ...
                if -1 == self._localPort:
                    self._setState(PortOpenerState.WEBSERVER_OFF)
                else:
                    self._setState(PortOpenerState.WEBSERVER_PROBING)
                    self._schedule(0)
                self._publish()
                return
            # make sure that the port can be reached from the outside
            if not self._portCheck(self._remotePort, self._remoteAddress):
                self._closeXNAT(self._remotePort)
                self._remotePort    = -1
                self._remoteIP      = None
                self._remoteAddress = None
                # since we cannot be sure if the web server is still working,
                # we better go back and check that one first
                self._setState(PortOpenerState.WEBSERVER_PROBING)
                self._schedule(0)
                return
            # all good, schedule us again for another gentle check
            self._schedule(self._chkIntvl)
            return
        elif PortOpenerState.TUNNEL_ACTIVE == self._state:
            # close the tunnel if the web server changed (or got turned off)
            if webServerChanged:
                self._closeTunnel()
                self._remotePort    = -1
                self._remoteAddress = None
                if -1 == self._localPort:
                    self._setState(PortOpenerState.WEBSERVER_OFF)
                else:
                    self._setState(PortOpenerState.WEBSERVER_PROBING)
                    self._schedule(0)
                self._publish()
                return
            # check tunnel connectivity
            if not self._portCheck(self._remotePort, self._remoteAddress):
                self._closeTunnel()
                self._remotePort    = -1
                self._remoteAddress = None
                # same as with XNAT above, go back and verify  that the web
                # server's actually working
                self._setState(PortOpenerState.WEBSERVER_PROBING)
                self._schedule(0)
                return
            # since we're optimists we dare and see if we can fall back to XNAT
            # again, since it is just cheaper
            succ, rmip, rmpt = self._openXNATVerify(
                self._localPort, self._localPort)
            if succ:
                # great to be back with XNAT, close the tunnel then
                self._closeTunnel()
                self._remoteIP      = rmip
                self._remoteAddress = rmip
                self._remotePort    = rmpt
                self._setState(PortOpenerState.XNAT_ACTIVE)
                self._publish()
                self._schedule(None)
                return
            # stick with the tunnel and come back in a while to re-verify
            self._schedule(self._chkIntvl)
            return
        else:
            # impossible, impossible I'm telling you
            self._logger.critical("unknown state %d ?!?" % self._state)


    ###########################################################
    def _publish(self):
        """ TODO: tell the DNS server the new remote IP, this might not be
        necessary with the ngrok tunnel solution, but we'll see; if the DNS
        name changed, e.g through ngrok or (less likely) via webserver
        configuration (user name?) then we'd need to do that too.
        """
        pass


    ###########################################################
    def _registerDNS(self):
        """ TODO: registering the new remote IP and port with a DNS service.

        @return  True if registration was successfull, followed by the DNS
                 name or host name respectively.
        """
        self._logger.debug("DNS registration not implemented yet")
        # <- success (True|False), remote host name
        return False, None


    ###########################################################
    def _localCheck(self, port):
        """ Does a quick socket check to see if the web server is running.

        @param port  The port to try to connect to.
        @return      True if a connection got established successfully.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except:
            self._logger.info("port %d seems to be closed: %s" %
                              (port, sys.exc_info()[1]))
            return False


    ###########################################################
    def _openTunnelVerify(self):
        """ Opens the tunnel and verifies if it is actually reachable.

        @return  True on success, followed by the established tunnel's host
                 name and port.
        """
        succ, rmhs, rmpt = self._openTunnel()
        if succ and not self._portCheck(rmpt, rmhs):
            self._logger.error("just opened tunnel not reachable")
            self._closeTunnel()
            return False, None, -1
        return succ, rmhs, rmpt


    ###########################################################
    def _openTunnel(self):
        """ Opens a tunnel connection. This is a remote endpoint which can be
        reached from everywhere and forwards all of the HTTP(S) traffic to our
        locally running server.

        @return  True on success, followed by the established tunnel's host
                 name and port.
        """
        self._logger.info("tunnel opening not implemented yet")
        # <- success (True|False), remote host, remote port
        # assuming that we use the ngrok solution, which would open a tunnel
        # from the remote spot to local IP (where the webserver is running)
        return False, None, -1


    ###########################################################
    def _closeTunnel(self):
        """ Closes the tunnel connection.

        @return  True if the tunnel teardown was successful.
        """
        self._logger.info("closing tunnel...")
        return False


    ###########################################################
    def _openXNATVerify(self, localPort, remotePort):
        """ Tries to open an externally reachable port in the router/gateway
        and verifies if it is really working.

        @param localPort   Port of the (locally running) web server.
        @param remotePort  Demanded remote port (to be opened in the router).
        @return            True if it all worked, followed by the remote IP and
                    port.
        """
        succ, rmip, rmpt = self._openXNAT(localPort, remotePort)
        if succ and not self._portCheck(rmpt, rmip):
            self._logger.error("just opened XNAT port is not reachable")
            self._closeXNAT(rmpt)
            return False, None, -1
        return succ, rmip, rmpt


    ###########################################################
    def _openXNAT(self, localPort, remotePort):
        """ Tries to open an externally reachable port in the router/gateway.

        @param localPort   Port of the (locally running) web server.
        @param remotePort  Demanded remote port (to be opened in the router).
        @return            True if opening worked, followed by the remote IP
                           and port.
        """
        xnat = XNAT(self._timeout, self._logger, self._workDir)
        while True:
            self._logger.info("trying to open port %d using protocol %d..." %
                              (remotePort, self._xnatProtocol))
            xres = xnat.open(localPort, remotePort, self._xnatTTL,
                             self._xnatProtocol)
            xlog = xres.get(XNAT.RSP_LOGS, None)
            if xlog is not None:
                for ln in str(xlog).splitlines():
                    self._logger.info("XNATLOG [%s]" % ln)
            if xres[XNAT.RSP_RESULT] != XNAT.RES_SUCCESS:
                self._logger.warn("opening failed (%s)" % xres[XNAT.RSP_ERROR])
                if self._xnatProtocol == XNAT.PROTOCOL_NATPMP:
                    self._xnatProtocol = XNAT.PROTOCOL_UPNP_NATPMP
                    continue
                if self._xnatProtocol == XNAT.PROTOCOL_UPNP:
                    self._xnatProtocol = XNAT.PROTOCOL_NATPMP_UPNP
                    continue
                return False, None, -1
            self._xnatProtocol = xres[XNAT.RSP_PROTOCOL]
            remoteIP           = xres[XNAT.RSP_REMOTEIP]
            remotePort         = xres[XNAT.RSP_REMOTEPORT]
            self._logger.info("protocol %d successfully opened %s:%d" %
                              (self._xnatProtocol, remoteIP, remotePort))
            if self._isPrivateIP(remoteIP):
                self._logger.warn("IP is private, potentially double-NATed")
                # we keep going, maybe it's still going to work out for people
                # who have a proper and manual outer port mapping ...
            return True, remoteIP, remotePort


    ###########################################################
    def _closeXNAT(self, remotePort):
        """ Closes the formely opened port in the router.

        @param remotePort  The remote port to close.
        @return            True if the port close attempt was sucessful. Not
                           being able to close (False) is not that dramatic
                           since reasons for it might be way beyond our
                           possibilities to fix.
        """
        xnat = XNAT(self._timeout, self._logger, self._workDir)
        self._logger.info("closing remote port %d..." % remotePort)
        xres = xnat.close(remotePort, self._xnatProtocol)
        if xres[XNAT.RSP_RESULT] != XNAT.RES_SUCCESS:
            self._logger.info("closing failed (%s)" % xres[XNAT.RSP_ERROR])
            return False
        return True


    ###########################################################
    def _getCheckURL(self, url):
        """ Hits the check URL, the externally hosted (PHP) script.

        @param url  The complete check URL containing all of the parameters
                    for the script for an attempt to connect back to us.
        @return     The script's result data, which is a Python dictionary,
                    similar concept as JSON, or None if an error occurred.
        """
        timeout = self._timeout + _kPortOpenerCheckExtraSecs
        hc = HttpClient(timeout, self._logger)
        status, doc, _ = hc.get(url)
        if httplib.OK == status:
            return doc
        if status:
            self._logger.error("check URL status %d" % status)
        return None


    ###########################################################
    def _portCheck(self, remotePort, remoteAddress=None):
        """ Creates the check URL, hits it and parses its response.

        @param remotePort  The remote port to check.
        @param remotePort  The remote address to check (can be either an IP
                           or a host name.
        @return            True if the port was found to be open. False if
                           closed or if the check URL itself has an issue or is
                           n/a.
        """
        url = "%s?timeout=%d&port=%d" % \
            (self._checkURL, 1000 * self._timeout, remotePort)
        if remoteAddress is not None:
            url += "&host=%s" % remoteAddress
        self._logger.info("checking port via %s ..." % url)
        data = self._getCheckURL(url)
        if data is None:
            # NOTE: this is not controversial, although it might seem so: if the
            #       port check script is n/a then we shouldn't jump to the
            #       conclusion that the port is not reachable, because otherwise
            #       a simple problem with the hosted script would start all of
            #       clients to start open/verify/close looping for nothing ...
            # NOTE: we trust the port opening script to always have sufficient
            #       connectivity - if this is not true meaning itself produces
            #       false negatives then we'd suffer from the same effect ...
            self._logger.warn("port check failure, taking no action");
            return False
        m = self._reResult.match(data)
        if m is None:
            self._logger.error("invalid response: %s" % data);
            return False
        res = m.group(1)
        if res == "OK":
            self._logger.info("port reported to be open: %s" % m.group(2))
            return True
        elif res == "ERROR":
            self._logger.warn("port cannot be reached: %s" % m.group(2))
        else:
            self._logger.error("invalid result '%s'" % res);
        return False


    ###########################################################
    def _isPrivateIP(self, ip):
        """ Checks of an IP address is of private nature.

        @param ip  The IPv4 address to examine.
        @return    True if this address is not publicly routable.
        """
        # TODO: this should become a utility
        for pfx in ["0.", "127.", "169.254.", "192.168."]:
            if ip.startswith(pfx):
                return True
        for i in range(16, 31):
            if ip.startswith("172.%d." % i):
                return True
        return False


    ###########################################################
    def status(self, s):
        """ Adds status information about the port opener's current state.

        @param s  The status dictionary to add to.
        """
        s[kStatusKeyPortOpenerState] = portOpenerStateToStr(self._state)
        s[kStatusKeyRemotePort     ] = self._remotePort
        s[kStatusKeyRemoteAddress  ] = self._remoteAddress \
                             if self._remoteAddress is not None else ""

###############################################################################

class LogRotater:
    """ Takes care about tracking the log files of the web server and when
    limits are reached rotate them out, keeping a history of files of a certain
    depth. If the maximum of files have been reached the oldest ones get deleted
    (think about it as some kind of ring buffer). If files cannot be moved or
    deleted the rotater might attempt to restart the web server to prevent
    things from filling up, which could happen under Windows.
    """

    ###########################################################
    def __init__(self, logs, maxSize, maxFiles, webServer, checkIntvl = 30):
        """
        @param logs         List of log files to monitor and rotate.
        @param maxSize      The maximum size an active log file should be
                            allowed to have, before being rotated. It might
                            actually exceed this size since we only check now
                            and then.
        @param  maxFiles    Number of old/rotated files to keep (per log file).
        @param  webServer   The associated web server.
        @param  checkIntvl  How often to check the log files. In seconds.
        """
        self._logs = self._logs = {}
        for log in logs:
            self._logs[log] = 0
        self._maxSize = maxSize
        self._maxFiles = maxFiles
        self._webServer = webServer
        self._logger = webServer.logger()
        self._checkIntvl = checkIntvl
        self._nextRun = 0
        self._schedule()


    ###########################################################
    """ Get the current time.

    @return Time since epoch in seconds.
    """
    def _now(self):
        return time.time()


    ###########################################################
    """ Renames a file.

    @param old  Current file name/path.
    @param new  New file name/path.
    """
    def _rename(self, old, new):
        os.rename(old, new)


    ###########################################################
    """ Removes a file.

    @param path  The path of the file to remove.
    """
    def _remove(self, path):
        os.remove(path)


    ###########################################################
    def run(self):
        """ Gives the rotater the opportunity to run. """
        if self._now() < self._nextRun:
            return
        rotated = False
        for log in self._logs:
            if not os.path.exists(log) or not os.path.isfile(log):
                continue
            if self._maxSize <= os.path.getsize(log):
                rotated = True
                idx = self._logs[log]
                self._logger.info("rotating log %s [%d]..." % (log, idx))
                arc = "%s.%d" % (log, idx)
                try:
                    if os.path.exists(arc):
                        self._remove(arc)
                        self._logger.info("removed oldest file %s" % arc)
                except:
                    self._logger.error("cannot remove oldest file %s (%s)" %
                                       (arc, sys.exc_info()[1]))
                retries = 3
                while True:
                    try:
                        if os.path.exists(log):
                            self._rename(log, arc)
                        break
                    except:
                        err = sys.exc_info()[1]
                        retries -= 1
                        if 0 == retries:
                            self._logger.error(
                                "cannot rotate current log file %s to %s (%s)" %
                                (log, arc, err))
                            # better try and get rid of it, rather than filling
                            # up hard drive space indefinitely ...
                            try:
                                self._remove(log)
                            except:
                                self._logger.error("cannot remove either (%s)" %
                                    sys.exc_info()[1])
                                # if the log file gets too big we need to
                                # relaunch the server, there is no other way
                                maxLog = self._maxFiles * self._maxSize
                                if os.path.exists(log) and \
                                   os.path.getsize(log) > maxLog:
                                    self._logger.error("emergency relaunch...")
                                    self._webServer.reconfigure()
                            break;
                        time.sleep(.1)
                self._logs[log] = (idx + 1) % self._maxFiles
        if rotated:
            self._webServer.startServer("reload")
        self._schedule()


    ###########################################################
    def _schedule(self):
        """ Schedules the next time the rotater should execute. """
        self._nextRun = self._now() + self._checkIntvl
