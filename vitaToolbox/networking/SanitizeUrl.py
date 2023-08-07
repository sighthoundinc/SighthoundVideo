#!/usr/bin/env python

#*****************************************************************************
#
# SanitizeUrl.py
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
import re
import urlparse

# Common 3rd-party imports...

# Local imports...


##############################################################################
def sanitizeUrl(url):
    """Return a version of the given url with user, password, and IP stripped.

    @param  url       The original URL.
    @return cleanUrl  A clean version of the URL.
    """
    uriScheme, uriNetloc, uriPath, uriQuery, uriFragment = \
        urlparse.urlsplit(url)

    # Replace any auth information by 'x', and any location information other
    # than . and : with x.
    authPart, atSign, locPart = uriNetloc.partition('@')
    if not atSign:
        # Partition almost does what we want, but if no @ sign we'd rather have
        # the info in locPart...
        assert locPart == ""
        locPart = authPart
        authPart = ""
    authPart = 'x' * len(authPart)
    locPart = re.sub(r'[^\.\:]', r'x', locPart)

    # Heuristically replace query parameter's values looking like passwords.
    for var in ['pwd', 'password', 'passw']:
        p = re.compile("((%s)=[^&]*)" % var, re.IGNORECASE)
        uriQuery = p.sub(lambda m: "%s=xxxxxx" % m.group(2), uriQuery)

    uriNetloc = (authPart + atSign + locPart)

    url = urlparse.urlunsplit((uriScheme, uriNetloc, uriPath,
                               uriQuery, uriFragment))

    return url


##############################################################################
def processUrlAuth(url):
    """Process authentification info in the given URL.

    The function has a double purpose.  It:
    1. Replaces __USERNAME__ and __PASSWORD__ in the url with the username or
       password from the auth part of the URL (it still leaves it in the auth
       part).  This is because some cameras want the user/password to be in
       the URL.  ...and leaving them in the auth part doesn't hurt, since
       FFMPEG will only try them from there if noauth doesn't work.
    2. Clean the URL, with user, password, and IP stripped.  This has to be
       done at the same time as the above since we won't know how to strip
       the username/password after this function runs.

    # User and pass; no reference to __USERNAME__ or __PASSWORD__
    >>> processUrlAuth(u'http://myuser:mypass@www.yahoo.com/foo?abc&def=ghi')
    (u'http://myuser:mypass@www.yahoo.com/foo?abc&def=ghi', u'http://xxxxxxxxxxxxx@xxx.xxxxx.xxx/foo?abc&def=ghi')

    # User and pass; reference to __USERNAME__ and __PASSWORD__
    >>> processUrlAuth(u'http://uu:pp@www.z.com/path?u=__USERNAME__&pw=__PASSWORD__')
    (u'http://uu:pp@www.z.com/path?u=uu&pw=pp', u'http://xxxxx@xxx.x.xxx/path?u=xx&pw=xx')

    # No username or password, but still putting it in the URL
    >>> processUrlAuth(u'http://www.z.com/path?u=__USERNAME__&pw=__PASSWORD__')
    (u'http://www.z.com/path?u=&pw=', u'http://xxx.x.xxx/path?u=xx&pw=xx')

    # Just a username
    >>> processUrlAuth(u'http://uu@www.z.com/path?u=__USERNAME__&pw=__PASSWORD__')
    (u'http://uu@www.z.com/path?u=uu&pw=', u'http://xx@xxx.x.xxx/path?u=xx&pw=xx')

    # Username but blank password
    >>> processUrlAuth(u'http://uu:@www.z.com/path?u=__USERNAME__&pw=__PASSWORD__')
    (u'http://uu:@www.z.com/path?u=uu&pw=', u'http://xxx@xxx.x.xxx/path?u=xx&pw=xx')

    # RTSP:
    >>> processUrlAuth(u'rtsp://uu:pp@www.z.com/path?u=__USERNAME__&pw=__PASSWORD__')
    (u'rtsp://uu:pp@www.z.com/path?u=uu&pw=pp', u'rtsp://xxxxx@xxx.x.xxx/path?u=xx&pw=xx')

    # Screwy stuff
    >>> processUrlAuth(u'device:9999:My w@cky web:cam')
    (u'device:9999:My w@cky web:cam', u'device:9999:My w@cky web:cam')

    >>> processUrlAuth(u'')
    (u'', u'')

    >>> processUrlAuth(u'__USERNAME____USERNAME____PASSWORD__')
    (u'', u'xxxxxx')

    @param  url       The URL to process.
    @return url       The URL w/ username / password in the URL (if needed)
    @return cleanUrl  A clean version of the URL that can be used for logging.
    """
    uriScheme, uriNetloc, uriPath, uriQuery, uriFragment = \
        urlparse.urlsplit(url)

    # Replace any auth information by 'x', and any location information other
    # than . and : with x.
    authPart, atSign, locPart = uriNetloc.partition('@')
    if not atSign:
        # Partition almost does what we want, but if no @ sign we'd rather have
        # the info in locPart...
        assert locPart == ""
        locPart = authPart
        authPart, username, password = ('', '', '')
    else:
        username, _, password = authPart.partition(':')
    authPart = 'x' * len(authPart)
    locPart = re.sub(r'[^\.\:]', r'x', locPart)

    uriNetloc = (authPart + atSign + locPart)

    sanitizedUrl = urlparse.urlunsplit((uriScheme, uriNetloc, uriPath,
                                        uriQuery, uriFragment))

    # Just put xx in there, rather than trying to keep the same length.
    # Don't want the length because it exposes how long the username/password
    # is (we've already exposed how long the username + password are together,
    # but this seems one step worse?)  ...but want some replacement because it
    # shows that this code ran...
    sanitizedUrl = sanitizedUrl.replace('__USERNAME__', 'xx')
    sanitizedUrl = sanitizedUrl.replace('__PASSWORD__', 'xx')

    url = url.replace('__USERNAME__', username)
    url = url.replace('__PASSWORD__', password)

    return url, sanitizedUrl


##############################################################################
def _runTests():
    """OB_REDACT
       Run any self-tests.  This will be removed from obfuscated code.
    """
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    _runTests()
