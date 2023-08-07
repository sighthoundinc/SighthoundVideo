#!/usr/bin/env python

#*****************************************************************************
#
# QueryEditorDialog.py
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
import os
import sys

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BindChildren import bindChildren
from vitaToolbox.wx.FixModalDialog import fixModalDialog

# Local imports...
from appCommon.CommonStrings import kAnyCameraStr
from QueryConstructionView import checkQueryName
from QueryConstructionView import QueryConstructionView
from constructionComponents.ResponseConfigPanel import checkResponses
from constructionComponents.ResponseConfigPanel import hasResponses
from frontEnd.FrontEndUtils import getUserLocalDataDir

# Constants...
_kDialogTitle = "Rule Editor"

_kAnyCameraResponseErr = 'A response can only apply to one camera. Change the'\
                         ' video source from "%s" to a specific camera.' \
                         % kAnyCameraStr
_kAnyCameraResponseTitle = "Rule Response"

##############################################################################
class QueryEditorDialog(wx.Dialog):
    """A dialog for editing a query."""

    ###########################################################
    def __init__(self, parent, dataMgr, backEndClient, queryDataModel,
                 existingNames, cameraLocations):
        """QueryConstructionView constructor.

        @param  parent          Our parent UI element.
        @param  dataMgr         The data manager for the app.
        @param  backEndClient   Client to the back end; used for flushing video.
                                May be None for test code.
        @param  queryDataModel  The data model to edit in the construction view.
                                _Should be a copy_.
        @param  existingNames   Reserved names the user should not be allowed
                                to use; must not include the current query
                                name unless we're not allowed to use that name.
        @param  cameraLocations A list of cameras the query can apply to.
        """
        # Call our super
        super(QueryEditorDialog, self).__init__(
            parent, title=_kDialogTitle
        )

        try:
            # Adjust existingNames to be all lowercase...
            existingNames = set([s.lower() for s in existingNames])

            # Save parameters...
            self._dataMgr = dataMgr
            self._backEndClient = backEndClient
            self._queryDataModel = queryDataModel
            self._existingNames = existingNames

            # Create the UI...

            # Most of this is just the query construction view...
            self._constructionView = \
                QueryConstructionView(self, dataMgr, backEndClient,
                                      queryDataModel, existingNames,
                                      cameraLocations)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self._constructionView, 1, wx.EXPAND)
            sizer.Add(buttonSizer, 0, wx.EXPAND | wx.ALL, 10)
            self.SetSizer(sizer)

            self.Fit()
            self.CenterOnParent()

            # Bind to OK...
            self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

            if wx.Platform == '__WXMAC__':
                bindChildren(self, wx.EVT_CHAR, self.OnChar)

            fixModalDialog(self)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def OnOK(self, event):
        """Respond to the user pressing OK

        @param  event  The button event
        """
        queryName = self._queryDataModel.getName()

        cameraName = self._queryDataModel.getVideoSource().getLocationName()
        if not checkQueryName(queryName, cameraName, self._existingNames, self,
                              self._queryDataModel.isAutoNamed()):
            return

        if not checkResponses(self._queryDataModel, self._backEndClient, self):
            return

        if cameraName == kAnyCameraStr and hasResponses(self._queryDataModel):
            wx.MessageBox(_kAnyCameraResponseErr, _kAnyCameraResponseTitle,
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            return

        self.EndModal(wx.ID_OK)


    ############################################################
    def OnChar(self, event):
        """Handle key character events.

        @param  event  The key event, from the system
        """
        # Close the window if Cmd+W is pressed.
        if ord('w') == event.GetKeyCode() and \
           wx.MOD_CMD == event.GetModifiers():
            self.Close()
            return

        event.Skip()


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    # Ugly test code to quickly bring up the query editor dialog...
    # ...import all kinda of private / inappropriate stuff...
    from BackEndClient import BackEndClient
    from appCommon.CommonStrings import kVideoFolder
    from FrontEndApp import kAppName
    from FrontEndFrame import _clipDbName, _objDbName
    from backEnd.ClipManager import ClipManager
    from backEnd.DataManager import DataManager
    from backEnd.SavedQueryDataModel import SavedQueryDataModel
    from vitaToolbox.loggingUtils.LoggingUtils import getLogger

    app = wx.App(False)
    app.SetAppName(kAppName)

    dataDirectory = os.path.join(getUserLocalDataDir(), "videos")
    logger = getLogger("bogus")

    backEndClient = BackEndClient()
    didConnect = backEndClient.connect()
    assert didConnect, "Need back end"

    clipMgr = ClipManager(logger)
    clipMgr.open(os.path.join(dataDirectory, _clipDbName))
    videoDirectory = os.path.join(backEndClient.getVideoLocation(),
                                  kVideoFolder)
    dataMgr = DataManager(logger, clipMgr, videoDirectory)
    dataMgr.open(os.path.join(dataDirectory, _objDbName))
    queryDataModel = SavedQueryDataModel("")

    dlg = QueryEditorDialog(None, dataMgr, backEndClient, queryDataModel, [],
                            [kAnyCameraStr] + clipMgr.getCameraLocations() + ["foo"])
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
