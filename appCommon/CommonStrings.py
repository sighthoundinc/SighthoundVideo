#!/usr/bin/env python
# -*- coding: utf8 -*-

#*****************************************************************************
#
# CommonStrings.py
#    Contains variables for strings that are commonly used or changed
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
# https://github.com/sighthoundinc/SighthoundVideo
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



import os
import os.path
import urllib
import operator

# Helper that we use to make file:/// URLs, since those need to be absolute
# and refer to the current working directory.
def __fileUrlHelper(url):
    return url % {
        'cwd': urllib.quote(os.getcwdu().replace(os.path.sep, '/').lstrip('/'),
                            '/:')
    }


def OB_ASID(a): return a

# Info about Sighthound, the creator of the app...
kSighthoundCompanyName      = "Sighthound, Inc."
kSighthoundWebsite          = "www.sighthound.com"
kSighthoundWebsiteBaseUrl   = "https://%s/" % kSighthoundWebsite
kOpenSourceVersion=True


# Info about whatever company is shipping the app (the OEM)...
kOemName         = kSighthoundCompanyName
kOemWebsite      = kSighthoundWebsite



# Names of the apps...
kAppName          = "Sighthound Video"
kExeName          = "Sighthound Video"  # Limit to 16 chars for Mac
kBackendExeName   = "Sighthound Agent"
kWebcamExeName    = "Sighthound USB"
kWebserverExeName = "Sighthound Web"
kXNATExeName      = "SighthoundXNAT"

# Backend command line argument: identifies an agent/backend process.
kBackendMarkerArg = "--sh-2e4fce7e"
# Backend command line argument: reserved/placeholder.
kReservedMarkerArg = "--sh-e977efba"
# Backend command line argument: reserved/placeholder used by the service.
kReservedMarkerSvcArg = "--sh-baef77e9"
# Backend command line argument: nginx processes replace kBackendMarkerArg to
# this value, so they can be identified as such (and not as backends).
kNginxMarkerArg = "--sh-dc95b4d2"
# Backend command line argument: XNAT processes identify themselves by replacing
# the kBackendMarkerArg with this value.
kXNATMarkerArg = "--sh-1194711f"

# Test non-ASCII data paths.  This includes Chinese wide characters
# in encoded and decoded forms, precomposed, and decomposed Unicode chars.
#kAppName = u'維\u4ed6\u547dD Vi\u0301d\u00E9o'



# The app version...
kVersionString = "7.0.16"
# Gets appended to UI representation of version ... change from beta to release as needed
kVersionStringModifier = ""
kMajorVersionString = "7.0"

# Date when the release of the current major version happened.
kMajorVersionFirstReleaseDate = "03/23/2021"
# kMajorVersionFirstReleaseDate may be backdated -- keep the actual release date we show
kMajorVersionFirstReleaseDateDisplay = "03/23/2021"

# The API version...
kApiVersion = "1.1"


# These try to make the URLs below easier to customize if we have OEMs that
# have their own of any of these...
kStoreWebsite         = kSighthoundWebsite

_kDocumentationBaseUrl = "https://%s/app-help/" % kSighthoundWebsite
_kStoreBaseUrl         = _kDocumentationBaseUrl



kDocumentationIconUrl = "https://%s/favicon.ico" % kSighthoundWebsite
kDocumentationDescription = "View Online Reference Guide"

kOemUrl               = "http://%s/"            % kOemWebsite



kCopyrightMoreInfoUrl = "https://%s/opensource/" % kSighthoundWebsite   # (!!!) ALSO IN the EULA (.rtf and SLAResources.r)


kForumsUrl         = kSighthoundWebsiteBaseUrl + "forums"


kDocumentationUrl  = _kDocumentationBaseUrl + "reference-guide"
kSlowFpsUrl        = _kDocumentationBaseUrl + "low-frame-rate-warning"
kSlowProcessingUrl = _kDocumentationBaseUrl + "slow-processing-warning"
kCameraConfigUrl   = _kDocumentationBaseUrl + "camera-config"
kStorageDetailUrl  = _kDocumentationBaseUrl + "storage-detail"
kRemoteAccessUrl   = _kDocumentationBaseUrl + "remote-access"
kPushHelpUrl       = _kDocumentationBaseUrl + "mobile-notifications"
kIftttHelpUrl      = _kDocumentationBaseUrl + "ifttt"
kReleaseNotesUrl   = _kDocumentationBaseUrl + "release-notes"
kUpgradeFeaturesUrl = _kDocumentationBaseUrl + "upgrade-features"
kAboutAccountsUrl  = _kDocumentationBaseUrl + "about-accounts"
kCorruptDataUrl    = _kDocumentationBaseUrl + "corrupt-data"

