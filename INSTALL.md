# Installation

## Requirements
- Python (version >= 3.7)
- Kubernetes (Idealy version >=1.24)
    - We provide a script to install kubernetes via kubeadm on Ubuntu. Run `. ./utils/k8s_setup.sh`
- perf (version 5.4)
- mpstat

# Set up env variable
```
echo "export MESHINSIGHT_DIR=$PWD" >> ~/.bashrc
source ~/.bashrc
```

# Python Dependencies
```
pip3 install -r requirements.txt
```

# Install BCC

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

# Install Istio
Istio release page: https://github.com/istio/istio/releases/. MeshInsight is tested on v1.13.x and v1.14.x.
```
# Run "curl -k -L https://istio.io/downloadIstio | sh -" to get the latest release.
curl -k -L https://istio.io/downloadIstio | ISTIO_VERSION=1.14.1 sh -
cd istio-1.14.1
echo  "export PATH=$PWD/bin:$PATH" >> ~/.bashrc
source ~/.bashrc
istioctl x precheck
istioctl install --set profile=default -y

# turn on auto-injection
kubectl label namespace default istio-injection=enabled
# turn off auto-injection
kubectl label namespace default istio-injection-
```

# Install wrk and wrk2
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
cd $MESHINSIGHT_DIR
```

# Benchmarking tips (Optional)
In order to obtain stable results, you can disable the following OS feature.
```
# Disable TurboBoost
cat /sys/devices/system/cpu/intel_pstate/no_turbo
echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo

# Disable CPU Frequency Scaling 
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Disable CPU Idle State
sudo cpupower frequency-info
sudo cpupower idle-set -D 0

# Disable address space randomization 
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

# Disable hyperthreading (first check slibing list)
echo 0 | sudo tee /sys/devices/system/cpu/cpuX/online
```