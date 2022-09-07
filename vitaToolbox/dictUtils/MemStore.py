#!/usr/bin/env python

#*****************************************************************************
#
# MemStore.py
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


import threading, time, copy

###############################################################################
class MemStore(object):
    """ Thread-safe in-memory key/value store with versioning, externally
    driven expiration and long-poll support. The version scheme used is ever
    increasing integers, so a newer item will always carry a higher number,
    however not in increments of 1, but arbitrary ones. So even if an item
    expires and isn't in the list for a while and reappears later, its version
    number will be higher than that of a former generation.
    """

    ###########################################################
    def __init__(self, lock=None, now=time.time):
        """ Constructor.

        @param lock Lock to use, None to create an internal (RLock) one.
        @param now Function returning a time.time() compatible value, optional.
        """
        lock = threading.RLock() if lock is None else lock
        self._cond = threading.Condition(lock=lock)
        self._now = now
        self._data = {}
        self._version = 0


    ###########################################################
    def put(self, key, value, ttl=-1):
        """ Puts or updates data.

        @param key The key, as a string.
        @param value The value. Must be able to deep-copy it though.
        @param ttl Expiration time in seconds. -1 for no expiration.
        @return The new version of the item.
        """
        self._cond.acquire()
        try:
            version = self._version
            self._version += 1
            expires = -1 if -1 == ttl else self._now() + ttl
            self._data[key] = (version, expires, value)
            return version
        finally:
            try:
                self._cond.notifyAll()
            finally:
                self._cond.release()


    ###########################################################
    def get(self, key, timeout=0, oldVersion=None):
        """ Gets data. Expired items will not be returned, but purged.

        @param key The key, as a string.
        @param timeout Number of seconds to wait for an item to appear or to
        be updated to a new version.
        @param oldVersion The current version the caller has, who wants to get a
        different instance of the data. None by default, meaning any value will
        be returned.
        @return Copy of the item, a tuple (version, expiration, data). Or None.
        """
        self._cond.acquire()
        try:
            now = self._now()
            brk = now + timeout
            while now <= brk:
                item = self._data.get(key, None)
                if item is not None:
                    expires = item[1]
                    if -1 != expires and expires <= now:
                        self._data.pop(key)
                        item = None
                    else:
                        if oldVersion is None or oldVersion < item[0]:
                            item = copy.deepcopy(item)
                        else:
                            item = None
                if item or now >= brk:
                    return item
                self._cond.wait(brk - now)
                now = self._now()
        finally:
            self._cond.release()


    ###########################################################
    def remove(self, key):
        """ Removes data.

        @param key The key, as a string.
        @return Removed item, a tuple (version, expiration, data), no matter if
        it expired or not. Or None.
        """
        self._cond.acquire()
        notify = False
        try:
            notify = self._data.has_key(key)
            return self._data.pop(key) if notify else None
        finally:
            try:
                if notify:
                    self._cond.notifyAll()
            finally:
                self._cond.release()


    ###########################################################
    def expire(self):
        """ Expire items. Should be called on a regular interval to avoid
        things piling up.

        @param key The key, as a string.
        @return Removed item, a tuple (version, expiration, data). Or None.
        """
        result = 0
        self._cond.acquire()
        notify = False
        try:
            now = self._now()
            for key in self._data.keys():
                item = self._data[key]
                expiresAt = item[1]
                if expiresAt != -1 and expiresAt <= now:
                    notify = True
                    self._data.pop(key)
                    result += 1
            return result
        finally:
            try:
                if notify:
                    self._cond.notifyAll()
            finally:
                self._cond.release()
