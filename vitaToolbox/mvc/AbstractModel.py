#!/usr/bin/env python

#*****************************************************************************
#
# AbstractModel.py
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


import weakref
import copy

class AbstractModel(object):
    """Super class of many subclasses that want to be a MVC model."""


    ###########################################################
    def __init__(self):
        """AbstractModel constructor."""
        # We store two different kinds of listeners: those that want a key
        # passed to them and those that don't.  We store them based on the
        # key that they're interested in.  We'll use the key "None" if they
        # want all keys.
        self.listeners = { None: [] }
        self.listenersWithKeyParam = { None: [] }


    ###########################################################
    def addListener(self, listenerFunc, wantKeyParam=False, key=None,
                    strongRef=False):
        """Add the given function as a listener of the data model.

        If the listenerFunc is a bound method (it has the attribute im_self),
        we will by default add a _weak reference_ to the method bound "self".
        This is a bit complicated, but the basic idea is that calling:
            model.addListener(obj.method)
        will _NOT_ increase the reference count of 'obj'.  Once no more copies
        of 'obj' are stored elsewhere, 'obj' will be deleted and we will
        automatically remove obj.method from the list of listeners.  This is
        almost always what you want.

        If a key is given, the listener will only be called for updates that
        match the given key.  If a key is not given, the listener will be
        called for all updates.

        @param  listenerFunc  The function that will be called on updates.
                              If wantKeyParam is False, this should take one
                              parameter (the data model).  If wantKeyParam is
                              True, it should take two (the data model and key).
        @param  wantKeyParam  If True, we'll pass the key that update() is
                              called with to the listenerFunc.  Otherwise, we
                              won't (default=False).
        @param  key           If specified, we'll only call the listenerFunc
                              for updates of a certain key (default=None).
        @param  strongRef     Normally we only keep a weak reference to the
                              the bound object in listenerFunc.  Setting this
                              to True will make it a strong one.
        @return listenerFunc  The function that was actually registered.  If you
                              want to call removeListener(), you should use
                              this.  This may be different than the
                              listenerFunc passed in if we needed to create
                              a weak reference.
        """
        if wantKeyParam:
            destDict = self.listenersWithKeyParam
        else:
            destDict = self.listeners

        # Register a weak reference if we can...
        if (not strongRef) and hasattr(listenerFunc, "im_self"):
            # Get the weakObj and actual function now.  That way newListenerFunc
            # will not create a reference to the original listenerFunc...
            weakObj = weakref.ref(listenerFunc.im_self)
            actualFunc = listenerFunc.im_func

            # We'll use this as the listener func...
            def newListenerFunc(*args, **kwargs):
                # Don't reference "self" here--instead use the first argument
                # (which should be the same thing).  This should make deepcopy
                # of our subclasses work better...  Thus, the bound variables are:
                # - weakObj and actualFunc (both which come from listenerFunc)
                # - wantKeyParam
                # - key
                model = args[0]

                origObj = weakObj()
                if origObj is None:
                    # We remove stale weakrefs right before calling...
                    model.removeListener(newListenerFunc, wantKeyParam, key)
                elif origObj.__class__.__name__ == '_wxPyDeadObject':
                    # We shouldn't get here, but we'll try to handle it
                    # in release code (since some users were seeing it).  Leave
                    # the assert in so we can try to figure out how it's
                    # hapening in debug mode...
                    if __debug__:
                        print "Shouldn't have dead object lying around."
                        import gc
                        print str(gc.get_referrers(origObj))

                    model.removeListener(newListenerFunc, wantKeyParam, key)
                else:
                    actualFunc(origObj, *args, **kwargs)
            listenerFunc = newListenerFunc

        if key not in destDict:
            destDict[key] = []
        destDict[key].append(listenerFunc)

        return listenerFunc


    ###########################################################
    def removeListener(self, listenerFunc, wantedKeyParam=False, key=None):
        """Remove the given listener.

        See addListener() for details--this is the opposite.

        @param  listenerFunc    The function that was passed to addListener()
        @param  wantedKeyParam  The value of wantKeyParam that was passed to
                                addListener() (default=False).
        @param  key             The value of key that was passed to
                                addListener() (default=None).
        """
        if wantedKeyParam:
            destDict = self.listenersWithKeyParam
        else:
            destDict = self.listeners

        destDict[key].remove(listenerFunc)
        if (key is not None) and (not destDict[key]):
            del destDict[key]


    ###########################################################
    def update(self, key=None):
        """Send updates to listeners.

        We will call the listeners and tell them that there was an update to
        the data model.  If a key is passed in, we will only call listeners
        that registered with that key (plus those that registered without
        passing in a key).

        @param  key  If None, we'll only update listeners that registered
                     without a key.  If non-none, we'll update listeners that
                     registered with that key plus all those that registered
                     without a key.
        """
        # Note: in all iterations below, it's important to make a copy of the
        # list.  That's because functions are allowed to remove themselves
        # from the list (like happens with weak references).

        # If a key was specified, first notify all of the listeners that only
        # wanted to know about that key...
        if (key is not None):
            if key in self.listenersWithKeyParam:
                for eachFunc in self.listenersWithKeyParam[key][:]:
                    eachFunc(self, key)
            if key in self.listeners:
                for eachFunc in self.listeners[key][:]:
                    eachFunc(self)

        # Now, notify all listeners that want to be told about all updates...
        for eachFunc in self.listenersWithKeyParam[None][:]:
            eachFunc(self, key)
        for eachFunc in self.listeners[None][:]:
            eachFunc(self)


    ###########################################################
    def __getstate__(self):
        """Return state information necessary to pickle the object

        @return state  State information from which the object can be restored
        """
        stateDict = copy.copy(self.__dict__)
        stateDict['listenersWithKeyParam'] = {None: []}
        stateDict['listeners'] = {None: []}

        return stateDict


