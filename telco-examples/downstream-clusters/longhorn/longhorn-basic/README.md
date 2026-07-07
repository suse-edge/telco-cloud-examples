# BMH + CAPI Multi-Node Basic Longhorn Example

This example demonstrates how to deploy a multi-node downstream cluster with basic Longhorn storage using CAPI, Metal3, and MetalLB.

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
- Basic Longhorn installation (suse-storage 1.11.1)
- Default storage settings without custom optimizations
- No custom StorageClass (uses Longhorn chart defaults)
- No encryption configured

## Files

- `bmh-cp-node1.yaml` - BareMetalHost definition for control plane node 1
- `bmh-cp-node2.yaml` - BareMetalHost definition for control plane node 2
- `bmh-cp-node3.yaml` - BareMetalHost definition for control plane node 3
- `capi-multinode-basic-longhorn.yaml` - CAPI manifest with multi-node Longhorn configuration

## Variables to replace

### In bmh-cp-node*.yaml files

For each of the 3 control plane nodes:

- `${BMC_NODE*_USERNAME}` - BMC username for each node
- `${BMC_NODE*_PASSWORD}` - BMC password for each node
- `${NODE*_MAC_BOOT}` - MAC address of the NIC on each server used to execute the PXE boot
- `${BMC_NODE*_ADDRESS}` - BMC URL for each node (e.g. redfish-virtualmedia://192.168.200.75/redfish/v1/Systems/1/)

### In capi-multinode-basic-longhorn.yaml

- `${CLUSTER_NAME}` - Name for your cluster
- `${VIP_ADDRESS}` - VIP address for the cluster endpoint (MetalLB managed)
- `${RKE2_VERSION}` - RKE2 version (e.g. v1.35.3+rke2r3)
- `${IMAGE_URL}` - URL to the EIB-generated image
- `${IMAGE_CHECKSUM_URL}` - URL to the image checksum file
- `${DP_APPS_RANCHER_SECRET}` - Base64 encoded dockerconfigjson for dp.apps.rancher.io registry

## Deployment steps

### Step 1: Generate the registry secret for dp.apps.rancher.io

You need credentials to pull Longhorn images from dp.apps.rancher.io. Generate the base64 encoded dockerconfigjson with your credentials:

```bash
REGISTRY_USER="your-username"
REGISTRY_PASS="your-password"

echo -n '{"auths":{"dp.apps.rancher.io":{"username":"'$REGISTRY_USER'","password":"'$REGISTRY_PASS'","auth":"'$(echo -n "$REGISTRY_USER:$REGISTRY_PASS" | base64)'"}}}' | base64 -w0
```

Copy the output and replace `${DP_APPS_RANCHER_SECRET}` in the capi-multinode-basic-longhorn.yaml file.

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
kubectl apply -f capi-multinode-basic-longhorn.yaml
```

## Post-deployment verification

Get cluster kubeconfig:

```bash
clusterctl get kubeconfig ${CLUSTER_NAME} > <cluster-kubeconfig>
```

Check cluster status:

```bash
kubectl get cluster ${CLUSTER_NAME}
kubectl get machines
```

Check Longhorn installation:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get pods -n longhorn-system
kubectl --kubeconfig=<cluster-kubeconfig> get storageclass
```

Verify MetalLB and VIP:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get svc kubernetes-vip -n default
kubectl --kubeconfig=<cluster-kubeconfig> get ipaddresspool -n metallb-system
```

## Notes

This is a basic multi-node example with 3 replicas for Longhorn volumes. For production deployments with encryption or CAPI in-place upgrades, use the corresponding examples.
