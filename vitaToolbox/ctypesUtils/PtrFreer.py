#!/usr/bin/env python

#*****************************************************************************
#
# PtrFreer.py
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
import ctypes


##############################################################################
class PtrFreer(object):
    """An object used to add refcounted frees to pointers returned by ctypes.

    As a simple example, you can use this class like this:
       p = allocate_some_ctypes_pointer_object()
       p.__freer = PtrFreer(p, free_the_ctypes_pointer_object)

    Now, when there are no more references to the pointer, the free function
    will be called.  ...but, as with a lot fo ctypes, things aren't always
    quite that straightforward.  I'll try to explain more, and hopefully that
    will help with some of the weird corner cases...


    The fundamental thing to realize here is that ctypes "pointer" objects
    are full python objects.  That means two things:
    - Anyone who makes a simple python "copy" of this pointer is actually
      getting a reference to the same ctypes pointer object.
    - You can store anything you want in the object as sorta metadata.

    For instance, I can do the following:
      p = ctypes.POINTER(ctypes.c_uint8)
      p.myName = "Doug"
      q = p
      print q.myName
    ...the above will print "Doug".

    The above facts are all that is needed for PtrFreer to work.  Specifically,
    what we do is we ask you to store a reference to a PtrFreer object somewhere
    in your ctypes pointer.  As long as someone keeps a refernece to the
    ctypes pointer object around, there will be a reference to the PtrFreer
    object.  When they're all gone, then the PtrFreer's destructor will be
    called and we can call the proper free function.  Note that PtrFreer
    doesn't keep a reference to the pointer object (it creates a new object
    with the same data), so you don't get into refcount loops.


    Now, that you understand the above (hopefully), I can explain the corner
    cases.  The key is to remember that memory will be freed whenever the
    PtrFreer object is destructed, and that in the simple example, I kept a
    reference to the PtrFreer object in the original pointer object:
    * If you cast the pointer object to another type, you'll get a new pointer
      object which will not automatically get a refernece to your PtrFreer.
    * If you pass the pointer back into C code, the C code will not get a
      reference to the PtrFreer object.
    """

    ###########################################################
    def __init__(self, toFree, freeFn):
        """Constructor for PtrFreer objects.

        @param  toFree  Should be a ctypes POINTER object of something we'd
                        like to add refcounting to.
        @param  freeFn  The function to call when the refcount goes to zero.
        """
        # Save the address of the pointer.  This is important because it
        # fools python into thinking we don't have a reference anymore, but
        # still stores the info we need to free it.
        self._addr = ctypes.addressof(toFree.contents)

        # Also save the type, just so we have type safety...
        self._type = type(toFree)

        # Obviously, we need the free function to call...
        self._freeFn = freeFn

    ###########################################################
    def __del__(self):
        # On destruction, free right away...
        # ...but not if ctypes is gone (happens when we're quitting)
        if (self._addr is not None) and (ctypes is not None):
            self.freeNow()

    ###########################################################
    def freeNow(self):
        """Can be called to free right away.

        NOTE: In release code, double-free won't hurt, but generally we don't
        want to encourage it...
        """
        if self._addr is not None:
            #print "Freeing: %s" % str(self._type)
            self._freeFn(ctypes.cast(self._addr, self._type))
            self._addr = None
        else:
            assert False, "Double-free: %s" % (str(self._type))


##############################################################################
def withByref(fn):
    """Takes a func and returns one where argument is called with ctypes.byref.

    This is useful because some free functions require you to call them this way.

    @param  fn  A function that takes 1 argument.
    @return fn  A function that takes 1 argument.
    """
    return lambda x: fn(ctypes.byref(x))


