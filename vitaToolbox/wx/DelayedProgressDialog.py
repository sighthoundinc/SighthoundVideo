#!/usr/bin/env python

#*****************************************************************************
#
# DelayedProgressDialog.py
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
import sys
import time

# Common 3rd-party imports...
import wx


##############################################################################
class DelayedProgressDialog(object):
    """A ProgressDialog that only shows if an operation is slow.

    Basically, this will delay creating a progress dialog until a certain amount
    of time has passed.

    This is purposely not a subclass of wx.ProgressDialog.  We may never
    actually create a progress dialog (if we are destroyed before enough time
    passes).  Because of this, we have to implement the pieces of the dialog
    that we need.
    """

    ###########################################################
    def __init__(self, delay, *args, **kwargs):
        """DelayedProgressDialog constructor.

        @param  delay   The delay before actually creating the progress dialog,
                        in seconds.
        @param  args    Args to pass to the progress dialog.
        @param  kwargs  Args to pass to the progress dialog.
        """
        super(DelayedProgressDialog, self).__init__()

        self._delay = delay
        self._args = args
        self._kwargs = kwargs

        self._dlg = None

        self._latestValue = None
        self._latestMessage = ""

        self._startTime = time.time()


    ###########################################################
    def Pulse(self, newMsg=""):
        """Wrap the Pulse() method.

        @param  newMsg    The new message
        @return continue  True normally; False if the cancel button was used.
        @return skip      False normally; True if the skip button was used.
        """
        if self._dlg:
            return self._dlg.Pulse(newMsg)
        else:
            self._latestValue = None
            if newMsg:
                self._latestMessage = newMsg

            self._createIfNeeded()

            return True, False


    ###########################################################
    def Update(self, newValue, newMsg=""):
        """Wrap the Update() method.

        @param  newValue  The new value.
        @param  newMsg    The new message.
        @return continue  True normally; False if the cancel button was used.
        @return skip      False normally; True if the skip button was used.
        """
        if self._dlg:
            return self._dlg.Update(newValue, newMsg)
        else:
            self._latestValue = newValue
            if newMsg:
                self._latestMessage = newMsg

            self._createIfNeeded()

            return True, False


    ###########################################################
    def Destroy(self):
        """Wrap the Destroy() method."""
        if self._dlg:
            self._dlg.Destroy()
            self._dlg = None


    ###########################################################
    def _createIfNeeded(self):
        """Create the dialog if needed."""
        if (self._dlg is None) and \
           ((time.time() - self._startTime) > self._delay):

            self._dlg = wx.ProgressDialog(*self._args, **self._kwargs)

            if self._latestValue is not None:
                self._dlg.Update(self._latestValue, self._latestMessage)
            else:
                self._dlg.Pulse(self._latestMessage)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)
    _ = app

    # First, do a pulse for 5 seconds, waiting 1.5 seconds before showing...
    dlg = DelayedProgressDialog(1.5, "Just a moment...",
                                "Just a moment...                             ",
                                parent=None, style=wx.PD_APP_MODAL)
    try:
        startTime = time.time()

        i = 0
        while time.time() - startTime < 5:
            dlg.Pulse("%s: %d" % (time.asctime(), i))
            i += 1
    finally:
        dlg.Destroy()

    # Now, a pulse for 1 second, waiting 1.5 seconds before showing (shouldn't
    # show the dialog...)
    dlg = DelayedProgressDialog(1.5, "Just a moment...",
                                "Just a moment...                             ",
                                parent=None, style=wx.PD_APP_MODAL)
    try:
        startTime = time.time()

        i = 0
        while time.time() - startTime < 1:
            dlg.Pulse("%s: %d" % (time.asctime(), i))
            i += 1
    finally:
        dlg.Destroy()

    # Now, a update for 3 seconds, waiting 1.5 seconds before showing...
    dlg = DelayedProgressDialog(1.5, "Just a moment...",
                                "Just a moment...                             ",
                                maximum=300,
                                parent=None, style=wx.PD_APP_MODAL)
    try:
        startTime = time.time()

        i = 0
        while time.time() - startTime < 3:
            val = int(round((time.time() - startTime) * 100))
            dlg.Update(val, "%s: %d" % (time.asctime(), i))
            i += 1
    finally:
        dlg.Destroy()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
