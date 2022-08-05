
# Validate the parameters
if [ $# -lt 2 ]; then
    echo "Usage: createDmg.sh APP_DIR OUTPUT_FOLDER [APP_NAME]"
fi

# Read the parameters and set up the defaults
SCRIPT_PATH="`dirname \"$0\"`" 
APP_DIR=$1
OUTPUT_FOLDER=$2
APP_NAME="SighthoundVideo"
if [ $# -gt 2 ]; then
    APP_NAME=$3
fi
DMG_NAME="${APP_NAME}.dmg"
# app max size, in MB
APP_MAX_SIZE=600


rm -rf "${OUTPUT_FOLDER}/rw"
rm "${OUTPUT_FOLDER}/${DMG_NAME}"
mkdir -p ${OUTPUT_FOLDER}/rw

echo "Making DMG from ${APP_DIR} ..."
hdiutil create -size "${APP_MAX_SIZE}m" -fs HFS+ -volname "${APP_NAME}" -srcfolder "${APP_DIR}" -format UDRW "${OUTPUT_FOLDER}/rw/${DMG_NAME}"
if [ $? -ne 0 ]; then
	echo "Failure in hdiutil create"
	exit -1
fi

echo "Mounting the DMG to set the 'custom icon' flag on..." &&
DEVICE=`hdiutil attach -readwrite -noautoopen "${OUTPUT_FOLDER}/rw/${DMG_NAME}" | awk 'NR==1{print$1}'` &&
echo "DEVICE=${DEVICE}" &&
VOLUME=`mount | grep "${DEVICE}" | sed 's/^[^ ]* on //;s/ ([^)]*)$//'` &&
echo "VOLUME=${VOLUME}" &&
SetFile -c icnC "${VOLUME}/.VolumeIcon.icns" &&
SetFile -a C "${VOLUME}" &&
hdiutil detach "${DEVICE}" &&
echo "Converting DMG ..." &&
hdiutil convert -format UDZO "${OUTPUT_FOLDER}/rw/${DMG_NAME}" -o "${OUTPUT_FOLDER}/${DMG_NAME}"


# Attach the SLA
SLA_TEMPLATE="${SCRIPT_PATH}/../frontEnd/resources/SLATemplate.xml"
SLA_TEMPLATE_RW="${OUTPUT_FOLDER}/rw/SLATemplate.xml"
SLA="${SCRIPT_PATH}/../frontEnd/docs/Sighthound Video SW License Agreement.rtf"

SLA_BASE64=`base64 -i "${SLA}"`
cp "${SLA_TEMPLATE}" "${SLA_TEMPLATE_RW}" || exit 1
sed -i -e "s~SLA_ATTACHED_HERE~${SLA_BASE64}~g" "${SLA_TEMPLATE_RW}" || exit 1
hdiutil udifrez -xml "${SLA_TEMPLATE_RW}" " " "${OUTPUT_FOLDER}/${DMG_NAME}" || exit 1

rm -rf "${OUTPUT_FOLDER}/rw"


# Sign and notarize
${SCRIPT_PATH}/signMacosBinaries.sh "${OUTPUT_FOLDER}/${DMG_NAME}"
${SCRIPT_PATH}/notarizeMacosApp.sh "${OUTPUT_FOLDER}/${DMG_NAME}"