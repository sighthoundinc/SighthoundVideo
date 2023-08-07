#!/usr/bin/env python

#*****************************************************************************
#
# Upnp.py
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

# Python imports...
#import errno
import base64
import httplib
import pprint
import random
import re
import select
import socket
import struct
import sys
import StringIO
import time
import traceback
import urllib
import urlparse
import logging
import copy
# Common 3rd-party imports...
import netifaces

# Toolbox imports...
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.networking.XmlUtils import vitaParseXML

# Local imports...


# Patch urlparse to make upnp:// behave just like http://
# ...a bit of a hack, but really handy to use urlparse!
#
# Note: any program that imports Upnp.py will automatically get this
# functionality...
if 'upnp' not in urlparse.uses_netloc:
    urlparse.uses_relative.append('upnp')
    urlparse.uses_netloc.append('upnp')
    urlparse.uses_params.append('upnp')
    urlparse.uses_query.append('upnp')
    urlparse.uses_fragment.append('upnp')


# Constants...

kSearchTargetAll = "ssdp:all"

# Our version of UPnP.  We only do 1.0 (rather than 1.1), because it's simpler
# and seems sufficient.  ...and that's what all of our cameras do.
_kUpnpMajorVersion = 1
#_kUpnpMinorVersion = 0

# This is the IP and port that we do multicasting on (and listening on) for
# UPNP...
_kMulticastIp = "239.255.255.250"
_kMulticastPort = 1900

# The TTL should be 4 according to UPnP 1.0, but should be configurable
# (at the moment, we don't do that).  Note that UPNP 1.1 says it should be 2.
_kMulticastTTL = 4

# Devices will randonly delay between 0 and this many deconds before responding
# to reduce network congestion...
_kMaxResponseDelay = 3

# The magic "search request" packet that we'll send out for discovery.  It's
# pretty much hardcoded, but we'll make it use the above constants to be nice.
_kSearchRequest = (
    """M-SEARCH * HTTP/1.1\r\n"""
    """Host: %(hostIp)s:%(hostPort)d\r\n"""
    """MAN:"ssdp:discover"\r\n"""
    """ST: %(searchTarget)s\r\n"""
    #"""ST: upnp:rootdevice\r\n"""  # Won't get embedded devices, I think...
    """MX: %(mx)d\r\n"""
    """\r\n"""
) % dict(
    hostIp=_kMulticastIp,
    hostPort=_kMulticastPort,
    mx=_kMaxResponseDelay,
    searchTarget="%(searchTarget)s",   # Filled in later...
)

# HTTP over UDP must fit within a single packet.  Spec says that requests
# should really fit in 512 bytes, but I decided to be a little more
# conservative.  Note that mirandy code uses 1024.
_kMaxUdpPacketSize = 2048

# We will repeat our search a few times with a random delay between...
# HTTPUDP RFC draft (which is expired) suggests 3 retries between 0 and 10
# seconds.  That seems like overkill.  Also: UPnP 1.0 architecture doc says
# we should probably wait longer than the MX delay.  ...so I've toned things
# down a little bit...
_kHttpUdpMaxRetries = 2
_kHttpUdpMinRetryInterval = _kMaxResponseDelay + 1
_kHttpUdpMaxRetryInterval = _kMaxResponseDelay + 8


# The magic "description request" packet.
_kDescriptionRequest = (
    """GET %(path)s HTTP/1.1\r\n"""
    """HOST: %(netloc)s\r\n"""
    """ACCEPT-ENCODING: identity\r\n"""
    """CONNECTION: close\r\n"""         # Don't use persistent connections!
                                        # ...needed for my state machine...
    #"""ACCEPT-LANGUAGE: en-US\r\n"""   # Optional if we want to request a lang.
    """\r\n"""
)

# We are allowed to fail twice before we give up...
_kMaxDescriptionFailures = 4

# The buffer size we give to recv()
_kDescriptionBufsize = 4096

# Our timeout for http requests when getting descriptions...
_kHttpTimeout = 15

# We'll make sure that we get this many chances at polling before timing out
# HTTP...
_kHttpMinPolls = 8


# We'll actually expire stuff this many seconds later than we're supposed to.
# This means that if someone (like ACTi cameras) sends out their announcements
# right at expiration time, we won't expire them just before their renewal
# notice.
_kExpireSlopSeconds = 60


# We'll append this suffix to UPNP host names...
# ...should be all lowercase, since host names are case insensitive.
# Note that the USN part of the hostname is encoded very specifically.  First,
# it is encoded into UTF-8, then made base32.
_kUpnpHostnameSuffix = '.vitaupnp.'


