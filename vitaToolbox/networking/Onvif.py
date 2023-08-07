#*****************************************************************************
#
# Onvif.py
#
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

import base64
import calendar
import copy
import hashlib
import os
import pprint
import random
import re
import select
import socket
import sys
import threading
import time
import traceback
import urllib
import urlparse

import uuid as uuidlib

from xml.dom import minidom

from collections import defaultdict

import netifaces

from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.loggingUtils.LoggingUtils import MsgPrefixLogger
from vitaToolbox.networking.HttpClient import HttpClient
from vitaToolbox.networking.XmlUtils import vitaParseXML
from vitaToolbox.sysUtils.TimeUtils import formatTime


_kDeviceTimeout = 30 # consider the device gone if not seen for that long

# This is the official IP and port that we send multicast for the WS-Discovery.
# <http://en.wikipedia.org/wiki/WS-Discovery>
_kMulticastAddr = ("239.255.255.250", 3702)

# This library follows the Onvif specification found here:
# <http://www.onvif.org/specs/core/ONVIF-Core-Specification-v242.pdf>
# and the WS-Discovery specification found here:
# <http://docs.oasis-open.org/ws-dd/discovery/1.1/os/wsdd-discovery-1.1-spec-os.html#_Toc234231804>

# WS-Discovery URI XML namespaces
_kWsSecurity = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
_kWsSecurityCreated = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"

# WS-Discovery URI XML types
_kTypePasswordDigest = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest"
_kTypeBase64Binary = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"

# ONVIF URI XML namespaces.
_kOnvifSchema = "http://www.onvif.org/ver10/schema"
_kOnvifDevice = "http://www.onvif.org/ver10/device/wsdl"
_kOnvifMedia = "http://www.onvif.org/ver10/media/wsdl"
_kOnvifNetwork = "http://www.onvif.org/ver10/network/wsdl"

# Action values to accompany the HTTP header field "Content-Type" under "action".
_kOnvifActionGetSystemDateAndTime = "%s/GetSystemDateAndTime" % _kOnvifDevice
_kOnvifActionGetDeviceInformation = "%s/GetDeviceInformation" % _kOnvifDevice
_kOnvifActionGetProfiles = "%s/GetProfiles" % _kOnvifMedia
_kOnvifActionGetStreamUri = "%s/GetStreamUri" % _kOnvifMedia

# WS-Discovery URI XML namespaces referenced by ONVIF.
_kWsSoapEnv = "http://www.w3.org/2003/05/soap-envelope"
_kWsSoapBodyInstance = "http://www.w3.org/2001/XMLSchema-instance"
_kWsSoapBody = "http://www.w3.org/2001/XMLSchema"
_kWsDiscovery = "http://schemas.xmlsoap.org/ws/2005/04/discovery"
_kWsAddressing = "http://schemas.xmlsoap.org/ws/2004/08/addressing"

# WS-Discovery URI commands referenced by ONVIF.
_kActionProbe = "http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe"
_kActionProbeMatches = "http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches"
_kAddressAll = "urn:schemas-xmlsoap-org:ws:2005:04:discovery"
_kAddressUnknown = "http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous"

# These are used to parse thru the list of scopes of an ONVIF compliant device.
# A scope is a URI with a scheme, hostname, and path. For ONVIF, the scheme
# must be "onvif", the hostname must be "www.onvif.org", and the path must
# contain a text describing an attribute or capability that the camera may
# perfom as a service.
_kOnvifUrlScheme = "onvif"
_kOnvifUrlAuthority = "www.onvif.org"
_kOnvifUrl = urlparse.urlunparse((_kOnvifUrlScheme, _kOnvifUrlAuthority, '', '', '', ''))
_kMalformedWsScopes = "MalformedWsScopes"

# ONVIF general/main Fault Codes
kFaultCodeVersionMismatch = "VersionMismatch"
kFaultCodeMustUnderstand = "MustUnderstand"
kFaultCodeDataEncodingUnknown = "DataEncodingUnknown"
kFaultCodeSender = "Sender"
kFaultCodeReceiver = "Receiver"
kMainFaultCodes = [kFaultCodeVersionMismatch, kFaultCodeMustUnderstand,
                   kFaultCodeDataEncodingUnknown, kFaultCodeSender,
                   kFaultCodeReceiver,
                   ]

# ONVIF Sender Fault Subcodes
kFaultSubcodeWellFormed = "WellFormed"
kFaultSubcodeTagMismatch = "TagMismatch"
kFaultSubcodeTag = "Tag"
kFaultSubcodeNamespace = "Namespace"
kFaultSubcodeMissingAttr = "MissingAttr"
kFaultSubcodeProhibAttr = "ProhibAttr"
kFaultSubcodeInvalidArgs = "InvalidArgs"
kFaultSubcodeInvalidArgVal = "InvalidArgVal"
kFaultSubcodeUnknownAction = "UnknownAction"
kFaultSubcodeOperationProhibited = "OperationProhibited"
kFaultSubcodeNotAuthorized = "NotAuthorized"
kSenderFaultSubcodes = [kFaultSubcodeWellFormed, kFaultSubcodeTagMismatch,
                        kFaultSubcodeTag, kFaultSubcodeNamespace,
                        kFaultSubcodeMissingAttr, kFaultSubcodeProhibAttr,
                        kFaultSubcodeInvalidArgs, kFaultSubcodeInvalidArgVal,
                        kFaultSubcodeUnknownAction,
                        kFaultSubcodeOperationProhibited,
                        kFaultSubcodeNotAuthorized,
                        ]

# ONVIF Receiver Fault Subcodes
kFaultSubcodeActionNotSupported = "ActionNotSupported"
kFaultSubcodeAction = "Action"
kFaultSubcodeOutofMemory = "OutofMemory"
kFaultSubcodeCriticalError = "CriticalError"
kReceiverFaultSubcodes = [kFaultSubcodeActionNotSupported,
                          kFaultSubcodeAction, kFaultSubcodeOutofMemory,
                          kFaultSubcodeCriticalError,
                          ]

# All ONVIF Fault codes
kAllFaultCodes = kMainFaultCodes + kSenderFaultSubcodes + kReceiverFaultSubcodes

# This is used in place of fault code for errors caused by the http request.
# If something goes wrong with the http request, we won't get a fault code. So
# it would be nice if we could specify that something went wrong with the
# connection, instead of something going wrong with the camera.
kHttpRequestError = "HttpRequestError"

# Maximum UDP paypload size we accept. Packet fragmentation is not an issue.
_kDescriptionBufsize = 0xffff

# How long to wait for discovery to accept responses.
_kDiscoveryTimeout = 5

# HTTP method to talk to the ONVIF service.
_kHttpMethod="POST"

# HTTP URL path to use for onvif device management services.
_kDeviceServicePath = "onvif/device_service"
_kDeviceServiceFallbackPaths = ["onvif/device", "onvif/service"]

# HTTP URL path to use for onvif media services.
_kMediaServicePath = "onvif/Media"
_kMediaServiceFallbackPaths = ["onvif/media_service"]

# HTTP header fields needed to talk to the ONIVF service.
_kContentTypeField = "Content-Type"
_kContentTypeFieldSeparator = ';'
_kApplicationSoapXML = "application/soap+xml"
_kCharSetUTF8 = "charset=utf-8"
_kActionValue = 'action="%s"'

# Timeout per HTTP request made.
_kHttpTimeout = 5
# How many HTTP retries to make. Retrying happens because we don't want to miss
# a camera just because a single request somehow got stuck or lost.
_kHttpRetries=1

# Stream types to try out. For now there's only one.
_kOnvifStreamTypes = ['RTP-Unicast']
# All of the stream transports to look for. Starting with the most preferred.
_kOnvifTransportTypes = ['RTSP', 'HTTP', 'UDP']

# Things to build an ONVIF URL.
_kOnvifHostnameSuffix = ".ardenaionvif"

# Max number of times to send probe requests.
_kWsDiscoveryMulticastUdpMaxRepeat = 4

# Max delay in seconds to wait till sending out the next probe request.
_kOnvifMaxUdpDelay = 0.600

# HTTP status success -- OK.
_kHttpOk = 200

# HTTP status client error -- the client issued a bad request.
_kHttpBadRequest = 400

# HTTP status client error -- the client is unauthorized.
_kHttpUnauthorized = 401

# HTTP status client error -- the requested url was not found on the server.
_kHttpUrlNotFound = 404

# HTTP status server error -- service unavailable.
_kHttpServiceUnavailable = 503


