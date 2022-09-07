#!/usr/bin/env python

#*****************************************************************************
#
# SearchResultsList.py
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



# Python imports...
import bisect
from collections import defaultdict
import math
import time
import datetime
import traceback

# Common 3rd-party imports...
from PIL import Image
import wx
from wx.lib import delayedresult

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.wx.TruncateText import truncateText, truncateTextMid
from vitaToolbox.profiling.MarkTime import TimerLogger
from vitaToolbox.sysUtils.TimeUtils import getDebugTime, formatTime

# Local imports
from backEnd.ClipManager import ClipManager
from backEnd.DataManager import DataManager
from backEnd.VideoMarkupModel import VideoMarkupModel
from appCommon.CommonStrings import kFrontEndLogName
from appCommon.CommonStrings import kImportSuffix
from appCommon.CommonStrings import kSearchingString, kSearchingOnString

import MenuIds


_kItemHeight = 64
_kPreviewWidth = 64
_kPreviewHeight = 48
_kImgXOffset = 8
_kImgYOffset = 8
_kLabelXOffset = 88
_kLabelYOffset = 5
_kNotSavedlYOffset = 42
_kTimeXOffset = 88
_kTimeYOffset = 26
_kNumLoadRetries = 100
_kPopupTimeout = 2

# Font size different on Win and Mac
if wx.Platform == '__WXMSW__':
    _kLabelFontSize = 11
    _kTimeFontSize = 8
else:
    _kLabelFontSize = 14
    _kTimeFontSize = 10

_kNotSavedStr = "Temporary video (not saved by a rule)"

# If we're halfway between two selections, we'll use this...  Note that the
# height is the height on either side of the border.
_kBetweenSelectionHeight = 1
_kBetweenSelectionColor = (21, 84, 172)

_kTime12Hour = '%I:%M %p'
_kTime24Hour = '%H:%M'