##############################################################################
class ControlPointManager(object):
    """This class handles functions associated with being a control point.

    A control point, in UPNP terminology, is the thing that looks for / uses
    UPNP devices.

    This class is really about the "discovery" and "description" part of UPNP.
    No support for "control" and "eventing" is provided.
    """

    ###########################################################
    def __init__(self, logger):
        """ControlPointManager constructor."""
        super(ControlPointManager, self).__init__()

        self._logger = logger if logger is not None else logging.getLogger()

        # We will search several times per interface, since UDP is supposed
        # to be unreliable.  This dict is keyed by IP address and contains
        # a dict with keys 'numSearches' and 'nextSearchTime'
        # ...it is initialized to [1, time.time() + rand(...)] on the 1st search
        self._searchCountDict = {}

        # A dictionary keyed by USN, whose values are UpnpDevice objects.
        self._deviceDict = {}

        # A dictionary like self._deviceDict, but contains devices that we
        # haven't gotten a descriptor for yet.
        self._pendingDeviceDict = {}

        # Setup our passive and active sockets...
        # ...request sockets are keyed by IP address...
        try:
            self._passiveSock = self._createPassiveSocket()
        except socket.error:
            print >>sys.stderr, "Couldn't open UPNP listening socket."
            self._passiveSock = None
        self._requestSocks = {}

        # Add all of our IP addresses, which will start searching...
        self._checkForIpChanges()


    ###########################################################
    def _createPassiveSocket(self):
        """Returns the socket that we'll listen to for multicast events.

        IMPORTANT: This won't actually listen on our interfaces.  You should
        call _maintainPassiveSocket() to add initial interfaces and then
        whenever the set of IP addresses changes.

        @return passiveSock  Our passive sockets.
        """
        # Make our socket...
        passiveSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                    socket.IPPROTO_UDP)

        # Bind to the port that we care about.  Say that we're OK if someone
        # else on the compuer is also bound to that port (we're OK reusing),
        # since we're just listening.
        #
        # Including the multicast IP address seems important on Mac (though most
        # samples don't have it), since it seems to make SO_REUSEADDR behave
        # like SO_REUSEPORT.  ...and SO_REUSEADDR is supposed to be portable.
        # Note that putting the address breaks on Windows XP and 7, so don't
        # do it there.
        passiveSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sys.platform == 'win32':
            passiveSock.bind(("", _kMulticastPort))
        else:
            passiveSock.bind((_kMulticastIp, _kMulticastPort))

        # Just in case someone is multicasting from our own machine, add loop
        # mode in...
        try:
            passiveSock.setsockopt(socket.IPPROTO_IP,
                                   socket.IP_MULTICAST_LOOP, 1)
        except socket.error:
            # Throw in an assert failure; failing isn't super terrible, tho,
            # so the following could be relaced with 'pass' if it's a problem...
            assert False, "Couldn't set multicast loop mode..."

        # Don't add to inaddr_any.  It will throw an exception on XP if there
        # are no active interfaces...

        # Note:
        # - Much sample code sets the TTL.  We don't do this on our passive
        #   socket because we'll only be using it for listening.
        # - Much sample code sets the IP_MULTICAST_IF.  ...but that also only
        #   affects sending.  ...and we're not sending on this socket.

        return passiveSock


    ###########################################################
    def _maintainPassiveSocket(self, passiveSock, oldIpSet, newIpSet):
        """This should be called periodically whenever our own IP changes.

        It should also be called once right after creating our passive socket
        with oldIpList equal to [].

        This is trying to account for the fact that a machine may have multiple
        interfaces that may be appearing and disappearing at various times.
        Many machines have WiFi and Ethernet, so this is pretty common.

        @param  passiveSock  The passive socket that was returned above.
        @param  oldIpSet     A set of old IP addresses.
        @param  newIpSet     A set of new IP addresses.
        """
        # Some background on what this function is doing:
        #
        # Really, we want to just tell the OS to give us multicast events on
        # _all_ interfaces.  You'd think there'd be a way to do that, and much
        # of the sample code seems to use INADDR_ANY as the parameter to
        # IP_ADD_MEMBERSHIP, implying that they are expecting to do just that.
        # ...but on my Mac (OS X version 10.5.8), that didn't seem to work.
        #
        # What did seem to work is to enumerate over all of my known IP
        # addresses and add all of them.  ...and since that should work on all
        # platforms, I just do that.
        #
        # ...but, there are some problems / weirdnesses.  Most notable:
        # - Really, we want to add _interfaces_ to the multicast group.  ...but
        #   there's no way that I can see to do that, so we have to add by IP
        #   address.  That means that if an interface has no IP address at
        #   the moment, there's no way to add it to the multicast gorup.  That's
        #   why we tell the caller to call us back whenever our IP addresses
        #   change, so we can try to add any new interfaces.
        # - A given interface may have more than one IP address.  This is
        #   multihoming.  When this happens, we'll fail to do some of the
        #   "add membership" calls (the os will complain that we're trying to
        #   double-add an interface).  We just ignore those errors.
        # - When IPs disappear, we don't un-add them.  Honestly, we really want
        #   to be listening to all interfaces, so why would we unadd?  ..and it
        #   could be a really bad idea if you were multi-homed and then one of
        #   those IP addresses disappeared.
        #
        # Another random comment is that I know that we're supposed to do an
        # IGMP join for multicast.  I'm assuming that the OS does that for us,
        # but haven't actually sniffed the network to confirm.  Some web
        # searches I did implied this, so hope it's true.
        #
        # TODO: ...so maybe a good reason to remove membership when an interface
        # goes away is to make sure that the OS re-sends any IGMP join??

        for ipAddr in (newIpSet - oldIpSet):
            #print "Passive add: %s" % ipAddr
            mreq = struct.pack("4s4s", socket.inet_aton(_kMulticastIp),
                               socket.inet_aton(ipAddr))
            try:
                passiveSock.setsockopt(socket.IPPROTO_IP,
                                       socket.IP_ADD_MEMBERSHIP, mreq)
            except socket.error:
                # This is an expected failure.  See comments above...
                # Expect e.args = (errno.EADDRINUSE, "Address already in use")
                pass


    ###########################################################
    def _maintainRequestSockets(self, requestSocks, newIpSet):
        """Maintain our request sockets.

        This will create / kill sockets for making requests on as the list
        of IP addresses change.

        @param  requestSocks  A dictionary, keyed by IP address, of sockets.
        @param  newIpSet      A set of new IP addresses.
        """
        oldIpSet = set(requestSocks.iterkeys())

        removedIps = oldIpSet - newIpSet
        addedIps = newIpSet - oldIpSet

        for ipAddr in removedIps:
            #print "Request remove: %s" % ipAddr
            requestSocks[ipAddr].close()
            del requestSocks[ipAddr]

        # We will iterate over all IP addresses...
        for ipAddr in addedIps:
            try:
                #print "Request add: %s" % ipAddr
                requestSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                            socket.IPPROTO_UDP)
                requestSock.setsockopt(socket.IPPROTO_IP,
                                       socket.IP_MULTICAST_TTL,
                                       _kMulticastTTL)
                # Make sure that we bind to the right address; things work
                # pretty well without doing this, but I think this will make
                # them work even better (?)
                requestSock.bind((ipAddr, socket.INADDR_ANY))

                try:
                    requestSock.setsockopt(socket.IPPROTO_IP,
                                           socket.IP_MULTICAST_IF,
                                           socket.inet_aton(ipAddr))
                except socket.error:
                    # Not sure how common this is, especially after the bind
                    # has already succeeded...
                    if __debug__:
                        traceback.print_exc()

                requestSocks[ipAddr] = requestSock
            except Exception:
                # Got this if bind failed, maybe because the addedIps list is
                # not quite right (maybe the IP address already vanished?)
                # Ignore it...  We'll retry later...
                if __debug__:
                    print "Failed to add request socket for %s" % ipAddr


    ###########################################################
    def _getMyIps(self):
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
                                socket.inet_aton(addr) # valid IPv4, please
                            except:
                                continue
                            addrs.append(inetAddress)
        except:
            # due to IPHLPAPI.DLL incompatibilities we've seen this happening
            # in the wild, so protecting us against it cannot hurt ...
            if __debug__:
                print ("Some issue (%s) while getting IPs (%s)" %
                    (sys.exc_info()[0], sys.exc_info()[1]))
        return addrs

    ###########################################################
    def _checkForIpChanges(self):
        """Maintain the sockets, handling changes in IP addresses.

        Should be called periodically.
        """
        oldIpSet = set(self._requestSocks.iterkeys())
        newIpSet = set(addr['addr'] for addr in self._getMyIps())
        if oldIpSet != newIpSet:
            # Update sockets...
            if self._passiveSock:
                self._maintainPassiveSocket(self._passiveSock,
                                            oldIpSet, newIpSet)
            self._maintainRequestSockets(self._requestSocks, newIpSet)

            # Delete old addresses from the search count dict...
            for removedIp in (oldIpSet - newIpSet):
                self._searchCountDict.pop(removedIp, None)

            for ipAddr in (newIpSet - oldIpSet):
                self._searchCountDict[ipAddr] = {
                    'numSearches': 0,
                    'nextSearchTime': 0,
                }

        nowTime = time.time()
        for ipAddr, searchInfo in self._searchCountDict.items():
            if searchInfo['nextSearchTime'] <= nowTime:
                try:
                    requestSock = self._requestSocks[ipAddr]
                except KeyError:
                    # Handle the case where a request socket wasn't created
                    # for some reason...  Don't expect this...
                    if __debug__:
                        print "Missing request socket"
                    del self._searchCountDict[ipAddr]
                    continue

                #print "Requesting on %s" % (str(requestSock.getsockname()))
                try:
                    requestSock.sendto(
                        _kSearchRequest % {'searchTarget': kSearchTargetAll},
                        (_kMulticastIp, _kMulticastPort)
                    )

                    searchInfo['numSearches'] += 1
                    if searchInfo['numSearches'] >= _kHttpUdpMaxRetries:
                        del self._searchCountDict[ipAddr]
                    else:
                        searchInfo['nextSearchTime'] = \
                            nowTime + random.uniform(_kHttpUdpMinRetryInterval,
                                                     _kHttpUdpMaxRetryInterval)
                except socket.error:
                    # Don't expect this error, but saw it once when I tried to
                    # make a request socket on 0.0.0.0 but there were no active
                    # interfaces on XP.  Better safe than sorry...
                    if __debug__:
                        traceback.print_exc()


    ###########################################################
    def activeSearch(self, searchFor=kSearchTargetAll):
        """Actively send out a search.

        TODO (later):
        - If not searching for all, try a unicast search at last known address
          before spamming the whole network.  Retry twice.
        - Add in a retry for multicast searches.
        - If we've got a device in our list and it's not respoding to active
          searches, expire it sooner rather than waiting for it to disappear.

        @param  searchFor       Could be "ssdp:all" to search for everything, or
                                a USN to search for just a specific device.
        """
        # Request verification of devices...
        if searchFor == kSearchTargetAll:
            # Request verification of all know devices...
            for device in self._deviceDict.itervalues():
                device.requestVerify()
            for device in self._pendingDeviceDict.itervalues():
                device.requestVerify()
        else:
            # Request verification of this device...
            if searchFor in self._deviceDict:
                self._deviceDict[searchFor].requestVerify()
            if searchFor in self._pendingDeviceDict:
                self._pendingDeviceDict[searchFor].requestVerify()

        # Actively search on all known interfaces...
        for requestSock in self._requestSocks.itervalues():
            #print "Active search: %s (%s)" % (str(requestSock.getsockname()),
            #                                  searchFor)
            try:
                requestSock.sendto(
                    _kSearchRequest % {'searchTarget': searchFor},
                    (_kMulticastIp, _kMulticastPort)
                )
            except socket.error:
                # Don't expect this error, but better to be safe...
                if __debug__:
                    traceback.print_exc()


    ###########################################################
    def pollForChanges(self):
        """Look for changes in device info.

        This should be called periodically, like at idle time.

        @return changedUsns    A set of USNs that changed in some significant
                               way.  This could be new devices or ones that
                               changed in a big way; all devices here are in
                               getDevices()
        @return goneUsns       A set of device USNs that are gone.  Should only
                               contain USNs that you've seen before.
        """
        # Keep track of old USNs first, since _checkForIpChanges can kill
        # them (it doesn't now, but it might in the future)...
        oldUsns = set(self._deviceDict)

        # Any time a USN changes in a big way, we'll add it here...
        # ...we'll worry about clearing stuff at the end of the func...
        changedUsns = set()

        # Handle when our interfaces changed...
        self._checkForIpChanges()

        sockList = self._requestSocks.values()
        if self._passiveSock:
            sockList.append(self._passiveSock)


        while True:
            # Run any needed queries; iterate over copy so we can delete...
            for usn, device in self._pendingDeviceDict.items():
                if device.pollForDescription():
                    if usn in self._deviceDict:
                        isBig = self._deviceDict[usn].updateFromNewer(device)
                        if isBig:
                            self._logger.info( "Updating from newer: %s" % str(device) )
                            changedUsns.add(usn)
                    else:
                        self._logger.info ( "New device: %s" % str(device) )
                        self._deviceDict[usn] = device
                        changedUsns.add(usn)
                    del self._pendingDeviceDict[usn]

            try:
                readySocks, _, errorSocks = select.select(sockList, [],
                                                          sockList, 0)
            except select.error, e:
                # Seen this: (10022, 'An invalid argument was supplied')
                # ...at the same time I see: Couldn't open UPNP listening socket.
                print >>sys.stderr, "Socket select error: %s" % str(e)
                readySocks, errorSocks = ([], [])

            assert not errorSocks
            if not readySocks:
                break

            for sock in readySocks:
                self._pollSocket(sock)

        # Purge expired devices...
        self._purgeExpired()

        # Get a list of all current USNs...
        currUsns = set(self._deviceDict)

        # We can easily figure out which are gone by comparing the current UNSs
        # with the ones at the start of this function...
        goneUsns = oldUsns - currUsns

        # While this function was running, we added a USN to the changedUsns
        # set whenever there was a big change or something was added.  ...but
        # we never removed.  Take out anything that's not in currUsns.
        changedUsns.intersection_update(currUsns)

        return changedUsns, goneUsns


    ###########################################################
    def _pollSocket(self, sock):
        """Poll the given socket.

        We will update self._deviceDict and self._pendingDeviceDict as
        appropriate.  New devices will go into self._pendingDeviceDict and gone
        devices will be deleted from both.

        @param  sock  The socket; we know there's data because select() returned
                      this socket.
        """
        try:
            # Note: A user has seen this error in recvfrom, though we're not
            #       fully sure why.
            # <class 'socket.error'>: (10054, 'Connection reset by peer')
            responseStr, (fromIpAddr, _) = \
                sock.recvfrom(_kMaxUdpPacketSize)

            # Get out status line and bail right away if it's not
            # something we care about...
            startLine, responseStr = responseStr.split('\r\n', 1)
            if not self._isDeviceStatusMessage(startLine):
                return

            # Use httplib.HTTPMessage to parse the headers.  This
            # returns a dict-like object.
            httpMessage = httplib.HTTPMessage(StringIO.StringIO(responseStr), 0)

            # Adjust for bugs, and look for messages to drop right away...
            shouldDrop = self._adjustHttpMessageForBugs(httpMessage, fromIpAddr)
            if shouldDrop:
                return

            goneUsn = self._checkForByebye(httpMessage)
            if goneUsn is not None:
                # Process the byebye...
                for thisDict in (self._deviceDict, self._pendingDeviceDict):
                    #print "--- %s is totally byebye" % goneUsn
                    thisDict.pop(goneUsn, None)
            elif self._getStatusType(httpMessage).startswith('uuid:'):
                # Should be a standard notification...
                device = UpnpDevice(fromIpAddr, httpMessage, self._logger)
                usn = device.getUsn()

                olderDescribed = self._deviceDict.get(usn)
                olderPending = self._pendingDeviceDict.get(usn)

                if not device.handleDuplicatesEarly(olderDescribed,
                                                    olderPending):
                    self._pendingDeviceDict[usn] = device
                    device.pollForDescription()
        except Exception:
            if __debug__:
                traceback.print_exc()


    ###########################################################
    @staticmethod
    def _isDeviceStatusMessage(startLine):
        """Tell whether the given startLine represents a status message.

        A status message is either a response to one of our requests or is a
        general notification.

        @param  startLine              The first line of the HTTP response.
        @return isDeviceStatusMessage  True if this was the startline for a
                                       device status message.
        """
        statusWords = [s.upper() for s in startLine.split()]
        if statusWords == ['HTTP/1.1', '200', 'OK']:
            # Should be a response to our request (on our request socket)...
            return True
        elif statusWords == ['NOTIFY', '*', 'HTTP/1.1']:
            # Should be something sent to our passive socket; but I've noticed
            # cases where devices (due to bugs?) send this to our request
            # socket...
            return True
        #elif statusWords == ['M-SEARCH', '*', 'HTTP/1.1']:
        #    # Someone else doing a search...
        #    return False
        else:
            #if __debug__:
            #    print >>sys.stderr, "Unknown message:\n%s\n%s" % (startLine, responseStr)
            return False


    ###########################################################
    @staticmethod
    def _checkForByebye(httpMessage):
        """If this is a byebye message, returns the USN that's gone.

        @param  httpMessage  The httplib.HTTPMessage object.
        @return goneUsn      The USN that's gone; or None if nothing's gone.
        """
        try:
            if httpMessage['nts'].lower() == 'ssdp:byebye':
                # Try to take out of new devices (if there).  If it's
                # not there, try get from deviceDict.  If it's not
                # there, we'll just fail, but isGone will be set.  Note:
                # we'll remove from deviceDict at end of func..
                return httpMessage['usn']
        except Exception:
            pass

        return None


    ###########################################################
    @staticmethod
    def _adjustHttpMessageForBugs(httpMessage, fromIpAddr):
        """Adjust an httpMessage to workaround any known device bugs.

        @param  httpMessage  The httplib.HTTPMessage object.
        @param  fromIpAddr   The IP address that the message came from.
        @return shouldDrop   If True, we should drop the message.
        """
        try:
            # Get attributes; anything we get here needs to be safe for all
            # workarounds...
            usn = httpMessage['usn']
            server = httpMessage['server']
            cacheControl = httpMessage['cache-control']
            location = httpMessage['location']

            _kActiServerTypes = [
                'Linux, UPnP/1.0, LibUPnP',      # ACM4001
                'Linux, UPnP/1.0, ACTi libupnp', # TCM4301
            ]
            _kLinksysHnapServerTypes = [
                'POSIX, UPnP/1.0 linux/5.10.56.51', # LinksysWRT610N
            ]

            # ACTi workaround.  When we do an active search on ACTi for
            # ssdp:all, they only return a single response, and it's for
            # a root device.  If we detect this case, we'll hack the message
            # together to make it look like they gave a result for a given
            # UUID, which is what we want.
            #
            # Here's what ACTi gives us (as of Jan 2010):
            #  CACHE-CONTROL: max-age=1800
            #  Date: Sun, 04 Jan 2004 04:49:26 GMT
            #  EXT:
            #  LOCATION: http://192.168.11.170:49152/devicedesc.xml
            #  SERVER: Linux, UPnP/1.0, LibUPnP
            #  ST: upnp:rootdevice
            #  USN: uuid:ACM4001-09F-X-00005::upnp:rootdevice
            #
            # ...and TCM cameras:
            #  HTTP/1.1 200 OK
            #  CACHE-CONTROL: max-age=1800
            #  DATE: Mon, 1 Jan 2007 13:55:40 GMT
            #  EXT:
            #  LOCATION: http://192.168.11.122:49152/devicedesc.xml
            #  SERVER: Linux, UPnP/1.0, ACTi libupnp
            #  ST: upnp:rootdevice
            #  USN: uuid:TCM4301-09J-X-00120::upnp:rootdevice
            #
            # We want to change this to:
            #  ...
            #  ST: uuid:ACM4001-09F-X-00005
            #  USN: uuid:ACM4001-09F-X-00005
            if (server in _kActiServerTypes) and \
               (usn.startswith('uuid:TCM') or usn.startswith('uuid:ACM')):

                if 'st' in httpMessage:
                    statusType = httpMessage['st']

                    if (statusType == 'upnp:rootdevice')      and \
                       (usn.endswith('::upnp:rootdevice'))    and \
                       (usn.startswith('uuid:')):

                        usn = usn.rsplit('::upnp:rootdevice', 2)[0]
                        httpMessage['usn'] = usn
                        httpMessage['st'] = usn

            # LinksysWRT610N workaround.  That device sends us lots of stuff,
            # and one of the things contains what appears to be an invalid
            # location field.  ...at least the bug report we got showed it
            # as invalid.  Just drop this one.
            #   'cache-control': 'max-age=60',
            #   'host': '239.255.255.250:1900',
            #   'location': 'http://192.168.0.1/HNAP1/',
            #   'nt': 'uuid:160F7BFB-457F-3058-06AB-1C244666013D',
            #   'nts': 'ssdp:alive',
            #   'server': 'POSIX, UPnP/1.0 linux/5.10.56.51',
            #   'usn': 'uuid:160F7BFB-457F-3058-06AB-1C244666013D'
            # It should be pretty safe, since I think 5.10.56.51 is a Linksys
            # firmware number, and looks pretty unique.  Add in a check for the
            # max-age=60, too, since that's rare (the UPnP spec says max-age
            # should be 1800 or more, though it doesn't say it MUST).
            elif (server in _kLinksysHnapServerTypes) and \
                 (cacheControl == 'max-age=60') and \
                 (location == ("http://%s/HNAP1/" % fromIpAddr)):
                return True

        except KeyError:
            # If we get a key error, it's because the HTTP header is malformed,
            # or it is missing a response field that we need or are looking for.
            # Therefore, return "True" here to indicate that this message should
            # be dropped.  If we don't do this, then when "updateFromNewer"
            # function from "UpnpDevice" gets called, a KeyError exception will
            # bubble upwards, unhandled, to whoever is calling the
            # "pollForChanges" function.
            return True

        return False


    ###########################################################
    @staticmethod
    def _getStatusType(httpMessage):
        """Get the status type (search type or notification type) from message.

        @param  httpMessage  The httplib.HTTPMessage object.
        @return statusType   The status type, like "uuid:....".  If this
                             is not a valid UPNP message, we'll return ""
        """
        try:
            # Try looking at notification type first...
            statusType = httpMessage['nt']
            assert httpMessage['nts'] == 'ssdp:alive', \
                   "Unexpected notification sub type"
        except KeyError:
            try:
                # Next, try the search target...
                statusType = httpMessage['st']
            except KeyError:
                # Upon failure, just do the empty string...
                statusType = ""

        return statusType


    ###########################################################
    def _purgeExpired(self):
        """Purge expired devices.

        Also initiates an active search for something that's about to expire.

        @return expiredDeviceDict  A dictionary of expired devices (key=usn).
        """
        # Make toKill list first, then go through a second pass and delete.
        # That way, we don't delete from a dict we're iterating over...
        toKill = {}
        for usn, upnpDevice in self._deviceDict.iteritems():
            if upnpDevice.isExpired():
                toKill[usn] = upnpDevice
            elif upnpDevice.wantAboutToExpireSearch():
                # If something is about to expire, start an active search
                # for it.
                self.activeSearch(usn)

        # Kill 'em...
        for usn in toKill:
            del self._deviceDict[usn]

        return toKill


    ###########################################################
    def getDevices(self):
        """Get a list of all known devices.

        @return deviceDict    A dictionary of devices (keyed by their USN).
        """
        return copy.deepcopy(self._deviceDict)


    ###########################################################
    def getDevice(self, usn):
        """Get a given device.

        This is a shorthand for getDevices()[usn]

        @return device  The device.
        """
        return self._deviceDict[usn]


