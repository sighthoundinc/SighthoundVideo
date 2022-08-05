#!/usr/bin/env python

#*****************************************************************************
#
# CreateMenuFromData.py
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

# Common 3rd-party imports...
import wx

# Local imports...


##############################################################################
def createMenuFromData(menuData, win):
    """Creates a wx.Menu() from the given table.

    The table should look something like:
            ("Show Selected Node at &Top", "", wx.ID_ANY, self.OnShowSelfAtTop),
            ("Go &up one level\tCtrl+Up", "", wx.ID_ANY, self.OnGoUpOneLevel),
            (None, None, None, None),
            ("* &Line Chart", "", wx.ID_ANY, self.OnChooseLineChart),
            ("* &Bar Chart", "", wx.ID_ANY, self.OnChooseBarChart),
            (None, None, None, None),
            ("* &Maximum Width", "", wx.ID_ANY, self.OnMaximumWidth),
            ("* &Equal Width", "", wx.ID_ANY, self.OnEqualWidth),
            (None, None, None, None),
            ("* &Show Row", "", wx.ID_ANY, self.OnShowRow),
            ("* &Hide Row", "", wx.ID_ANY, self.OnHideRow),

    The first element is the title.  It's kinda special:
    - If it has a '* ' or '+ ' before it, it becomes a radio item.  The '+ '
      means it will be checked by default.
    - If it has a 'x ' or 'X ' before it, it becomes a checkbox item.  The 'X '
      means it will be checked by default.
    - For the use of the & and \t, see the wxpython docs.

    The second element is the help text.

    The third element is the ID.

    The fourth element is the handler.


    Notes:
    - 'E&xit' and '&About xyzzy' are moved automatically by the system if on
      a Mac.  Because of this, this function inserts a separator before these
      items if NOT on a Mac.


    @param  menuData  The table describing the menu.  See function desc.
    @param  win       The window that will get the EVT_MENU events
    @return menu      The created wx.Menu
    """
    menu = wx.Menu()
    for i, (label, helpString, idd, handler) in enumerate(menuData):
        kind = wx.ITEM_NORMAL

        wantCheck = False
        if idd == wx.ID_NONE:
            # If ID_NONE, we just continue on our merry way and skip this one
            continue
        elif label is None:
            menu.AppendSeparator()
            continue
        elif idd in (wx.ID_EXIT, wx.ID_ABOUT, wx.ID_PREFERENCES):
            # Since Exit, About, and Prefs get moved on the Mac, the separator
            # before each needs to be added only on other platforms
            if (i != 0) and ("__WXMAC__" not in wx.PlatformInfo):
                menu.AppendSeparator()
        elif label[:2] in ("* ", "+ "):
            wantCheck = (label[:2] == "+ ")
            label = label[2:]
            kind = wx.ITEM_RADIO
        elif label[:2] in ("x ", "X "):
            wantCheck = (label[:2] == "X ")
            label = label[2:]
            kind = wx.ITEM_CHECK

        menuItem = menu.Append(idd, label, helpString, kind)
        if wantCheck:
            menuItem.Check()
        win.Bind(wx.EVT_MENU, handler, menuItem)
    return menu