###############################################################################
def _createProbeRequest(uuid, withTypes=False):
    """Create a WS-Discovery request.

    @param uuid  Individual UUID for that discovery, to correlate responses and
                 to detect (and discard) such of older discoveries.
    @return      Request, as XML DOM.
    """

    impl = minidom.getDOMImplementation()
    doc = impl.createDocument(_kWsSoapEnv, "s:Envelope", None)

    envelopeEl = doc.documentElement
    envelopeEl.setAttribute("xmlns:s", _kWsSoapEnv)
    envelopeEl.setAttribute("xmlns:a", _kWsAddressing)
    envelopeEl.setAttribute("xmlns:d", _kWsDiscovery)
    envelopeEl.setAttribute("xmlns:dn", _kOnvifNetwork)

    headerEl = doc.createElementNS(_kWsSoapEnv, "s:Header")
    envelopeEl.appendChild(headerEl)

    actionEl = doc.createElementNS(_kWsAddressing, "a:Action")
    actionEl.setAttributeNS(_kWsSoapEnv, "s:mustUnderstand", "1")
    text = doc.createTextNode(_kActionProbe)
    actionEl.appendChild(text)
    headerEl.appendChild(actionEl)

    messageIdEl = doc.createElementNS(_kWsAddressing, "a:MessageID")
    text = doc.createTextNode(uuid)
    messageIdEl.appendChild(text)
    headerEl.appendChild(messageIdEl)

    replyToEl = doc.createElementNS(_kWsAddressing, "a:ReplyTo")
    headerEl.appendChild(replyToEl)

    addressEl = doc.createElementNS(_kWsAddressing, "a:Address")
    text = doc.createTextNode(_kAddressUnknown)
    addressEl.appendChild(text)
    replyToEl.appendChild(addressEl)

    toEl = doc.createElementNS(_kWsAddressing, "a:To")
    toEl.setAttributeNS(_kWsSoapEnv, "s:mustUnderstand", "1")
    text = doc.createTextNode(_kAddressAll)
    toEl.appendChild(text)
    headerEl.appendChild(toEl)

    bodyEl = doc.createElementNS(_kWsSoapEnv, "s:Body")
    envelopeEl.appendChild(bodyEl)

    probeEl = doc.createElementNS(_kWsDiscovery, "d:Probe")
    bodyEl.appendChild(probeEl)

    if withTypes:
        typesEl = doc.createElementNS(_kWsDiscovery, "d:Types")
        text = doc.createTextNode("dn:NetworkVideoTransmitter")
        typesEl.appendChild(text)
        probeEl.appendChild(typesEl)

    return doc


###############################################################################
def _addSecurityHeader(doc, credentials, timeOffset):
    """ To add data for authentication.

    @param  doc           The XML DOM to update.
    @param  credenatials  Credentials as (username, password).
    @param  timeOffset    Difference between local time and device time.
    @return               The updated XML DOM.
    """

    # Generate our nonce (a unique, one-time random number).
    try:
        nonce = os.urandom(24).encode('base64')[:-1]
    except:
        nonce = "".join(chr(random.randint(0, 255)) for _ in range(24))
        nonce = nonce.encode('base64')

    nonceDecoded = base64.b64decode(nonce)

    # Get the time that this digest was created, relative to the device's time.
    created = formatTime("%Y-%m-%dT%H:%M:%SZ",
                            time.gmtime(time.time() + timeOffset))

    # Concatenate everything together for the digest.
    concatPassword = nonceDecoded + created + credentials[1]

    passwordDigest = base64.b64encode(hashlib.sha1(concatPassword).digest())

    envelopeEl = doc.documentElement
    envelopeEl.setAttribute("xmlns:wsu", _kWsSecurityCreated)

    try:
        headerEl = doc.getElementsByTagNameNS(_kWsSoapEnv, "Header")[0]
    except:
        headerEl = doc.createElementNS(_kWsSoapEnv, "s:Header")
        envelopeEl.insertBefore(headerEl, envelopeEl.firstChild)

    securityEl = doc.createElementNS(_kWsSecurity, "Security")
    securityEl.setAttributeNS(_kWsSoapEnv, "s:mustUnderstand", "1")
    securityEl.setAttribute("xmlns", _kWsSecurity)
    headerEl.insertBefore(securityEl, headerEl.firstChild)

    usernameTokenEl = doc.createElement("UsernameToken")
    securityEl.appendChild(usernameTokenEl)

    usernameEl = doc.createElement("Username")
    text = doc.createTextNode(credentials[0])
    usernameEl.appendChild(text)
    usernameTokenEl.appendChild(usernameEl)

    passwordEl = doc.createElement("Password")
    passwordEl.setAttribute("Type", _kTypePasswordDigest)
    text = doc.createTextNode(passwordDigest)
    passwordEl.appendChild(text)
    usernameTokenEl.appendChild(passwordEl)

    nonceEl = doc.createElement("Nonce")
    nonceEl.setAttribute("EncodingType", _kTypeBase64Binary)
    text = doc.createTextNode(nonce)
    nonceEl.appendChild(text)
    usernameTokenEl.appendChild(nonceEl)

    createdEl = doc.createElementNS(_kWsSecurityCreated, "wsu:Created")
    text = doc.createTextNode(created)
    createdEl.appendChild(text)
    usernameTokenEl.appendChild(createdEl)

    return doc


###############################################################################
def _createGetDeviceInformationRequest():
    """ Create request data to get the device's basic information: manufacturer,
        model, firmware version, serial number, and hardware ID.

    @return  Request, as XML DOM.
    """

    impl = minidom.getDOMImplementation()
    doc = impl.createDocument(_kWsSoapEnv, "s:Envelope", None)

    envelopeEl = doc.documentElement
    envelopeEl.setAttribute("xmlns:s", _kWsSoapEnv)

    bodyEl = doc.createElementNS(_kWsSoapEnv, "s:Body")
    envelopeEl.appendChild(bodyEl)

    deviceInfoEl = doc.createElementNS(_kOnvifDevice, "GetDeviceInformation")
    deviceInfoEl.setAttribute("xmlns", _kOnvifDevice)
    bodyEl.appendChild(deviceInfoEl)

    return doc


###############################################################################
def _createGetSystemDateAndTimeRequest():
    """ Create request data to get the device's date and time, especially
    needed for authentication.

    NOTE: this request itself sometimes needs authentication data, since some
          camera's don't seem to stick to the standard or we haven't really
          understood precisely why it is happening.

    @return  Request, as XML DOM.
    """

    impl = minidom.getDOMImplementation()
    doc = impl.createDocument(_kWsSoapEnv, "s:Envelope", None)

    envelopeEl = doc.documentElement
    envelopeEl.setAttribute("xmlns:s", _kWsSoapEnv)

    bodyEl = doc.createElementNS(_kWsSoapEnv, "s:Body")
    envelopeEl.appendChild(bodyEl)

    sysDatAndTimeEl = doc.createElementNS(_kOnvifDevice, "GetSystemDateAndTime")
    sysDatAndTimeEl.setAttribute("xmlns", _kOnvifDevice)
    bodyEl.appendChild(sysDatAndTimeEl)

    return doc

# NOTE: neither date-time nor profile request data must be cached because the
#       DOM might be modified (e.g. authentication data) by the caller!

###############################################################################
def _createGetProfilesRequest():
    """ Create request data to get the profiles the device cares to announce.

    @return  Request, as XML DOM.
    """

    impl = minidom.getDOMImplementation()
    doc = impl.createDocument(_kWsSoapEnv, "s:Envelope", None)

    envelopeEl = doc.documentElement
    envelopeEl.setAttribute("xmlns:s", _kWsSoapEnv)
    envelopeEl.setAttribute("xmlns:trt", _kOnvifMedia)

    bodyEl = doc.createElementNS(_kWsSoapEnv, "s:Body")
    envelopeEl.appendChild(bodyEl)

    profilesEl = doc.createElementNS(_kOnvifMedia, "trt:GetProfiles")
    bodyEl.appendChild(profilesEl)

    return doc


###############################################################################
def _createGetStreamUriRequest(stream, transport, profile):
    """ Creates a request to get a potential URI for a stream.

    @param  profile    The profile, as returned by the device.
    @param  transport  Transport type we want to use.
    @param  stream     The stream token/identifier, as found in a profile.
    @return            Request, as XML DOM.
    """

    impl = minidom.getDOMImplementation()
    doc = impl.createDocument(_kWsSoapEnv, "s:Envelope", None)

    envelopeEl = doc.documentElement
    envelopeEl.setAttribute("xmlns:s", _kWsSoapEnv)
    envelopeEl.setAttribute("xmlns:trt", _kOnvifMedia)
    envelopeEl.setAttribute("xmlns:tt", _kOnvifSchema)

    bodyEl = doc.createElementNS(_kWsSoapEnv, "s:Body")
    envelopeEl.appendChild(bodyEl)

    streamUriEl = doc.createElementNS(_kOnvifMedia, "trt:GetStreamUri")
    bodyEl.appendChild(streamUriEl)

    streamSetupEl = doc.createElementNS(_kOnvifMedia, "trt:StreamSetup")
    streamUriEl.appendChild(streamSetupEl)

    streamEl = doc.createElementNS(_kOnvifSchema, "tt:Stream")
    text = doc.createTextNode(stream)
    streamEl.appendChild(text)
    streamSetupEl.appendChild(streamEl)

    transportEl = doc.createElementNS(_kOnvifSchema, "tt:Transport")
    streamSetupEl.appendChild(transportEl)

    protocolEl = doc.createElementNS(_kOnvifSchema, "tt:Protocol")
    text = doc.createTextNode(transport)
    protocolEl.appendChild(text)
    transportEl.appendChild(protocolEl)

    profileTokenEl = doc.createElementNS(_kOnvifMedia, "trt:ProfileToken")
    text = doc.createTextNode(profile)
    profileTokenEl.appendChild(text)
    streamUriEl.appendChild(profileTokenEl)

    return doc

###############################################################################
class OnvifXMLException(Exception):
    pass

###############################################################################
def _getElement(xmldoc, ns, name):
    """ Return first matching element,
        or raise OnvifXMLException if not found or failed
    """
    try:
        matchingElements = xmldoc.getElementsByTagNameNS(ns, name)
        if len(matchingElements) == 0 or matchingElements[0] is None:
            raise OnvifXMLException("No element %s found" % (name))
        return matchingElements[0]
    except:
        raise OnvifXMLException("Exception parsing xmldoc: ns=%s element=%s" % (ns, name))

###############################################################################
def _getElementChildNode(xmldoc, ns, name):
    """ Return first matching child of first matching element,
        or raise OnvifXMLException if not found or failed
    """
    element = _getElement(xmldoc, ns, name)
    children = element.childNodes
    if children is None or len(children) == 0 or children[0].data is None:
        raise OnvifXMLException("No child nodes for element %s found" % (name))
    return children[0].data