##############################################################################
class UpnpDevice(object):
    """A class for holding info about UPNP devices that we've found."""
    ###########################################################
    def __init__(self, ssdpIp, ssdpData, logger):
        """UpnpDevice constructor.

        Note that you should call pollDescription() after creating the device.

        @param  ssdpIp    The IP address that the SSDP message came from.
        @param  ssdpData  A HTTPMessage of the info that was discovered from the
                          SSDP request.  Must contain required fields (like usn)
        """
        super(UpnpDevice, self).__init__()

        self._logger = logger

        # Anything that might be called in __del__ needs to be initialized
        # before the value error exception. Ideally everything would be but
        # I don't want to muck with the file structure too much at the moment.
        self._sock = None

        if 'usn' not in ssdpData:
            raise ValueError("SSDP response is missing the usn: " + str(ssdpData))

        # Init members...
        self._ssdpIp = ssdpIp
        self._ssdpData = ssdpData

        self._urlBase = None
        self._simpleAttributes = {}

        # Keep track of how many times we've tried to get the description...
        self._descriptionFailures = -1
        self._resetHttpState()

        self._gotDescription = False

        # If we're asked to verify the device, we'll set this to the time.
        self._verifyRequestAt = None

        # Keep expiration time...
        self._expiresAtTime = self._calcExpiredTime(ssdpData)

        # We'll set this to True if we've initiated an active search for
        # something because it's about to expire...
        self._didAboutToExpireSearch = False


    ###########################################################
    def __getstate__(self):
        """Pickling function

        @return state  A dictionary of pickleable state.
        """
        assert not self.needsDescription(), "Can't pickle %s until desc phase done" % (self.getUsn())

        # Return just a few attributes; after we've gone through description
        # phase, this is all we need...
        #
        # NOTE: the fact that we have bare strings here makes us able to
        # communicate our state across builds (with different obfuscation).
        return {
            '_simpleAttributes': self._simpleAttributes,
            '_ssdpData': self._ssdpData,
            '_ssdpIp': self._ssdpIp,
            '_urlBase': self._urlBase,
        }


    ###########################################################
    def __setstate__(self, state):
        """Unpickling function

        @param  state  The information previously returned from __getstate__
        """
        # Store those things from __getstate__...
        #
        # NOTE: the fact that we have bare strings here makes us able to
        # communicate our state across builds (with different obfuscation).
        self._simpleAttributes = state['_simpleAttributes']
        self._ssdpData = state['_ssdpData']
        self._ssdpIp = state['_ssdpIp']
        self._urlBase = state['_urlBase']

        # We don't keep track of created time at the other end of the pickle...
        self._expiresAtTime = None

        # Make sure we know that we have no socket...
        self._sock = None


    ###########################################################
    def __del__(self):
        """Destructor function.

        This just calls self._tryToCloseSocket() to be nice.
        """
        self._tryToCloseSocket()


    ###########################################################
    def _tryToCloseSocket(self):
        """Close our socket.

        We just make sure to try to read from our socket; this attempts to keep
        us from crashing the UPNP on the panasonic pet camera, which we seem
        to be able to kill with something as simple as this:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect_ex(("192.168.11.182", 1900))
            sock.close()
        """
        if self._sock is not None:
            # Try one last recv on the socket; we don't care if it fails.  We're
            # just trying to be nice...
            try:
                self._sock.recv(_kDescriptionBufsize)
            except Exception:
                pass

            # Try to close the socket.  Again, don't care if it fails...
            try:
                self._sock.close()
            except Exception:
                pass

            # Socket is now None...
            self._sock = None


    ###########################################################
    def __str__(self):
        """Gives a nice representation of the recognition object.

        This doesn't need to be enough to completely reconstruct the object;
        it's just a nice, printable, summary.

        @return s  Our string representation.
        """
        return pprint.pformat({
            'ssdpIp': self._ssdpIp,
            'ssdpData': dict(self._ssdpData),
            'simpleAttributes': self._simpleAttributes,
            'urlBase': self._urlBase}
        )


    ###########################################################
    def getAttributes(self):
        """Return the dict of attributes.

        @return attributes  A dictionary of simple attributes.
        """
        # Return a copy, just to be paranoid.
        return dict(self._simpleAttributes)


    ###########################################################
    def getFriendlyName(self, alwaysIncludeIp=False):
        """Get the friendly name of this device.

        @param  alwaysIncludeIp  If True, we'll always include the IP address.
        @return friendlyName     The friendly name; if we don't have a
                                 description yet, this is just "Unknown
                                 (IP Address)"
        """
        if 'friendlyName' in self._simpleAttributes:
            friendlyName = self._simpleAttributes['friendlyName']
            if alwaysIncludeIp:
                return "%s -- %s" % (friendlyName, self._ssdpIp)
            else:
                return friendlyName
        else:
            return "Unknown -- %s" % self._ssdpIp


    ###########################################################
    def getModelName(self):
        """Get the model name of this device.

        This does a best attempt at figuring things out--it doesn't just do
        a simple mapping.  This heuristic is based on looking at several UPNP
        devices and deciding that this was the best solution.

        A few samples:

                          AXIS 207W                 AIC250
                          ---------                 ------
        manufacturer      AXIS                      n/a
        modelNumber       207W                      3.29 (2007-08-03)
        modelName         AXIS 207W                 AIC250
        modelDescription  AXIS 207W Network Camera  Internet Camera

                          TV-IP312W                 D-Link DCS-920
                          ---------                 --------------
        manufacturer      n/a                       D-Link
        modelNumber       312W                      DCS-920
        modelName         TV-IP312W                 DCS-920
        modelDescription  Wireless Network Camera   Wireless Internet Camera

                          Panasonic BL-C20A
                          -----------------
        manufacturer      Panasonic
        modelNumber       BL-C20A
        modelName         Network Camera
        modelDescription  Panasonic Network Camera

                          AXIS M1031-W
                          ------------
        manufacturer      AXIS
        modelNumber       M1031-W
        modelName         AXIS M1031-W
        modelDescription  AXIS M1031-W Network Camera

                          ACTi TCM4301               # (4.06.09-AC)
                          ------------
        manufacturer      ACTi Corporation
        modelNumber       TCM4301-09J-X-00120        # I think includes serial#?
        modelName         TCM4301
        modelDescription  Mega IP Cube Camera

                          IQEye 041S
                          ----------
        manufacturer      IQinVision
        modelNumber       n/a
        modelName         IQ041S
        modelDescription  IQ041S IP video camera

                          Asante Voyager I
                          ----------------
        manufacturer      ASANTE
        modelNumber       1.0
        modelName         IPCam
        modelDescription  ASANTE IPCam

        @return modelName  The name of the model.
        """
        # We'll try getting / combining various attributes to come up with a
        # model number.  This tries to make sense of the various ways
        # manufacturers have decided to put stuff in these fields.
        attrsToTry = [
            ['manufacturer', 'modelNumber'],
            ['modelName'],
            ['modelNumber'],
            ['manufacturer'],
            ['modelDescription'],
        ]

        # Special cases, depending on manufacturer.  We'll use what we find in
        # here instead of attrsToTry if we find a manufacturer that we
        # recognize.
        specialCases = {
            'ACTi Corporation': [['manufacturer', 'modelName']] + attrsToTry,
            'ASANTE': [['manufacturer', 'modelName']] + attrsToTry,
        }

        manufacturer = self._simpleAttributes.get('manufacturer', None)
        attrsToTry = specialCases.get(manufacturer, attrsToTry)

        # Just keep trying to return something, expecting a KeyError if the
        # attributes aren't present...
        for attrList in attrsToTry:
            try:
                return ' '.join(self._simpleAttributes[attr]
                                for attr in attrList)
            except KeyError:
                pass

        return 'Unknown'


    ###########################################################
    def getPresentationUrl(self, username=None, password=None):
        """Get the presentation URL.

        If the device doesn't have one, we attempt to make one up based on
        their IP.

        This will also cleanup the presentation URL a little bit, adding a
        trailing "/" if needed...

        @param  username         If non-None, we'll add this username.  Should
                                 NOT be pre-quoted.
        @param  password         If non-None, we'll add this password.  Should
                                 NOT be pre-quoted.
        @return presentationUrl  The presentation URL.
        @return isGuess          True if the presentation URL is a guess.
        """
        if 'presentationURL' in self._simpleAttributes:
            url, guess = (self._simpleAttributes['presentationURL'], False)
            if self._urlBase is not None:
                url = urlparse.urljoin(self._urlBase, url)
        else:
            url, guess = ("http://%s/" % (self._ssdpIp), True)

        splitUrl = urlparse.urlsplit(url)
        assert splitUrl.scheme == 'http', "Only tested for HTTP"

        # If there's no path, we'll add a "/" at the end.  That makes things
        # more consistent for our clients...
        if not splitUrl.path:
            assert not (splitUrl.query or splitUrl.fragment), \
                   "Didn't expect query/fragment when no path, please test."
            pathPart = "/"
        else:
            pathPart = splitUrl.path

        if username or password:
            # If either username or password, but not both, then make missing
            # one "".
            if username is None:
                username = ""
            if password is None:
                password = ""

            # Figure out netloc without any username / password (we'll replace
            # any that are there).  Not that we expect ones to be there, but
            # good to be safe.
            assert not (splitUrl.username or splitUrl.password), \
                   "Didn't expect username or password in presentation URL."
            netloc = ""
            if splitUrl.hostname:
                netloc += splitUrl.hostname
                if splitUrl.port:
                    netloc += ":%d" % (splitUrl.port)
            else:
                assert False, "Didn't expect presentation URL without a host"

            # Put everything back together...
            url = urlparse.urlunsplit((
                splitUrl.scheme, "%s:%s@%s" % (
                    urllib.quote(username, ""), urllib.quote(password, ""),
                    netloc
                ),
                pathPart, splitUrl.query, splitUrl.fragment
            ))
        else:
            # Put everything back together...
            url = urlparse.urlunsplit((
                splitUrl.scheme, splitUrl.netloc,
                pathPart, splitUrl.query, splitUrl.fragment
            ))

        return (url, guess)


    ###########################################################
    def getUsn(self):
        """Return the USN (Unique Service Name) for this device.

        @return  usn  The usn.
        """
        return self._ssdpData['usn']


    ###########################################################
    def isRouter(self):
        """Return True if this device is a router.

        Routers have a deviceType of:
          urn:schemas-upnp-org:device:InternetGatewayDevice:1

        This function is useful if you want to filter out routers
        because you only want to show other types of devices.
        """
        deviceType = self._simpleAttributes.get('deviceType', "")
        modelDescription = self._simpleAttributes.get('modelDescription', "")

        # We'll say that it's a router if it starts with any version of
        # internet gateway device...
        isRouter = deviceType.startswith(
            # Seen this...
            'urn:schemas-upnp-org:device:InternetGatewayDevice'
        ) or deviceType.startswith(
            # Seen this...
            'urn:dslforum-org:device:InternetGatewayDevice'
        ) or deviceType.startswith(
            # Seen in LinksysWRT610N
            'urn:schemas-wifialliance-org:device:WFADevice:1'
        ) or (
            # Seen in LinksysWRT610N, which spouts out tons of UPnP devices,
            # some of which identify as urn:schemas-upnp-org:device:Basic:1
            # with this modelDescription...
            modelDescription == 'Linksys EGHN Architecture Device'
        )

        return isRouter


    ###########################################################
    def isPresentable(self, valueForUncertain=False):
        """Return whether this device has a presentation URL.

        This function has the option to return either True or False for devices
        that we are uncertain about.  These are devices that we haven't fetched
        the description for yet, or that we tried and failed to fetch a
        description for.

        This functionality is useful if you want to show all devices that are
        presentable plus all devices that appear to be misconfigured (because
        we can't fetch a description for them).

        @param  valueForUncertain  The value to return for devices that we're
                                   not certain about.  See above.
        @return isPresentable      True if the device is presentable.
        """
        # If we don't have any attributes, we are uncertain...
        if not self._simpleAttributes:
            return valueForUncertain

        # If we have attributes, it is presentable if it has a presentation URL.
        return 'presentationURL' in self._simpleAttributes


    ###########################################################
    def handleDuplicatesEarly(self, olderDescribed, olderPending):
        """Handle the case that this is a duplicate of an older UpnpDevice.

        Call this right after you've created a device, passing in older
        copies of the device.

        If this is a duplicate, we'll return True.  That means you should
        throw it away (we've already updated the older devices with its info).
        If we return False, it means you should add this to pending (clobbering
        any older pending device you might have).

        @param  olderPending    If non-None, this is an older version of this
                                deivce that is still pending.
        @param  olderDescribed  If non-None, this is an older version of this
                                device that has already been described.
        @return isDuplicate     If True, toss the device; if True, keep it.
        """
        if olderPending is not None:
            assert olderPending.getUsn() == self.getUsn(), "USNs should match"
            if ((olderPending.needsVerify())             or
                (olderPending._ssdpData['location'] !=
                 self._ssdpData['location']           )    ):

                # A newer location; throw the old pending one away...
                #print "--- Newer location takes pending: %s" % self.getUsn()
                return False
            else:
                # Same location as something else pending; just take the newer
                # expiration time / IP addresses...
                #print "--- Dupe location; update pending: %s" % self.getUsn()
                olderPending._expiresAtTime = self._expiresAtTime
                return True

        if olderDescribed is not None:
            assert olderDescribed.getUsn() == self.getUsn(), "USNs should match"
            if ((olderDescribed.needsVerify())           or
                (olderDescribed.isExpired())             or
                (not olderDescribed._simpleAttributes)   or
                (olderDescribed._ssdpData['location'] !=
                 self._ssdpData['location']             )  ):

                # A newer location, or the older one needs verification.  Add
                # this new device to pending; it will eventually replace
                # the other one using updateFromNewer()

                #if olderDescribed.needsVerify():
                #    print "--- Newer takes described (verify): %s" % self.getUsn()
                #if olderDescribed.isExpired():
                #    print "--- Newer takes described (expired): %s" % self.getUsn()
                #if not olderDescribed._simpleAttributes:
                #    print "--- Newer takes described (attributes): %s" % self.getUsn()
                #if olderDescribed._ssdpData['location'] != self._ssdpData['location']:
                #    print "--- Newer takes described (location): %s (%s != %s)" % \
                #           (self.getUsn(), olderDescribed._ssdpData['location'], self._ssdpData['location'])

                return False
            else:
                # Same location; just take the newer time / IP...
                #print "--- Dupe updates described: %s" % self.getUsn()
                olderDescribed._expiresAtTime = self._expiresAtTime
                return True

        # No older devices, keep it.
        #print "--- Totally new: %s" % self.getUsn()
        return False


    ###########################################################
    def updateFromNewer(self, other):
        """Update a device from a newer version.

        This does the following:
        - If the current device doesn't need to be verified and the other
          device refers to the same location, it just updates the expiration
          date.

        @param  other  The newer version.
        @return isBig  If True, this is a big change.
        """
        isBig = False

        # Take everything from the newer...
        self._expiresAtTime = other._expiresAtTime
        self._didAboutToExpireSearch = other._didAboutToExpireSearch

        if self._simpleAttributes != other._simpleAttributes:
            isBig = True
            self._simpleAttributes = other._simpleAttributes
        if self._urlBase != other._urlBase:
            isBig = True
            self._urlBase = other._urlBase
        if self._ssdpData['location'] != other._ssdpData['location']:
            isBig = True
        self._ssdpData = other._ssdpData
        if self._ssdpIp != other._ssdpIp:
            isBig = True
            self._ssdpIp = other._ssdpIp

        # We no longer need to be verified, unless 'other' did...
        self._verifyRequestAt = other._verifyRequestAt

        return isBig


    ###########################################################
    def isExpired(self):
        """Return true if this object is expired.

        @return isExpired  True if we've expired.
        """
        # Happens if we've been pickled / unpickled...
        if self._expiresAtTime is None:
            return False

        return time.time() > self._expiresAtTime


    ###########################################################
    def wantAboutToExpireSearch(self):
        """Check if this is about to expire and needs an active search.

        We will only request one search before we expire, as a last-ditch
        attempt to find updated info.  Note that we don't start this last-dicth
        effort until we're halfway into the slop that we give the device before
        expiring it.

        @param  wantAboutToExpireSearch  True if we should do an active search
                                         for this device.
        """
        if (not self._didAboutToExpireSearch)                            and \
           ((time.time() + _kExpireSlopSeconds/2) > self._expiresAtTime):

            self._didAboutToExpireSearch = True
            return True

        return False


    ###########################################################
    @staticmethod
    def _calcExpiredTime(ssdpData, createdAtTime=None):
        """Figure out when the SSDP packet will expire.

        @param  ssdpData       The SSDP data.
        @param  createdAtTime  The time the data was captured; or None for now.
        """
        if createdAtTime is None:
            createdAtTime = time.time()

        # Default: it expires at time of creation...
        expiresAtTime = createdAtTime

        try:
            # UPNP 1.0 spec says that this is required...
            assert 'cache-control' in ssdpData, \
                   "Expected cache-control header: " + str(dict(ssdpData))

            # Parse cache-control, which should be like 'max-age=xyz'
            # ...technically, I think this can have
            mo = re.match(r'max-age\s*\=\s*(\d*)',
                          ssdpData['cache-control'], re.IGNORECASE)
            assert mo, "Bad cache-control: %s" % ssdpData['cache-control']

            # Actually get the time out...
            (maxAge, ) = mo.groups()
            expiresAtTime = createdAtTime + int(maxAge) + _kExpireSlopSeconds

            # The SSDP RFC draft says that 'expires' is also valid, but the
            # UPNP 1.0 spec doesn't say anything about it and I don't see it.
            # I'll ignore it, but put in an assert in case someone is doing
            # it.  Note: SSDP RFC says that cache-control will be used in
            # preference to expires anyway.
            assert 'expires' not in ssdpData, \
                   "Didn't expect 'expires' header"
        except Exception:
            # If we fail to parse for some reason, we'll just assume it expires
            # right away...
            if __debug__:
                traceback.print_exc()

        return expiresAtTime


    ###########################################################
    def _resetHttpState(self):
        """Reset our http-related state.

        The first time this is called, self._sock should already be None and
        self._descriptionFailures should be -1.
        """
        # Our socket; we do our own networking so we can do it nonblocking...
        self._tryToCloseSocket()

        # Our peer address
        self._peerAddr = None

        # True once we've sent the HTTP request...
        self._sentRequest = False

        # We always read into a buffer.
        self._buffer = ""

        # Increase our number of failure.  Should be init to -1 in __init__
        # so this starts at 0.
        self._descriptionFailures += 1

        # This is the time of the last reset, used for figuring out timeouts.
        self._resetTime = time.time()

        # The number of time we've polled since the last reset.  We'll only
        # timeout if we've had more than 8 calls to "poll" since the last
        # reset...
        self._pollsSinceReset = 0


    ###########################################################
    def requestVerify(self):
        """Request that we re-verify this device.

        This will make self.needsVerify() return True.  You can verify a device
        by calling updateFromNewer().
        """
        self._verifyRequestAt = time.time()


    ###########################################################
    def needsVerify(self):
        """Return true if this device needs to be verified.

        We set this right before actively searching for a device.  That means
        we're expecting to get another copy, which will actively verify
        (including getting another description).
        """
        return self._verifyRequestAt is not None


    ###########################################################
    def needsDescription(self):
        """Returns true if we still need to query the details for this device.

        May return False even if we don't have a description if we never expect
        to get one.

        @return needsDetails  True if we still need to query details.
        """
        try:
            return ('location' in self._ssdpData) and \
                (not self._gotDescription) and \
                (self._descriptionFailures < _kMaxDescriptionFailures)
        except:
            # The only way this exception happens, is if attempting to re-pickle
            # a pickled UpnpDevice object (which doesn't have, for example, _gotDescription)
            #
            # In such a case, no update is ever expected, and we expect to see a full description
            return False

    ###########################################################
    def pollForDescription(self):
        """Query for more details about this device.

        This should be called periodically until needsDescription() returns
        False.

        @return gotDescription  True if we finished getting a description.
        """
        if not self.needsDescription():
            return True

        data = self._giveHttpTime()
        if data is None:
            return False

        md = None
        try:
            try:
                md = vitaParseXML(data)
            except:
                self._logger.error("Error parsing XML from " + str(self._ssdpIp) + ": " + ensureUtf8(data))
                raise
            #print md.toprettyxml()

            assert len(md.getElementsByTagName('specVersion')) == 1, \
                   "Bad spec version:\n\n%s\n\n" % data
            specVersionDom = md.getElementsByTagName('specVersion')[0]
            majorVersionDom = specVersionDom.getElementsByTagName('major')[0]
            majorVersion = int(majorVersionDom.childNodes[0].data)

            # If we get a mismatch, then we'll reset and retry...
            if majorVersion != _kUpnpMajorVersion:
                self._resetHttpState()
                return False

            # Parse the device DOM
            self._urlBase = None
            self._simpleAttributes = {}

            # Get the URLBase if it's there; not that the URLBase is a
            # deprecated feature of UPNP, but it's still good to support it...
            # We don't really worry if somehow we fail parsing this, though...
            try:
                if len(md.getElementsByTagName('URLBase')) == 1:
                    urlBaseDom = md.getElementsByTagName('URLBase')[0]
                    self._urlBase = urlBaseDom.childNodes[0].data
            except Exception:
                if __debug__:
                    traceback.print_exc()

            # Get device DOM; extra crud is to ignore embedded devices...
            deviceDomList = [deviceDom for deviceDom
                             in md.getElementsByTagName('device')
                             if deviceDom.parentNode.localName=='root']
            assert len(deviceDomList) == 1
            deviceDom = deviceDomList[0]

            for childDom in deviceDom.childNodes:
                if len(childDom.childNodes) == 1:
                    grandChildDom = childDom.childNodes[0]
                    if grandChildDom.nodeType == grandChildDom.TEXT_NODE:
                        self._simpleAttributes[childDom.nodeName] = \
                            grandChildDom.data

            #pprint.pprint(deviceDict)

            self._gotDescription = True
            return True
        except Exception:
            if __debug__:
                traceback.print_exc()

            self._resetHttpState()
            return False
        finally:
            if md is not None:
                md.unlink()


    ###########################################################
    def _giveHttpTime(self):
        """Give time to our "http request" state machine.

        We do our own HTTP socket work so that we can do it asynchronously.
        We still hack things into the standard python httplib, though, to
        try to take advantage of all of their logic.

        @return body  If non-None, our body; if None, we need more time.
        """
        try:
            location = self._ssdpData['location']

            # If we've timed out, reset and we'll try again...
            if ((time.time() - self._resetTime) > _kHttpTimeout) and \
               (self._pollsSinceReset > _kHttpMinPolls):
                # TODO: See if we actually did get the data, but maybe the other
                # side just forgot to close us?
                self._resetHttpState()

            # Every time we give HTTP time, it's considered one "poll".  This
            # helps keep us from timing out too quickly if we're not called
            # very often...
            self._pollsSinceReset += 1

            # If we haven't connected, connect and then return...
            if self._sock is None:
                splitLoc = urlparse.urlsplit(location)
                if splitLoc.hostname is None:
                    splitLoc = urlparse.urlsplit('//'+splitLoc.path.lstrip('/'))
                    if splitLoc.hostname is None:
                        return None
                if splitLoc.port is None:
                    self._peerAddr = (splitLoc.hostname, httplib.HTTP_PORT)
                else:
                    self._peerAddr = (splitLoc.hostname, splitLoc.port)

                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.setblocking(False)
                err = self._sock.connect_ex(self._peerAddr)
                if err:
                    #assert err in (errno.EINPROGRESS, errno.WSAEWOULDBLOCK)
                    return None

            # If we haven't requested, try to send the request and then return.
            if not self._sentRequest:
                # Wait until we've connected.  It appears that 'select' can be
                # used to do this more reliably than just calling connect
                # until we get no error...
                rSocks, wSocks, eSocks = \
                    select.select([self._sock], [self._sock], [self._sock], 0)

                if eSocks:
                    assert False, "Unexpected error"
                    self._resetHttpState()
                    return None

                if not (rSocks or wSocks):
                    return None

                # We're connected; send the request.  Use sendall, which should
                # be safe even w/ blocking sockets (I hope), since our request
                # is so tiny.
                splitLoc = urlparse.urlsplit(location)
                descPath = splitLoc.path
                if splitLoc.query: descPath += "?" + splitLoc.query
                if splitLoc.fragment: descPath += "#" + splitLoc.fragment
                try:
                    self._sock.sendall(_kDescriptionRequest %
                                   {'path': descPath,'netloc': splitLoc.netloc})
                    self._sentRequest = True
                except socket.error:
                    # Happens while Axis 1031 is coming up...
                    self._resetHttpState()

                return None

            # Working on getting data...
            try:
                newData = self._sock.recv(_kDescriptionBufsize)
            except socket.error:
                # No new data...
                return None

            # If we've got data, add it to our buffer and return...
            if newData:
                self._buffer += newData
                return

            # If no data was ever received, don't bother trying to parse it...
            if not self._buffer:
                self._resetHttpState()
                return None

            # If we get here, the connection closed on us; give it to httplib
            # to parse...
            #
            # Make a lame-o fake socket that represents all the data that we
            # got from the socket and feed it into
            fakeSock = _StringSock(self._buffer)
            response = httplib.HTTPResponse(fakeSock, method='GET')
            response.begin()

            # Close the socket to be a good citizen...
            self._sock.close()
            self._sock = None

            data = response.read()
            if response.status != 200:
                self._logger.error("Got an error response " + str(response.status) + " from " + str(self._peerAddr))
                return None

            return data
        except Exception:
            if __debug__:
                traceback.print_exc()
                print "%s" % str(self._buffer)

            self._resetHttpState()
            return None


