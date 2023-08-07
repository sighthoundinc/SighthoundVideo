#!/usr/bin/env python

#*****************************************************************************
#
# EnsureUnicode.py
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
import hashlib

# Common 3rd-party imports...

# Toolbox imports...

# Local imports...

# Constants...


##############################################################################
def ensureUnicode(strOrUnicode, encoding="utf-8"):
    """Ensures that the given "string" is of type unicode.

    This function does nothing if it's already unicode.  Otherwise, it decodes
    using the passed encoding.

    This is _DIFFERENT_ than just "casting" the object as a unicode object by
    doing something like this:
       unicode(strOrUnicode)

    ...since that mechanism will use ASCII to convert to unicode if the string
    isn't unicode, which usually fails.
       Try: unicode('Arden.ai\xc2\xae Video')

    It's also _DIFFERENT_ than casting with an encoding like this:
       unicode(strOrUnicode, 'utf-8')

    ...since that will fail if the string is already unicode:
       Try: unicode(u'Arden.ai\xae Video', 'utf-8')


    Note: doctest examples have an extra backslash in them to make doctest work.

    >>> ensureUnicode('Arden.ai\xc2\xae Video')
    u'Arden.ai\\xae Video'

    >>> ensureUnicode(ensureUnicode('Arden.ai\xc2\xae Video'))
    u'Arden.ai\\xae Video'

    >>> ensureUnicode('Arden.ai\xae Video', 'windows-1252')
    u'Arden.ai\\xae Video'

    >>> ensureUnicode(u'Arden.ai\xae Video', 'windows-1252')
    u'Arden.ai\\xae Video'


    @param  strOrUnicode  A unicode object, or a string encoded w/ the passed
                          encoding.
    @param  encoding      If strOrUnicode is not of type unicode, it will be
                          decoded using this encoding.
    @return u             If strOrUnicode was of type unicode, returns it.  If
                          not, this is it decoded with the encoding.
    """
    if strOrUnicode is None:
        return "None"

    if isinstance(strOrUnicode, unicode):
        return strOrUnicode
    else:
        return strOrUnicode.decode(encoding)


##############################################################################
def ensureUtf8(strOrUnicode, encoding="utf-8"):
    """A shortcut for ensureUnicode(usn, encoding).encode('utf-8').

    @param  strOrUnicode  A unicode object, or a string encoded w/ the passed
                          encoding.
    @param  encoding      If strOrUnicode is not of type unicode, it will be
                          decoded using this encoding.
    @return s             The result of:
                            ensureUnicode(usn, encoding).encode('utf-8')
    """
    return ensureUnicode(strOrUnicode, encoding).encode('utf-8')


##############################################################################
def simplifyString(strOrUnicode, encoding="utf-8"):
    """Strings with special chars can be problematic. Generate a 'safe' name.

    @param  strOrUnicode  A unicode object, or a string encoded w/ the passed
                          encoding.
    @return hash          A hash of strOrUnicode.
    """
    return hashlib.md5(ensureUtf8(strOrUnicode)).hexdigest()


##############################################################################
def test_main():
    """OB_REDACT
    Our main function, which runs test code
    """
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    test_main()
