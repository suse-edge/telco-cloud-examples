# BMH + CAPI Multi-Node Longhorn with Encryption Example

This example demonstrates how to deploy a multi-node downstream cluster with Longhorn encrypted storage using CAPI, Metal3, and MetalLB.

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
- Encryption secret with LUKS/AES-256 configuration
- Encrypted StorageClass as default
- Minimal required settings for encrypted volumes

## Files

- `bmh-cp-node1.yaml` - BareMetalHost definition for control plane node 1
- `bmh-cp-node2.yaml` - BareMetalHost definition for control plane node 2
- `bmh-cp-node3.yaml` - BareMetalHost definition for control plane node 3
- `capi-multinode-encryption.yaml` - CAPI manifest with multi-node Longhorn encryption configuration

## Variables to replace

### In bmh-cp-node*.yaml files

For each of the 3 control plane nodes:

- `${BMC_NODE*_USERNAME}` - BMC username for each node
- `${BMC_NODE*_PASSWORD}` - BMC password for each node
- `${BMC_NODE*_MAC}` - MAC address of each server
- `${BMC_NODE*_ADDRESS}` - BMC URL for each node (e.g. redfish-virtualmedia://192.168.200.75/redfish/v1/Systems/1/)

### In capi-multinode-encryption.yaml

- `${CLUSTER_NAME}` - Name for your cluster
- `${VIP_ADDRESS}` - VIP address for the cluster endpoint (MetalLB managed)
- `${RKE2_VERSION}` - RKE2 version (e.g. v1.35.3+rke2r3)
- `${IMAGE_URL}` - URL to the EIB-generated image
- `${IMAGE_CHECKSUM_URL}` - URL to the image checksum file
- `${DP_APPS_RANCHER_SECRET}` - Base64 encoded dockerconfigjson for dp.apps.rancher.io registry
- `${ENCRYPTION_KEY}` - Base64 encryption key (generate with: openssl rand -base64 32)

## Deployment steps

### Step 1: Generate the registry secret for dp.apps.rancher.io

You need credentials to pull Longhorn images from dp.apps.rancher.io. Generate the base64 encoded dockerconfigjson with your credentials:

```bash
REGISTRY_USER="your-username"
REGISTRY_PASS="your-password"

echo -n '{"auths":{"dp.apps.rancher.io":{"username":"'$REGISTRY_USER'","password":"'$REGISTRY_PASS'","auth":"'$(echo -n "$REGISTRY_USER:$REGISTRY_PASS" | base64)'"}}}' | base64 -w0
```

Copy the output and replace `${DP_APPS_RANCHER_SECRET}` in the capi-multinode-encryption.yaml file.

### Step 2: Generate encryption key

```bash
openssl rand -base64 32
```

Copy the output and replace `${ENCRYPTION_KEY}` in capi-multinode-encryption.yaml.

### Step 3: Enroll the BareMetalHosts

```bash
kubectl apply -f bmh-cp-node1.yaml
kubectl apply -f bmh-cp-node2.yaml
kubectl apply -f bmh-cp-node3.yaml
```

Wait for all hosts to become available:

```bash
kubectl get bmh -w
```

### Step 4: Deploy the cluster

```bash
kubectl apply -f capi-multinode-encryption.yaml
```

## Post-deployment verification

Check cluster status:

```bash
kubectl get cluster ${CLUSTER_NAME}
kubectl get machines
```

Check Longhorn installation and encryption:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get pods -n longhorn-system
kubectl --kubeconfig=<cluster-kubeconfig> get storageclass
kubectl --kubeconfig=<cluster-kubeconfig> get secret longhorn-crypto -n longhorn-system
```

Verify encrypted volume creation:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get volumes.longhorn.io -n longhorn-system -o json | jq '.items[] | select(.spec.encrypted == true)'
```

Verify MetalLB and VIP:

```bash
kubectl --kubeconfig=<cluster-kubeconfig> get svc kubernetes-vip -n default
kubectl --kubeconfig=<cluster-kubeconfig> get ipaddresspool -n metallb-system
```

## Security notes

- Never commit the encryption key to version control
- Store the encryption key securely (password manager, vault)
- Without the encryption key, encrypted volumes are permanently unrecoverable
- Consider using different keys for different clusters

## Notes

This example provides basic encryption configuration with 3 replicas for HA. For production deployments with CAPI in-place upgrades, use the bmh-capi-encryption-inplace-upgrade example.