##############################################################################
def isUpnpUrl(url):
    """Return True if the given url is a valid UPNP URL.

    Never throws any exception.

    @param  url        The URL to check.
    @return isUpnpUrl  True if the URL is a UPNP URL.
    """
    try:
        _ = extractUsnFromUpnpUrl(url)
    except ValueError:
        return False
    else:
        return True


##############################################################################
def extractUsnFromUpnpUrl(url):
    """Extract the USN from a UPNP URL.

    Modern UPNP URLs look like this:
      scheme://[[user][:pass]@]encodedUsn.vitaupnp.[:port]/path

    Older, backward-compatible UPNP URLs look like this (this was a bad
    mechanism, but we now have people in the field with them):
      upnp://user:pass@quotedUsn/path

    @param  url  The URL; if it's not a UPNP URL, we'll raise a ValueError.
                 Should be unicode or UTF-8 encoded.
    @return usn  The USN, in unicode.
    """
    try:
        if not url:
            raise ValueError("Not a valid UPNP URL: %s" % url)

        url = ensureUtf8(url)
        splitResult = urlparse.urlsplit(url)
        if splitResult.scheme == 'upnp':
            # Old-style; note that we can't use 'hostname', since that
            # does a lower()
            usn = urllib.unquote(splitResult.netloc.split('@', 1)[-1])
            return usn.decode('utf-8')

        # Get the hostname; if it's blank or None, that's not a valid UPNP URL.
        hostname = splitResult.hostname
        if not hostname:
            raise ValueError("Not a valid UPNP URL: %s" % url)

        if hostname.endswith(_kUpnpHostnameSuffix):
            # Strip off the suffix...
            encodedUsn = hostname[:-len(_kUpnpHostnameSuffix)]

            # Decode from our terribly convoluted way of encoding a USN into
            # a hostname.  All of this work is to try to make sure that we can
            # represent arbitrary USNs, while only using alpha-numeric, case-
            # insenstive chars.  Note that the pad ('=') violates that, so we
            # replace it with 9 (which should be unused).  We also put a "."
            # every 16 characters, to make it look pretty and keep any part
            # from being >63 characters...
            encodedUsn = encodedUsn.replace('9', '=').replace('.', '')
            usn = base64.b32decode(encodedUsn, True)

            #print "USN: %s" % usn.decode('utf-8')
            return usn.decode('utf-8')
    except ValueError:
        # Don't care about value error debug message...
        pass
    except Exception:
        # Could happen if the hostname ends with the suffix, but isn't
        # a valid encoding...
        if __debug__:
            traceback.print_exc()

    raise ValueError("Not a valid UPNP URL: %s" % url)


