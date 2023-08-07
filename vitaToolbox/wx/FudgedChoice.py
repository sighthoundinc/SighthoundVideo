#!/usr/bin/env python

#*****************************************************************************
#
# FudgedChoice.py
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

# Common 3rd-party imports...
import wx

# Toolbox imports...

# Local imports...



# Constants...



##############################################################################
class FudgedChoice(wx.Choice):
    """A choice where the strings displayed are a bit fudged from model strings.

    For instance, you might want the strings underlying the choice to be:
       Hello
       Goodbye <inactive>
       Testing **bad**

    ...but you might want to display to the user:
       Hello
       Goodbye (inactive)
       Testing (may be bad)

    This lets you do that.
    """

    ###########################################################
    def __init__(self, parent, id, pos=wx.DefaultPosition, size=wx.DefaultSize,
                 choices=[], fudgeList=[], *args, **kwargs):
        """The initializer for FudgedChoice

        @param  parent       The parent window
        @param  id           Our UI ID.
        @param  pos          Our position
        @param  size         Our size
        @param  choices      The choices to start with.
        @param  fudgeList    A list of (from, to) tuples of fudges to make.
                             We'll so s.replace(from, to) on each string before
                             displaying it to the user.
        @param  ...          See wx.Choice
        """
        self._fudgeList = list(fudgeList)
        self._realChoices = list(choices)

        choices = [self._doFudge(s) for s in choices]

        # Call the base class initializer
        super(FudgedChoice, self).__init__(
            parent, id, pos, size, choices, *args, **kwargs
        )


    ###########################################################
    def _doFudge(self, s):
        """Fudge the given string.

        @param  s  The string to fudge.
        @return s  The fudged string.
        """
        for (fromStr, toStr) in self._fudgeList:
            s = s.replace(fromStr, toStr)

        return s


    ###########################################################
    def Append(self, item, *args, **kwargs): #PYCHECKER wx has *args and **kwargs
        self._realChoices.append(item)
        super(FudgedChoice, self).Append(self._doFudge(item), *args, **kwargs)


    ###########################################################
    def AppendItems(self, items): #PYCHECKER wx has *args and **kwargs
        self._realChoices.extend(items)
        for item in items:
            super(FudgedChoice, self).AppendItems(self._doFudge(item))


    ###########################################################
    def Clear(self): #PYCHECKER wx has *args and **kwargs
        self._realChoices = []
        super(FudgedChoice, self).Clear()


    ###########################################################
    def Delete(self, n): #PYCHECKER wx has *args and **kwargs
        del self._realChoices[n]
        super(FudgedChoice, self).Delete(n)


    ###########################################################
    def FindString(self, s): #PYCHECKER wx has *args and **kwargs
        for i, item in enumerate(self._realChoices):
            if s == item:
                return i

        return wx.NOT_FOUND


    ###########################################################
    def GetItems(self):
        # Return a _copy_ so client can mess with them...
        return list(self._realChoices)


    ###########################################################
    def GetString(self, n): #PYCHECKER wx has *args and **kwargs
        return self._realChoices[n]


    ###########################################################
    def GetStrings(self): #PYCHECKER wx has *args and **kwargs
        # Return a _copy_ so client can mess with them...
        return list(self._realChoices)


    ###########################################################
    def GetStringSelection(self): #PYCHECKER wx has *args and **kwargs
        selection = self.GetSelection()
        if selection == -1:
            return ""
        return self._realChoices[selection]


    ###########################################################
    def Insert(self, item, pos, *args, **kwargs): #PYCHECKER wx has *args and **kwargs
        self._realChoices.insert(pos, item)
        super(FudgedChoice, self).Insert(self._doFudge(item), pos,
                                         *args, **kwargs)


    ###########################################################
    def SetItems(self, items):
        self._realChoices = list(items)
        super(FudgedChoice, self).SetItems([self._doFudge(item)
                                            for item in items])


    ###########################################################
    def SetString(self, n, s): #PYCHECKER wx has *args and **kwargs
        self._realChoices[n] = s
        super(FudgedChoice, self).SetString(n, self._doFudge(s))


    ###########################################################
    def SetStringSelection(self, s): #PYCHECKER wx has *args and **kwargs
        try:
            selection = self._realChoices.index(s)
        except ValueError:
            return False
        else:
            return super(FudgedChoice, self).SetSelection(selection)




##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)

    choice = FudgedChoice(panel, -1,
                          choices=["Hello", "Goodbye <inactive>",
                                   "Testing **bad**"],
                          fudgeList=[("<inactive>", "(inactive)"),
                                     ("**bad**", "(may be bad)")])

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(choice)

    panel.SetSizer(sizer)

    frameSizer = wx.BoxSizer()
    frameSizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(frameSizer)

    frame.CenterOnParent()
    frame.Show()



    # Run the main loop, which will close when the frame does.
    app.MainLoop()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
