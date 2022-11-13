#!/bin/bash

set -ex

# Set up env variable
echo "export MESHINSIGHT_DIR=$PWD" >> ~/.bashrc
. ~/.bashrc

# Install necessary tools
sudo apt-get update
sudo apt-get install -y linux-tools-common linux-tools-generic linux-tools-`uname -r`
sudo apt-get install -y sysstat

# Python Dependencies
sudo apt install -y python3-pip
pip3 install -r requirements.txt

# Install BCC (Ubuntu 20.04)
cd $MESHINSIGHT_DIR
sudo apt update
sudo apt install -y bison build-essential cmake flex git libedit-dev   libllvm11 llvm-11-dev libclang-11-dev python zlib1g-dev libelf-dev libfl-dev python3-distutils
# Delete if installed
if [ -d "$MESHINSIGHT_DIR/bcc"];
then sudo rm -rf $MESHINSIGHT_DIR/bcc;
fi
git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake ..
make -j $(nproc)
sudo make install
cmake -DPYTHON_CMD=python3 .. # build python3 binding
pushd src/python/
make -j $(nproc)
sudo make install
popd

# Install Istio
cd $MESHINSIGHT_DIR
# Delete if installed
if [ -d "$MESHINSIGHT_DIR/istio-1.14.1"];
then sudo rm -rf $MESHINSIGHT_DIR/istio-1.14.1;
fi
curl -k -L https://istio.io/downloadIstio | ISTIO_VERSION=1.14.1 sh -
cd istio-1.14.1
sudo cp bin/istioctl /usr/local/bin
istioctl x precheck
istioctl install --set profile=default -y

# turn on auto-injection
kubectl label namespace default istio-injection=enabled
# turn off auto-injection
# kubectl label namespace default istio-injection-

# Install wrk and wrk2
sudo apt-get install luarocks -y
sudo luarocks install luasocket

cd $MESHINSIGHT_DIR/meshinsight/profiler
# Delete if installed
if [ -d "$MESHINSIGHT_DIR/meshinsight/profiler/wrk"];
then sudo rm -rf $MESHINSIGHT_DIR/meshinsight/profiler/wrk;
fi
git clone https://github.com/wg/wrk.git
cd wrk
make -j $(nproc)

cd $MESHINSIGHT_DIR/meshinsight/profiler
# Delete if installed
if [ -d "$MESHINSIGHT_DIR/meshinsight/profiler/wrk2"];
then sudo rm -rf $MESHINSIGHT_DIR/meshinsight/profiler/wrk2;
fi
git clone https://github.com/giltene/wrk2.git
cd wrk2
make -j $(nproc)
cd $MESHINSIGHT_DIR

set +ex