##############################################################################
def constructUpnpUrl(usn, username=None, password=None, pathPart=None,
                     scheme='http://', port=None):
    """Create a UPNP URL.

    Modern UPNP URLs look like this:
      scheme://[[user][:pass]@]encodedUsn.vitaupnp.[:port]/path

    @param  usn       The USN to encode.  Should either be unicode or utf-8.
    @param  username  The username (optional); this function handles quoting.
                      Should be unicode or utf-8.
    @param  password  The password (optional); this function handles quoting.
                      Should be unicode or utf-8.
    @param  pathPart  The path part (optional).  If there, should start with
                      a '/'.  Should be unicode or utf-8.
    @param  scheme    The URL scheme to use.  By default, this is 'http://'.
                      Should be unicode or utf-8.
    @param  port      The port to use.  If None, we'll use the default port.
                      Note that for HTTP, the "default" port is whatever port
                      is in the presentation URL, which is not always 80.
                      Should be an integer if non-None.
    @return url       The UPNP URL.  Will be UTF-8.
    """
    url = ensureUtf8(scheme)

    if username or password:
        if username:
            url += urllib.quote(ensureUtf8(username), "")
        if password:
            url += ":%s" % urllib.quote(ensureUtf8(password), "")
        url += "@"

    # Encode into our terribly convoluted way of encoding a USN into
    # a hostname.  All of this work is to try to make sure that we can
    # represent arbitrary USNs, while only using alpha-numeric, case-
    # insenstive chars.  Note that the pad ('=') violates that, so we
    # replace it with 9 (which should be unused).  We also put a "."
    # every 16 characters, to make it look pretty and keep any part
    # from being >63 characters...
    encodedUsn = base64.b32encode(ensureUtf8(usn))
    encodedUsn = encodedUsn.lower()
    encodedUsn = encodedUsn.replace('=', '9')
    encodedUsn = re.sub(r'(.{16})', r'\1.', encodedUsn).rstrip('.')

    url += (encodedUsn + _kUpnpHostnameSuffix)

    if port:
        url += ":%d" % port

    if pathPart:
        assert pathPart.startswith('/')
        url += ensureUtf8(pathPart)

    #print "URL: %s" % url
    return url