###############################################################################
def _getElementChildNodeSafe(xmldoc, ns, name, defaultValue):
    """ Return first matching child of first matching element,
        or default value if not found or failed
    """
    try:
        return _getElementChildNode(xmldoc, ns, name)
    except OnvifXMLException:
        return defaultValue

###############################################################################
def _getElementChildNodeAsList(xmldoc, ns, name):
    """ Return first matching child of first matching element as list,
        splitting on commas, or raise OnvifXMLException if not found or failed
    """
    result = _getElementChildNode(xmldoc, ns, name)
    if result is not None:
        return result.split()

###############################################################################
def _getElementChildNodeAsListSafe(xmldoc, ns, name, defaultValue):
    """ Return first matching child of first matching element as list,
        splitting on commas, or default value if not found or failed
    """
    try:
        return _getElementChildNodeAsList(xmldoc, ns, name)
    except OnvifXMLException:
        return defaultValue

###############################################################################
def _parseProbeResponse(doc, logger):
    """Parses the Probe Response from a XML document object, and returns the
    UUID of the probe request that this message is associated with, the unique
    device ID, a list of all IP addresses where the device may be reached, and
    a list of general device info.

    @param   doc            The XML DOM.

    @return  relatesToUuid  The unique identifier of the probe request that this
                            response is associated with. None on parse error.
    @return  deviceUuid     The unique identifier of the device. None on parse
                            error.
    @return  xAddrs         A list of IP addresses where the device
                            may be reached. None on parse error.
    @return  scopes         A list of general information of the device:
                            it's profile, name, and hardware info. None on parse
                            error.
    """
    try:
        headerEl       = _getElement(doc, _kWsSoapEnv, "Header")
        msgUuid        = _getElementChildNode(headerEl, _kWsAddressing, "RelatesTo")
        probeMatchesEl = _getElement(doc, _kWsDiscovery, "ProbeMatches")
        deviceUuid     = _getElementChildNodeSafe(probeMatchesEl, _kWsAddressing, "Address", None)
        xAddrs         = _getElementChildNodeAsListSafe(probeMatchesEl, _kWsDiscovery, "XAddrs", None)
        scopes         = _getElementChildNodeAsListSafe(probeMatchesEl, _kWsDiscovery, "Scopes", [])
    except OnvifXMLException:
        logger.error("ProbeResponse: Error parsing ONVIF XML %s" % ensureUtf8(doc.toxml("utf-8")), exc_info=True)
        return None
    except:
        logger.error("Probe parse error for document %s!" % ensureUtf8(doc.toxml("utf-8")), exc_info=True)
        return None

    logger.debug("Discovered device with uuid %s at %s" % (deviceUuid, str(xAddrs)))
    return (msgUuid, deviceUuid, xAddrs, scopes)


###########################################################
def _parseGetDeviceInformationResponse(doc, logger):
    """ Parses the response to a device information request.

    @param      doc     The XML DOM.
    @param      logger  logger to report errors.

    @return     Device information as a dict with keys: manufacturer, model,
                firmwareVersion, serialNumber, hardwareId; or error as {}.
    """
    try:
        messageEl       = _getElement(doc, _kOnvifDevice, "GetDeviceInformationResponse")
        manufacturer    = _getElementChildNode(doc, _kOnvifDevice, "Manufacturer")
        model           = _getElementChildNode(doc, _kOnvifDevice, "Model")
        firmwareVersion = _getElementChildNode(doc, _kOnvifDevice, "FirmwareVersion")
        serialNumber    = _getElementChildNode(doc, _kOnvifDevice, "SerialNumber")
        hardwareId      = _getElementChildNode(doc, _kOnvifDevice, "HardwareId")
    except OnvifXMLException:
        logger.error("GetDeviceInformation: Error parsing ONVIF XML %s" % ensureUtf8(doc.toxml("utf-8")), exc_info=True)
        return None
    except:
        logger.error("GetDeviceInformation parse error!", exc_info=True)
        return {}

    theKeys = ('manufacturer', 'model', 'firmwareVersion', 'serialNumber', 'hardwareId')
    theValues = (manufacturer, model, firmwareVersion, serialNumber, hardwareId)

    return dict(zip(theKeys, theValues))


###########################################################
def _parseGetSystemDateAndTimeResponse(doc, logger):
    """ Parses the response to a date and time request.

    @param  doc  The XML DOM.

    @return      Date-time (y,m,d,h,m,s) or error None.
    """

    try:
        messageEl       = _getElement(doc, _kOnvifDevice, "GetSystemDateAndTimeResponse")
        utcDateTimeEl   = _getElement(doc, _kOnvifSchema, "UTCDateTime")
        dateEl          = _getElement(utcDateTimeEl, _kOnvifSchema, "Date")
        timeEl          = _getElement(utcDateTimeEl, _kOnvifSchema, "Time")
        year            = int(_getElementChildNode(dateEl, _kOnvifSchema, "Year"))
        month           = int(_getElementChildNode(dateEl, _kOnvifSchema, "Month"))
        day             = int(_getElementChildNode(dateEl, _kOnvifSchema, "Day"))
        hour            = int(_getElementChildNode(timeEl, _kOnvifSchema, "Hour"))
        minute          = int(_getElementChildNode(timeEl, _kOnvifSchema, "Minute"))
        second          = int(_getElementChildNode(timeEl, _kOnvifSchema, "Second"))
    except OnvifXMLException:
        logger.error("GetSystemDateAndTimeResponse: Error parsing ONVIF XML %s" % ensureUtf8(doc.toxml("utf-8")), exc_info=True)
        return None
    except:
        logger.error("GetSystemDateAndTimeResponse parse error!", exc_info=True)
        return None

    return (year, month, day, hour, minute, second)


###############################################################################
def _parseGetProfilesResponse(doc, logger):
    """ Parses a profiles response.

    @param   doc       The XML DOM.

    @return  profiles  List of profile strings. Empty on parse error, or if
                       the device really has no profiles somehow.
    """
    profiles = []
    numTotal = 0
    numAcquired = 0

    try:
        messageEl = _getElement(doc, _kOnvifMedia, "GetProfilesResponse")

        profilesList = doc.getElementsByTagNameNS(_kOnvifMedia, "Profiles")
        if not profilesList:
            logger.error('ComplexType missing: Profiles.')
            return profiles

        for profileEl in profilesList:
            numTotal += 1

            profileToken = profileEl.getAttribute("token")

            # Tokens are needed to get stream uri's.  If it's an empty string,
            # there's nothing we can do. Continue the loop.
            if not profileToken:
                continue

            profileName = "UnknownProfile %d" % numTotal
            encoder = "UnknownEncoding"
            resolution = ('###', '###')

            try:
                profileName = _getElementChildNode(profileEl, _kOnvifSchema, "Name")
            except:
                pass

            try:
                videoEncoderConfiguration = _getElement(profileEl, _kOnvifSchema, "VideoEncoderConfiguration")
                encoder = _getElementChildNodeSafe(videoEncoderConfiguration, _kOnvifSchema, "Encoding", encoder)

                try:
                    resolutionEl = _getElement(videoEncoderConfiguration, _kOnvifSchema, "Resolution")
                    width = _getElementChildNode(resolutionEl, _kOnvifSchema, "Width")
                    height = _getElementChildNode(resolutionEl, _kOnvifSchema, "Height")
                    resolution = (width, height)
                except:
                    pass
            except:
                pass

            profiles.append((profileName, profileToken, encoder, resolution))
            numAcquired += 1
    except OnvifXMLException:
        logger.info("GetProfilesResponse: Error parsing ONVIF XML %s" % ensureUtf8(doc.toxml("utf-8")), exc_info=True)
    except:
        logger.error("GetProfilesResponse parse error!", exc_info=True)

    if numTotal != numAcquired:
        logger.info("Acquired %d profiles, out of %d." % (numAcquired, numTotal,))
    return profiles


##############################################################################
def _parseGetStreamUriResponse(doc, logger):
    """ Gets the stream UI from a response.

    @param   doc            The XML DOM.

    @return  streamUri      Streaming URI or None on parse error.
    """
    streamUri = None
    try:
        messageEl = _getElement(doc, _kOnvifMedia, "GetStreamUriResponse")
        streamUri = _getElementChildNode(doc, _kOnvifSchema, "Uri")
    except OnvifXMLException:
        logger.error("GetStreamUriResponse: Error parsing ONVIF XML %s" % ensureUtf8(doc.toxml("utf-8")), exc_info=True)
    except:
        logger.error("GetStreamUriResponse parse error!", exc_info=True)
    return streamUri

###############################################################################
def _parseFaultCode(doc, logger):
    """Parses the Fault Code Response from a XML document object; Returns
    the error code, if there is one, and None otherwise.

    @param   doc            The XML DOM.

    @return  faultCode      The error code, or None on parse error.
    """
    try:
        bodyEl = doc.getElementsByTagNameNS(_kWsSoapEnv, "Body")[0]
        faultEl = bodyEl.getElementsByTagNameNS(_kWsSoapEnv, "Fault")[0]
        codeEl = faultEl.getElementsByTagNameNS(_kWsSoapEnv, "Code")[0]
        valueEl = codeEl.getElementsByTagNameNS(_kWsSoapEnv, "Value")[0]
        faultCodeStr = valueEl.childNodes[0].data.split(":")[-1]

        if (faultCodeStr == kFaultCodeSender) or \
                (faultCodeStr == kFaultCodeReceiver):
            subcodeEl = codeEl.getElementsByTagNameNS(_kWsSoapEnv, "Subcode")[0]
            valueEl = subcodeEl.getElementsByTagNameNS(_kWsSoapEnv, "Value")[0]
            faultCodeStr = valueEl.childNodes[0].data.split(":")[-1]

            if (faultCodeStr in kSenderFaultSubcodes) or \
                    (faultCodeStr in kReceiverFaultSubcodes):
                return faultCodeStr

        else:
            if faultCodeStr in kMainFaultCodes:
                return faultCodeStr

        # We were able to parse the fault code, but we don't know what it is.
        logger.warn("Unknown Fault Code: %s" % faultCodeStr)
        return faultCodeStr

    except:
        logger.error("FaultCode parse error %s!", ensureUtf8(doc.toxml("utf-8")), exc_info=True)
        return None


