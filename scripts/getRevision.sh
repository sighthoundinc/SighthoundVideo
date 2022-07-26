#!/bin/sh
# Return the source control revision, like "6234"
# ...allows you to put a REVISION.txt file to use instead for cases where
# you're running outside of source control.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [ ! -z $SV_BUILD_REVISION ]; then
  echo $SV_BUILD_REVISION
elif [ -e REVISION.txt ]; then
  cat REVISION.txt
else
  pushd $DIR > /dev/null
  git rev-list HEAD | wc -l | awk '{print $1+10000}'
  popd > /dev/null
  # At the svn to git transition svn revision was shy of 6300. Fake
  # svn-like revision numbers by counting the number of commits and adding
  # a large number (10000) to ensure there is no overlap with the old
  # revision numbers to avoid any confusion.
fi
