/*
#*****************************************************************************
#
# main.m
#
#
#
#*****************************************************************************
#
 *
 * Copyright 2013-2022 Arden.ai, Inc.
 *
 * Licensed under the GNU GPLv3 license found at
 * https://www.gnu.org/licenses/gpl-3.0.txt
 *
 * Alternative licensing available from Arden.ai, Inc.
 * by emailing opensource@ardenai.com
 *
 * This file is part of the Arden AI project which can be found at
 * https://github.com/ardenaiinc/ArdenAI
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
#
#*****************************************************************************
*/

#import <Cocoa/Cocoa.h>


int main(int argc, char *argv[])
{
    if (argc > 4) {
        NSString *fileName = [[[[[NSBundle mainBundle] bundlePath] stringByDeletingPathExtension] stringByAppendingPathExtension:@"log"] lastPathComponent];
        NSString *logFile = [[NSString stringWithUTF8String:argv[4]] stringByAppendingPathComponent:fileName];
        freopen ([logFile UTF8String], "w", stderr);
    }
    return NSApplicationMain(argc,  (const char **) argv);
}

