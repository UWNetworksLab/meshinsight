VERSION=5.4.156
wget -O linux.tar.gz wget https://mirrors.edge.kernel.org/pub/linux/kernel/v5.x//linux-$VERSION.tar.gz

sudo apt-get update
sudo apt-get install libiberty-dev binutils-dev

mkdir -p linux
tar -xf linux.tar.gz -C linux

cd linux/linux-$VERSION

#sed -i '47,50d' ./tools/perf/jvmti/jvmti_agent.c

#patch -p1 < ../../perf-patch-5.4-conv.patch
#patch -p1 < ../../binutils.patch

#PYTHON=python3 make -C tools/perf install

cd tools/perf/
make clean && make -j 8

cd ../../../../

mkdir -p perf/
cp -r linux/linux-$VERSION/tools/perf/* perf/
rm -r linux/
rm -r linux.tar.gz
