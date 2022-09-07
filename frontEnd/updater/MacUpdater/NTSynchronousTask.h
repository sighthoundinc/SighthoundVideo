/*
#*****************************************************************************
#
# NTSynchronousTask.h
#
#
#
#*****************************************************************************
#
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
#
#*****************************************************************************
*/

//
//  NTSynchronousTask.h
//  CocoatechCore
//
//  Created by Steve Gehrman on 9/29/05.
//  Copyright 2005 Steve Gehrman. All rights reserved.
//  used by permission
// 	From: 	Steve Gehrman <sgehrman@cocoatech.com>
// Subject: 	Re: Cocoatech Open Source - What license is the code available under?
// Date: 	December 15, 2009 9:29:34 PM PST
// To: 	David Matiskella <david050173@gmail.com>

//I don't really think about the whole license issue.  BSD?  Do what you want with it.

//-steve

//On Dec 15, 2009, at 2:02 PM, David Matiskella wrote:
//
//I have been using a couple of files that I got from Sparkle (namely NTSynchronousTask) and I realized that they are not under the Sparkle copyright. Could you let me know what licensing policy for the cocoatech open source code is? Thank you.
//--David
//
//Steve Gehrman
//
//steve@cocoatech.com
//310.770.5341


#ifndef NTSYNCHRONOUSTASK_H
#define NTSYNCHRONOUSTASK_H

@interface NTSynchronousTask : NSObject
{
    NSTask *mv_task;
    NSPipe *mv_outputPipe;
    NSPipe *mv_inputPipe;

	NSData* mv_output;
	BOOL mv_done;
	int mv_result;
}

// pass nil for directory if not needed
// returns the result
+ (NSData*)task:(NSString*)toolPath directory:(NSString*)currentDirectory withArgs:(NSArray*)args input:(NSData*)input;

@end

#endif