##############################################################################
def realizeUpnpUrl(deviceDict, url):
    """Given a UPNP url, convert it into a real one.

    Modern UPNP URLs look like this:
      scheme://[[user][:pass]@]encodedUsn.vitaupnp.[:port]/path

    Older, backward-compatible UPNP URLs look like this (this was a bad
    mechanism, but we now have people in the field with them):
      upnp://user:pass@quotedUsn/path

    We convert it to a real one by getting the 'presentation URL' from UPNP,
    then adding the user/pass as well as the path.

    @param  deviceDict  A dictionary of devices, like returned by getDevices()
    @param  url         A UPNP url.  If this isn't a UPNP URL, we'll
                        raise a ValueError.  Should be unicode or utf-8, though
                        technically it should have all ASCII values.
    @return url         The realized URL; will be "" if the device wasn't
                        in the deviceDict.  Will be utf-8.
    """
    # Extract the USN; this will raise a ValueError if the URL wasn't a UPNP
    # URL...
    usn = extractUsnFromUpnpUrl(url)

    # If we don't know about this USN, we just return a blank URL as per spec.
    if usn not in deviceDict:
        return ""

    try:
        # Get the UPNP device info...
        device = deviceDict[usn]

        # Get the presentation URL out; don't give username/password to the
        # getPresentationUrl function, since we need to do our own parsing
        # anyway...
        presUrl, _ = device.getPresentationUrl()
        presUrl = ensureUtf8(presUrl)
        presSplitResult = urlparse.urlsplit(presUrl)

        # Split the UPNP URL.  This requires our patched urlparse to deal with
        # old-style upnp:// URLs (we patched up in the imports section)...
        url = ensureUtf8(url)
        upnpSplitResult = urlparse.urlsplit(url)

        if upnpSplitResult.scheme == 'upnp':
            # Old-style always used scheme from presentation URL...
            # We expect this is always http...
            newUrl = "%s://" % presSplitResult.scheme
        else:
            # New-style requires user to specify scheme...
            newUrl = "%s://" % upnpSplitResult.scheme

        # Always get username/password from the UPNP URL (should be quoted
        # already)...
        if upnpSplitResult.username or upnpSplitResult.password:
            if upnpSplitResult.username:
                newUrl += upnpSplitResult.username
            if upnpSplitResult.password:
                newUrl += ":%s" % upnpSplitResult.password
            newUrl += "@"

        # Add the hostname from the presentation URL...
        assert presSplitResult.hostname, "Expected hostname in presentation URL"
        newUrl += presSplitResult.hostname

        # Port rules are complicated.  If UPNP URL has a port, that always
        # wins.  Otherwise, if the presentation URL has a port __AND__ the
        # schemes of both URLs match, we use the presentation URL's port.
        if upnpSplitResult.port:
            newUrl += ":%d" % upnpSplitResult.port
        elif (upnpSplitResult.scheme == 'upnp') or \
             (upnpSplitResult.scheme.lower() == presSplitResult.scheme.lower()):
            if presSplitResult.port:
                newUrl += ":%d" % presSplitResult.port

        # We ignore the path part of the presentation URL and just jam the
        # path part of the UPNP URL in.  TODO: Is that the right thing to do
        # if the UPNP URL isn't absolute???
        pathPart = upnpSplitResult.path
        if upnpSplitResult.query:
            pathPart += "?" + upnpSplitResult.query
        if upnpSplitResult.fragment:
            pathPart += "#" + upnpSplitResult.fragment

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
        raise ValueError("Not a valid UPNP URL: %s" % url)


