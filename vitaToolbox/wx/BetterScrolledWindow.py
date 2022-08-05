#!/usr/bin/env python

#*****************************************************************************
#
# BetterScrolledWindow.py
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

"""
## @file
Contains the BetterScrolledWindow class.
"""


import wx

from BindChildren import bindChildren

class BetterScrolledWindow(wx.ScrolledWindow):
    """Implements a version of wx.ScrolledWindow that is slightly saner.

    The major differences between this version of ScrolledWindow and the
    one that ships with wxPython:
    - It implements SetBestSize() properly, that lets you influence the value
      that's returned by GetBestSize() without messing with the min size.
    - It captures scrollwheel events from children.  At the moment, it's not
      very efficient at it, but it'll do.
    - The scrollbar doesn't need to be a multiple of scrollRate pixels, and
      doesn't need to be scrolled scrollRatePixels at a time.  This gets rid
      of the ugly partial line at the bottom of the scroll window.

    Since some of the workarounds implemented in this class are a bit hacky,
    I'd expect some amount of revisiting for future versions of wxPython
    and future platforms.

    Overall, mousewheel events seem to be all sorts of craziness on the two
    platforms I've tested (Mac and PC):
    - On Mac, they are sent to the control that the mouse is over.  On Windows,
      they are sent to whatever has focus in the topmost frame.
    - On Mac, they aren't passed up the container heirarchy.  On Windows, they
      are passed up the container heirarchy if not skipped (though not through
      the standard 'propagation' method that command events are).  On Mac, this
      means that if the mouse happens to be over a static label, the scroll
      wheel won't do anything.
    - On Mac, you will get two scroll events, unless you don't skip the first
      one.  They are different events: if the first event causes the mouse to
      be over a different object, the new object will be the 'eventobject' of
      the second event.
    - Horizontal scroll wheel events end up causing vertical scrolling.
    - On a PC, a multiline text control will 'skip' on mousewheel events (so
      the app will get a chance to see them), then won't actually scroll if the
      app eats them.  On a Mac, a multiline text control will 'skip' on
      mousewheel events (again, app can see them), but will still scroll even
      if the app eats them.

    Another attempted implementation of this class involved creating one big
    translucent window at the highest z-ordering.  This got all mousewheel
    events, but also stole all other mouse events (clicks, etc).  I couldn't
    find a way to get them passed down properly, thus that method wasn't used.

    Note: a version of this code was posted to the "wxPython in Action" forum
    by me.
    """
    def __init__(self, parent, id, *args, **keywords):
        """BetterScrolledWindow constructor.

        ...most parameters are just passed straight onto our superclass.

        @param  parent     The parent window.
        @param  id         Our ID (usually -1)
        @param  debug      Keyword only parameter. Set to True to enable debug.
        @param  osxFix     Keyword only parameter. Set to True to fix osx
                           scroll layout bug.
        @param  redrawFix  Keyword only parameter.  Set to True if the window
                           is not drawing properly after scroll/size events.
        """
        # Pull out osxFix keyword...
        if "osxFix" in keywords:
            self._osxFix = keywords["osxFix"]
            del keywords["osxFix"]
        else:
            self._osxFix = False

        # Pull out redrawFix keyword...
        if "redrawFix" in keywords:
            self._redrawFix = keywords["redrawFix"]
            del keywords["redrawFix"]
        else:
            self._redrawFix = False

        # Call super...
        wx.ScrolledWindow.__init__(self, parent, id, *args, **keywords)

        # Keep track of bestSize for the implementation of SetBestSize()
        self._bestSize = (-1, -1)

        # We'll tell our superclass that this is our scroll rate.  Ideally,
        # we want a value of 1 here.  That's because we don't want any ugly
        # "partial lines" at the bottom of the scroll window, which happens
        # normally with wx.  We pass 2 instead of 1 because on the Mac a
        # value of 1 ends up putting children at the wrong positions as you
        # do a bunch of scrolling.
        self._scrollBasis = 2

        # Here's where we'll store the client's requested scroll rate.
        # Really, this has to be a multiple of scrollBasis.
        self.SetScrollRate(20,20)

        if wx.Platform == "__WXMSW__":
            # Register to get the lineup/linedown events, so we can multiply
            # scrollBasis to get scrollRate.
            self.Bind(wx.EVT_SCROLLWIN_LINEDOWN, self.OnScrollwinLineDown)
            self.Bind(wx.EVT_SCROLLWIN_LINEUP,   self.OnScrollwinLineUp)
        else:
            # On mac allowing the system to handle scrolling causes hangs so
            # we register for mouswheel events to take care of it ourselves.
            self.Bind(wx.EVT_MOUSEWHEEL, self.OnScrollWheel)

        # Bind mousewheel handler to ourselves and all of our children.
        # ..._processingEvents is used to avoid recursion in the handler.
        self._processingEvents = False
        bindChildren(self, wx.EVT_MOUSEWHEEL, self.OnChildScrollWheel)

        if self._osxFix:
            self.Bind(wx.EVT_SCROLLWIN_THUMBTRACK, self.OnMiscScrollEvent)
            self.Bind(wx.EVT_SCROLLWIN_THUMBRELEASE, self.OnMiscScrollEvent)
        if self._redrawFix:
            self.Bind(wx.EVT_SCROLLWIN, self.OnMiscScrollEvent)

        self.Bind(wx.EVT_SIZE, self.OnSize)


    ############################################################
    def SetBestSize(self, bestSize): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """A proper implementation of SetBestSize()

        Unlike the one in wx.ScrolledWindow, this one doesn't set the
        minimum size (which was really dumb!).

        @param  bestSize  The best size to use.
        """
        self._bestSize = bestSize


    ############################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Implement DoGetBestSize() to properly apply our bestSize.

        This is called automatically when someone wants to know our best size.
        We'll return the value that was passed into us, using our superclass
        result whenever we have a -1.

        TODO: Should the default behavior (unlike scrolled window) be to
        return the size from our sizer: self.GetSizer().GetMinSize()?  That
        would make a lot of sense, but there must be a reason that scrolled
        window doesn't do it that way (?).

        @return bestSize  The actual best size.
        """
        bestWidth, bestHeight = self._bestSize
        if bestWidth != -1 and bestWidth != -1:
            return self._bestSize

        superBestWidth, superBestHeight = wx.ScrolledWindow.DoGetBestSize(self)
        if bestWidth == -1:
            bestWidth = superBestWidth
        if bestHeight == -1:
            bestHeight = superBestHeight

        return (bestWidth, bestHeight)


    ############################################################
    def SetScrollRate(self, xstep, ystep): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Set the number of pixels that a lineup/linedown should scroll.

        We need to patch the call before it makes it to our superclass, since
        we always tell our superclass we have a scroll rate of (2, 2) so we
        can get smoother scrolling (and no partial line at the bottom).
        """
        wx.ScrolledWindow.SetScrollRate(self, self._scrollBasis, self._scrollBasis)
        self._scrollRate = (xstep, ystep)


    ###########################################################
    def _applyFixes(self):
        """Apply any fixes specified in the initializer."""
        if self._osxFix:
            self.Layout()
        if self._redrawFix:
            wx.CallAfter(self.Refresh)


    ###########################################################
    def OnSize(self, event=None):
        """Handle a size event of the preview window.

        @param  event  The size event.
        """
        self.FitInside()
        # Setting the virtual size to the client size fixes a bug where resizing
        # the window very quickly causes the scrolled window to not fit/layout
        # its subwindows correctly. This is needed for both Windows and OSX.

        clientWidth, clientHeight = self.GetClientSize()
        virtualWidth, virtualHeight = self.GetVirtualSize()

        # Using the fixed client width, check to see if the vertical scroll bar
        # is showing. This happens when our virtual size is greater than our
        # client size.
        if clientWidth != 0 and \
                (virtualWidth > clientWidth or virtualHeight > clientHeight):

            # Calculate the new virtual width to be the current client width.
            # Calculate the new virtual height to be the AREA of the current
            # virtual size divided by the current client width. We need to make
            # sure the area of the new virtual size is greater than or equal to
            # the area of the old virtual size to make sure everything is drawn
            # correctly. We add a 1 to the new virtual height calculation to
            # ensure we're always greater than or equal to the old virtual area.
            newVirtualSize = (clientWidth,
                              virtualWidth*virtualHeight/clientWidth+1)

            # Set the new virtual size so that our sizer knows it needs to
            # reshape/relayout to update/draw correctly.
            self.SetVirtualSize(newVirtualSize)

        if event is not None:
            event.Skip()


    ###########################################################
    def OnMiscScrollEvent(self, event):
        """Handle a scroll event.

        @param  event  A scroll event.
        """
        self._applyFixes()
        event.Skip()


    ############################################################
    def OnScrollwinLineUp(self, event):
        """Handle scrolling to translate client units into superclass units.

        This is called when the client hits a scrollup arrow and during
        scrollwheel movements.

        @param  event  The scrollup event.
        """
        x, y = self.GetViewStart()
        if event.GetOrientation() == wx.VERTICAL:
            yScrollTo = y - (self._scrollRate[1]/self._scrollBasis)
            # if you pass -1 into scroll, it is a noop, what we want is to scroll
            # to the top
            if yScrollTo==-1:
                yScrollTo = 0
            self.Scroll(x, yScrollTo)
        else:
            self.Scroll(x - (self._scrollRate[1]/self._scrollBasis), y)
        self._applyFixes()


    ############################################################
    def OnScrollwinLineDown(self, event):
        """Handle scrolling to translate client units into superclass units.

        This is called when the client hits a scrollup arrow and during
        scrollwheel movements.

        @param  event  The scrolldown event.
        """
        x, y = self.GetViewStart()
        if event.GetOrientation() == wx.VERTICAL:
            self.Scroll(x, y + (self._scrollRate[0]/self._scrollBasis))
        else:
            self.Scroll(x + (self._scrollRate[0]/self._scrollBasis), y)
        self._applyFixes()


    ############################################################
    def OnScrollWheel(self, event):
        """Handle scroll wheel events.

        On mac we must control the scrolling ourselves as the line up/down
        code is stuttery and gets flooded with events causing a temporary
        app freeze.

        @param  event  The event.
        """
        x, y = self.GetViewStart()
        self.Scroll(x, y-event.GetWheelRotation()*self._scrollRate[1])


    ############################################################
    def OnChildScrollWheel(self, event):
        """Handle scroll wheel events for ourself and our children.

        This is bound to _all_ of our children.

        @param  event  The event.
        """
        # If we're in a recursive call, we must have intercepted the event
        # destined for the superclass.  Just skip it.  Otherwise, steal the
        # event and pass it to our event handler (which should eventually
        # go to the normal scrolled window).  I know it doesn't make a ton
        # of sense, but this is what worked due to trial and error...
        if not self._processingEvents:
            self._processingEvents = True
            self.GetEventHandler().ProcessEvent(event)
            self._processingEvents = False
        else:
            event.Skip()
        self._applyFixes()



