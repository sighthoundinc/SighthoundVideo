#!/bin/sh

if [ ! -z "${SV_SKIP_NOTARIZATION}" ]; then
    exit 0
fi

CERTFILE="$1"
PASSWORD="$2"
TIMESERVER="$3"
FILESTOSIGN="$4"

if [ ! -f "$CERTFILE" ]; then
   echo "Certificate not found at ${CERTFILE}, skipping signing"
   exit 0
fi

signtool sign -f "$(CERTFILE)" -p $(PASSWORD) -t $(TIMESERVER) -v "${FILESTOSIGN}"