##############################################################################
class _StringSock(object):
    """A fake socket-like object that points to a string.

    This implements just enough to feed to httplib.HTTPResponse.
    """
    ###########################################################
    def __init__(self, allData):
        """_StringSock constructor.

        @param  allData  The string to point to.
        """
        super(_StringSock, self).__init__()
        self._allData = allData


    ###########################################################
    """NO_OBS makefile"""
    def makefile(self, mode, bufsize):
        """Make a file out of our string.

        @param  mode     Ignored.
        @param  bufsize  Ignored.
        """
        _ = mode
        _ = bufsize
        return StringIO.StringIO(self._allData)



##############################################################################
def main():
    cpm = ControlPointManager(None)
    while True:
        changedUsns, goneUsns = cpm.pollForChanges()
        for usn in changedUsns:
            print time.asctime()
            print "%s:\n%s\n%s\n%s\n%s\n\n---\n" % (
                usn,
                cpm.getDevice(usn).getFriendlyName(),
                cpm.getDevice(usn).getPresentationUrl(),
                cpm.getDevice(usn).getModelName(),
                str(cpm.getDevice(usn))
            )

        for usn in goneUsns:
            print time.asctime()
            print "GONE: %s:\n\n---\n" % (usn)
        time.sleep(.1)


if __name__ == '__main__':
    main()