##############################################################################
def isOnvifUrl(url):
    """Return True if the given URL is a valid ONVIF URL.

    @param  url         The URL to check.
    @return isOnvifUrl  True if the URL is a ONVIF URL.
    """
    try:
        _ = extractUuidFromOnvifUrl(url)
    except:
        return False
    else:
        return True


##############################################################################
def extractUuidFromOnvifUrl(url):
    """Extract the UUID from an ONVIF URL.

    ONVIF URLs look like this:
      scheme://[[user][:pass]@]encodedUuid.ardenaionvif.[:port]/path

    @param  url        The URL. Should be Unicode or UTF-8 encoded.
    @return uuid       The UUID, in unicode.
    @raise ValueError  If parsing failed.
    """
    try:
        if not url:
            raise ValueError("URL is None or Empty String.")
        url = ensureUtf8(url)
        splitResult = urlparse.urlsplit(url)

        # Get the host name. If blank or None, then it's not a valid ONVIF URL.
        hostname = splitResult.hostname
        if not hostname:
            raise ValueError("Not a valid ONVIF URL: %s" % url)

        if hostname.endswith(_kOnvifHostnameSuffix):
            # Strip off the suffix...
            encodedUuid = hostname[:-len(_kOnvifHostnameSuffix)]

            # Decode from our terribly convoluted way of encoding a UUID into
            # a hostname.  All of this work is to try to make sure that we can
            # represent arbitrary UUIDs, while only using alpha-numeric, case-
            # insensitive chars.  Note that the pad ('=') violates that, so we
            # replace it with 9 (which should be unused).  We also put a "."
            # every 16 characters, to make it look pretty and keep any part
            # from being >63 characters...
            encodedUuid = encodedUuid.replace('9', '=').replace('.', '')
            uuid = base64.b32decode(encodedUuid, True)

            return uuid.decode('utf-8')
    except ValueError:
        # Don't care about value error debug message...
        pass
    except Exception:
        # Could happen if the hostname ends with the suffix, but isn't
        # a valid encoding...
        if __debug__:
            traceback.print_exc()

    raise ValueError("Not a valid ONVIF URL: %s" % str(url))


##############################################################################
def realizeOnvifUrl(deviceDict, url):
    """Given an ONVIF URL, convert it into a real one.

    ONVIF URLs look like this:
      scheme://[[user][:pass]@]encodedUuid.ardenaionvif.[:port]/path

    We convert it to a real one by getting the base address from ONVIF,
    then adding the user/pass as well as the path.

    @param  deviceDict  A dictionary of devices, like returned by getDevices()
    @param  url         An ONVIF URL. Should be Unicode or UTF-8, though
                        technically it should(?) have all ASCII values only.
    @return url         The realized URL; will be "" if the device wasn't
                        in the deviceDict, or if there were no valid reachable
                        IP addresses.  Will be encoded as UTF-8.
    @raise  ValuError   If it isn't a ONVIF URL.
    """
    # Extract the UUID; this will raise a ValueError if the URL wasn't an ONVIF
    # URL...
    uuid = extractUuidFromOnvifUrl(url)

    # If we don't know about this UUID, we just return a blank URL as per spec.
    if uuid not in deviceDict:
        return ""

    try:
        # Get the ONVIF device info...
        device = deviceDict[uuid]

        # Get the base address.
        if not device.validOnvifIpAddrs:
            return ""
        base = device.validOnvifIpAddrs[-1]
        hostname = ensureUtf8(base[0])

        # Split the ONVIF URL.
        url = ensureUtf8(url)
        onvifSplitResult = urlparse.urlsplit(url)

        newUrl = "%s://" % onvifSplitResult.scheme

        # Always get username/password from the ONVIF URL (should be quoted
        # already)...
        if onvifSplitResult.username or onvifSplitResult.password:
            if onvifSplitResult.username:
                newUrl += onvifSplitResult.username
            if onvifSplitResult.password:
                newUrl += ":%s" % onvifSplitResult.password
            newUrl += "@"

        # Add the hostname from the presentation URL...
        assert hostname, "Expected hostname in presentation URL"
        newUrl += hostname

        # If ONVIF URL has a port, use it. If it does not have one, leave it alone.
        if onvifSplitResult.port:
            newUrl += ":%s" % onvifSplitResult.port

        # We ignore the path part of the base URL and just jam the
        # path part of the ONVIF URL in.
        pathPart = onvifSplitResult.path
        if onvifSplitResult.query:
            pathPart += "?" + onvifSplitResult.query
        if onvifSplitResult.fragment:
            pathPart += "#" + onvifSplitResult.fragment

        # Make sure that the path part is not relative...
        if not pathPart.startswith('/'):
            pathPart = '/' + pathPart

        newUrl += pathPart

        #print "newURL: %s" % newUrl
        return newUrl
    except Exception:
        # Not expected, but when parsing stuff that user or network could
        # give us, you never know.  One possible way to get here is if the
        # user puts a non-integer port into their string, somehow?
        if __debug__:
            traceback.print_exc()
        raise ValueError("Not a valid ONVIF URL: %s" % str(url))


##############################################################################
def constructOnvifUrl(uuid, username=None, password=None, streamUri=None):
    """Create an ONVIF URL.

    ONVIF URLs look like this:
      scheme://[[user][:pass]@]encodedUuid.ardenaionvif.[:port]/path

    @param  uuid         The UUID to encode.  Should either be Unicode or UTF-8.
    @param  credentials  (username, password) This function handles
                         quoting. Credentails should be Unicode or UTF-8.
    @param  streamUri    The streamUri of the ONVIF device we wish to stream from.
    @return url          The ONVIF URL. Will be UTF-8.
    """
    if streamUri:
        splitResult = urlparse.urlsplit(streamUri)
    else:
        splitResult = urlparse.urlsplit('')

    scheme, _, path, query, fragment = splitResult

    pathPart = urlparse.urlunsplit(('','',path,query,fragment))

    port = ''
    try:
        port = str(int(splitResult.port))
    except:
        # We expect this if splitResult.port is None or ''.
        pass

    if not scheme:
        scheme = 'rtsp'

    url = ensureUtf8(scheme + '://')

    if username or password:
        if username:
            url += urllib.quote(ensureUtf8(username), "")
        if password:
            url += ":%s" % urllib.quote(ensureUtf8(password), "")
        url += "@"

    # Encode into our terribly convoluted way of encoding a UUID into
    # a hostname.  All of this work is to try to make sure that we can
    # represent arbitrary UUIDs, while only using alpha-numeric, case-
    # insensitive chars.  Note that the pad ('=') violates that, so we
    # replace it with 9 (which should be unused).  We also put a "."
    # every 16 characters, to make it look pretty and keep any part
    # from being >63 characters...
    encodedUuid = base64.b32encode(ensureUtf8(uuid))
    encodedUuid = encodedUuid.lower()
    encodedUuid = encodedUuid.replace('=', '9')
    encodedUuid = re.sub(r'(.{16})', r'\1.', encodedUuid).rstrip('.')

    url += (encodedUuid + _kOnvifHostnameSuffix)

    if port:
        url += ":%s" % port

    if pathPart:
        if not pathPart.startswith('/'):
            url += '/'
        url += ensureUtf8(pathPart)

    return url


