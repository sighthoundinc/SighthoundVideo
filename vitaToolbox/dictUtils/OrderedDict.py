#!/usr/bin/env python

#*****************************************************************************
#
# OrderedDict.py
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



# Python imports...
from   itertools import izip
import sys
from   UserDict import DictMixin


##############################################################################
class OrderedDict(object, DictMixin):
    """A dictionary object whose keys are ordered.

    Normally, a dictionary's keys are unordered.  However, at times this is a
    big hassle.  This dictionary's keys have an order: the order that you
    add them to the dictionary.

    A few rules:
    - The keys are ordered by the time when they are first assigned a value.
    - Modifying the value assigned to a key doesn't affect its order.
    - Deleting a key, then re-adding a value for it _does_ affect its order.
    - Two OrderedDicts are only equal if they have the same order.

    >>> d = OrderedDict([('a', 'b'), ('c', 'd'), ('e', 'f'), ('h', 'i'), ('J', 'K'), ('L', 'M')])
    >>> d
    OrderedDict([('a', 'b'), ('c', 'd'), ('e', 'f'), ('h', 'i'), ('J', 'K'), ('L', 'M')])

    >>> d.keys()
    ['a', 'c', 'e', 'h', 'J', 'L']

    >>> d.values()
    ['b', 'd', 'f', 'i', 'K', 'M']

    >>> d.items()
    [('a', 'b'), ('c', 'd'), ('e', 'f'), ('h', 'i'), ('J', 'K'), ('L', 'M')]

    >>> e = OrderedDict(d)
    >>> e.items()
    [('a', 'b'), ('c', 'd'), ('e', 'f'), ('h', 'i'), ('J', 'K'), ('L', 'M')]

    >>> (e == d) and (d == e)
    True

    >>> (e != d) or (d != e)
    False

    >>> del e['h']
    >>> e.keys()
    ['a', 'c', 'e', 'J', 'L']

    >>> e['h'] = 'i'
    >>> e.items()
    [('a', 'b'), ('c', 'd'), ('e', 'f'), ('J', 'K'), ('L', 'M'), ('h', 'i')]

    >>> d == e
    False

    >>> eval(repr(e))
    OrderedDict([('a', 'b'), ('c', 'd'), ('e', 'f'), ('J', 'K'), ('L', 'M'), ('h', 'i')])

    >>> e['x'] = 'y'
    >>> e.keys()[-1]
    'x'

    >>> e['a'] = 'B'
    >>> e.items()
    [('a', 'B'), ('c', 'd'), ('e', 'f'), ('J', 'K'), ('L', 'M'), ('h', 'i'), ('x', 'y')]
    """

    ###########################################################
    def __init__(self, seqOrMapping=None):
        """OrderedDict constructor.

        Note: we don't allow kwargs to be used to init a OrderedDict, since
        python doesn't guarantee that it will give us those in order!

        @param  seqOrMapping  A sequence or a mapping to use to init the
                              dictionary.  WARNING: If you init with a mapping,
                              we'll use iterkeys() on the mapping as the
                              ordering for the initial items.  This probably
                              isn't what you want unless the mapping is itself
                              an OrderedDict.
        """
        super(OrderedDict, self).__init__()

        if seqOrMapping is not None:
            # The dict constructor should handle either a sequence or a mapping.
            # Pass stuff to it and let it error check that the args are OK...
            self.__realDict = dict(seqOrMapping)

            # We should either have a mapping (which needs iterkeys()) or a
            # sequence (which has two-tuples).  Anything else should have been
            # caused an exception by the call to dict() above.
            try:
                self.__orderedKeys = list(seqOrMapping.iterkeys())
            except Exception:
                self.__orderedKeys = [k for (k, v) in seqOrMapping]
        else:
            # Just init to nothing...
            self.__realDict = {}
            self.__orderedKeys = []


    ###########################################################
    def __getitem__(self, key):
        """Get an item out of the dict.

        @param  key    The key to get.
        @return value  The value.
        """
        return self.__realDict[key]


    ###########################################################
    def __setitem__(self, key, value):
        """Set an item in the dict.

        @param  key    The key to set.
        @param  value  The value.
        """
        # If we've never seen this key before, add it to the end of the order.
        # Note: just modifying an item __doesn't__ reset its order...
        if key not in self.__realDict:
            self.__orderedKeys.append(key)

        self.__realDict[key] = value


    ###########################################################
    def __delitem__(self, key):
        """Delete an item in the dict.

        @param  key    The key to delete.
        """
        # We get rid of it from the order...
        if key in self.__realDict:
            self.__orderedKeys.remove(key)

        del self.__realDict[key]


    ###########################################################
    def keys(self):
        """Return the keys.

        @return keys   The keys, in order.
        """
        # Return a COPY, since that's the interface for keys()
        return list(self.__orderedKeys)


    ###########################################################
    def __contains__(self, key):
        """Return whether the dictionary contains the given key.

        @param  key          The key to test.
        @return doesContain  True if the key is in the dict.
        """
        return key in self.__realDict


    ###########################################################
    def __iter__(self):
        """Return an iterator over the keys.

        @return keyIter  An iterator over the keys, in order.
        """
        # Use the 'iter' wrapper so that the user doesn't accidentally modify.
        return iter(self.__orderedKeys)


    ###########################################################
    def iteritems(self):
        """Return an iterator over the items.

        @return itemIter  An iterator over the items, in order.
        """
        # Use a simple generator...
        return ((k, self.__realDict[k]) for k in self.__orderedKeys)


    ###########################################################
    def __str__(self):
        """Gives a nice representation of the recognition object.

        This doesn't need to be enough to completely reconstruct the object;
        it's just a nice, printable, summary.

        @return  s  Our string representation.
        """
        return '{' + \
               ', '.join('%s: %s' % (repr(k), repr(v))
                         for (k, v) in self.iteritems()) + \
               '}'


    ###########################################################
    def __repr__(self):
        """Gives representation of ourselves suitable for reconstruction.

        @return  s  Our string representation.
        """
        return self.__class__.__name__ + '(' + str(self.items()) + ')'


    ###########################################################
    def __eq__(self, other):
        """Return whether we're equal to an other object.

        @param  other  Another to compare to.
        """
        # We're only equal to ourselves or subclasses.  Specifically, we don't
        # want to be equal to a normal dictionary, even if its keys just happen
        # to come out in the same order as ours.
        if isinstance(other, OrderedDict):
            return self.items() == other.items()
        return False



##############################################################################
def test_main():
    """Contains various self-test code."""
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