# The following are managed by an apache redirect, not in drupal
kForgotPassUrl     = _kDocumentationBaseUrl + "forgot-password"
kCreateAccountUrl  = _kDocumentationBaseUrl + "create-account"
kBuyNewUrl     = _kStoreBaseUrl + "buy-new"
kBuyUpgradeUrl = _kStoreBaseUrl + "upgrade?sn=%s"
kRenewSupportUrl = _kStoreBaseUrl + "renew?sn=%s"
kDirectBuyBasic = _kStoreBaseUrl + "buy-basic?id=%s&mach=%s"
kDirectBuyPro = _kStoreBaseUrl + "buy-pro?id=%s&mach=%s"

kServicesHost = "licensing.sighthound.com"

kBugReportWebsite     = "vitamind.fogbugz.com"
kBugReportUrlSuffix = "/ScoutSubmit.asp"

kSupportEmail = "support@sighthound.com"

# Mac PLST strings
kBundleIdentifier  = "com.sighthound.sighthoundvideo"
kMinMacOSVersion   = "10.10"



# The name of the license agreement RTF (used in the build)...
kSoftwareLicenseAgreementRtf = "Sighthound Video SW License Agreement.rtf"
kSoftwareLicenseAgreementResource = "SLAResources.r"  # Also in FrontEnd.mk



# Copyright info...
kCopyrightYear = "2008-2021"
kCopyrightStr = (
    u"""© %s %s All rights reserved.\n\n"""
    u"""This product contains software whose copyright and """
    u"""IPR are owned by and licensed from x264, LLC\n"""
    u"""FFmpeg copyright © 2000-2021 Fabrice Bellard, et al. """
    u"""LIVE555 copyright © 1996-2021 Live Networks, Inc. """
    u"""Pthreads-win32 copyright © 1998 John E. Bossom and """
    u"""copyright © 1999, 2006 pthreads-win32 contributors. """
    u"""FreeType © 2006-2021 The FreeType Project.""") % (
    kCopyrightYear, kSighthoundCompanyName,
)
kCopyrightMoreInfoStr = "Click here for detailed copyright information."


# Log names
kFrontEndLogName = "%s.log" % (kAppName)



# The name of the folder where video files are stored.
kVideoFolder = "archive"

# This is the name of the license file stored in app data...
kLicenseFileName = "license.lic"

# This is the name of the license file (in frontEnd/licenses) that will be
# used if no other license is found...
# FIXME: obsolete, remove after all dependencies have been updated
kBuiltinLicenseFileName = "Builtin.lic"

# We store the TCP port that the NetworkMessageServer listens on in this file.
kPortFileName = "port"


# We use these to keep track of how we're storing rules...
kRuleDir = "rules"
kRuleExt = ".rule"
kQueryExt = ".query"
kBackupExt = ".backup"

# More backend store file names...
kPrefsFile = 'backEndPrefs'
kCamDbFile = 'camdb'
kObjDbFile = 'objdb2'
kClipDbFile = 'clipdb'
kResponseDbFile = 'responsedb'
kSQLiteDatabases = [kObjDbFile, kClipDbFile, kResponseDbFile]

# A special setting indicating that any camera will do.  Not necessarily
# human readable in the current locale...
kAnyCameraStr = "Any camera"


# Names of response types...
kCommandResponse = "CommandResponse"
kEmailResponse = "EmailResponse"
kRecordResponse = "RecordResponse"
kSoundResponse = "SoundResponse"
kFtpResponse = "FtpResponse"
kLocalExportResponse = "LocalExportResponse"
kPushResponse = "PushResponse"
kIftttResponse = "IftttResponse"
kWebhookResponse = "WebhookResponse"

