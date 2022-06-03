set -ex

which python3 > /tmp/python3path

make clean
echo "############################################################"
python3 configure.py $1 $2
echo "############################################################"
make all P4PROG=$1.p4