###############################################################################
class OnvifDeviceState(object):
    """ The current state of what we know about a device. The device itself is
    identified via the WS-Discovery UUID, remember however that it is NOT
    defined to be the ultimate key forever (might change after boot etc)! The
    state data itself is treated immutable when it comes to external usage, it
    only gets changed internally, but then copied when passed out. The class
    itself is just data, no active parts or anything which does not have to do
    with the device state. Must be kept this way. To emphasize this
    characteristic we don't use setters here, more ressembling a structure. The
    current members are:

    generation            - discovery or poll generation
    uuid                  - the WS-Discovery identifier
    wsdiscoveryIp         - (ip,port) where the WS-Discovery response came from
    generalInfo           - general information gained from the discovery
    announcedOnvifIpAddrs - the (ip,port) addresses announced in the discovery
    validOnvifIpAddrs     - (ip,port) addresses confirmed by polling via HTTP
    profiles              - profile string list populated during polling
    streamUris            - stream URI dictionary (profile,URI) got via polling
    """

    def __init__(self, generation, fromIpAddr, uuid, xAddrs, scopes, settings, logger):
        """ Initializes the state.

        @param  generation   Discovery generation number.
        @param  fromIpAddr   The IP address that the probe response
                             message came from of this device.
        @param  uuid         The unique identifier for this device.
        @param  xAddrs       The list of IP addresses where this device
                             can be reached.
        @param  scopes       string that stores friendly name, hardware info,
                             and service info retrieved from the device.
        @param  settings     Local settings for the device
        @param  logger       Logger instance to report activity for debugging.
        """

        object.__init__(self)

        self.generation = generation
        self.uuid = uuid
        self.wsdiscoveryIp = fromIpAddr
        self.scopes = {
            _kOnvifUrl: {}
        }
        self.settings = settings
        self.authenticated = False
        self.lastFailureReason = ""

        # parse the scopes (available capabilities) for this type of device...
        if scopes is not None:

            for scope in scopes:

                scope = urllib.unquote(scope)
                (scheme, netloc, path, params, query, fragment) = \
                    parseResult = urlparse.urlparse(scope)

                # Parse for ONVIF capabilities...
                if (scheme == _kOnvifUrlScheme) and \
                    (parseResult.hostname == _kOnvifUrlAuthority):

                    category, _, value = path.lstrip('/').partition('/')
                    onvifScopes = self.scopes[_kOnvifUrl]

                    if not onvifScopes.has_key(category):
                        onvifScopes[category] = []
                    onvifScopes[category].append(value.lstrip('/').rstrip('/'))

                # Parse for other standards' capabilities, if they're reported
                # by the device...
                elif scheme or netloc:

                    unknownStdUrl = urlparse.urlunparse(
                        (scheme, netloc,'','','','')
                    )
                    unknownStdResource = urlparse.urlunparse(
                        ('', '', path, params, query, fragment)
                    )
                    category, _, value = unknownStdResource.lstrip('/').partition('/')

                    if not self.scopes.has_key(unknownStdUrl):
                        self.scopes[unknownStdUrl] = {}
                    unknownStdScopes = self.scopes[unknownStdUrl]

                    if not unknownStdScopes.has_key(category):
                        unknownStdScopes[category] = []
                    unknownStdScopes[category].append(value.lstrip('/').rstrip('/'))

                # Don't parse any malformed capabilites; just store them...
                else:

                    if not self.scopes.has_key(_kMalformedWsScopes):
                        self.scopes[_kMalformedWsScopes] = []
                    self.scopes[_kMalformedWsScopes].append(scope)


        self.announcedOnvifIpAddrs = []
        if xAddrs:
            for url in xAddrs:
                try:
                    # This can throw an AttributeError exception if url is an
                    # object without "find" as an attribute (which string
                    # objects do have). This should never happen, but we'll
                    # catch it and report it, just in case.
                    p = urlparse.urlparse(url)

                    # This can throw a ValueError exception if the port number
                    # is a string that cannot be converted into a valid integer.
                    port = p.port

                    # Check if the url is IPV6.  We don't support it (as of this
                    # writing) yet, so we will simply skip it.
                    if p.hostname.find(':') != -1:
                        continue

                except (ValueError, AttributeError):
                    # If we're here, it's most likely because we caught a
                    # ValueError exception from trying to retrieve the port
                    # number from the urlparse result. In python version 2.5
                    # IPV6 addresses are not handled by the urlparse.urlparse()
                    # method, and as a result, retrieving the port number does
                    # throw a ValueError because it incorrectly parses the
                    # address. IPV6 addresses are handled in version 2.7,
                    # however. For now, just ignore it, and move on to the next
                    # available address.
                    logger.warn("invalid URL (%s), ignoring it" % url)
                    continue

                if not port:
                    port = 80
                self.announcedOnvifIpAddrs.append((p.hostname, port))

        # This is a dict that should eventually be filled from a dict returned
        # by a "GetDeviceInformationResponse" message as long as the device is
        # ONVIF compliant. The keys, when this dict is populated, should be:
        # 'manufacturere', 'model', 'firmwareVersion', 'serialNumber', and
        # 'hardwareId'.
        self.basicInfo = {}
        self.validOnvifIpAddrs = []
        self.profiles = []
        self.streamUris = {}


    ###########################################################
    def __str__(self):
        """Gives a nice representation of the recognition object.

        This doesn't need to be enough to completely reconstruct the object;
        it's just a nice, printable, summary.

        @return s  Our string representation.
        """
        return pprint.pformat(self.asDict())


    ###########################################################
    def isValid(self):
        """Checks if this device has a UUID. The ONVIF specs states that a
        compliant device must have these four things in the probe response.
        However, we will only check if the device has a UUID, since
        non-compliant devices may not have friendly names, hardware info, and
        service info.

        @return  isValid  True if this device is valid, and False otherwise.
        """
        return bool(self.uuid)

    ###########################################################
    def updateSettings(self, settings):
        self.settings = settings

    ###########################################################
    def hasChanged(self, formerState, simpleCheck=False):
        """Checks if the current state is different from a former one, meaning
        the end-point might be reachable over different means.

        @param  formerState  The former state to compare against.
        @return              True if a change got detected.
        """

        if simpleCheck:
            return (
                (cmp(self.scopes, formerState.scopes) != 0) or
                (sorted(self.announcedOnvifIpAddrs) != sorted(formerState.announcedOnvifIpAddrs)) or
                (self.settings != formerState.settings)
            )

        if ((cmp(self.scopes, formerState.scopes) != 0) or
            (cmp(self.basicInfo, formerState.basicInfo) != 0) or
            (sorted(self.profiles) != sorted(formerState.profiles)) or
            (sorted(self.announcedOnvifIpAddrs) != sorted(formerState.announcedOnvifIpAddrs)) or
            (sorted(self.validOnvifIpAddrs) != sorted(formerState.validOnvifIpAddrs)) or
            (self.settings != formerState.settings) or
            (cmp(self.streamUris, formerState.streamUris) != 0)):

            return True
        return False


    ###########################################################
    def getFriendlyName(self, alwaysIncludeIp = False):
        """Get this device's friendly name.

        @param  alwaysIncludeIp  Include the IP addresses of this device
                                 with the friendly name.

        @return  name            This device's friendly name.
        """

        ipAddrs = []

        # Get the IP address...
        if alwaysIncludeIp:
            ipAddrs += ["--"]
            try:
                ipAddrs += [str(self.wsdiscoveryIp[0])]
            except:
                # We should NEVER get here; but if we do, we'll see it in the UI
                # since the device will have 'ipAddrs' next to it's name.
                ipAddrs = ['IP Unavailable']

        # Construct the friendly name from the device's basic info first; this
        # information should be more accurate and reliable than the getting the
        # device's information from its scopes information. However, some
        # cameras do not allow us to see its basic information without first
        # authenticating with a username and password.  If that happens, the
        # basicInfo will be an empty dict, and we'll need to pull a name and
        # model number from the scopes information we got from the probe request
        # response in device discovery...
        manufacturer = self.basicInfo.get('manufacturer', None)
        model = self.basicInfo.get('model', None)

        if not manufacturer:
            manufacturerList = self.scopes[_kOnvifUrl].get('name', [])
            if len(manufacturerList) > 0:
                manufacturer = manufacturerList[0]

        if not model:
            modelList = self.scopes[_kOnvifUrl].get('hardware', [])
            if len(modelList) > 0:
                model = modelList[0]

        camName = manufacturer if manufacturer else 'Unknown'
        camModel = model if model else 'Unknown'

        # It's possible for camera manufacturers to put the hardware number
        # in the name of the camera and vice-a-versa. Check for it, and
        # construct the friendly name accordingly...
        if camModel.lower() in camName.lower():
            friendlyName = camName.split()
        elif camName.lower() in camModel.lower():
            friendlyName = camModel.split()
        else:
            friendlyName = camName.split() + camModel.split()


        return ' '.join(friendlyName + ipAddrs).strip()

    ###########################################################
    def isAuthenticated(self):
        return self.authenticated

    ###########################################################
    def getLogId(self):
        return self.getFriendlyName(True) + " [" + self.uuid + "]"

    ###########################################################
    def getFailureReason(self):
        return self.lastFailureReason

    ###########################################################
    def getCredentials(self):
        return self.settings[0] if self.settings else None


    ###########################################################
    def asDict(self):
        """ Copies the state into a dictionary. For debugging/logging purposes.

        @return  States as dictionary.
        """
        d = {"uuid": self.uuid,
             "generation": self.generation,
             "wsdiscoveryIp": self.wsdiscoveryIp,
             "scopes": self.scopes,
             "basicInfo": self.basicInfo,
             "friendlyName": self.getFriendlyName(True),
             "announcedOnvifIpAddrs": self.announcedOnvifIpAddrs,
             "validOnvifIpAddrs": self.validOnvifIpAddrs,
             "profiles": self.profiles,
             "streamUris": self.streamUris
        }

        return copy.deepcopy(d)