# Various 'protocols' that the SendClipResponse knows about
kFtpProtocol = 'ftp'
kLocalExportProtocol = 'localExport'


# Various states of the camera...
kCameraUndefined = "undefined"
kCameraOn = "on"
kCameraOff = "off"
kCameraConnecting = "connecting"
kCameraFailed = "failed"


# We'll communicate this key between the back end and the front end to make
# sure that the back end and front end have matching versions...
# Note: because the obfuscated ID includes the build number, we are guaranteed
# to only match back ends that are from our build...
kMagicCommKey = OB_ASID("Open_Sesame")


# Associated with TestStream.py; the memory mapped file.
kTestLiveFileName = 'test'

# The header contains:
# 1 bytes: frame number % 10
# 4 bytes: height
# 4 bytes: width
# 1 byte: \n
kTestLiveHeaderSize = (1 + 4 + 4 + 1)


# This is the header for all but the test stream...
# The header contains:
# 9 bytes: frame number % 10^9
# 4 bytes: height
# 4 bytes: width
# 7 bytes: request FPS (format code %7.2f)
# 7 bytes: capture FPS (format code %7.2f)
# 1 byte: \n
kLiveHeaderSize = (9 + 4 + 4 + 7 + 7 + 1)

# A file signifiying that a database corruption occurred and the user should
# be notified as soon as possible.
kCorruptDbFileName = "err-corruptdb"

# DatabaseError message strings that signify a corrupt databse.
kCorruptDbErrorStrings = ["SQL logic error or missing database",
                          "database disk image is malformed",
                          "file is encrypted or is not a database",
                          "auxiliary database format error",
                          "bind or column index out of range" ]

# The default search rules.
kSearchViewDefaultRules = ['All objects', 'People', 'Vehicles', 'Animals', 'Unknown objects']
kBuiltInRules           = { "5.1" : ['All objects', 'People', 'Unknown objects'],
                               "6.0" : kSearchViewDefaultRules,
                               "current": kSearchViewDefaultRules,
                             }

# The suffix for inactive cameras.
kInactiveSuffix = ' (inactive)'

# Response config dictionary lookup for commands.
kCommandResponseLookup = 'command'


# The suffix for imported cameras.  Purposely contains characters in
# kInvalidPathChars so that we know it can't conflict with a real camera...
kImportSuffix = ' <imported>'

# A prettier way to display the above.  Note that once you replace the real
# suffix with this one, it could conflict with user named cameras (rare, but
# possible), so don't try to go in reverse...
kImportDisplaySuffix = ' (imported)'


# The default amount to record before the triggered event.
kDefaultPreRecord = 5

# The directory in which files pertaining to remote sessions are stored.
kRemoteFolder = "remote"

# Displayed in the results list while a search is ongoing.
kSearchingString = "Searching..."
kSearchingOnString = "Searching on %s..."

# Name of the web server directory. Below it the mostly transient web server
# directory structures spawn.
kWebDirName = "web"

# Environment variable to place the web server directory at an arbitrary spot.
kWebDirEnvVar = "SIGHTHOUND_WEBDIR"

# Web server status is reported into a file in the web directory initially and
# every time there is a change to the web server or the port opening. The state
# is stored as a simple pickled dictionary.
kStatusFile = "status"

# Web server status key: the status number, allows proper identification of
# different status sets or files respectively, without the need to rely on
# unreliable things like file time-stamps or deltas etc.
kStatusKeyNumber = "number"
# Web server status key: the port number the web server is supposed to use, or
# just -1 if it is turned off
kStatusKeyPort = "port"
# Web server status key: the instance identifier (integer) of the web server.
kStatusKeyInstance = "instance"
# Web server status key: flag if the web server is running and has been verified
# to be fully operational (True) or not (False).
kStatusKeyVerified = "verified"
# The SSL certificate identifier, i.e. the SHA-1 fingerprint of it.
kStatusKeyCertificateId = "certificateId"
# Web server status key: state of the port opener. Check for this key's existence
# to see whether the port opener is running or not. If latter then all of the
# remote information won't be in the status dictionary either.
kStatusKeyPortOpenerState = "portOpenerState"
# Web server status key: the remote port (-1 if not available)
kStatusKeyRemotePort = "remotePort"
# Web server status key: the remote address (host name or IP), or None if n/a.
kStatusKeyRemoteAddress = "remoteAddress"

