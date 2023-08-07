#!/usr/bin/env python

#*****************************************************************************
#
# TruncateText.py
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

# Common 3rd-party imports...

# Local imports...

# Constants...


###########################################################
def truncateText(dc, text, availableWidth):
    """Truncate text so that it fits within the given space

    @param  dc              The dc into which the text will be drawn
    @param  text            The text to be truncated
    @param  availableWidth  The maximum space to draw text into
    @return truncText       The truncated text
    """
    ellipsisWidth, _ = dc.GetTextExtent("...")
    textWidth, _ = dc.GetTextExtent(text)

    if textWidth <= availableWidth:
        return text

    partialLineWidths = dc.GetPartialTextExtents(text)
    for i, partialLineWidth in enumerate(partialLineWidths):
        if partialLineWidth > (availableWidth - ellipsisWidth):
            i = max(0, i - 1)
            break
    return text[:i] + "..."


###########################################################
def truncateTextMid(dc, text, availableWidth):
    """Truncate text from the middle so that it fits within the given space.

    @param  dc              The dc into which the text will be drawn
    @param  text            The text to be truncated
    @param  availableWidth  The maximum space to draw text into
    @return truncText       The truncated text
    """
    ellipsisWidth, _ = dc.GetTextExtent("...")
    textWidth, _ = dc.GetTextExtent(text)

    if textWidth <= availableWidth:
        return text

    while text:
        l = len(text)
        firstHalf = text[:l//2]
        secondHalf = text[l//2+1:]

        text = firstHalf + secondHalf

        textWidth, _ = dc.GetTextExtent(text)
        if textWidth <= (availableWidth - ellipsisWidth):
            break
    else:
        return "..."

    return firstHalf + "..." + secondHalf


###########################################################
def truncateStaticText(win):
    """Truncate text so that it fits within current size of a static text ctrl.

    @param  win  A StaticText control.
    """
    text = win.GetLabel()
    ellipsisWidth, _ = win.GetTextExtent("...")
    textWidth, _ = win.GetTextExtent(text)
    availableWidth, _ = win.GetClientSize()

    if textWidth <= availableWidth:
        return

    for i in xrange(len(text)):
        partialLineWidth, _ = win.GetTextExtent(text[:i])
        if partialLineWidth > (availableWidth - ellipsisWidth):
            i = max(0, i - 1)
            break

    win.SetLabel(text[:i] + "...")


