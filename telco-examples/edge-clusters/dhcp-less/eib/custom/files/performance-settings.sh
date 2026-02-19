#!/bin/bash

# Script generate to tuning the performance of the system for running Telco Workloads
# This script is intended to be run on a worker node in a Telco Edge Cluster

if [ "$(whoami)" != "root" ]; then
        echo root required to quiten machine
        exit 127
fi

MAX_EXIT_LATENCY=1
input=$(cat /etc/tuned/cpu-partitioning-variables.conf | grep isolated_cores | head -1)
total_cores=$(grep -c ^processor /proc/cpuinfo)
cpus=$(echo "$input" | awk -F'=' '{print $2}')

expand_ranges() {
    echo "$1" | awk -v RS=',' '
    {
        if ($1 ~ /-/) {
            split($1, range, "-")
            for (i = range[1]; i <= range[2]; i++) {
                printf i (i==range[2] ? "" : " ")
            }
        } else {
            printf $1
        }
        printf " "
    }' | sed 's/ $//'
}

ISOLATED_CPUS=$(expand_ranges "$cpus")
all_cores=$(seq 0 $((total_cores-1)))
isolated_set=$(echo $ISOLATED_CPUS | tr ' ' '\n') # Convert to newline separated list
HK_CPUS=""

for core in $all_cores; do
    if ! echo "$isolated_set" | grep -q "^$core$"; then
        HK_CPUS+="$core "
    fi
done

HK_CPUS=$(echo "$HK_CPUS" | sed 's/ $//')

# Helper variables for comma-separated lists
HK_CPUS_LIST=$(echo $HK_CPUS | tr ' ' ',')
ISOLATED_CPUS_LIST=$(echo $ISOLATED_CPUS | tr ' ' ',')

set_cpufreq_performance() {
	echo "=== Configure: CpuFreq performance ==="
	cpupower frequency-set -g performance | grep -v "Setting cpu:"
	cpupower set -b 0
}

unset_timer_migration() {
	echo Configure: Disable Timer migration
	sysctl kernel.timer_migration=0
}

migrate_kdaemons_hk() {
	echo "=== Configure: Migrate kthreads to HK ==="
	for NODE in `ls -1 -d /sys/devices/system/node/node* | sed -e 's/.*node//'`; do
		for KTHREAD in kswapd$NODE kcompactd$NODE ; do
			PID_KTHREAD=`pidof $KTHREAD`
			[ "$PID_KTHREAD" = "" ] && PID_KTHREAD=`pidof -w $KTHREAD`
			if [ "$PID_KTHREAD" = "" ]; then
				echo "WARNING: Unable to identify PID of $KTHREAD"
				continue
			fi
			taskset -pc $HK_CPUS_LIST $PID_KTHREAD
		done
	done
}

set_isolatecpu_latency() {
	echo "=== Configure: IsolCpus latency requirements ==="
	cat /proc/cmdline  | tr ' ' '\n' | grep -q ^idle=poll
	if [ $? -eq 0 ]; then
		echo "WARNING: Using idle=poll as a kernel paramter makes per-cpu pm qos redundant"
		return
	fi

	for CPU in $ISOLATED_CPUS; do
		SYSFS_PARAM="/sys/devices/system/cpu/cpu$CPU/power/pm_qos_resume_latency_us"
		if [ ! -e $SYSFS_PARAM ]; then
			echo "WARNING: Unable to set PM QOS max latency for CPU $CPU\n"
			continue
		fi
		echo $MAX_EXIT_LATENCY > $SYSFS_PARAM
		echo "=== Set PM QOS maximum resume latency on CPU $CPU to ${MAX_EXIT_LATENCY}us ==="
	done
}

delay_vmstat_updates() {
	echo "=== Configure: Delay vmstat updates ==="
	sysctl -w vm.stat_interval=300
}

fix_kernel_isolation() {
	echo "=== Stop IRQ Balance ==="
	systemctl stop irqbalance 2>/dev/null

	echo "=== Move Interrupts (IRQs) to HK ($HK_CPUS_LIST) ==="
	for irq_dir in /proc/irq/*; do
		[ -d "$irq_dir" ] || continue
		# Avoid moving IRQ 0 (timer) or 2 (cascade), they are immovable
		irq_num=$(basename $irq_dir)
		if [ "$irq_num" -gt 2 ]; then
			echo "$HK_CPUS_LIST" > "$irq_dir/smp_affinity_list" 2>/dev/null
		fi
	done

	echo "=== Move RCU and Kernel Threads to HK ==="
	# Adding ktimersoftd which usually generates latency
	for thread in "rcuo" "ksoftirqd" "ktimersoftd"; do
		pgrep -f "$thread" | while read -r pid; do
			taskset -pc $HK_CPUS_LIST $pid >/dev/null 2>&1
		done
	done

	echo "=== Memory Optimization ==="
	if command -v sync >/dev/null 2>&1; then
		sync
	fi
	echo 3 > /proc/sys/vm/drop_caches
	# Prevent the kernel from using isolated cores for "dirty writeback"
    if [ -f /sys/bus/workqueue/devices/writeback/cpumask ]; then
	    echo "$HK_CPUS_LIST" > /sys/bus/workqueue/devices/writeback/cpumask 2>/dev/null
    fi
}

move_tasks() {
	echo "=== Moving unbound processes from isolated CPUs ($ISOLATED_CPUS_LIST) to housekeeping CPUs ($HK_CPUS_LIST) ==="

	# Iterate over all user processes (avoiding errors with kernel threads)
	for pid in $(ps -e -o pid=); do
		if [ ! -d "/proc/$pid" ] || [ -z "$(ls /proc/$pid/task 2>/dev/null)" ]; then
			continue
		fi

		affinity=$(taskset -pc "$pid" 2>/dev/null | awk -F: '{print $2}' | tr -d ' ')

		[ -z "$affinity" ] && continue

		should_move=false
		affinity_expanded=$(expand_ranges "$affinity")
        
        if echo "$affinity_expanded" | tr ' ' '\n' | grep -q -F -w -f <(echo "$isolated_set"); then
            should_move=true
        fi
		
		if [ "$should_move" = true ]; then
			if taskset -pc "$HK_CPUS_LIST" "$pid" >/dev/null 2>&1; then
				name=$(ps -p "$pid" -o comm=)
				echo "[MOVED] PID $pid ($name) -> $HK_CPUS_LIST"
			fi
		fi
	done

	echo "=== Process completed. CPUs $ISOLATED_CPUS_LIST are available for RT loads ==="
}

set_cpufreq_performance
unset_timer_migration
migrate_kdaemons_hk
set_isolatecpu_latency
delay_vmstat_updates
fix_kernel_isolation
move_tasks
