idpath="${1}"
shift
rpath="${1}"
shift

while test $# -gt 0
do
    filepath="${1}"
    filename=`basename "${1}"`
    if [ -h "${filepath}" ]; then
        echo "Skipping $filename"
    else
        echo "Processing $filename"
        install_name_tool -add_rpath "${rpath}" "${filepath}"
        install_name_tool -id "${idpath}/${filename}" "${filepath}"
    fi
    shift
done