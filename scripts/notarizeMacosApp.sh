
#=================================================================================
# Set up variables
#=================================================================================
SCRIPT_PATH="`dirname \"$0\"`" 
BUNDLE_ID=com.sighthoundlabs.sighthoundvideo
APPLE_ID=ci@sighthound.com
APP_PATH="${1}"

if [ ! -z "${SV_SKIP_NOTARIZATION}" ]; then
    exit 0
fi

#=================================================================================
# Submit the notarization request
#=================================================================================
ditto -c -k --keepParent "${APP_PATH}" "${APP_PATH}.zip" || exit 1
echo "Sending notarization request to Apple..."
APPLE_SAYS=`xcrun altool --notarize-app -t osx --primary-bundle-id "${BUNDLE_ID}" --username "${APPLE_ID}" --password "@keychain:CI_PASSWORD" --file "${APP_PATH}.zip"`
#APPLE_SAYS="No errors uploading '/Users/alex/work/sv/smartvideo/build/app-out/FrontEnd-Mac/Sighthound Video.app.zip'. RequestUUID = 78943e2b-ca7a-498c-94b4-bd11843991f8"
echo "APPLE_SAYS=${APPLE_SAYS}"
APPLE_REQ_ID=`echo $APPLE_SAYS | grep RequestUUID | sed 's/.*RequestUUID = \(.*\)/\1/g'`
echo "APPLE_REQ_ID=${APPLE_REQ_ID}"
if [ -z "${APPLE_REQ_ID}" ]; then
    echo "Failed to determine RequestUUID"
    exit 1
fi


#=================================================================================
# Query for result
#=================================================================================

#=================================================================================
# Example of a failure
#=================================================================================
    # No errors getting notarization info.

    #           Date: 2020-12-18 00:16:47 +0000
    #           Hash: 5e12d0e79f56ddd694c2717d46ae6b4e7a5097d413c879a8166fdac15406266f
    #     LogFileURL: https://osxapps-ssl.itunes.apple.com/itunes-assets/Enigma114/v4/12/3f/7e/123f7ed2-e38d-6824-4fdb-83e3b9265552/developer_log.json?accessKey=1608445545_4452914554061052844_08w7M7ZIUUKZWnM4ihVRTHmsddaOMExl6%2FALQ7w2AlkYrrWpEDcJJzdWWrb99wc135f0pd3MEJnbZ2Wa%2Bcux6i62dHdiVo5u2%2FOx3bFt6zMJlXk23rIEIcpflpwMpXHe8YC%2Ba%2BiO1mItuf3Hjsf1pR76vjHe21tzC%2Fr00XeqzNw%3D
    #    RequestUUID: 78943e2b-ca7a-498c-94b4-bd11843991f8
    #         Status: invalid
    #    Status Code: 2
    # Status Message: Package Invalid

#=================================================================================
# Example of a success
#=================================================================================
    # No errors getting notarization info.

    #           Date: 2020-12-18 02:10:22 +0000
    #           Hash: 661b0dca1d07d6ae825fa82316fb5059ed48213634f5e9b9568c204dbf9bba1e
    #     LogFileURL: https://osxapps-ssl.itunes.apple.com/itunes-assets/Enigma114/v4/21/4f/a5/214fa591-e81f-fe2c-bc18-a670ff096925/developer_log.json?accessKey=1608452045_1787926363891998334_4ihgyVUbPxMwR3XIiTPRnSwkwiNOk9JtcrR%2F%2Fp909gWQ3bQmXlK6EODfoGUWQHyRUi1HPIEREw1Sm2ocKVEc3SBjmPG%2F%2B7iWxVdndO3N%2Bz2hjTWfnL64Ihb9KULMaaRIpCf8j%2FXnk75WwCXHXhdyG61rhCkCK%2BvWHqA6Ih5tIXs%3D
    #    RequestUUID: f8f84e16-6034-4a4b-8052-176ea0615bf6
    #         Status: success
    #    Status Code: 0
    # Status Message: Package Approved
rm "${APP_PATH}.zip"
while true; do 
    APPLE_SAYS=`xcrun altool --notarization-info "${APPLE_REQ_ID}" -u "${APPLE_ID}" --password "@keychain:CI_PASSWORD"`
    echo "APPLE_SAYS=${APPLE_SAYS}"
    if [[ "$APPLE_SAYS" == *"Status: success"* ]]; then
        echo "Notarization request successful!"
        break
    elif [[ "$APPLE_SAYS" == *"Status: invalid"* ]]; then
        echo "Notarization request failed!"
        exit 1
    else
        echo "Still waiting for notarization result!"
        sleep 15s
        echo "Trying again ..."
    fi
done

echo "Stapling the bundle at ${APP_PATH}"
xcrun stapler staple "${APP_PATH}" || exit 1

if [[ "$APP_PATH" == *".app" ]]; then
    echo "Validating the bundle at ${APP_PATH}"
    spctl --assess --verbose --type execute --ignore-cache --no-cache "${APP_PATH}" || exit 1
fi

echo "Validating the bundle at ${APP_PATH}"
xcrun stapler validate "${APP_PATH}" || exit 1