# Free licenses are limited to resolutions smaller than this.
kMaxRecordSize = (640, 480)
# The default camera record size
kDefaultRecordSize = kMaxRecordSize
# If we're grabbing frames from a device that is configured to have a specific
# resolution outside the app (like IP cameras), then (0, 0) tells our logic to
# record at the resolution of the frames coming from said device.
kMatchSourceSize = (0, 0)
# The default camera audio recording checkbox value.
kDefaultRecordAudio = True

# The hostname the notification gateway.
# We are moving away from Pushwoosh and from Linode to AWS.  The old Linode server(s) are at the name
# push.sighthound.com; the new AWS server(s) are at push2.sighthound.com.  At some point we will also
# point push.sighthound.com at the AWS cluster.  There is also (sometimes) a push2.staging.sighthound.com
# running in the Engineering cluster.
kGatewayHost    = "push2.sighthound.com"
# The URL path for the notification gateway.
kGatewayPath = "/gateway.php"
# Timeout for talking to the notification gateway.
kGatewayTimeoutSecs = 20

# The gateway for routing IFTTT messages.
kIftttHost = "ifttt.sighthound.com"
# IFTTT path: where to send events to.
kIftttPathTrigger = "/ifttt.php"
# IFTTT path: to save the current state, i.e. camera and rule names.
kIftttPathState = "/ifttt.php/state"


kUploaderProxyHost = "updog.sighthoundvideo.com"
kUploaderProxyPath = "/fetch-url/problem-video"

# Users of old licenses must have updated by this point in time. The feature
# that uses this variable was disabled prior to (but enabled on) 06/15/2015.
kLegacyLicDropDeadDate = "06/15/2015"

# MemStore key: current license data (dictionary).
kMemStoreLicenseData = "license.data"
# MemStore key: login status (dictionary)
kMemStoreLicenseLoginStatus = "license.login.status"
# MemStore key: list of current licenses available (array of dictionaries)
kMemStoreLicenseList = "license.list"
# MemStore key: backend readiness (boolean).
kMemStoreBackendReady = "backend.ready"
# MemStore key: rule lock (boolean).
kMemStoreRulesLock = "rules.lock"

# Report level: informational message.
kReportLevelInfo = "info"
# Report level: some anomaly has happened.
kReportLevelError = "error"

# Login status: the account identifier. None if login hasn't happened yet.
kLoginStatusAccountId = "accountID"
# Login status: True if the current token got rejected or the actual login
# failed (if token is empty). We need this apart from the regular last
# error because the token might become invalid outside of a regular login call.
kLoginStatusFailed = "failed"
# Login status: the last user name (currently an e-mail address) used for a
# successful login. Useful to determine if there was every an account involved
# and also on clients to play back this string on a new password/login prompt.
kLoginStatusLastUser = "lastUser"
# Login status: the machine ID used for the last login (attempt).
kLoginStatusMachineId = "machineID"
# Login status: the (obfuscated) token.
kLoginStatusToken = "token"
# Prefix to distinguish local camera URIs from the rest
kLocalCameraPrefix = "device:"
def isLocalCamera(uri):
    if uri is None:
      return False
    return uri.startswith(kLocalCameraPrefix)

# Default string to use for email notifications
kDefaultNotificationSubject = (
    "%s alert" % (kAppName)
)

# always keep at least that much available on system drive
kMinFreeSysDriveSpaceMB = 1024

kThumbsSubfolder="thumbs"

# Mapping choice labels to settings in the model...
kTargetMapping = [
    ('anything', "Any object"),
    ('person', "People"),
    ('animal', "Animals"),
    ('object', "Unknown objects"),
    ('vehicle', "Vehicles"),
]
kTargetLabels = map(operator.itemgetter(1), kTargetMapping)
kTargetSettingToLabel = dict(kTargetMapping)
kTargetLabelToSetting = dict(map(operator.itemgetter(1, 0),
                                  kTargetMapping))
kExecAlertThreshold = os.getenv("SV_EXEC_ALERT_THRESHOLD", "0.2")
kSqlAlertThreshold = os.getenv("SV_SQL_ALERT_THRESHOLD", "2.0")