###############################################################################
class OnvifDevicePoll(object):
    """ Does the polling on a specific device, meaning issuing HTTP requests to
    get date+time, profiles and streaming URIs. To be run by a thread-pool.
    """

    ###########################################################
    def __init__(self, state, callbacks, logger, forceNotify):
        """ Constructor.

        @param  state      The state known so far. Can be what just popped out
                           of a discovery, or something which needs refreshing.
        @param  callbacks  Where to report back after execution. Usually
                           implemented by the device manager which holds
                           everything together.
        @param  logger     Logger to use for reporting.
        """

        super(OnvifDevicePoll, self).__init__()
        self._logger = MsgPrefixLogger(logger, "DEVPLL(%s,%d) - " %
                                       (state.getFriendlyName(True), state.generation))
        self._state = copy.deepcopy(state)
        self._state.updateSettings(callbacks._deviceSettings.get(state.uuid, None))
        self._callbacks = callbacks
        self._forceNotify = forceNotify

        # NOTE: we could in theory pass in formerly known time offset via the
        #       settings, since some devices want it for any HTTP request being
        #       made to their ONVIF interface. Could. Not that we should.
        self._timeOffset = 0


    ###########################################################
    def isValid(self):
        """Checks if this device is valid.

        @return  isValid  True if this device is valid, and False otherwise.
        """
        return self._state.isValid()

    ###########################################################
    def run(self):
        """ To run the poll. This is a one time shot.
        """
        try:
            self._logger.debug("Querying the device " + str(self._state.announcedOnvifIpAddrs))
            self._runUnsafe()
        except:
            self._logger.error("uncaught poll error!", exc_info=True)


    ###########################################################
    def _sendOnvifRequest(self, op, address, httpServicePaths,
                            msgToSend, onvifAction, logger,
                            onlySecure=False):
        retval = None
        status = None

        host = address[0]
        port = address[1]
        credentials = self._state.getCredentials()

        logger.debug("%s - starting" % op)
        for httpServicePath in httpServicePaths:
            status = None
            if credentials:
                shouldTryWithAuth = [True] if onlySecure else [False, True]
            else:
                shouldTryWithAuth = [False]
            for tryWithAuth in shouldTryWithAuth:
                if tryWithAuth:
                    logger.debug("%s - trying with auth" % op)
                    msgToSend = _addSecurityHeader(msgToSend, credentials,
                                             self._timeOffset)
                xml = msgToSend.toxml("UTF-8")
                status, result = self._httpRequest(
                    host, xml, port=port,
                    headers=self._getOnvifHttpHeaders(onvifAction),
                    path=httpServicePath,
                    logger=logger,
                )
                if status in [_kHttpBadRequest, _kHttpUnauthorized]:
                    if tryWithAuth or credentials is None:
                        logger.error("%s failed (%s)" % (op, status))
                    continue

                # successful request amounts to authentication
                if (tryWithAuth or credentials is None and onlySecure) and \
                   (status == _kHttpOk):
                    self._state.authenticated = True
                break
            if status: # HACK: any status counts as "address reachable"
                if address not in self._state.validOnvifIpAddrs:
                    self._state.validOnvifIpAddrs.append(address)
            if status == _kHttpOk:
                retval = vitaParseXML(result)
                logger.debug("%s success" % op)
                break
            elif status in [_kHttpBadRequest, _kHttpUnauthorized]:
                logger.warning(
                    "%s failed (%s, Sender is not authorized)" % (op, status)
                )
            elif status in [_kHttpServiceUnavailable, _kHttpUrlNotFound]:
                logger.warning(
                    "%s failed (%s, device does not support the '%s' ONVIF "
                    "service path in the HTTP POST request)" %
                    (op, status, httpServicePath)
                )
            else:
                logger.error("%s failed (%s, %s)" % (op, status, result))

        if retval is None:
            self.lastFailureReason = kHttpRequestError
        return retval

    ###########################################################
    def _processFaultCode(self, msg):
        # Check if the device gave us an error code.
        faultCode = _parseFaultCode(msg, self._logger)
        if faultCode == kFaultSubcodeNotAuthorized:
            logger.error("Incorrect username or password!")
            # and thus authentication is negated
            self.authenticated = False
        elif faultCode is not None:
            logger.error("Fault code received: %s" % faultCode)

        if failtCode is not None:
            self.lastFailureReason = faultCode

    ###########################################################
    def _runUnsafe(self):
        """ Internal run. May throw any exception, hence the name.
        """
        try:
            selectedIp = None if self._state.settings is None else self._state.settings[1]
            credentials = self._state.getCredentials()
            if selectedIp:
                ips = [selectedIp]
            else:
                ips = self._state.announcedOnvifIpAddrs

            self._logger.debug("trying IPs %s, credentials %sexist" % (str(ips), "do not " if credentials is None else "" ))
            for ip in ips:
                logger = MsgPrefixLogger(self._logger, "%s - " % str(ip))

                # According to the ONVIF specs, the HTTP POST url must be
                # present and of the form
                # "http://<device_IP>:80/<onvif_service_path>" where
                # "onvif_service_path" is the determined by the type of service
                # we are requesting from the device. Unfortunately, there are
                # many devices out there that are not compliant, and so might
                # respond with various HTTP errors because the path we provide
                # in the POST URL is unavailable or the service doesn't exist.
                # To get around that, we try to call the ONVIF method with many
                # ONVIF service fallback paths to see if we can successfully
                # communicate with the camera. This comment applies to all four
                # of the ONVIF action methods that we call to the device below.
                httpServicePaths = \
                    [_kDeviceServicePath] + _kDeviceServiceFallbackPaths

                msg = self._sendOnvifRequest("getSystemDateAndTime", ip,
                                        httpServicePaths,
                                        _createGetSystemDateAndTimeRequest(),
                                        _kOnvifActionGetSystemDateAndTime,
                                        logger )
                if msg is not None:
                    utcTime = _parseGetSystemDateAndTimeResponse(msg, self._logger)
                    if utcTime is not None:
                        deviceTime = calendar.timegm(utcTime)
                        now = time.time()
                        self._timeOffset = deviceTime - now
                        logger.debug("time offset is %d" % self._timeOffset)

                msg = self._sendOnvifRequest("getDeviceInformation", ip,
                                        httpServicePaths,
                                        _createGetDeviceInformationRequest(),
                                        _kOnvifActionGetDeviceInformation,
                                        logger )
                if msg is not None:
                    deviceBasicInfo = _parseGetDeviceInformationResponse(msg, self._logger)
                    if deviceBasicInfo:
                        self._state.basicInfo = deviceBasicInfo
                        logger.info("deviceBasicInfo=%s" % str(deviceBasicInfo))

                # we only poll the exact information if we have credentials and
                # a preferred IP address, because that's what we want ...
                if not credentials or selectedIp != ip:
                    continue

                profiles = []
                httpServicePaths = \
                    [_kMediaServicePath] + _kMediaServiceFallbackPaths + \
                    [_kDeviceServicePath] + _kDeviceServiceFallbackPaths
                msg = self._sendOnvifRequest("getProfiles", ip,
                                        httpServicePaths,
                                        _createGetProfilesRequest(),
                                        _kOnvifActionGetProfiles,
                                        logger,
                                        True)
                if msg is not None:
                    profiles = _parseGetProfilesResponse(msg, self._logger)
                logger.info('%d profiles retrieved: %s' % (len(profiles), str(profiles)))
                self._state.profiles = profiles
                if len(profiles) == 0:
                    if msg is not None:
                        self._processFaultCode(msg)
                    continue



                for profile in self._state.profiles:
                    for transport in _kOnvifTransportTypes:
                        logger.info("getting stream URI for '%s' (%s) ..." %
                                    (profile, transport))
                        streamType = _kOnvifStreamTypes[0]
                        streamUri = None
                        msg = self._sendOnvifRequest("getStreamUri", ip,
                                                httpServicePaths,
                                                _createGetStreamUriRequest(streamType, transport, profile[1]),
                                                _kOnvifActionGetStreamUri,
                                                logger,
                                                True)
                        if msg is not None:
                            streamUri = _parseGetStreamUriResponse( msg, self._logger )
                            if streamUri is None:
                                # Check if the device gave us a fault code.
                                self._processFaultCode(msg)
                            else:
                                logger.info(
                                    "stream URI '%s' (profile='%s', transport='%s')" %
                                    (self._maskUsernameAndPassword(streamUri),
                                     profile, transport))
                                self._state.streamUris[profile] = (streamUri, transport)
                                break

            state = copy.deepcopy(self._state) # not really necessary, but...
            self._callbacks.onPollDone(state, self._forceNotify)
        except:
            # if we cannot process what's coming from a device then there is no
            # reason to repeat the request on a different IP address ...
            self._logger.error(traceback.format_exc())
            self._callbacks.onPollDone(self._state.uuid,
                                       self._forceNotify,
                                       sys.exc_info()[1])


    ###########################################################
    def _maskUsernameAndPassword(self, url):
        """Replaces username and password from the given url with 'xxxx:xxxx'.

        @param   url     URL that needs username and password masked.
        @return  result  URL after username and password have been replaced.
        """
        if url:
            # Strip out username and password from the URL...
            scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
            parts = netloc.split('@', 1)
            netloc = parts[-1]
            if len(parts) == 2:
                netloc = "xxxx:xxxx@"+netloc
            url = urlparse.urlunsplit((scheme, netloc, path, query, fragment))
        return url


    ###########################################################
    def _getOnvifHttpHeaders(self, actionUri=None):
        """Returns a dict with "Content-Type" HTTP header field populated with
        necessary values for compliance with ONVIF.

        @param      actionUri   The ONVIF function URI being performed. If
                                action is None, the action value will be omitted
                                from the "Content-Type" header field.
        @return     result      A dict containing the "Content-Type" HTTP
                                header, meant to be used by an HTTP post command.
        """
        contentTypeValue = _kContentTypeFieldSeparator.join([
            _kApplicationSoapXML, _kCharSetUTF8,
        ])
        if actionUri is not None:
            contentTypeValue = _kContentTypeFieldSeparator.join([
            contentTypeValue, _kActionValue % actionUri,
        ])
        return {_kContentTypeField: contentTypeValue}


    ###########################################################
    def _httpRequest(self, host, body, scheme="http", port=80,
                     path=_kDeviceServicePath, headers={},
                     logger=None):
        """ To make an HTTP/POST request to the ONVIF service.

        NOTE: yes, we do support HTTPS, but does OnVIF really encourage that?
              If so, how would an IP-based camera create a certificate without
              the validation not going to fail? Well, Python does not validate,
              but that's not the point...

        @param  host    IP or host name to connect to.
        @param  body    The data to POST.
        @param  scheme  Either "http" or "https".
        @param  port    Which port to connect to.
        @param  path    Path for Onvif services. Should be "onvif/<service_here>"
        @param  headers A dict that contains HTTP header fields for the HTTP
                        request.
        @return         (status-code,response-data) or (None,error-message)
        """
        if logger is None:
            logger = self._logger

        hc = HttpClient(_kHttpTimeout)
        # Whenever we speak to a device using the ONVIF service, we *MUST* use
        # "/onvif/device_service" as the path in the http request. This lets
        # the device know that we are about to make an ONVIF request.
        url = "%s://%s:%d/%s" % (scheme, host, port, path)
        status, data, _ = hc.post(url, body, headers)
        # Do not wait for garbage collector to free a socket-consuming object
        # This may help with "out of file handles" exception we are seeing on Mac
        del hc
        if status is not None:
            logger.debug("response status %d, read %d bytes of data" %
                              (status, len(data)))
            return status, data
        return None, "HTTP request failed (%s)" % data


    ###########################################################
    def getState(self):
        return copy.deepcopy(self._state)



