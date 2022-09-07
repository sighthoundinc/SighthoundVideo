#!/bin/sh

# Echos the current date/time and svn revision to stdin
date=`date "+%Y-%m-%d-%H.%M.%S"`
revision=`./scripts/getRevision.sh`
echo "Build $date r$revision"
