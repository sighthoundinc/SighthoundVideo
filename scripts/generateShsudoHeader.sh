DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo "Current script dir ${DIR}"
export SHLAUNCH_REV=`${DIR}/getRevision.sh`
echo "Rev is ${SHLAUNCH_REV}"
echo "#define SHLAUNCH_BUILD \"r${SHLAUNCH_REV}\"" > $1