###############################################################################
class OnvifDiscovery(object):

    def __init__(
            self, logger, timeout, manager, generation, numProbes=1,
            probeDelay=_kOnvifMaxUdpDelay,
    ):
        self._logger = MsgPrefixLogger(logger, "DEVDSC(%d) - " % generation)
        self._timeout = timeout
        self._manager = manager
        self._generation = generation
        self._devicesDiscovered = set()
        # Maximum number of probe requests our client wants to send...
        self._probeMaxRepeat = numProbes
        # We will always do at least one probe request...
        self._probeCurRepeat = 1
        # Time, in seconds as float or int, to wait till our next probe
        # request...
        self._probeDelay = probeDelay


    ###########################################################
    def _getLocalIPAddresses(self):
        """Return a list of IPv4 addresses for this computer.

        Doesn't every return 0.0.0.0, which is what I saw on Windows XP when
        an interface wasn't connected to anything.

        @return myIpList  A list of dictionaries, where each dict is contains
                          at least { 'addr': ipAddress, 'netmask': netmask }
        """
        addrs = []
        try:
            for ifName in netifaces.interfaces():
                ifAddresses = netifaces.ifaddresses(ifName)
                if netifaces.AF_INET in ifAddresses:
                    for inetAddress in ifAddresses[netifaces.AF_INET]:
                        addr = inetAddress.get('addr')
                        if addr != '0.0.0.0':
                            try:
                                socket.inet_aton(addr) # IP4 for now
                            except:
                                continue
                            addrs.append(inetAddress)
        except:
            self._logger.error(
                "Could not retrieve local IP addresses!", exc_info=True
            )
        return addrs


    ###########################################################
    def run(self):
        """ To run the poll. To be called only once per instance.
        """
        socks = []
        try:
            self._runUnsafe(socks)
        except:
            self._logger.error(
                "Uncaught discovery error: %s (%s)", exc_info=True
            )
        finally:
            self._manager.onDiscoveryDone(self._devicesDiscovered)
        for sock in socks:
            try:
                sock.close()
            except:
                pass
        return

    ###########################################################
    def _runUnsafe(self, socks):
        """ Internal run. May throw any exception, hence the name.
        """
        sock = None

        ipAddrs = self._getLocalIPAddresses()
        if not ipAddrs:
            self._logger.warn("No local IP addresses found.")
            return
        self._logger.debug("IP addresses found %s" % ipAddrs)

        socks = []
        for ipAddr in ipAddrs:
            ip = ipAddr['addr']
            self._logger.debug("creating multicast socket for %s..." % ip)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                socket.inet_aton(ip))
                sock.bind((ip, socket.INADDR_ANY))
                sock.setblocking(False)
                socks.append(sock)
            except:
                self._logger.error("cannot create multicast!", exc_info=True)
                try:
                    sock.close()
                except:
                    pass
        if not socks:
            self._logger.warn("no multicast socket could be created")
            return

        msgUuids = []

        for probeWithTypes in [True, False]:

            # Message ID's format is supposed to be "uuid:<uuid4_string_value_here>"
            msgUUID = "uuid:" + str(uuidlib.uuid4())
            msgUuids.append(msgUUID)
            doc = _createProbeRequest(msgUUID, probeWithTypes)
            probeXml = doc.toxml("UTF-8")

            self._probeCurRepeat = 1

            recvSocks = []
            for sock in socks:
                self._logger.debug(
                    "sending multicast %s/%s type=%s (%s) now ..." %
                    (
                        str(self._probeCurRepeat),
                        self._probeMaxRepeat,
                        2 if probeWithTypes else 1,
                        msgUUID
                    )
                )
                try:
                    sock.sendto(probeXml, _kMulticastAddr)
                    recvSocks.append(sock)
                except:
                    self._logger.error(
                        "Failed to send probe request!", exc_info=True
                    )
            if not recvSocks:
                self._logger.error("All probe requests failed to send!!")
                return
            self._probeCurRepeat += 1

            # Init variables for receiving probe responses and resending probe
            # requests...
            now = time.time()
            tmout = now + self._timeout
            readSockTmout = min(tmout - now, self._probeDelay)
            lastSelectError = None
            self._logger.debug("waiting on %d sockets ..." % len(recvSocks))

            # Send and recieve until we reach our timeout...
            while now <= tmout:

                # Check if we need to do a resend of probe request.
                # Note: this will probably not run the first time we enter this
                #       while loop, since we will have reached this too quickly for
                #       "now > readSockTmout" to be "True".
                if self._probeCurRepeat <= self._probeMaxRepeat:
                    if now > readSockTmout:
                        for sock in recvSocks:
                            try:
                                self._logger.debug(
                                    "sending multicast %s/%s type=%s (%s) now ..." %
                                    (
                                        str(self._probeCurRepeat),
                                        self._probeMaxRepeat,
                                        2 if probeWithTypes else 1,
                                        msgUUID
                                    )
                                )
                                sock.sendto(probeXml, _kMulticastAddr)
                            except:
                                self._logger.error(
                                    "Failed to send probe request!",
                                    exc_info=True
                                )
                        # Bump this up by 1, even if some or all of the sockets
                        # failed to send. We never guaranteed that the repeated
                        # probe request would be successful...
                        self._probeCurRepeat += 1
                        # Set the next time we want to send the probe request...
                        readSockTmout = max(
                            0.0,
                            min(tmout - now, self._probeDelay)
                        )
                else:
                    # No more sending probe requests, so give the "select" command
                    # all the time they want within our timeout time...
                    readSockTmout = tmout - now

                # Check for any probe responses and process any that we receive...
                try:
                    readSocks, _, _ = select.select(recvSocks, [], [], readSockTmout)
                except:
                    lastSelectError = sys.exc_info[1]
                    readSocks = []
                    time.sleep(.1) # avoid hot-looping
                for sock in readSocks:
                    try:
                        payload, endpoint = sock.recvfrom(_kDescriptionBufsize)
                        if self._manager.deviceBlacklisted(endpoint):
                            # ignore devices that we have blacklisted due to invalid responses from them
                            continue
                        self._logger.debug("payload from %s: %s..." % (endpoint, payload[:16]))

                        # for each device, we get its device UUID, friendly name,
                        # and all of its service addresses. There will usually be
                        # only one service address, but there can be more. The
                        # "uuid" is the message UUID that the device originally
                        # responded to. We use this to ensure the device responded
                        # to the most recent probe request, and not an earlier one.
                        xml = vitaParseXML(payload)
                        parsedProbeResponse = _parseProbeResponse(xml, self._logger)
                        if parsedProbeResponse is None:
                            continue
                        uuid, deviceUuid, xAddrs, scopes = parsedProbeResponse
                        if uuid is None:
                            continue
                        if uuid not in msgUuids:
                            self._logger.warn("UUID mismatch (%s)" % uuid)
                            continue
                        self._logger.debug("response match (uuid=%s)" % uuid)
                        if not deviceUuid:
                            self._logger.warn("No device UUID provided in probe response from %s (%s)" % ( str(endpoint), str(payload)))
                            self._manager.blacklistDevice(endpoint)
                            continue

                        deviceState = OnvifDeviceState(self._generation,
                                    endpoint, deviceUuid, xAddrs, scopes,
                                    self._manager._deviceSettings.get(deviceUuid, None),
                                    self._logger)
                        if not deviceState.isValid():
                            self._logger.warn( "invalid device state not accepted: %s (payload=%s, endpoint=%s)" % ( str(deviceState), str(payload), str(endpoint)))
                            continue
                        self._manager.onDeviceDiscovered(deviceState)
                        self._devicesDiscovered.add(deviceState.uuid)
                    except Exception:
                        self._logger.error("receive error!", exc_info=True)
                now = time.time()
            if lastSelectError:
                self._logger.error("last select error: %s" % lastSelectError)