##############################################################################
def _simpleTest():
    """OB_REDACT
       A simple test function to exercise basic functionality."""
    outputs = []

    model = AbstractModel()
    class C(object):
        def justPrint(self, m):
            assert m == model
            outputs.append("justPrint")
    def printKey(m, k):
        assert m == model
        outputs.append("printKey: " + str(k))
    def printKey2(m, k):
        assert m == model
        outputs.append("printKey2: " + str(k))
    def justPrint2(m):
        assert m == model
        outputs.append("justPrint2")

    # Expect:
    #   justPrint
    #   justPrint
    c = C()
    jp = model.addListener(c.justPrint)
    _ = jp # we will never remove jp

    model.update()
    assert (outputs.pop(0) == "justPrint")

    model.update("key1")
    assert (outputs.pop(0) == "justPrint")

    # Expect:
    #   printKey: None
    #   justPrint
    #   printKey: key2
    #   justPrint
    pk = model.addListener(printKey, True)

    model.update()
    outputs.sort()
    assert (outputs.pop(0) == "justPrint")
    assert (outputs.pop(0) == "printKey: None")

    model.update("key2")
    outputs.sort()
    assert (outputs.pop(0) == "justPrint")
    assert (outputs.pop(0) == "printKey: key2")

    # Expect:
    #   printKey, None
    #   justPrint
    #   printKey, key2
    #   justPrint
    #   printKey2, pk2
    #   printKey, pk2
    #   justPrint
    pk2 = model.addListener(printKey2, True, "pk2")

    model.update()
    outputs.sort()
    assert (outputs.pop(0) == "justPrint")
    assert (outputs.pop(0) == "printKey: None")

    model.update("key2")
    outputs.sort()
    assert (outputs.pop(0) == "justPrint")
    assert (outputs.pop(0) == "printKey: key2")

    model.update("pk2")
    outputs.sort()
    assert (outputs.pop(0) == "justPrint")
    assert (outputs.pop(0) == "printKey2: pk2")
    assert (outputs.pop(0) == "printKey: pk2")

    # Except:
    #   printKey, None
    #   justPrint2
    model.addListener(justPrint2)
    del c

    model.update()
    outputs.sort()
    assert (outputs.pop(0) == "justPrint2")
    assert (outputs.pop(0) == "printKey: None")

    # Try removing.  This doesn't exercise all code, but at least do the
    # bare minimum test to make sure it doesn't crash...  Expect no output.
    model.removeListener(pk, True)
    model.removeListener(pk2, True, "pk2")
    model.removeListener(justPrint2)
    model.update()
    model.update("key2")
    model.update("pk2")

    assert len(outputs) == 0

    print "AbstractModel test: Success..."


##############################################################################
if __name__ == '__main__':
    _simpleTest()
