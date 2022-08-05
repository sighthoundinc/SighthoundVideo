#! /usr/local/bin/python

#*****************************************************************************
#
# MessageIds.py
#     Definition of messages exchanged between various processes of SV
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


"""
## @file
Contains Message Ids for IPC communication.
"""

# Messages are delivered in a list with the first item being the message id
# and the following items being any additional parameters as specified here.

###############################################################
# General Messages

# Nothing
msgIdNone = 0

# No additional parameters
msgIdQuit = 10000

# Followed by a message list
msgIdQuitWithResponse = 10001

# Onvif devices had changed
msgIdUpdateOnvif = 10002

# UPNP devices had changed
msgIdUpdateUpnp = 10003

###############################################################
# XMLRPC Messages

# Followed by True or False indicating start success, plus the port numbers
# (primary and secondary, low priority) in a collection.
msgIdXMLRPCStarted = 11000


###############################################################
# Camera Management Messages

# Followed by a camLocation and camUri
msgIdCameraAdded = 12000

# Followed by origLocationName, camLocation, camUri and changeTime
msgIdCameraEdited = 12001

# Followed by a camera location, True/False to remove associated data
msgIdCameraDeleted = 12002

# Followed by a camera location
msgIdCameraEnabled = 12003
msgIdCameraDisabled = 12004
msgIdEnableLiveView = 12005
msgIdDisableLiveView = 12006

# Followed by a camera location, and optionally msNeeded
msgIdFlushVideo = 12007

# Followed by oldName, newName, changeTime, and optionally a delayed message
msgIdRenameCamera = 12008

# Followed by uri, forceTCP
msgIdCameraTestStart = 12010

# Followed by nothing
msgIdCameraTestStop = 12011

# Followd by cameraLocation, startSec, stopSec and bool quick
msgIdDeleteVideo = 12012

# Followed by isMajor
msgIdActiveCameraSearch = 12013

# Followed by a camera location, width, height, audio volume, fps
msgIdSetLiveViewParams = 12014

# Followed by True or False, width, height, fps
msgIdSetMmapParams = 12015

# Followed by uuid, selectedIp, username, password
msgIdSetOnvifSettings = 12017

# Followed by camera location, delaySeconds, pcap directory
msgIdPacketCaptureStart = 12018

# Followed by nothing
msgIdPacketCaptureStop = 12019

# Followed by an integer
msgIdPacketCaptureEnabled = 12020

# Followed by a return code as an integer, string to describe return code
msgIdPacketCaptureStatus = 12021

# Volume for live stream's audio
msgIdSetAudioVolume = 12022

# Followed by camera URI
msgIdCameraUriUpdated = 12023

# Followed by (pickled) camera manager state, chosen hw device
msgIdHardwareAccelerationSettingUpdated = 12024

###############################################################
# Camera Capture Messages

# Followed by the camera location and optional failure reason
msgIdStreamOpenFailed = 13000

# Followed by the pipe id
msgIdPipeFinished = 13001

# Followed by the camera location
msgIdStreamTimeout = 13002

# Followed by camera location, highest processed ms
msgIdStreamProcessedData = 13003

# Followed by cameraLocation, list of (firstMs, lastMs) tuples to mark as saved
msgIdAddSavedTimes = 13004

# Followed by camera location
msgIdCameraCapturePing = 13005

# Followed by nothing
msgIdTestCameraFailed = 13006

# Followed by a path and camera location
msgIdFileMoveFailed = 13007

# Followed by a camera location
msgIdSetCamCanTerminate = 13008
msgIdSetTerminate = 13009

# Followed by the camera location and processing size as (width, height)
msgIdStreamOpenSucceeded = 13010

# Followed by the camera location and frame size
msgIdStreamUpdateFrameSize = 13011

# Followed by a camera location and the current port number of its WSGI server.
msgIdWsgiPortChanged = 13100

# Port of the analytics platform had changed
msgIdAnalyticsPortChanged = 13101


###############################################################
# DataManager Messages

# Followed by pipeid, camObjId, time, object type, and camera location
msgIdDataAddObject = 14000

# Followed by pipeid, dbId or (pipeId, camObjId), frame, time, bbox, fullBox,
#             objType, action
msgIdDataAddFrame = 14001


