#!/bin/bash

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