##############################################################################
def _runTests():
    """OB_REDACT
       Run any self-tests.  This will be removed from obfuscated code.
    """
    # Create a simple test app to see how things worked!
    app = wx.App(redirect=bool("__WXMAC__" not in wx.PlatformInfo))
    frame = wx.Frame(None, -1, "BetterScrolledWindow test", size=(200,200))
    frame.CreateStatusBar()

    scrolledWindow = BetterScrolledWindow(frame, -1)
    scrolledWindow.SetLabel("BetterScrolledWindow")
    scrolledWindow.SetScrollRate(20, 20)

    # Try to give ourselves focus so we'll get mousewheel events on Windows
    # (they follow focus).  This a is necessary step if we only have static
    # text controls inside us.  If we have any other controls, they will steal
    # focus anyway so this won't matter...
    scrolledWindow.SetFocus()

    # Create our sizer, and the first 10 static texts...
    sizer = wx.BoxSizer(wx.VERTICAL)
    scrolledWindow.SetSizer(sizer)
    for i in xrange(0, 10):
        text = wx.StaticText(scrolledWindow, -1, "------------ %d ------------" % i)
        sizer.Add(text)

    # Add a button, just to have something that will take focus...
    button = wx.Button(scrolledWindow, -1, "Button")
    sizer.Add(button)

    # Add a multiline, scrolling text field, to see how it will behave...
    #
    # This ends up behaving strangely on both mac and windows.  On mac, the
    # text control will scroll, but will still skip the event (so, with the
    # implementation above, we'll end up both scrolling).  On windows, the
    # text control will never scroll.  We could probably fix that if needed
    # by registering an event handler for mousewheel events, handling them,
    # then eating them.
    textControl = wx.TextCtrl(scrolledWindow, -1, "TextControl",
                              style=wx.HSCROLL | wx.TE_MULTILINE,
                              size=(100,100))
    sizer.Add(textControl)

    # Add the last 10 static texts...
    for i in xrange(10, 20):
        text = wx.StaticText(scrolledWindow, -1, "------------ %d ------------" % i)
        sizer.Add(text)

    # Go!
    frame.Show(1)
    app.MainLoop()


if __name__ == '__main__':
    _runTests()
