#!/usr/bin/env python

#*****************************************************************************
#
# Obfuscate.py
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

import sys, random, base64

"""
## @file
Obfuscation functions based on doing an XOR of an 8bit random sequence over a
string's characters. The sequence is generated by Python's Wichmann-Hill PRNG,
an 16bit (two characters) salt value is used to make the obfuscated result
different and not too easy to guess. This is just for hiding purposes, since the
'secret' key and the method can be dug up easily it should NOT be used for truly
sensitive data!
"""

# the global "secret" for obfuscation
_kSecret = 0xb3ec6759ec8c2328

###############################################################################
def save(text, secret=_kSecret):
    """ Obfuscates a string.

    @param text    The text to obfuscate
    @param secret  The individual secret value to obfuscation, 64bit integer.
    @return        The obfuscated value. Likely to be different on every call.
    """
    rnd = random.SystemRandom()
    slt = rnd.randint(0, 32767)
    gen = random.WichmannHill(secret + slt)
    result = chr(slt >> 8) + chr(slt & 255)
    for c in text:
        result += chr(ord(c) ^ gen.getrandbits(8))
    return base64.b64encode(result)


###############################################################################
def load(text, secret=_kSecret):
    """ De-obfuscates a string formerly obfuscated with the save() function.

    @param text        The text to de-obfuscate.
    @param secret      The individual secret value (int64) to obfuscation. Must
                       match what was used for obfuscation before, otherwise
                       only gibberish gets returned.
    @return            The (hopefully) de-obfuscated text.
    @raise ValueError  If the text somehow caused a decoding error.
    """
    try:
        enc = base64.b64decode(text)
        slt = (ord(enc[0]) << 8) | ord(enc[1])
        gen = random.WichmannHill(secret + slt)
        result = ""
        for c in enc[2:]:
            result += chr(ord(c) ^ gen.getrandbits(8))
        return result
    except:
        raise ValueError(str(sys.exc_info()[1]))


###############################################################################

if __name__ == '__main__':
    print save(sys.argv[1])

