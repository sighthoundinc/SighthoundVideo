#!/usr/bin/python

#*****************************************************************************
#
# portcheck_log_metrics.py
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

""" To run over the Apache error log files, collects logs from the portcheck.php
script and computes the number of requests per IP address, where the check
indicates a successfully opened port.
"""

import sys, re, time, datetime

reLine = re.compile("\[(.*?)\].*PORTCHECK - ([a-f0-9].*) - (.*)")
reMsg = re.compile("checking <http://(.*):.*")

lines = 0
nopslines = 0
nomatches = 0
requests = {}
for fname in sys.argv[1:]:
    print "reading %s..." % fname
    f = open(fname)
    for ln in f.readlines():
        lines += 1
        if -1 == ln.find("] PORTCHECK -"):
            nopslines += 1
            continue
        m = reLine.match(ln)
        if m is None:
            nomatches += 1
            continue
        date = m.group(1)
        reqId = m.group(2)
        msg = m.group(3)
        msgs = requests.get(reqId, [])
        msgs.append((date, msg))
        requests[reqId] = msgs
noIPs = 0
localIPs = {}
publicIPs = {}
no401s = 0
opens = {}
notOpens = {}
ipReqs = {}
for reqId in requests.keys():
    msgs = requests[reqId]
    m = reMsg.match(msgs[0][1])
    if m is None:
        noIPs += 1
        continue
    ip = m.group(1)
    ipReq = ipReqs.get(ip, [])
    ipReq.append((reqId, msgs))
    ipReqs[ip] = ipReq
    if ip.startswith("0.") or ip.startswith("10.") or ip.startswith("192.168") or ip.startswith("172.16"):
        c = localIPs.get(ip, 0)
        localIPs[ip] = 1 + c
        continue
    c = publicIPs.get(ip, 0)
    publicIPs[ip] = 1 + c
    got401 = False
    for msg in msgs[1:]:
        if msg[1] == "status is 401":
            got401 = True
            c = opens.get(ip, 0)
            opens[ip] = 1 + c
            break
    if not got401:
        no401s += 1
        c = notOpens.get(ip, 0)
        notOpens[ip] = 1 + c

mixedOpens = {}
limits = [0, 0, 0, 0, 0]
cmin = sys.maxint
cmax = 0
std = 24 * 30
for o in opens.keys():
    if notOpens.has_key(o):
        c = mixedOpens.get(o, 0)
        mixedOpens[o] = 1 + c
    c = opens[o]
    #print "%s --> %d" % (o, c)
    cmin = min(cmin, c)
    cmax = max(cmax, c)
    if 1 == c:
        limits[0] += 1
    elif 30 > c:
        limits[1] += 1
    elif std / 2 > c:
        limits[2] += 1
    elif std > c:
        limits[3] += 1
    else:
        limits[4] += 1

print ("%d lines" % lines)  # number of log lines read
print ("%d none-portcheck lines" % nopslines) # number of log lines not emitted by portcheck.php
print ("%d no-matches" % nomatches)  # number of lines which didn't match the log format portcheck.php emits
print ("%d requests" % len(requests)) # number of individual requests detected
print ("%d no-IPs" % noIPs) # number of requests for which no IP could be determined
print ("%d local-IPs" % len(localIPs)) # number of IPs which are local network or 0.0.0.*
print ("%d public-IPs" % len(publicIPs)) # number of IPs which are external
print ("%d no-401s" % no401s) # number of requests which didn't show a 401 response from the SV (=port not open)
print ("%d not-opens" % len(notOpens)) # number of port-is-no-reachable IPs
print ("%d mixed-opens" % len(mixedOpens)) # number of IPs which has open successes and failures
print ("%d opens" % len(opens)) # number of port-is-open IPs
print ("%s limits (min: %d, max: %d, std: %d)" % (limits, cmin, cmax, std)) # pseudo histogram of port opening activity

for mo in mixedOpens.keys():
    ipReq = ipReqs[mo]
    if len(ipReq) < 100:
        continue
    fname = "mixed(%s).txt" % mo
    lns = []
    for req in ipReq:
        for itm in req[1]:
            tm = time.strptime(itm[0], "%a %b %d %H:%M:%S %Y")
            dt = datetime.datetime(*(tm[0:6]))
            lns.append((dt, req[0], itm[1]))
    lns.sort(cmp=lambda x,y: cmp(x[0], y[0]))
    print "writing %s ..." % fname
    f = open(fname, "w")
    for ln in lns:
        f.write("%s - %s - %s\n" % ln)
    f.close()