################################################################################
class SearchResultsList(wx.VListBox):
    """Implements the list box for showing search results."""
    ###########################################################
    def __init__(self, parent, dataManager, resultsModel, markupModel):
        """The initializer for SearchResultsList

        @param  parent        The parent window
        @param  dataManager   An interface for retrieving video frames
        @param  resultsModel  The SearchResultDataModel to listen to.
        @param  markupModel   A model describing how to markup video frames.
        """
        # Call the base class initializer
        super(SearchResultsList, self).__init__(parent, style=wx.LB_MULTIPLE)

        self._logger = getLogger(kFrontEndLogName)

        # Save params...
        self._dataMgr = dataManager
        self._resultsModel = resultsModel

        # We may show things differently for debug mode
        self._debugModeModel = wx.GetApp().getDebugModeModel()
        self._debugModeModel.addListener(self._handleDebugModeChange)

        # We make our own markup model and update it from the passed in one.
        # This allows us to give our data manager separate settings.
        self._markupModel = markupModel
        self._subMarkupModel = VideoMarkupModel (
            True,
            markupModel.getShowBoxesAroundObjects() and
            markupModel.getShowDifferentColorBoxes(),
            False, False, False
        )
        self._markupModel.addListener(self._handleMarkupChange, True)

        # Register for time preference changes.
        self.GetTopLevelParent().getUIPrefsDataModel().addListener(
                self._handleTimePrefChange, key='time')
        self._timeStr = _kTime12Hour

        self._curResults = None
        # A list of (image preview, label, time string, isSaved) tuples for
        # each item in the list box
        self._dataCache = None

        # Two dicts that map client (external) indexes to selection (internal)
        # indexes. These are used to implement sorting in this list view.
        self._clientIdxToSelectionIdx = {-1: -1}
        self._selectionIdxToClientIdx = {-1: -1}

        # Tells us whether or not we should sort by ascending or descending
        # order when displaying results to the user.
        self._isAscending = resultsModel.isSortAscending()

        self._abortEvent = None
        self._loadRunning = False
        self._searching = False
        self._pendingPopupPoint = None
        self._pendingPopupTimeout = None

        self._gradientCol1 = wx.Colour(21, 84, 172)
        self._gradientCol2 = wx.Colour(95, 149, 215)
        self._colGray = wx.Colour(128, 128, 128)

        self._blankImg = Image.new('1', (_kPreviewWidth, _kPreviewHeight))

        # Listen to our results model...
        self._resultsModel.addListener(self._handleResultsChange,
                                       False, 'results')
        self._resultsModel.addListener(self._handleClipChange,
                                       False, 'videoSegment')
        self._resultsModel.addListener(self._handleSearch, False, 'searching')
        self._resultsModel.addListener(self._handleClipChange, False,
                                       'multipleSelected')
        self._resultsModel.addListener(self._handleSortChange, False,
                                       'sortResults')

        # Store any menu items we'll be using.
        topWin = self.GetTopLevelParent()
        menuBar = topWin.GetMenuBar()
        self._exportClipMenuItem         = MenuIds.getToolsMenuItem(menuBar, MenuIds.kExportClipMenu)
        self._exportForBugReportMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kExportClipForBugReportMenu)
        self._deleteClipMenuItem         = MenuIds.getToolsMenuItem(menuBar, MenuIds.kDeleteClipMenu)
        self._submitClipForAnalysisMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kSubmitClipForAnalysis)
        self._submitClipForAnalysisWithNoteMenuItem = MenuIds.getToolsMenuItem(menuBar, MenuIds.kSubmitClipForAnalysisWithNote)


        # NOTE: If select all is added, make sure that right-clicking on a non-
        # selected item in the list does the right thing on Mac.
        self._menuItems = [self._deleteClipMenuItem, self._exportClipMenuItem,
                           self._exportForBugReportMenuItem, self._submitClipForAnalysisMenuItem,
                           self._submitClipForAnalysisWithNoteMenuItem ]

        # Register to know about sys.exit(), so we can stop our thread if it's
        # running
        topWin.registerExitNotification(self.stopLoader)

        self.Bind(wx.EVT_LISTBOX, self.OnResult)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnResultsListClick)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)


    ###########################################################
    def __del__(self):
        """SearchResultsList finalizer.

        This will stop any delayed results code that we have running.
        """
        self.stopLoader()


    ###########################################################
    def _handleDebugModeChange(self, debugModeModel):
        """Update the debug info.

        @param  debugModeModel  Should be self._debugModeModel
        """
        self._restartLoader()

    ###########################################################
    def _handleMarkupChange(self, markupModel, whatChanged):
        """Handle changes in the markup model.

        @param  markupModel  Should be self._markupModel.
        @param  whatChanged  The thing that changed; if None, assume that
                             everything changed.
        """
        assert markupModel == self._markupModel

        if (whatChanged == 'showBoxesAroundObjects') or \
           (whatChanged == 'showDifferentColorBoxes') or \
           (not whatChanged):

            self._subMarkupModel.setShowDifferentColorBoxes(
                markupModel.getShowBoxesAroundObjects() and
                markupModel.getShowDifferentColorBoxes()
            )

            if self._curResults:
                self._restartLoader()


    ###########################################################
    def _handleResultsChange(self, resultsModel):
        """Handle a change in search results.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel
        self._searching = False

        # If we have a pending context menu make sure it doesn't fire.
        self._pendingPopupPoint = None

        resultItems = self._resultsModel.getMatchingClips()
        if not resultItems:
            self.Clear()
            self.Refresh()
        else:
            clientIdx = resultsModel.getCurrentClipNum()
            self._setSearchResults(resultItems, clientIdx)


    ###########################################################
    def _ensureVisible(self, lineNum):
        """Ensure that the given line is visible in the list.

        This is slightly more elegant than ScrollToRow(), as it will not always
        force the line to be at the top of the list.

        @param  lineNum  The line number to make sure is visible.
        """
        if lineNum == -1:
            return

        if not self.IsVisible(lineNum):
            # Note: we subtract 1 from visibleEnd, since GetVisibleEnd() seems
            # to count partially visible lines...
            visibleBegin = self.GetVisibleBegin()
            visibleEnd = self.GetVisibleEnd() - 1

            # If the line is after the last visible, we want it to become the
            # new last visible.  Else, we can use ScrollToRow directly
            # which will make it the first visible...
            if lineNum >= visibleEnd:
                self.ScrollToRow(lineNum - (visibleEnd - visibleBegin - 1))

                # Just in case we've got a bug somewhere (or if the OS has
                # a bug somewhere), really make sure it's visible...
                if not self.IsVisible(lineNum):
                    assert False
                    self.ScrollToRow(lineNum)
            else:
                self.ScrollToRow(lineNum)


    ###########################################################
    def _handleSearch(self, resultsModel):
        """Update UI to reflect that a search is taking place.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel
        self._searching = True
        self.DeselectAll()
        self.SetItemCount(1)
        self.Refresh()
        self.Update()


    ###########################################################
    def _handleClipChange(self, resultsModel):
        """Handle a change in what clip is selected.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        self._updateUi(resultsModel)


    ###########################################################
    def _handleSortChange(self, resultsModel):
        """Handle a change in sort order.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        if self._isAscending == resultsModel.isSortAscending():
            return

        self._isAscending = resultsModel.isSortAscending()

        self._configureSortOrder()
        self._updateUi(resultsModel)
        self._restartLoader()


    ###########################################################
    def _configureSortOrder(self):
        """Configures data structures needed to handle changes in sort order
        dynamically.
        """
        if self._curResults is None:
            return

        itemCount = len(self._curResults)

        clientIndexes = range(itemCount)
        selectionIndexes = range(itemCount)

        if not self._isAscending:
            selectionIndexes.reverse()

        self._clientIdxToSelectionIdx = dict(zip(clientIndexes, selectionIndexes))
        self._selectionIdxToClientIdx = dict(zip(selectionIndexes, clientIndexes))

        # Negative one translates to itself. We need this value to support
        # conversion for when there is no selection, which is represented by
        # a "-1".
        self._clientIdxToSelectionIdx[-1] = -1
        self._selectionIdxToClientIdx[-1] = -1


    ###########################################################
    def _updateUi(self, resultsModel):
        """Updates and refreshes the UI to reflect the current state of the
        results model.

        Note:   This method should only be called if a lot of changes have taken
                place and it makes sense to just do a full UI update instead of
                trying to fix all the UI components piece by piece.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        clientIdx = resultsModel.getCurrentClipNum()
        areMultipleSelected = self._resultsModel.getMultipleSelected()

        if (clientIdx == int(clientIdx)) or (areMultipleSelected):
            # Integral selection means a real selection...

            if not areMultipleSelected:
                self._ensureVisible(self._clientIdxToSelectionIdx[clientIdx])

            if self._resultsModel.getSelectedIds() != self._getSelectedItems(
                    True):
                self.DeselectAll()
                for clientIdx in self._resultsModel.getSelectedIds():
                    self.SetSelection(self._clientIdxToSelectionIdx[clientIdx])
        else:
            # Floating point selection means between two items...

            # Nothing should be selected...
            self.DeselectAll()

            # Ensure that clip before and after are both visible...
            numItems = self.GetItemCount()
            itemBefore = int(math.floor(clientIdx))
            itemAfter = int(math.ceil(clientIdx))
            if (itemBefore >= 0) and (itemBefore < numItems):
                self._ensureVisible(self._clientIdxToSelectionIdx[itemBefore])
            if (itemAfter >= 0) and (itemAfter < numItems):
                self._ensureVisible(self._clientIdxToSelectionIdx[itemAfter])

        self.Refresh()


    ###########################################################
    def OnResult(self, event):
        """Prepare the selected result to be played.

        This is called for everything except if the user clicks on the currently
        selected clip.  In that case, we catch things in OnResultsListClick().

        @param  event  The selection event
        """
        # If we had a pending context menu it's no longer valid.
        self._pendingPopupPoint = None

        selectedResult = self._selectionIdxToClientIdx[event.GetInt()]
        selectedItems = self._getSelectedItems(True)
        multiple = (len(selectedItems) > 1)

        if not multiple:
            self._resultsModel.setCurrentClipNum(selectedResult)
        else:
            self._resultsModel.setMultipleSelected(multiple, selectedItems)


    ###########################################################
    def OnResultsListClick(self, event):
        """Reset the current video if the user clicks the current selection

        @param  event  The left down event
        """
        if self.GetSelectedCount() > 1:
            event.Skip()
            return

        curSelection = self.GetFirstSelected()[0]
        if curSelection != -1:
            newSelection = self.VirtualHitTest(event.Y)
            if curSelection == newSelection:
                self._resultsModel.resetLocationInSegment()

        event.Skip()


    ###########################################################
    def _setSearchResults(self, searchResults, clientIdx):
        """Add a new set of items to the list, clearing the old

        @param  searchResults  The new items to display in the list box.  This
                               is a list of (filename, objSet, ms)
        @param  clientIdx      The selection as a clientIdx.
        """
        self.Clear()

        itemCount = len(searchResults)
        self._curResults = searchResults
        self.SetItemCount(itemCount)

        clientIndexes = range(itemCount)
        selectionIndexes = range(itemCount)

        if not self._isAscending:
            selectionIndexes.reverse()

        self._clientIdxToSelectionIdx = dict(zip(clientIndexes, selectionIndexes))
        self._selectionIdxToClientIdx = dict(zip(selectionIndexes, clientIndexes))

        # Negative one translates to itself. We need this value to support
        # conversion for when there is no selection, which is represented by
        # a "-1".
        self._clientIdxToSelectionIdx[-1] = -1
        self._selectionIdxToClientIdx[-1] = -1

        self.DeselectAll()

        if ((clientIndexes[0] == clientIdx) and
            (self._selectionIdxToClientIdx[0] != clientIdx)):
            self._resultsModel.setCurrentClipNum(
                self._selectionIdxToClientIdx[0], None, False
            )
        else:
            selection = self._clientIdxToSelectionIdx[clientIdx]
            self.SetSelection(selection)
            self.RefreshRow(selection)

        self._restartLoader()


    ###########################################################
    def _restartLoader(self):
        """Stop (if needed) and start the loader."""

        # Ensure that any previous threads will exit
        self.stopLoader()

        numResults = len(self._curResults)

        self._abortEvent = delayedresult.AbortEvent()
        self._loadRunning = True
        self._dataCache = [(None, None, None, True)] * numResults

        # Create a new item loader
        delayedresult.startWorker(self._resultItemsLoaded,
                                  self._resultItemLoader,
                                  wargs=(self._abortEvent,
                                         numResults))


    ###########################################################
    def stopLoader(self):
        """Makes sure that the delayed result loader has stopped."""
        # Set the abort...
        if self._abortEvent is not None:
            self._abortEvent.set()

        # Wait for the thread to actually finish...
        while self._loadRunning:
            time.sleep(.02)


    ###########################################################
    def _resultItemLoader(self, abortEvent, numResults):
        """Load items for the result list.

        @param  abortEvent  An event that will be set if loading should abort.
        @param  numResults  The number of searchResults.
        """
        # We can't search databases opened in other threads so we need to open
        # our own.  Fortunately this seems to be pretty lightweight.

        timeLogger = TimerLogger("loading results")

        dataMgrPath, clipMgrPath, videoDir = self._dataMgr.getPaths()
        clipMgr = ClipManager(self._logger)
        clipMgr.open(clipMgrPath)
        dataMgr = DataManager(self._logger, clipMgr, videoDir)
        dataMgr.open(dataMgrPath)
        dataMgr.setMarkupModel(self._subMarkupModel)

        try:
            self._loadLoop(abortEvent, numResults, dataMgr, clipMgr)
        except delayedresult.AbortedException:
            # This exception is expected if (and when) we are told to stop, so
            # do nothing...
            pass
        except Exception:
            # Definitely log unhandled exceptions since they'd only get
            # swallowed up and tell us nothing about what happened.
            self._logger.error(
                "Unhandled exception in thumb loader!", exc_info=True
            )
        finally:
            clipMgr.close()
            dataMgr.close()

            self._loadRunning = False
            self._logger.debug(timeLogger.status() + ": " +
                            str(self.GetItemCount()) + " results loaded");


    ###########################################################
    def _loadLoop(self, abortEvent, numResults, dataMgr, clipMgr):
        """The actual load loop for the _resultItemLoader().

        We'll raise a delayedresult.AbortedException if we are aborted.

        Note: We now only load what were currently viewing and a few before and
              after, rather than continuing to laod everything as we did before.
              Eventually we should have a thumbnail cache of sorts, but for now
              simply cutting off the loads is a help, as particularly on larger
              setups we were burning through CPU loading thousands of never
              viewed results. Now we wind up never exiting this loop and
              just sleeping a lot.

        @param  abortEvent  An event that will be set if loading should abort.
        @param  numResults  The number of searchResults.
        @param  dataMgr     Our own private instance of the data manger.
        @param  clipMgr     Our own private instance of the clip manager.
        """
        unloadedIndicies = set(xrange(numResults))
        loadedIndicies = set([])
        retryLookup = {}

        while unloadedIndicies:
            firstVisible = self.GetVisibleBegin()
            lastVisible = self.GetVisibleEnd()

            # Convert to indices in our list...
            viewIndices = xrange(firstVisible, lastVisible)
            viewIndices = [x for x in viewIndices if x in unloadedIndicies]

            if viewIndices:
                shouldSleep = False
            else:
                # If we've loaded what's in our current view, load a few after
                # and before to speed scrolling.
                viewIndices = xrange(firstVisible-5, lastVisible+5)
                viewIndices = [x for x in viewIndices if x in unloadedIndicies]
                shouldSleep = True

            searchList = viewIndices

            if not searchList:
                # If we've got nothing to do, ensure we sleep a bit.
                abortEvent(.2)

            firstTraversal = True
            while searchList:
                for index in searchList:
                    retries = retryLookup.get(index, 0)
                    try:
                        if self._loadItem(self._selectionIdxToClientIdx[index],
                                          dataMgr, clipMgr, retries,
                                          firstTraversal):
                            if index in viewIndices:
                                wx.CallAfter(self._safeRefresh)
                            img, label, _, _ = self._dataCache[
                                self._selectionIdxToClientIdx[index]
                            ]
                            if img and label:
                                loadedIndicies.add(index)
                    except Exception:
                        if retries == _kNumLoadRetries:
                            self._logger.error(
                                "Unhandled exception: " + traceback.format_exc(), exc_info=True
                            )

                    if not firstTraversal:
                        retryLookup[index] = retries+1

                    # If the user scrolled break and reprioritize what we load.
                    if firstVisible != self.GetVisibleBegin():
                        searchList = []
                        break

                    # Check for abort events; raise an exception if one...
                    # ...we also use this as a chance to sleep between loads
                    # when we're loading the bitmaps (2nd traversal)...
                    if (not firstTraversal) and shouldSleep:
                        abortEvent(.1)
                    else:
                        abortEvent()

                firstTraversal = False

                searchList = set(searchList).difference(loadedIndicies)
                unloadedIndicies.difference_update(loadedIndicies)

                # Sleep for a little bit.  Technically, this is only needed if
                # we didn't actually load anything so that there will be a
                # little bit of time between retries.
                abortEvent(.1)


    ###########################################################
    def _safeRefresh(self):
        """Does a Refresh if we haven't been deleted yet.

        This is used by the self._loadLoop, which uses a wx.CallAfter to do
        a refresh.  It's possible that by the time the CallAfter executes we
        will already be deleted.  In that case, self.Refresh() will raise an
        exception.  We don't care about that exception, so we'll just ignore it.
        """
        try:
            self.Refresh()
        except Exception:
            pass


    ###########################################################
    def _resultItemsLoaded(self, delayedResultObj):
        """Respond to completion of the loaded items.

        @param delayedResultObj  The delayed result object that loaded items.
        """
        pass


    ###########################################################
    def OnDrawBackground(self, dc, rect, n): #PYCHECKER signature mismatch OK
        """Draw the background and border for the given item

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        if self._searching:
            assert n == 0
            return

        resultsModel = self._resultsModel

        areMultipleSelected = self._resultsModel.getMultipleSelected()
        clientIdx = resultsModel.getCurrentClipNum()
        if (clientIdx != int(clientIdx)) and (not areMultipleSelected):
            x, y, width, height = rect
            wantDraw = False
            nClientIdx = self._selectionIdxToClientIdx[n]
            if nClientIdx == math.floor(clientIdx):
                wantDraw = True
                y += (height - _kBetweenSelectionHeight - 1)
                height = _kBetweenSelectionHeight
            elif nClientIdx == math.ceil(clientIdx):
                wantDraw = True
                if nClientIdx < 0:
                    height = _kBetweenSelectionHeight + 1
                else:
                    height = _kBetweenSelectionHeight

            if wantDraw:
                dc.SetPen(wx.Pen(_kBetweenSelectionColor))
                dc.SetBrush(wx.Brush(_kBetweenSelectionColor))
                dc.DrawRectangle(x, y, width, height)
        elif n in self._getSelectedItems():
            dc.GradientFillLinear(rect, self._gradientCol1, self._gradientCol2,
                                  wx.NORTH)


    ###########################################################
    def OnDrawSeparator(self, dc, rect, n): #PYCHECKER signature mismatch OK
        """Draw a seperator for the given item

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        if self._searching:
            assert n == 0
            return

        resultsModel = self._resultsModel

        areMultipleSelected = self._resultsModel.getMultipleSelected()
        currentClipNum = resultsModel.getCurrentClipNum()
        isFloat = currentClipNum != int(currentClipNum)
        selection = self._clientIdxToSelectionIdx.get(
            int(math.floor(currentClipNum)), -1
        )
        if (not areMultipleSelected) and \
                isFloat and (n == math.floor(selection)):
            pen = wx.Pen(_kBetweenSelectionColor)
        else:
            pen = wx.GREY_PEN

        dc.SetPen(pen)
        dc.DrawLine(rect.X, rect.Y+rect.Height-1, rect.X+rect.Width-1,
                    rect.Y+rect.Height-1)


    ###########################################################
    def OnDrawItem(self, dc, rect, n):
        """Draw the item with the given index

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        noteStr = None
        noteColor = None

        if self._searching:
            assert n == 0
            currentCam = self._resultsModel.getCurrentSearchCamera()
            if currentCam:
                dc.DrawText(kSearchingOnString % currentCam, rect.X+4, rect.Y+4)
            else:
                dc.DrawText(kSearchingString, rect.X+4, rect.Y+4)
            return

        cacheIndex = self._selectionIdxToClientIdx[n]

        img, label, timeStr, isSaved = self._dataCache[cacheIndex]
        if not label:
            label = "Loading Preview"
            timeStr = ""

        isSelected = self.IsSelected(n)

        # Draw image
        if img:
            w, h = img.size
            wxImage = wx.ImageFromBuffer(w, h, img.convert('RGB').tobytes())

            dc.DrawBitmap(wx.Bitmap(wxImage), rect.X+_kImgXOffset,
                          rect.Y+_kImgYOffset)

        # Draw label
        font = dc.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        font.SetPointSize(_kLabelFontSize)
        dc.SetFont(font)
        if isSelected:
            dc.SetTextForeground(wx.WHITE)
        else:
            dc.SetTextForeground(wx.BLACK)

        tLabel = truncateText(dc, label, rect.Width-_kLabelXOffset)
        dc.DrawText(tLabel, rect.X+_kLabelXOffset, rect.Y+_kLabelYOffset)

        # Draw time str
        if timeStr:
            # If we stashed a note in the timeStr, split it out.
            if '\n' in timeStr:
                timeStr, noteStr = timeStr.split('\n', 2)
                noteColor = self._colGray

            font = dc.GetFont()
            font.SetWeight(wx.FONTWEIGHT_LIGHT)
            font.SetPointSize(_kTimeFontSize)
            dc.SetFont(font)
            if not isSelected:
                dc.SetTextForeground(self._colGray)

            tTime = truncateTextMid(dc, timeStr, rect.Width-_kLabelXOffset)
            dc.DrawText(tTime, rect.X+_kTimeXOffset, rect.Y+_kTimeYOffset)

        if img and not isSaved:
            noteStr = _kNotSavedStr
            noteColor = wx.BLACK

        if noteStr:
            font = dc.GetFont()
            font.SetWeight(wx.FONTWEIGHT_NORMAL)
            font.SetPointSize(_kTimeFontSize)
            dc.SetFont(font)
            if not isSelected:
                dc.SetTextForeground(noteColor)

            sLabel = truncateText(dc, noteStr, rect.Width-_kLabelXOffset)
            dc.DrawText(sLabel, rect.X+_kLabelXOffset,
                        rect.Y+_kNotSavedlYOffset)


    ###########################################################
    def OnMeasureItem(self, n):
        """Return the height of an item in the list box

        @param  n     The index of the item to retrieve the height of
        """
        return _kItemHeight


    ###########################################################
    def _loadItem(self, cacheIndex, dataMgr, clipMgr, retries, textOnly=False):
        """Load and store data necessary to display a clip preview

        @param  cacheIndex  The index of the item to load.
        @param  dataMgr     The data manager to use for retrieving data.
        @param  clipMgr     The data manager to use for retrieving data.
        @param  retries     The number of attempts made to load item cacheIndex.
        @param  textOnly    If True do not attempt to load the thumbnail.
        @return loaded      True if an item's UI was loaded.
        """
        result = self._curResults[cacheIndex]
        camLoc = result.camLoc
        startMs = result.startTime
        playMs = result.playStart
        previewMs = result.previewMs
        objList = result.objList
        objListForMarkup = objList if self._markupModel.getShowBoxesAroundObjects() else None
        isSaved = result.isSaved

        img, label, timeStr, _ = self._dataCache[cacheIndex]
        hadImg = img is not None
        hadLabel = label is not None


        # If data wasn't available to determine if a clip was saved or not
        # check if it is now.
        if not textOnly and isSaved > 1:
            # If isSaved is set to be > 1 it means we tucked away the real
            # stop time in preparation for this later call.  We'll use the
            # play time as the beginning of the clip, since that's likely
            # what we really care about.
            isSaved = self.checkIfRangeSaved(clipMgr, camLoc, playMs,
                                             isSaved)
            if retries > _kNumLoadRetries-5:
                # If something messed up and the tag is never going to come
                # through we still want to try to update the image.  We'll
                # err on the side of not showing the 'not saved' tag.
                isSaved = True

            if isSaved in (True, False):
                # We need to update this in the curResults too, to avoid
                # future confusion.
                result.isSaved = isSaved

        if img is None and not textOnly and isSaved in (True, False):
            if retries < _kNumLoadRetries:
                # we're still trying to load the frame at the correct offset
                img = dataMgr.getSingleMarkedFrame(camLoc, previewMs, objListForMarkup,
                                            (_kPreviewWidth, 0))
            elif retries == _kNumLoadRetries:
                # On the off chance that an image simply didn't exist at the
                # time we were requesting, attempt to grab the beginning
                # frame to avoid "video not found"
                img = dataMgr.getSingleMarkedFrame(camLoc, startMs, objListForMarkup,
                                               (_kPreviewWidth,
                                                0),
                                               False)
            else:
                # go for the safe option
                label = "Video not found"
                img = self._blankImg
                # We'll set isSaved to True...seems right to just not
                # show anything about saving/not saving when the video
                # doesn't exist...
                self._dataCache[cacheIndex] = (img, label, camLoc,
                                               True)
                return True

            if img is None:
                return False

            self._dataCache[cacheIndex] = (img, label, timeStr, isSaved)

        if not label:
            # Generate the label
            numPeople = 0
            numPets = 0
            numVehicles = 0
            numOther = 0
            typeStrs = []

            badTypes = defaultdict(int)
            for obj in objList:
                objType = dataMgr.getObjectType(obj)
                if objType == "person":
                    numPeople += 1
                elif objType == "animal":
                    numPets += 1
                elif objType == "vehicle":
                    numVehicles += 1
                elif objType == "object":
                    numOther += 1
                else:
                    # Shouldn't ever get here, but keep track of unexpected
                    # type, which will help us debug problems...
                    badTypes[objType] += 1

            if numPeople >= 1:
                typeStrs.append('People')
            if numPets >= 1:
                typeStrs.append('Animals')
            if numVehicles >= 1:
                typeStrs.append('Vehicles')
            if numOther >= 1:
                typeStrs.append('Unknown')

            # Add unexpected types...
            for (typeStr, count) in badTypes.iteritems():
                if count == 1:
                    typeStrs.append(typeStr)
                else:
                    typeStrs.append(typeStr + 's')

            label = ', '.join(typeStrs)

            if camLoc.endswith(kImportSuffix):
                try:
                    timeStr = result.filename

                    # Try to add the relative milliseconds to the timeStr as
                    # a note...
                    if result.fileStartMs:
                        ms = startMs - result.fileStartMs
                        ms = max(0, ms)
                        minutes, seconds = divmod(ms//1000, 60)
                        hours, minutes = divmod(minutes, 60)
                        timeStr += '\n%02d:%02d:%02d' % (hours, minutes, seconds)
                except AttributeError:
                    assert False, "Missing filename"
                    timeStr = ""
            else:
                if objList:
                    label += ' - ' + camLoc



                if self._debugModeModel.isDebugMode():
                    # Generate the time string for debug
                    timeStr = getDebugTime(startMs) + "-" + getDebugTime(result.stopTime)
                else:
                    # Generate the time string
                    timeStruct = time.localtime(startMs/1000.)
                    timeStr = formatTime(self._timeStr, timeStruct).swapcase()
                    if timeStr[0] == '0':
                        timeStr = timeStr[1:]

            self._dataCache[cacheIndex] = (img, label, timeStr, isSaved)

        if (label and not hadLabel) or (img and not hadImg):
            return True

        return False


    ###########################################################
    def checkIfRangeSaved(self, clipMgr, location, start, stop):
        """Check if the given time range is marked as saved at a location.

        @param  clipMgr   The clip database to use for lookups.
        @param  location  The location to investigate.
        @param  start     The start ms of the range of interest.
        @param  stop      The stop ms of the range of interest.
        @return isSaved   True if the full range is saved, False if not, and
                          stop if it is unknown.
        """
        isSaved = False

        savedRanges = clipMgr.getTimesFromLocation(location, start-60000, None,
                                                   True)
        numRanges = len(savedRanges)

        curMaxTagged = 0
        if numRanges:
            curMaxTagged = savedRanges[numRanges-1][1]
        _, tagged = self._resultsModel.getProcessedInfoForLocation(location)
        if stop > curMaxTagged and stop <= tagged:
            return stop

        if numRanges:
            idx = bisect.bisect_left(savedRanges, (start, 0))
            if idx < numRanges and start == savedRanges[idx][0] and \
               stop <= savedRanges[idx][1]:
                isSaved = True
            elif idx != 0 and stop <= savedRanges[idx-1][1]:
                isSaved = True

        return isSaved


    ###########################################################
    def _getSelectedItems(self, asClientIdxs=False):
        """Retrieve a the selected items.

        @return selected  A list of selected item indicies.
        """
        selected = []

        idx, cookie = self.GetFirstSelected()
        while idx != -1:
            if asClientIdxs:
                selected.append(self._selectionIdxToClientIdx[idx])
            else:
                selected.append(idx)
            idx, cookie = self.GetNextSelected(cookie)

        return selected


    ###########################################################
    def OnShowPopup(self, event):
        """Handle the context menu event.

        @param  event  The event to handle.
        """
        # Find which object was clicked
        realPoint = event.Position-self.GetScreenPosition()
        selection = self.VirtualHitTest(realPoint.y)

        if selection == -1:
            # If nothing was clicked don't show the menu or change seleciton.
            return

        elif selection not in self._getSelectedItems():
            # If a new item was clicked select it.
            self.DeselectAll()
            self.SetSelection(selection)

            # Notify ourselves about the change
            event.SetInt(selection)
            self.OnResult(event)

        self._pendingPopupPoint = self.ScreenToClient(event.GetPosition())
        self._pendingPopupTimeout = time.time() + _kPopupTimeout
        self._showPopup()


    ###########################################################
    def _showPopup(self):
        """Actually show the context menu."""
        if not self._pendingPopupPoint or time.time() > self._pendingPopupTimeout:
            return

        # Ensure we still have selected items.
        if not self._getSelectedItems():
            return

        # Create our menu.
        menu = wx.Menu()

        # Add any currently enabled / attached export-related items...
        # ...note that we should already be bound to them...
        for menuItem in self._menuItems:
            if menuItem.IsEnabled() and (menuItem.GetMenu() is not None):
                menu.Append(menuItem.GetId(), menuItem.GetItemLabel())

        if menu.GetMenuItemCount() != 0:
            # Popup the menu
            self.PopupMenu(menu, self._pendingPopupPoint)
        else:
            # If something was selected but the menu is not yet loaded we want
            # to try again until it is available.
            wx.CallLater(20, self._showPopup)

        # Kill the menu
        menu.Destroy()


    ###########################################################
    def _handleTimePrefChange(self, uiModel):
        """Handle a change to time display preferences.

        @param  resultsModel  The UIPrefsDataModel.
        """
        prevTimeStr = self._timeStr
        use12, _ = uiModel.getTimePreferences()

        if use12:
            self._timeStr = _kTime12Hour
        else:
            self._timeStr = _kTime24Hour

        # Throw out our data cache and reload if the time format changed.
        if self._timeStr != prevTimeStr and self._curResults:
            self._restartLoader()


################################################################################
if __name__ == '__main__':
    from FrontEndApp import main
    main()
