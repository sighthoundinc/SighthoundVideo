/******************************************************************************
 *
 * optsearches.c
 *     Small C library for optiming spatial triggers detection
 *
 *
 ******************************************************************************
 *
 *
 * Copyright 2013-2022 Sighthound, Inc.
 *
 * Licensed under the GNU GPLv3 license found at
 * https://www.gnu.org/licenses/gpl-3.0.txt
 *
 * Alternative licensing available from Sighthound, Inc.
 * by emailing opensource@sighthound.com
 *
 * This file is part of the Sighthound Video project which can be found at
 * https://github.com/sighthoundinc/SighthoundVideo
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; using version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
 *
 *
 *****************************************************************************/


#define CENTER_POINT 0
#define TOP_POINT    1
#define BOTTOM_POINT 2
#define LEFT_POINT   3
#define RIGHT_POINT  4

#define IS_LEFT  0
#define IS_RIGHT 1
#define IS_ON    2

#define FROM_LEFT  0
#define FROM_RIGHT 1
#define FROM_ANY   2

#ifdef _WIN32
    #define OPTSEARCH_EXPORT __declspec(dllexport)
#else
    #define OPTSEARCH_EXPORT __attribute__ ((visibility ("default")))
#endif

typedef struct twopoints {
    int x1;
    int y1;
    int x2;
    int y2;
} segment, bbox;

typedef struct point {
    int x;
    int y;
} point;


// Finds the point on an object to track.  Takes a bbox defining the object
// boundaries, an int defining the location on the box that should be tracked,
// and a point struct in which to place the calculated point.
inline static void get_object_track_point(bbox box, int location, point* trackPt)
{
    // (x2, y2) on bbox are outside the object so we need to adjust.
    box.x2--;
    box.y2--;

    // Calculate the point on the box we are investigating.
    if (CENTER_POINT == location) {
        trackPt->x = (box.x1+box.x2)/2;
        trackPt->y = (box.y1+box.y2)/2;
    }
    else if (TOP_POINT == location) {
        trackPt->x = (box.x1+box.x2)/2;
        trackPt->y = box.y1;
    }
    else if (BOTTOM_POINT == location) {
        trackPt->x = (box.x1+box.x2)/2;
        trackPt->y = box.y2;
    }
    else if (LEFT_POINT == location) {
        trackPt->x = box.x1;
        trackPt->y = (box.y1+box.y2)/2;
    }
    else { // RIGHT_POINT
        trackPt->x = box.x2;
        trackPt->y = (box.y1+box.y2)/2;
    }
}


// Determine whether an object crossed a line.  Takes the bounding box of an
// object at two points in time, the target line segment, the location on the
// object to track, and the cross direction.  Returns 1 if the object crossed
// the line in the target direction, else 0.
OPTSEARCH_EXPORT int did_obj_cross(bbox prevBox, bbox curBox, segment boundary, int location,
                  int direction)
{
    point prevPt;
    point curPt;
    int prevDir = 0;
    int curDir = 0;
    int a, b;
    int objXs, objYs;
    int segXs, segYs;
    int objCp, segCp;
    double intX, intY;
    double denom;

    // Find the points to track.
    get_object_track_point(prevBox, location, &prevPt);
    get_object_track_point(curBox, location, &curPt);

    // Determine in where the points are in relation to a line defined by our
    // boundary.
    a = (boundary.x2-boundary.x1)*(prevPt.y-boundary.y1);
    b = (boundary.y2-boundary.y1)*(prevPt.x-boundary.x1);

    if (a>b)
        prevDir = IS_LEFT;
    else if (a<b)
        prevDir = IS_RIGHT;
    else
        prevDir = IS_ON;

    a = (boundary.x2-boundary.x1)*(curPt.y-boundary.y1);
    b = (boundary.y2-boundary.y1)*(curPt.x-boundary.x1);

    if (a>b)
        curDir = IS_LEFT;
    else if (a<b)
        curDir = IS_RIGHT;
    else
        curDir = IS_ON;

    // If the points are on the same side of the line they didn't cross it.
    if (prevDir == curDir)
        return 0;

    /*
       Calculate the intersection of the test line with each segment.

            | |x1 y1|   x1-x2  |       | |x1 y1|   y1-y2  |
            | |x2 y2|          |       | |x2 y2|          |
            |                  |       |                  |
            | |x3 y3|   x3-x4  |       | |x3 y3|   y3-y4  |
            | |x4 y4|          |       | |x4 y4|          |
       x = ----------------------  y = ----------------------
            |  x1-x2    y1-y2  |       |  x1-x2    y1-y2  |
            |  x3-x4    y3-y4  |       |  x3-x4    y3-y4  |
    */

    objXs = prevPt.x-curPt.x;
    objYs = prevPt.y-curPt.y;
    segXs = boundary.x1-boundary.x2;
    segYs = boundary.y1-boundary.y2;

    denom = objXs*segYs-segXs*objYs;

    if (denom == 0)
        // Segments are parallel, couldn't have crossed.
        return 0;

    objCp = prevPt.x*curPt.y-curPt.x*prevPt.y;
    segCp = boundary.x1*boundary.y2-boundary.x2*boundary.y1;

    // Calculate the intersection points if both segments were infinite lines.
    intX = (objCp*segXs-segCp*objXs)/denom;
    intY = (objCp*segYs-segCp*objYs)/denom;

    // Check if the segments themselves actually intersect
    if ( ( ((prevPt.x <= intX) && (intX <= curPt.x)) ||
           ((curPt.x <= intX) && (intX <= prevPt.x)) ) &&
         ( ((boundary.x1 <= intX) && (intX <= boundary.x2)) ||
           ((boundary.x2 <= intX) && (intX <= boundary.x1)) ) ){

        // If the x's of either line segment are equal, we need an
        // additional check to ensure the line segment was actually crossed.
        if (boundary.x1 == boundary.x2) {
            if ( !((boundary.y2 <= intY) && (intY <= boundary.y1)) &&
                 !((boundary.y1 <= intY) && (intY <= boundary.y2)) )
                return 0;
        }
        if (prevPt.x == curPt.x) {
            if ( !((curPt.y <= intY) && (intY <= prevPt.y)) &&
                 !((prevPt.y <= intY) && (intY <= curPt.y)) )
                return 0;
        }

        if (direction == FROM_ANY) {
            if (prevDir != IS_ON)
                return 1;
        }
        else if (direction == prevDir)
            return 1;
    }

    return 0;
}


