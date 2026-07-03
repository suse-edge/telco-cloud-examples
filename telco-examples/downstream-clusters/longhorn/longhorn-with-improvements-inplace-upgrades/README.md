# BMH + CAPI Multi-Node Longhorn with In-Place Upgrade Example

This example demonstrates how to deploy a multi-node downstream cluster with Longhorn storage optimized for CAPI in-place upgrades using Metal3 nodeReuse, MetalLB, and Endpoint Copier.

## Prerequisites

- Management cluster deployed and running
- 3 BareMetalHosts available for control plane nodes
- Network connectivity configured
- VIP address reserved for the cluster endpoint

## What's included

This example deploys:

- 3 control plane nodes with HA configuration
- MetalLB for VIP management
- Endpoint Copier Operator for endpoint synchronization
- Longhorn installation (suse-storage 1.11.1)
- StorageClass with staleReplicaTimeout optimized for upgrades
- Critical settings for CAPI in-place upgrades (nodeReuse=true)
- Settings to prevent PDB blocking during node drain
- No encryption configured (for encryption, use bmh-capi-encryption example)

## Files

- `bmh-cp-node1.yaml` - BareMetalHost definition for control plane node 1
- `bmh-cp-node2.yaml` - BareMetalHost definition for control plane node 2
- `bmh-cp-node3.yaml` - BareMetalHost definition for control plane node 3
- `capi-multinode-inplace-upgrade.yaml` - CAPI manifest with Longhorn in-place upgrade optimizations

## Variables to replace

### In bmh-cp-node*.yaml files

For each of the 3 control plane nodes:

- `${BMC_NODE*_USERNAME}` - BMC username for each node
- `${BMC_NODE*_PASSWORD}` - BMC password for each node
- `${BMC_NODE*_MAC}` - MAC address of each server
- `${BMC_NODE*_ADDRESS}` - BMC URL for each node (e.g. redfish-virtualmedia://192.168.200.75/redfish/v1/Systems/1/)

### In capi-multinode-inplace-upgrade.yaml

- `${CLUSTER_NAME}` - Name for your cluster
- `${VIP_ADDRESS}` - VIP address for the cluster endpoint (MetalLB managed)
- `${RKE2_VERSION}` - RKE2 version (e.g. v1.35.3+rke2r3)
- `${IMAGE_URL}` - URL to the EIB-generated image
- `${IMAGE_CHECKSUM_URL}` - URL to the image checksum file
- `${DP_APPS_RANCHER_SECRET}` - Base64 encoded dockerconfigjson for dp.apps.rancher.io registry

## CAPI In-Place Upgrade Settings

This example includes critical configuration for CAPI in-place upgrades where nodes reboot but keep their data:

### staleReplicaTimeout: "60"

Wait 60 minutes before cleaning up stale replicas during node downtime. The default 30 minutes is too short for some upgrade scenarios. This prevents premature replica rebuilds when nodes return quickly.

Without this setting, Longhorn may mark replicas as stale and start unnecessary rebuilds during normal upgrade operations, wasting time and resources.

### nodeDrainPolicy: "always-allow"

Allow node drain even with last healthy replica. Required for CAPI rolling upgrades to proceed without manual intervention. Safe for nodeReuse because the node returns with the same data.

### replicaReplenishmentWaitInterval: 300

Wait 5 minutes before creating new replicas during node reboots. Prevents unnecessary replica creation when nodes return quickly from in-place upgrades.

## Deployment steps

### Step 1: Generate the registry secret for dp.apps.rancher.io

You need credentials to pull Longhorn images from dp.apps.rancher.io. Generate the base64 encoded dockerconfigjson with your credentials:

```bash
REGISTRY_USER="your-username"
REGISTRY_PASS="your-password"

echo -n '{"auths":{"dp.apps.rancher.io":{"username":"'$REGISTRY_USER'","password":"'$REGISTRY_PASS'","auth":"'$(echo -n "$REGISTRY_USER:$REGISTRY_PASS" | base64)'"}}}' | base64 -w0
```

Copy the output and replace `${DP_APPS_RANCHER_SECRET}` in the capi-multinode-inplace-upgrade.yaml file.

### Step 2: Enroll the BareMetalHosts

```bash
kubectl apply -f bmh-cp-node1.yaml
kubectl apply -f bmh-cp-node2.yaml
kubectl apply -f bmh-cp-node3.yaml
```

Wait for all hosts to become available:

```bash
kubectl get bmh -w
```

### Step 3: Deploy the cluster

```bash
kubectl apply -f capi-multinode-inplace-upgrade.yaml
```

## Post-deployment verification

Check cluster status:

```bash
kubectl get cluster ${CLUSTER_NAME}
kubectl get machines
```

Check Longhorn installation and configuration:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get pods -n longhorn-system
kubectl --kubeconfig=<cluster-kubeconfig> get storageclass
```

Verify settings:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get settings.longhorn.io -n longhorn-system node-drain-policy -o jsonpath='{.value}'
kubectl --kubeconfig=<cluster-kubeconfig> get settings.longhorn.io -n longhorn-system replica-replenishment-wait-interval -o jsonpath='{.value}'
kubectl --kubeconfig=<cluster-kubeconfig> get storageclass longhorn -o jsonpath='{.parameters.staleReplicaTimeout}'
```

Verify MetalLB and VIP:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get svc kubernetes-vip -n default
kubectl --kubeconfig=<cluster-kubeconfig> get ipaddresspool -n metallb-system
```

## Performing CAPI In-Place Upgrades

To upgrade the cluster:

1. Update the RKE2 version in the manifest:

```bash
kubectl patch rke2controlplane ${CLUSTER_NAME} --type merge -p '{"spec":{"version":"v1.35.4+rke2r1"}}'
```

2. Monitor the upgrade:

```bash
kubectl get machines -w
kubectl get bmh -w
```

The upgrade will proceed automatically with Longhorn handling replica management according to the optimized settings. Each node will reboot one at a time, and Longhorn will wait for the node to return before rebuilding replicas.

## References

For detailed technical information about these settings:

- [Longhorn Issue 8362](https://github.com/longhorn/longhorn/issues/8362) - CAPI Rolling Upgrade Investigation
- [Longhorn Issue 2639](https://github.com/longhorn/longhorn/issues/2639) - PDB blocking node drain
- [Metal3 Node Reuse Documentation](https://book.metal3.io/capm3/node_reuse)

