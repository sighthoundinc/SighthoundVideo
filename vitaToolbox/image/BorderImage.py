#! /usr/local/bin/python

#*****************************************************************************
#
# BorderImage.py
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
from PIL import Image

##############################################################################
def loadBorderImage(src, desiredSize, borderWidth, borderHeight=None):
    """Makes an image from the given border image.

    A border image is one that looks like what you want your final image to
    look like, it just is a different size.  We'll chop up the border image,
    expand it, and make the final image.  It probably makes sense to look at
    it graphically.  Say your source image looks like this:

      +-----+---------------+-----+
      |     |               |     |
      |  1  |       2       |  3  |
      +-----+---------------+-----+
      |     |               |     |
      |     |               |     |
      |  4  |       5       |  6  |
      |     |               |     |
      |     |               |     |
      +-----+---------------+-----+
      |     |               |     |
      |  7  |       8       |  9  |
      +-----+---------------+-----+

    ...this image is 29x13

    Now, we want to make another image that is a different size.  We'll chop
    the source image up and re-use the corners in the destination image.  Then,
    we'll replicate the edges and center as needed to make the destination
    image.  Like this to get a 50x16 image

      +-----+---------------+---------------+----+-----+
      |     |               |               |    |     |
      |  1  |       2       |       2       | 2  |  3  |
      +-----+---------------+---------------+----+-----+
      |     |               |               |    |     |
      |     |               |               |    |     |
      |  4  |       5       |       5       | 5  |  6  |
      |     |               |               |    |     |
      |     |               |               |    |     |
      +-----+---------------+---------------+----+-----+
      |     |               |               |    |     |
      |  4  |       5       |       5       | 5  |  6  |
      +-----+---------------+---------------+----+-----+
      |     |               |               |    |     |
      |  7  |       8       |       8       | 8  |  9  |
      +-----+---------------+---------------+----+-----+

    This is the same as the CSS concept of a border image...

    @param  src          The source border iamge.  Can be any of:
                         - A PIL Image (instance Image)
                         - A string path to a file.
                         - A file-like object.
    @param  desiredSize  A tuple (width, height) indicating what size you want.
    @param  borderWidth  The width of the border in the image.
    @param  borderHeight The height of the border in the image; if None, we just
                         use the same value as the width.
    @return dst          The resulting image.
    """
    # Adjust optional parameters
    if borderHeight is None:
        borderHeight = borderWidth

    # Open the image if needed...
    if not isinstance(src, Image.Image):
        src = Image.open(src)
    srcWidth, srcHeight = src.size

    # Create the destination in same mode as source...
    dst = Image.new(src.mode, desiredSize)
    dstWidth, dstHeight = desiredSize

    # If the destination is really small and can't fit two borders, then crop
    # the borders down so that it at least looks sorta reasonable (it won't
    # look good, but it should at least work...)
    if borderWidth > (dstWidth/2):
        borderWidth = dstWidth/2
    if borderHeight > (dstHeight/2):
        borderHeight = dstHeight/2

    # Figure out how big the middle section in the source image should be.
    srcMiddleWidth  = srcWidth - (2 * borderWidth)
    srcMiddleHeight = srcHeight - (2 * borderHeight)
    assert srcMiddleWidth > 0 and srcMiddleHeight > 0, \
           "Source image not big enough for specified border"

    # Figure out how many middle rows and columns there are, as well as the
    # number of extra pixels that don't evenly divide...
    numMiddleCols, extraWidth = \
        divmod((dstWidth - (2 * borderWidth)), srcMiddleWidth)
    numMiddleRows, extraHeight = \
        divmod((dstHeight - (2 * borderHeight)), srcMiddleHeight)

    # Break the source image into the main chunks...  Abbreviations are for
    # things like top-left, top, top-right, ...
    tlPiece = src.crop((0, 0, borderWidth, borderHeight))
    tPiece  = src.crop((borderWidth, 0, srcWidth-borderWidth, borderHeight))
    trPiece = src.crop((srcWidth-borderWidth, 0, srcWidth, borderHeight))
    lPiece  = src.crop((0, borderHeight, borderWidth, srcHeight-borderHeight))
    cPiece  = src.crop((borderWidth, borderHeight,
                        srcWidth-borderWidth, srcHeight-borderHeight))
    rPiece  = src.crop((srcWidth-borderWidth, borderHeight,
                        srcWidth, srcHeight-borderHeight))
    blPiece = src.crop((0, srcHeight-borderHeight, borderWidth, srcHeight))
    bPiece  = src.crop((borderWidth, srcHeight-borderHeight,
                        srcWidth-borderWidth, srcHeight))
    brPiece = src.crop((srcWidth-borderWidth, srcHeight-borderHeight,
                        srcWidth, srcHeight))

    # These are the extra pieces that we need to make since we need a fractional
    # number of middle pieces...  Abbreviations are like "top extra",
    # "center extra on right", ...
    if extraWidth:
        txPiece = tPiece.crop((0, 0, extraWidth, borderHeight))
        bxPiece = bPiece.crop((0, 0, extraWidth, borderHeight))
    if extraHeight:
        lxPiece = lPiece.crop((0, 0, borderWidth, extraHeight))
        rxPiece = rPiece.crop((0, 0, borderWidth, extraHeight))

    # Assume that the middle is a solid color--get that color...
    middleColor = cPiece.getpixel((0, 0))

    # Init x and y
    x, y = (0, 0)

    # Draw the top row...
    dst.paste(tlPiece, (x, y))
    x += borderWidth
    for _ in xrange(numMiddleCols):
        dst.paste(tPiece, (x, y))
        x += srcMiddleWidth
    if extraWidth:
        dst.paste(txPiece, (x, y))
        x += extraWidth
    dst.paste(trPiece, (x, y))
    x = 0
    y += borderHeight

    # Draw the edges of the middle region...
    # TODO: I think the only plausible "middle" pieces have to be all one solid
    # color.  Could we just fill with that color to speed things up?
    for _ in xrange(numMiddleRows):
        dst.paste(lPiece, (0, y))
        dst.paste(rPiece, (dstWidth-borderWidth, y))
        y += srcMiddleHeight

    # Draw the edges of the extra row...
    if extraHeight:
        dst.paste(lxPiece, (0, y))
        dst.paste(rxPiece, (dstWidth-borderWidth, y))
        y += extraHeight

    # Draw the bottom row...
    dst.paste(blPiece, (x, y))
    x += borderWidth
    for _ in xrange(numMiddleCols):
        dst.paste(bPiece, (x, y))
        x += srcMiddleWidth
    if extraWidth:
        dst.paste(bxPiece, (x, y))
        x += extraWidth
    dst.paste(brPiece, (x, y))

    # Fill in the middle as all one color...
    dst.paste(middleColor, (borderWidth, borderHeight,
                            dstWidth-borderWidth, dstHeight-borderHeight))

    return dst


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    i = loadBorderImage('vitaToolbox/wx/RaisedPanelBorder.png', (200, 400), 8)
    i.save("foo.png")

##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