// Use the ray casting algorithm as described at
// http://en.wikipedia.org/wiki/Point_in_polygon
// to determine whether a point is inside a polygon.
//
// Summary: Draw a horizontal line from the point to infinity.  For each
// intersection with a side of the region add one.  If the intersection
// is at a vertex, only count it if the other end of the side is below
// the drawn line.  The point is inside the region if the final count
// is odd.
//
// This function takes the bounding box of an object, the point on the object
// to track, a list of line segments defining the polygon and the number of
// segments.
OPTSEARCH_EXPORT int is_obj_inside(bbox box, int location, segment* segments,
                  int numSegments)
{
    int testX = 0;
    int testY = 0;
    int curSegment = 0;
    int numIntersections = 0;
    int tX1, tY1, tX2, tY2;
    int tXs, tYs;
    int tCp;

    // (x2, y2) on bbox are outside the object so we need to adjust.
    box.x2--;
    box.y2--;

    // Calculate the point on the box we are investigating.
    if (CENTER_POINT == location) {
        testX = (box.x1+box.x2)/2;
        testY = (box.y1+box.y2)/2;
    }
    else if (TOP_POINT == location) {
        testX = (box.x1+box.x2)/2;
        testY = box.y1;
    }
    else if (BOTTOM_POINT == location) {
        testX = (box.x1+box.x2)/2;
        testY = box.y2;
    }
    else if (LEFT_POINT == location) {
        testX = box.x1;
        testY = (box.y1+box.y2)/2;
    }
    else if (RIGHT_POINT == location) {
        testX = box.x2;
        testY = (box.y1+box.y2)/2;
    }


    /*
       Calculate the intersection of the test line with each segment.

            | |x1 y1|   x1-x2  |       | |x1 y1|   y1-y2  |
            | |x2 y2|          |       | |x2 y2|          |
            |                  |       |                  |
            | |x3 y3|   x3-x4  |       | |x3 y3|   y3-y4  |
            | |x4 y4|          |       | |x4 y4|          |
       x = ----------------------  y = ----------------------
            |  x1-x2    y1-y2  |       |  x1-x2    y1-y2  |
            |  x3-x4    y3-y4  |       |  x3-x4    y3-y4  |
    */


    tX1 = testX;
    tY1 = testY;
    tX2 = -1;
    tY2 = testY;

    tXs = tX1-tX2;
    tYs = 0;
    tCp = tXs*tY1;

    while (curSegment < numSegments) {
    	int x1, y1, x2, y2;
    	int xs, ys;
    	int cp;
    	double denom;
        double intX, intY;

        x1 = segments[curSegment].x1;
        y1 = segments[curSegment].y1;
        x2 = segments[curSegment].x2;
        y2 = segments[curSegment].y2;

        xs = x1-x2;
        ys = y1-y2;
        denom = tXs*ys-xs*tYs;

        if (denom == 0)
            // Lines are parallel.
            goto inc;

        cp = x1*y2-x2*y1;
        intX = (tCp*xs-cp*tXs)/denom;
        intY = (tCp*ys-cp*tYs)/denom;

        // The previous calculation assumed the lines were infinite, now check
        // where they intersect.
        if ( ( ((tX1<=intX) && (intX<=10000)) || ((10000<=intX) && (intX<=tX1)) ) &&
             ( ((x1 <=intX) && (intX<= x2))   || ((x2 <=intX) && (intX<= x1)) ) ){

            // If the x's of either line segment are equal, we need an
            // additional check to ensure the line segment was actually crossed.
            if (x1 == x2) {
                if ( !((y2 <= intY) && (intY <= y1)) &&
                     !((y1 <= intY) && (intY <= y2)) )
                    goto inc;
            }
            if (tX1 == tX2) {
                if ( !((tY2 <= intY) && (intY <= tY1)) &&
                     !((tY1 <= intY) && (intY <= tY2)) )
                    goto inc;
            }

            if (((x1 == intX) && (y1 == intY) && y2 > intY) ||
                ((x2 == intX) && (y2 == intY) && y1 > intY))
                goto inc;

            numIntersections++;
        }
inc:
        curSegment++;
    }

    return numIntersections % 2;
}
