# Installation

## Requirements
- Python (version >= 3.7)
- Kubernetes (Idealy version >=1.24)
    - We provide instructions to install kubernetes with kubeadm. See [k8s.md](k8s.md) for details.
- perf (version 5.4)
- mpstat

# Set up env variable
```
echo "export MESHINSIGHT_DIR=$HOME/meshinsight" >> ~/.bashrc
source ~/.bashrc
```

# Python Dependencies
```
pip3 install -r requirements.txt
```

# BCC

BCC requires Linux 4.1 and above. See https://github.com/iovisor/bcc/blob/master/INSTALL.md for installation instructions.
```
# For Ubuntu 20.04
sudo apt update
sudo apt install -y bison build-essential cmake flex git libedit-dev   libllvm11 llvm-11-dev libclang-11-dev python zlib1g-dev libelf-dev libfl-dev python3-distutils

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
```

# Istio
Istio release page: https://github.com/istio/istio/releases/
```
curl -k -L https://istio.io/downloadIstio | sh -
# or curl -k -L https://istio.io/downloadIstio | ISTIO_VERSION=x.xx.x sh - 
cd istio-{ISTIO_VERSION}
export PATH=$PWD/bin:$PATH
istioctl x precheck
istioctl install --set profile=default -y

# turn on auto-injection
kubectl label namespace default istio-injection=enabled
# turn off auto-injection
kubectl label namespace default istio-injection-
```

# wrk and wrk2
```
sudo apt-get install luarocks -y
sudo luarocks install luasocket

cd $MESHINSIGHT_DIR/meshinsight/profiler
git clone https://github.com/wg/wrk.git
cd wrk
make -j $(nproc)

cd $MESHINSIGHT_DIR/meshinsight/profiler
git clone https://github.com/giltene/wrk2.git
cd wrk2
make -j $(nproc)
cd ..
```

# Platform Set Up
```
# Disable TurboBoost
cat /sys/devices/system/cpu/intel_pstate/no_turbo
echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo

# Disable CPU Frequency Scaling 
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Disable CPU idle state
sudo cpupower frequency-info
sudo cpupower idle-set -D 0
```