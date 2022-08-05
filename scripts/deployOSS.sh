CONAN_BUILD=$1
OSS_FOLDER=$2
TMP_FOLDER=/tmp
if [ $# -ge 3 ]; then
    TMP_FOLDER=$3
fi

if [ ! -d $OSS_FOLDER ]; then
    echo "${OSS_FOLDER} does not exit!"
    exit -1
fi


rm -rf $TMP_FOLDER/sv
conan install $CONAN_BUILD -if $TMP_FOLDER/sv/win -s os=Windows
if [ $? -ne 0 ]; then
    echo "Failed to install Windows version of $CONAN_BUILD"
fi
conan install $CONAN_BUILD -if $TMP_FOLDER/sv/mac -s os=Macos
if [ $? -ne 0 ]; then
    echo "Failed to install Mac version of $CONAN_BUILD"
fi

pushd $OSS_FOLDER
git clean -dqfx
popd

tar -xvzf $TMP_FOLDER/sv/mac/SV-7.0/source.tgz -C $OSS_FOLDER
for OS in mac win
do
    mkdir -p $OSS_FOLDER/$OS
    cp $TMP_FOLDER/sv/$OS/SV-7.0/tools.tgz $OSS_FOLDER/$OS/
    cp $TMP_FOLDER/sv/$OS/SV-7.0/libs.tgz $OSS_FOLDER/$OS/
done
pushd $OSS_FOLDER
git add *
git commit -m "Updating to $CONAN_BUILD"
popd