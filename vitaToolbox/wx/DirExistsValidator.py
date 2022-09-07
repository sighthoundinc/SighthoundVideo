#!/usr/bin/env python

#*****************************************************************************
#
# DirExistsValidator.py
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

import os.path

import wx

##############################################################################
class DirExistsValidator(wx.Validator):
    """A validator that makes sure that an object's value is a valid dir.

    This will call GetValue() on its assocated window and make sure that
    os.path.isdir() returns True on it.
    """
    ###########################################################
    def __init__(self, offerToCreate=False):
        """DirExistsValidator constructor.

        @param  offerToCreate  Offer to create the directory if it's not
                               valid.
        """
        super(DirExistsValidator, self).__init__()
        self._offerToCreate = offerToCreate


    ###########################################################
    def Clone(self): #PYCHECKER OK; wx has *args and **kwargs
        """Return a clone of the validator, as required.

        @return clone  A clone of our validator.
        """
        return DirExistsValidator(self._offerToCreate)


    ###########################################################
    def Validate(self, win): #PYCHECKER OK; wx has *args and **kwargs
        """Validate ourselves.

        @param  win      Unused.
        @return isValid  If True, we are valid.
        """
        _ = win

        myWin = self.GetWindow()
        myVal = myWin.GetValue()

        if not os.path.isdir(myVal):
            if myVal:
                if self._offerToCreate:
                    resp = wx.MessageBox("The directory '%s' is not valid.  "
                                  "Do you want to create it?" %
                                  myVal, "Error", wx.YES_NO | wx.ICON_QUESTION)
                    if resp == wx.YES:
                        try:
                            os.makedirs(myVal)
                            return True
                        except Exception, e:
                            wx.MessageBox("Failed to create '%s'.\n\n%s" %
                                          (myVal, e),
                                          "Error", wx.OK | wx.ICON_ERROR)
                else:
                    wx.MessageBox("The directory '%s' is not valid." %
                                  myVal, "Error", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("You must choose a valid directory.", "Error",
                              wx.OK | wx.ICON_ERROR)
            myWin.SetFocus()
            return False
        return True


    ###########################################################
    def TransferToWindow(self): #PYCHECKER OK; wx has *args and **kwargs
        """Unused in this validator.

        @return true  True, since there are no errors.
        """
        return True


    ###########################################################
    def TransferFromWindow(self): #PYCHECKER OK; wx has *args and **kwargs
        """Unused in this validator.

        @return true  True, since there are no errors.
        """
        return True


##############################################################################
def test_main():
    """OB_REDACT
    Our main function, which runs test code
    """
    pass


##############################################################################
if __name__ == '__main__':
    test_main()

