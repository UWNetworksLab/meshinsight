#!/bin/bash

# Set default value for the argument
valid_proxy=("istio" "linkerd")
proxy="istio"

# Parse command line options
while getopts ":p:" opt; do
  case $opt in
    p)
      proxy="$OPTARG"
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done

case $proxy in
  "${valid_proxy[@]}")
    echo "Option '$proxy' is valid"
    ;;
  *)
    echo "Invalid option: $proxy"
    echo "Valid options are: ${valid_options[*]}"
    exit 1
    ;;
esac

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

version=$(lsb_release -r | awk '{print $2}')
if [ $(echo "$version == 22.04" | bc) -eq 1 ]; then
  # Execute command for Ubuntu 22.04
  sudo apt install -y bison build-essential cmake flex git libedit-dev libllvm14 llvm-14-dev libclang-14-dev python3 zlib1g-dev libelf-dev libfl-dev python3-distutils
else
  # Execute command for Ubuntu 20.04
  sudo apt install -y bison build-essential cmake flex git libedit-dev libllvm11 llvm-11-dev libclang-11-dev python zlib1g-dev libelf-dev libfl-dev python3-distutils
fi

# Delete if installed
if [ -d "$MESHINSIGHT_DIR/bcc" ];
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

# Install Istio or Linkerd
if [ "$1" == "istio" ]; then
  cd $MESHINSIGHT_DIR
  # Delete if installed
  if [ -d "$MESHINSIGHT_DIR/istio-1.14.1" ];
  then sudo rm -rf $MESHINSIGHT_DIR/istio-1.14.1;
  fi
  curl -k -L https://istio.io/downloadIstio | ISTIO_VERSION=1.14.1 sh -
  cd istio-1.14.1
  sudo cp bin/istioctl /usr/local/bin
  istioctl x precheck
  istioctl install --set profile=default -y
else
  cd $MESHINSIGHT_DIR
  curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | sh
  echo "export PATH=$PATH:~/.linkerd2/bin" > ~/.bashrc
  source ~/.bashrc
  linkerd version
  linkerd check --pre
  linkerd install --crds | kubectl apply -f -
  linkerd install | kubectl apply -f -
  linkerd check
fi

# turn on auto-injection
kubectl label namespace default istio-injection=enabled --overwrite

# Install wrk and wrk2
sudo apt-get install luarocks -y
sudo luarocks install luasocket

cd $MESHINSIGHT_DIR/meshinsight/profiler
# Delete if installed
if [ -d "$MESHINSIGHT_DIR/meshinsight/profiler/wrk" ];
then sudo rm -rf $MESHINSIGHT_DIR/meshinsight/profiler/wrk;
fi
git clone https://github.com/wg/wrk.git
cd wrk
make -j $(nproc)

cd $MESHINSIGHT_DIR/meshinsight/profiler
# Delete if installed
if [ -d "$MESHINSIGHT_DIR/meshinsight/profiler/wrk2" ];
then sudo rm -rf $MESHINSIGHT_DIR/meshinsight/profiler/wrk2;
fi
git clone https://github.com/giltene/wrk2.git
cd wrk2
make -j $(nproc)
cd $MESHINSIGHT_DIR

set +ex
