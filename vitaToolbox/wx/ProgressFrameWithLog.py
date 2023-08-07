#!/usr/bin/env python

#*****************************************************************************
#
# ProgressFrameWithLog.py
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

# Toolbox imports...
from FontUtils import makeFontDefault

# Constants...

_kDefaultWidth = 500
_kDefaultHeight = 400

##############################################################################
class ProgressFrameWithLog(wx.Frame):
    """A progress dialog that also contains a log window.

    This is not an actual subclass of wx.ProgressDialog, since that class has
    too many weird / undocumented behaviors.  In fact, we're not even
    technically a dialog, but instead are a frame.

    NOTES:
    - We don't support everything progress dialog does.

    TODO:
    - Disable parent window using parent.Enable(False), at least if a parent
      window was specified.
    - If PD_APP_MODAL flag is set, use wx.WindowDisabler() to disable everyone
      but us.  This is like pyprogress does.
    - Support more stuff that the normal progress dialogs does.
    - Support options.  Right now, we assume:
      - Can cancel
      - Non-modal
    """

    ###########################################################
    def __init__(self, parent, title, message, maximum=100, minSize=(-1, -1),
                 style=wx.CAPTION | wx.SYSTEM_MENU | wx.RESIZE_BORDER):
        """Initializer for ProgressFrameWithLog

        Note: purposely has things in a little different order than progress
        dialog.  This is partly because I think this makes more sense, and
        partly because the client should make sure to note that we're not a
        drop-in replacement.  Specifically, we don't take in the progress
        manager styles.

        TODO: Add a parameter allowing the user to specify some of the
        progress dialog-type features.  See class docstring.

        @param  parent   The UI parent.
        @param  title    The title for the dialog
        @param  message  Initial text to be displayed above the progress bar
        @param  maximum  The maximum to show in the gague.
        @param  minSize  The minimum size of the window; if (-1, -1), we'll use
                         some reasonable defaults (unlike wx).
        @param  style    The WINDOW style.  Don't pass wx.PD_ flags here.
                         Note that you can do things like
                         wx.FRAME_FLOAT_ON_PARENT, which is a really useful
                         style for progress dialogs.
        """
        super(ProgressFrameWithLog, self).__init__(
            parent, -1, title, style=style
        )

        minWidth, minHeight = minSize
        if minWidth == -1:
            minWidth = _kDefaultWidth
        if minHeight == -1:
            minHeight = _kDefaultHeight
        self.SetMinSize((minWidth, minHeight))

        self._shouldCancel = False
        self._isDone = False

        self._doneCallbackFn = None
        self._doneCallbackArgs = None
        self._doneCallbackKwargs = None

        self._wantYields = True

        self._initUiWidgets()

        self._gauge.SetRange(maximum)
        self._label.SetLabel(message)

        self.Fit()

        # Set a default menu bar, otherwise the Mac version gets confused
        # and uses the first frame's menu bar
        if wx.Platform == '__WXMAC__':
            self.SetMenuBar(wx.MenuBar())

        # Adjust focus, since on Mac it looks really ugly to have focus on
        # the text field...
        self._button.SetFocus()

        self.CenterOnParent()
        self.Show()


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        self._panel = wx.Panel(self)

        self._label = wx.StaticText(self._panel, -1, "",
                                    style=wx.ST_NO_AUTORESIZE)
        self._gauge = wx.Gauge(self._panel, -1, 100)

        self._console = wx.TextCtrl(self._panel, -1, style=wx.TE_MULTILINE |
                                    wx.TE_BESTWRAP | wx.TE_READONLY)
        makeFontDefault(self._console)
        self._console.SetMinSize((0, 200))

        buttonSizer = wx.StdDialogButtonSizer()
        self._button = wx.Button(self._panel, wx.ID_CANCEL)
        buttonSizer.AddButton(self._button)
        buttonSizer.Realize()

        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.Add(self._label, 0, wx.EXPAND | wx.BOTTOM, 8)
        mainSizer.Add(self._gauge, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                      wx.EXPAND | wx.BOTTOM, 16)
        mainSizer.Add(self._console, 1, wx.EXPAND | wx.BOTTOM, 8)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self._panel.SetSizer(borderSizer)

        frameSizer = wx.BoxSizer()
        frameSizer.Add(self._panel, 1, wx.EXPAND)

        # Bind...
        self.Bind(wx.EVT_BUTTON, self.OnButton, id=wx.ID_CANCEL)


    ###########################################################
    def enableYields(self, wantEnabled=True):
        """Enable / disable yielding.

        This will enable / disable calls to wx's Yield() when Update() or
        Pulse() are called.  By default, calling Yield() is enabled.

        Doing yields is a little sketchy and tends to make things not work
        all that smoothly, but is needed if we're blocking the UI thread while
        doing our long-running process.  If you can disableYields() and still
        have everything work right (like if you're doing your processing in
        a background timer task), that's better.

        @param  wantEnabled  True if you want yields enabled.
        """
        self._wantYields = wantEnabled


    ###########################################################
    def appendConsoleText(self, text, noReturn=False):
        """Add text to the scrolling text box

        @param  text      The text to append
        @param  noReturn  If True, we won't append a carriage return before
                          appending the text.
        """
        if text is None:
            return

        if (not self._console.IsEmpty()) and (not noReturn):
            text = '\n' + text
        self._console.AppendText(text)


    ###########################################################
    def setDone(self, doneCallbackFn=None, *doneCallbackArgs,
                **doneCallbackKwargs):
        """Change the dialog to it's completed state.

        Once this happens, you shouldn't call Update() or Pulse() any more.

        @param  doneCallbackFn  A function that will be called back when the
                                progress frame is actually done.  This will be
                                called right before the frame is closed.
        @param  ...             Any other parameters will be passed to to
                                doneCallbackFn when called.
        """
        self._isDone = True
        self._doneCallbackFn = doneCallbackFn
        self._doneCallbackArgs = doneCallbackArgs
        self._doneCallbackKwargs = doneCallbackKwargs

        # Hide the progress bar
        self._gauge.Show(False)

        self._button.SetLabel("Done")
        self._button.SetDefault()
        self._button.Enable()

        self._isDone = True


    ###########################################################
    def isDone(self):
        """Tell whether "setDone" has been called.

        @return isDone  True if setDone has been called.
        """
        return self._isDone


    ###########################################################
    def setMessage(self, text, color="black"):
        """Set a new message for the progress dialog

        @param  text  The new message
        """
        self._label.SetLabel(text)
        self._label.SetForegroundColour(color)


    ###########################################################
    def Update(self, percentage, message=""): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Update the progress dialog to a certain percentage

        @param  percentage      The amount of the gauge to fill
        @param  message         A message to display above the gauge
        @return shouldContinue  True if we should continue.
        @return shouldSkip      False if we shouldn't skip.  Note that skipping
                                is currently not supported.
        """
        assert not self._isDone, "Shouldn't call Update() after done."

        if message != "":
            # Set the message in our text control rather than the default
            self.setMessage(message)

        self._gauge.SetValue(percentage)

        if self._wantYields:
            wx.YieldIfNeeded()

        if self._shouldCancel:
            return False, False
        else:
            return True, False


    ###########################################################
    def Pulse(self, message=""):
        """Pulse the progress dialog

        @param  message         A message to display above the gauge
        @return shouldContinue  True if we should continue.
        @return shouldSkip      False if we shouldn't skip.  Note that skipping
                                is currently not supported.
        """
        assert not self._isDone, "Shouldn't call Pulse() after done."

        if message != "":
            self.setMessage(message)

        self._gauge.Pulse()

        if self._wantYields:
            wx.YieldIfNeeded()

        if self._shouldCancel:
            return False, False
        else:
            return True, False


    ###########################################################
    def Resume(self):
        """Continue after the user has chosen to abort."""
        self._shouldCancel = False
        self._button.Enable()


    ###########################################################
    def OnButton(self, event):
        """Handle Cancel or Done button presses.

        @param  event  The event.
        """
        if self._isDone:
            if self._doneCallbackFn is not None:
                self._doneCallbackFn(*self._doneCallbackArgs,
                                     **self._doneCallbackKwargs)
            self.Close()
        else:
            self._shouldCancel = True
            self._button.Disable()


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)
    _ = app

    # We'll have a parent frame, just so we can have an event loop...
    frame = wx.Frame(None)
    frame.Show()

    # Have a function to make the dialog so we can get it called after the
    # event loop has started...
    def makeDialog():
        # Make the dialog...
        dlg = ProgressFrameWithLog(None, "MyTitle", "My message", 100)

        # Loop, showing progress...
        for i in xrange(100):
            time.sleep(.1)

            shouldContinue, _ = dlg.Update(i)

            # If the user hit cancel, add some console text, then let them
            # confirm (so they can read the console log).
            if not shouldContinue:
                dlg.appendConsoleText("Cancelled!")
                dlg.setDone(frame.Close)
                break

            if (i % 2) == 0:
                dlg.appendConsoleText("%d / 50 done" % (i/2))
        else:
            dlg.setDone(frame.Close)

    wx.CallAfter(makeDialog)

    app.MainLoop()



##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
