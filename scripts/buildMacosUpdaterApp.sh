#=================================================================================
# Set up variables
#=================================================================================
SCRIPT_PATH="`dirname \"$0\"`"
PROJ_ROOT="${1}"



#=================================================================================
# Build
#=================================================================================
echo "Building Updater.app ..."
UPDATER_OUT=~/tmp/.updaterBuild
rm -rf "${UPDATER_OUT}"
xcodebuild ARCHS=x86_64 -project "${PROJ_ROOT}/MacUpdater/Updater.xcodeproj" -config Release SYMROOT="${UPDATER_OUT}" || exit 1
"${SCRIPT_PATH}/signMacosBinaries.sh" "${UPDATER_OUT}/Release/Updater.app" || exit 1
tar -C "${UPDATER_OUT}/Release" -cf "${PROJ_ROOT}/installScriptApp.tar" Updater.app || exit 1