
#=================================================================================
# Set up variables
#=================================================================================
SCRIPT_PATH="`dirname \"$0\"`" 
BUNDLE_ID=com.sighthoundlabs.sighthoundvideo
APP_PATH="${1}"
ENTITLEMENTS_PATH=${SCRIPT_PATH}/../FrontEnd/resources/entitlements.plist
CERT_NAME="Developer ID Application: Sighthound, Inc. (ZHUS2RP6P5)"
# -i ${BUNDLE_ID} causes webcam crash -- but can we notarize, if we sign without it?
CODESIGN_OPTIONS_REDUX="-f --timestamp --verbose=4 --options=runtime --entitlements ${ENTITLEMENTS_PATH}"
CODESIGN_OPTIONS="${CODESIGN_OPTIONS_REDUX}" # -i ${BUNDLE_ID}"
BIN_PATH="${APP_PATH}/Contents/MacOS"



#=================================================================================
# Sign the relevant binaries
#=================================================================================
if [[ "$APP_PATH" == *".dmg" ]]; then
	echo "Signing ${APP_PATH}"
	codesign -f -s "${CERT_NAME}" "${APP_PATH}" || { exit 1; }
elif [ -f "${BIN_PATH}/Updater" ]; then
	echo "Signing Updater Binaries"
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}/Updater" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${APP_PATH}" || { exit 1; }
else
	echo "Fixing libraries' rpath"
	${SCRIPT_PATH}/fixRPath.sh "@loader_path" "@executable_path" "${BIN_PATH}"/*.dylib || { exit 1; }
	${SCRIPT_PATH}/fixRPath.sh "@loader_path" "@executable_path" "${BIN_PATH}"/*.so || { exit 1; }
	${SCRIPT_PATH}/fixRPath.sh "@loader_path/PipelineNodes" "@executable_path" "${BIN_PATH}"/PipelineNodes/*.so || { exit 1; }

	echo "Signing Sighthound Video Binaries"
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}"/*.dylib || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}"/PipelineNodes/*.so || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}"/*.so || { exit 1; }
	codesign ${CODESIGN_OPTIONS_REDUX} -s "${CERT_NAME}" "${BIN_PATH}/Sighthound USB" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}/Python" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}/shlaunch" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}/Sighthound Web" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}/SighthoundVideoLauncher" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${BIN_PATH}/library.zip" || { exit 1; }
	codesign ${CODESIGN_OPTIONS} -s "${CERT_NAME}" "${APP_PATH}" || { exit 1; }

	spctl -a -t exec -vvvv --raw "${APP_PATH}" || { exit 1; }
	codesign -v -vvvv --deep "${APP_PATH}" || { exit 1; }
fi