###############################################################
# DiskCleaner Messages

# Followed by the number of cameras
msgIdSetNumCameras = 15000

# Followed by max disk space usage
msgIdSetMaxStorage = 15001

# No additional parameters
msgIdInsufficientSpace = 15002

# Followed by a location name
msgIdRemoveDataAtLocation = 15003

# Followed by a file path
msgIdDeleteFile = 15004

# Followed by maximum hours of cache
msgIdSetCacheDuration = 15005


###############################################################
# Preference Messages

# Followed by a path
msgIdSetStorageLocation = 16000

# Followed by a dictionary describing settings
msgIdSetEmailSettings = 16001

# Followed by a path, preserveData bool, and keepExisting bool
msgIdSetVideoLocation = 16002

# Followed by time, value
msgIdSetClipMergeThreshold = 16003

# Followed by a dictionary describing settings
msgIdSetFtpSettings          = 16004
msgIdSetLocalExportSettings  = 16005
msgIdSetNotificationSettings = 16006

# Followed by use12HourTime and useUSDate bools
msgIdSetTimePrefs = 16007

# Followed by dictionary with debug configuration settings
msgIdSetDebugConfig = 16009

# Followed by name, value
msgIdSetVideoSetting = 16010

# Followed by a boolean
msgIdSetRecordInMemory = 16011


###############################################################
# Rule Messages

# Followed by rule name, pickled rule, pickled query data model
msgIdRuleAdded = 17000

# Followed by rule name, schedule dict
msgIdRuleScheduleUpdated = 17001

# Followed by rule name
msgIdRuleDeleted = 17002

# Followed by rule name, True/False to enable/disable
msgIdRuleEnabled = 17003

# Followed by (pickled) camera manager state.
msgIdRuleReloadAll = 17004


###############################################################
# Response Messages

# Followed by: ruleName, camLoc, emailSettings, configDict, numTriggers,
#              objList, firstMs, lastMs, messageId
msgIdSendEmail = 18000

# Followed by camLoc, width, height
msgIdSetCamResolution = 18001

# Followed by nothing
msgIdSendClip = 18002

# Followed by nothing
msgIdResponseRunnerPing = 18003

# Followed by camLoc, ruleName, ms
msgIdSendPush = 18004

# Followed by camLoc, ruleName, epochSeconds
msgIdTriggerIfttt = 18005

# Followed by token
msgIdSetServicesAuthToken = 18006

# Followed by cameras, rules
msgIdSendIftttState = 18007

# Followed by ruleName, camLoc, list of (objId, time) tuples
msgIdSendWebhook = 18008


###############################################################
# Messages for the front end

# Followed by a path
msgIdDirectoryRemoveFailed = 19000
msgIdDirectoryCreateFailed = 19001

# Followed by nothing
msgIdOutOfDiskSpace = 19002

# Followed by old license data, new license data
msgIdLicenseChanged = 19003

# Followed by error text.
msgIdNeedRelogin = 19004

# Followed by number of days since the support expired, support-expires date,
# license serial number.
msgIdLicenseSupportExpired = 19005

###############################################################
# Misc error messages

# Followed by nothing
msgIdDatabaseCorrupt = 20000

###############################################################
# Web Server Messages

# Followed by nothing.
msgIdWebServerPing = 22000

# Followed by the new port number to use. Goes from frontend to backend and
# then also from backend to the web server process.
msgIdWebServerSetPort = 22001

# Followed by the auth information for the web server configuration.
msgIdWebServerSetAuth = 22002

# Followed by flag to enable (or disable) the port opener.
msgIdWebServerEnablePortOpener = 22003

###############################################################
# Licensing and Account Messages

# Followed by opid, user name and password.
msgIdUserLogin = 23000

# Followed by opid.
msgIdRefreshLicenseList = 23001

# Followed by opid, serial number.
msgIdAcquireLicense = 23002

# Followed by opid.
msgIdUnlinkLicense = 23003

# Followed by nothing
msgIdUserLogout = 23004

###############################################################
# External services integration

# Followed by camera name, start time, duration
msgIdSubmitClipToSighthound = 24000
