LOCATION=$1
declare -a LIBS_TO_RENAME=("shcv_core" "shcv_imgproc" "shcv_threading" "pipeline" "c3")
declare -a LIBS_TO_EDIT=("sentry" "sentry_pipelinePasses")

for x in "${LIBS_TO_RENAME[@]}"
do
    OLDNAME=${LOCATION}/lib${x}.dylib
    NEWNAME=${LOCATION}/lib${x}_legacy.dylib
    echo "Moving ${OLDNAME} to ${NEWNAME}"
    mv ${OLDNAME} ${NEWNAME}
    echo "Changing ID to @rpath/lib${x}_legacy.dylib"
    install_name_tool -id "@rpath/lib${x}_legacy.dylib" ${NEWNAME}
    LIBS_TO_EDIT+=("${x}_legacy")
done

for x in "${LIBS_TO_EDIT[@]}"
do
    for y in "${LIBS_TO_RENAME[@]}"
    do
        echo "Changing reference to lib${y} in lib${x}"
        install_name_tool -change "@rpath/lib${y}.dylib" "@rpath/lib${y}_legacy.dylib" ${LOCATION}/lib${x}.dylib
    done
done