###############################################################################
class OnvifDeviceManager(object):
    """This class searches for, and creates a list of, devices on the local
    network that comply with the ONVIF protocol. It also implements callbacks
    for OnvifDevicePoll instance launched by it.
    """

    ###########################################################
    def __init__(self, logger, threadPool):
        """OnvifDeviceManager constructor.

        @param logger      The logging instance to use.
        @param threadPool  Thread-pool to use to run all of the blocking I/O.
        """
        super(OnvifDeviceManager, self).__init__()
        self._logger0 = logger
        self._logger = MsgPrefixLogger(logger, "DEVMNG - ")
        self._threadPool = threadPool
        self._pendingPolls = 0
        self._currentDiscovery = None
        self._deviceStates = {}
        self._deviceLastSeenTime = {}
        self._lock = threading.RLock()
        self._generationCounter = -1
        self._deviceSettings = {}
        self._lastPollDevices = {}
        self._pendingForcedPolls = {}

        # Devices which sent an invalid response and were sent to timeout
        self._blacklistedDevices = {}
        self._blacklistedDevicesMtx = threading.Lock()
        # Lets say timeout is 30 seconds
        self._blacklistTimeout = 30

    ###########################################################
    def blacklistDevice(self, device):
        self._blacklistedDevicesMtx.acquire()
        try:
            self._blacklistedDevices[device] = time.time()
        finally:
            self._blacklistedDevicesMtx.release()

    ###########################################################
    def deviceBlacklisted(self, endpoint):
        self._blacklistedDevicesMtx.acquire()
        try:
            if endpoint in self._blacklistedDevices:
                if time.time() - self._blacklistedDevices[endpoint] < self._blacklistTimeout:
                    # This device is still in timeout
                    return True
                else:
                    # Lets give this device another chance
                    del self._blacklistedDevices[endpoint]
        finally:
            self._blacklistedDevicesMtx.release()
        return False

    ###########################################################
    def activeSearch(self, uuid=None, needsNotify=False):
        """ Runs a search, meaning either discovery and polls on what shows up,
        or just a poll on a particular device. If a discovery and/or polls are
        already pending nothing happens.

        @param  uuid  The device UUID, or None for a full discovery/poll cycle.
        @param  needsNotify  Forces the onvif device object to appear as though
                             it "changed" so that it eventually shows up in the
                             return values of pollForChanges(), whether or not
                             it actually has any relevant changes.
        """
        self._lock.acquire()
        try:
            self._logger.debug("active search (%s,%s) ..." % (str(uuid), str(needsNotify)))

            # the generation gets bumped, but not stored for the state(s) yet,
            # until discovery/poll reports back to us ...
            self._generationCounter += 1
            generation = self._generationCounter

            # Get the device that we need to do a poll on, if it exists...
            deviceState = self._deviceStates.get(uuid, None)

            if deviceState is not None:
                deviceState.generation = generation
                self._schedulePoll(deviceState, needsNotify)
            else:
                # Schedule a discovery for ONVIF devices...
                self._currentDiscovery = OnvifDiscovery(
                    self._logger0, _kDiscoveryTimeout, self, generation,
                    _kWsDiscoveryMulticastUdpMaxRepeat
                )
                self._threadPool.schedule(self._currentDiscovery)

        finally:
            self._lock.release()


    ###########################################################
    def _schedulePoll(self, deviceState, needsNotify=False):
        """ To launch a poll on a particular device.

        @param  deviceState  Current state of that device.
        """
        devicePoll = OnvifDevicePoll(deviceState, self, self._logger0, needsNotify)
        self._logger.info("scheduling search poll for device %s" % deviceState.getLogId())
        self._threadPool.schedule(devicePoll)
        self._pendingPolls += 1


    ###########################################################
    def pollForChanges(self):
        """ To check whether devices have changed for vanished since the last
        time the method has been called. New devices also count as changed.
        Nothing will change of course if not some kind of discovery and/or poll
        has been issued.

        @return  (changed,gone) as string lists.
        """
        self._lock.acquire()
        try:
            # get the current devices in a map
            currentDevices = self._deviceStates
            goneUuids = []
            changedUuids = []
            addedUuids = []
            # which of the formerly known devices are still there?
            for uuid, oldDevice in self._lastPollDevices.iteritems():
                currentDevice = currentDevices.get(uuid, None)

                if currentDevice is None:
                    goneUuids.append(uuid)
                # has anything significant changed?
                elif currentDevice.hasChanged(oldDevice):
                    changedUuids.append(uuid)
                elif self._pendingForcedPolls.get(uuid, False):
                    # forced notification
                    self._logger.debug("Forcing notification for %s" % uuid)
                    self._pendingForcedPolls.pop(uuid)
                    changedUuids.append(uuid)

            # also look for new devices
            for uuid, _ in currentDevices.iteritems():
                if self._lastPollDevices.get(uuid, None) is None:
                    addedUuids.append(uuid)
            # log devices when a change is detected
            self._logDevices("added", addedUuids, currentDevices)
            self._logDevices("changed", changedUuids, currentDevices)
            self._logDevices("gone", goneUuids, self._lastPollDevices)
            # remember the current states for the next poll call
            self._lastPollDevices = self.getDevices()
            return set(changedUuids).union(addedUuids), set(goneUuids)
        finally:
            self._lock.release()


    ###########################################################
    def getDevice(self, uuid):
        """ Get the state for a device.

        @param  uuid  The UUID the device was discovered under.
        @return       Device state (copy of such), or None if not found.
        """
        self._lock.acquire()
        try:
            result = self._deviceStates.get(uuid, None)
            if result:
                result = copy.deepcopy(result)
            return result
        finally:
            self._lock.release()

    ###########################################################
    def _logDevices(self, pref, uuids, devDict):
        """ Log the states for all devices.
        """
        for uuid in uuids:
            self._logger.info("DEVICE (%s): %s" %
                               (pref, pprint.pformat(devDict[uuid].asDict())))

    ###########################################################
    def getDevices(self):
        """ Get the states for all devices.

        @return  Dictionary {uuid,state} of all devices. All copies.
        """
        self._lock.acquire()
        try:
            result = copy.deepcopy(self._deviceStates)
            return result
        finally:
            self._lock.release()


    ###########################################################
    def setDeviceSettings(self, uuid, credentials, selectedIp):
        """ Brings in settings for a particular device, so polls can be
        completed. Settings are NOT part of the state, the manager ensures that
        they become effective.

        @param  uuid         The UUID of the device to get the settings.
        @param  credentials  Credentials (username,password) for determining
                             profiles and stream URIs (and for some devices
                             getting the date and time).
        """
        self._lock.acquire()
        try:
            # Need to do this because for some reason, selectedIp comes in as a
            # list type, instead of a tuple.
            selectedIp = tuple(selectedIp)
            settings = (credentials, selectedIp)
            self._deviceSettings[uuid] = settings
            self._logger.info("new settings (%s,%d,%s)" %
                              (credentials[0], len(credentials[1]),
                               str(selectedIp)))
        finally:
            self._lock.release()
        return True


    ###########################################################
    def onDeviceDiscovered(self, deviceState):
        """ Called by a discovery run when a device showed up due to a response.

        @param  deviceState  State of the discovered device. Duplicates will
                             be ignored. Any existing state of it (even if fully
                             polled before) will be discarded.
        """
        self._lock.acquire()
        try:
            self._deviceLastSeenTime[deviceState.uuid] = time.time()
            existingDevice = self._deviceStates.get(deviceState.uuid, None)
            if existingDevice is not None:
                # Same or older generation? If so we discard this device state.
                if existingDevice.generation >= deviceState.generation or \
                        not deviceState.hasChanged(existingDevice, True):
                    self._logger.debug("obsolete discovery for device %s" % deviceState.getLogId())
                    return

            self._deviceStates[deviceState.uuid] = deviceState

            if existingDevice is None:
                # Get all of the information of new devices...
                self._schedulePoll(deviceState)

        finally:
            self._lock.release()


    ###########################################################
    def onPollDone(self, result, forceNotify=False, error=None):
        """ Called if a poll is done. If an error happened the device will be
        removed.

        @param  result  Either updated device state or on error just the UUID.
        @param  error   Error message or None if the poll succeeded.
        """
        self._lock.acquire()
        try:
            self._pendingPolls -= 1

            if error:
                uuid = result
                try:
                    self._removeUuid(uuid)
                except KeyError:
                    pass
                self._logger.warning(
                    "poll error (%s), removed device state %s" % (error, uuid))
                return

            deviceState = result
            uuid = deviceState.uuid
            existingDevice = self._deviceStates.get(uuid, None)
            if existingDevice is None:
                # this is odd, device state should be there ready
                self._logger.warn("device not found post-poll (%s)" % deviceState.getLogId())
            elif not forceNotify:
                if existingDevice.generation > deviceState.generation or \
                   existingDevice.hasChanged(deviceState, True):
                    # TODO: slight matter for discussion: in theory we could use
                    # that state if the old one never got poll-completed ...
                    self._logger.debug("obsolete poll for device %s" % deviceState.getLogId())
                    self._deviceLastSeenTime[uuid] = time.time()
                    return
            # Store the new official device state.
            self._deviceStates[uuid] = deviceState
            self._deviceLastSeenTime[uuid] = time.time()

            # There is an outstanding active poll for this uuid; force a notification
            if forceNotify:
                self._pendingForcedPolls[uuid] = True

            self._logger.info("device %s poll completed" % deviceState.getLogId())
        finally:
            self._lock.release()


    ###########################################################
    def onDiscoveryDone(self, devicesDiscovered):
        """ Called when a discovery completed, meaning it waited long enough for
        responses to come back and has reported everyting it received.

        @param  devicesDiscovered  A set of UUID's of devices that have been
                                   discovered on the network during this
                                   discovery.
        """
        self._lock.acquire()
        try:
            # Find out if we have any devices that weren't discovered.
            goneUuids = \
                set(self._deviceStates.keys()).difference(devicesDiscovered)

            # Remove them from our dictionary of current device states.
            for uuid in goneUuids:
                self._removeUuid(uuid)

            # Setting this to None to indicate discovery is finished.
            self._currentDiscovery = None
        finally:
            self._lock.release()


    ###########################################################
    def _removeUuid(self, uuid):
        """Give devices a chance to be discovered. It's possible that they are
        busy, or they do not respond to all of the types of messages we send
        out.

        @param  uuid    The UUID of the device
        """
        self._lock.acquire()
        try:
            if self._deviceStates.has_key(uuid):
                diff = time.time()-self._deviceLastSeenTime[uuid]
                if diff > _kDeviceTimeout:
                    del self._deviceStates[uuid]
                    del self._deviceLastSeenTime[uuid]
                    self._logger.info("deleted=%s after not seeing for %.02s" % (uuid,diff))
        finally:
            self._lock.release()
