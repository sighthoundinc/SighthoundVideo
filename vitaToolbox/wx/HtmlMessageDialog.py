#!/usr/bin/env python

#*****************************************************************************
#
# HtmlMessageDialog.py
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
from wx.html import HtmlWindow

# Toolbox imports...

# Local imports...



##############################################################################
class HtmlMessageDialog(wx.Dialog):
    """Like the builtin ScrolledMessageDialog, but shows simple HTML.

    This heavily uses the builtin HtmlWindow.
    """


    ###########################################################
    def __init__(self, parent, id=-1, title="", pos=wx.DefaultPosition,
                 size=(620, 440), htmlFile=None):
        """HtmlMessageDialog constructor.

        Could easily make this take in a string, instead of a file.

        @param  parent    UI parent.
        @param  id        UI ID
        @param  title     The title for the self.
        @param  pos       UI Position.
        @param  size      UI size.
        @param  htmlFile  A path to the file containing the HTML to show;
                          shouldn't be None.
        """
        super(HtmlMessageDialog, self).__init__(parent, id, title, pos, size,
                                                style=wx.DEFAULT_DIALOG_STYLE |
                                                wx.RESIZE_BORDER)

        panel = wx.Panel(self)

        htmlWin = HtmlWindow(panel)
        htmlWin.LoadPage(htmlFile)

        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK)

        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(htmlWin, 1, wx.EXPAND | wx.BOTTOM, 12)

        panelSizer.Add(wx.StaticLine(self), 0,
                       wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        panelSizer.Add(buttonSizer, 0, wx.EXPAND | wx.ALL, 12)

        panel.SetSizer(panelSizer)

        dialogSizer = wx.BoxSizer()
        dialogSizer.Add(panel, 1, wx.EXPAND)

        self.SetSizer(dialogSizer)

        htmlWin.SetFocus()


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)
    _ = app

    testHtml = ('''Hello.  I can make a <B>Bold</B> statement.  '''
                '''Can I make a <A HREF="http://www.vitamindinc.com/">link</A>?''')
    open("HtmlMessageDialogTest.html", "w").write(testHtml)

    dlg = HtmlMessageDialog(None, -1, "Test dialog",
                            htmlFile="HtmlMessageDialogTest.html")
    dlg.ShowModal()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
