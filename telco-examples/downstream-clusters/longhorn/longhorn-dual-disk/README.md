# BMH + CAPI Multi-Node Longhorn Example with a Dual-Disk Setup

This example deploys the same 3-node control-plane cluster as [`longhorn-basic`](../longhorn-basic/README.md), with a second disk per node added to Longhorn. Replicas can then be placed on both the root disk and a dedicated secondary disk (for example an NVMe SSD), which is the setup used for Longhorn performance testing.

## What's different from longhorn-basic

- **Secondary disk formatting and mounting.** A first-boot script (`/usr/local/sbin/setup-longhorn-secondary-disk.sh`, run by `setup-longhorn-secondary-disk.service`) formats `SECONDARY_DISK_DEVICE` as ext4 and mounts it at `/var/lib/longhorn-disks/longhorn-disk-1`. It formats only a device that has no filesystem and no partition table, so existing data is never overwritten. It runs on every boot, and a second run changes nothing.
- **Longhorn creates disks on labelled nodes.** The Longhorn chart sets `defaultSettings.createDefaultDiskLabeledNodes: true`. The disks themselves are defined per node in a Longhorn annotation (Step 4).

Everything else (MetalLB, endpoint copier, Longhorn 1.12.1, registry secret) is the same as in `longhorn-basic`.

## Files

- `../longhorn-basic/bmh-cp-node1.yaml` - BareMetalHost definition for control plane node 1
- `../longhorn-basic/bmh-cp-node2.yaml` - BareMetalHost definition for control plane node 2
- `../longhorn-basic/bmh-cp-node3.yaml` - BareMetalHost definition for control plane node 3
- `capi-multinode-dual-disk-longhorn.yaml` - CAPI manifest with the dual-disk changes

## Variables to replace

Use the variables from [`longhorn-basic`](../longhorn-basic/README.md), plus:

- `${SECONDARY_DISK_DEVICE}` - Device of the secondary disk on every node, for example `/dev/nvme1n1`. The same device name must be present on all three nodes; otherwise the script skips a node and its Longhorn disk is not created.

Check the device name on a node before deploying (for example with `lsblk`). Device names can change between boots; a `/dev/disk/by-id/...` path is more stable if your hardware exposes one.

## Deployment steps

### Step 1: Generate the registry secret

As in [`longhorn-basic`](../longhorn-basic/README.md), generate the base64 dockerconfigjson for `dp.apps.rancher.io` and use it for `${DP_APPS_RANCHER_SECRET}`.

### Step 2: Enroll the BareMetalHosts

Refer to [`longhorn-basic`](../longhorn-basic/README.md) for required per-node configurations.

```bash
kubectl apply -f ../longhorn-basic/bmh-cp-node1.yaml
kubectl apply -f ../longhorn-basic/bmh-cp-node2.yaml
kubectl apply -f ../longhorn-basic/bmh-cp-node3.yaml
kubectl get bmh -w
```

### Step 3: Deploy the cluster

```bash
export SECONDARY_DISK_DEVICE=/dev/nvme1n1
# ... export the other variables as in longhorn-basic ...
envsubst < capi-multinode-dual-disk-longhorn.yaml | kubectl apply -f -
```

Use the same substitution method you use for the [`longhorn-basic`](../longhorn-basic/README.md) manifest if it differs.

### Step 4: Add the Longhorn disks to each node

Once the nodes are up, label each node and give it the disk list. Replace `<node>` with each node name (`kubectl get nodes`):

```bash
KUBECONFIG=<cluster-kubeconfig>

kubectl label node <node> node.longhorn.io/create-default-disk=true

kubectl annotate node <node> --overwrite node.longhorn.io/default-disks-config='[
  {"name": "root-disk", "path": "/var/lib/longhorn", "allowScheduling": true},
  {"name": "secondary-disk-1", "path": "/var/lib/longhorn-disks/longhorn-disk-1", "allowScheduling": true}
]'
```

Do not name the root disk `default-disk-*`. The `block-storage` test suite in sv-tests removes disks with that prefix before it registers the secondary disk, so the root disk would be removed.

## Post-deployment verification

Check that the secondary disk is mounted on each node:

```bash
ssh root@<node> 'findmnt /var/lib/longhorn-disks/longhorn-disk-1 && lsblk -f'
```

Check that Longhorn sees both disks as ready and schedulable:

```bash
kubectl -n longhorn-system get nodes.longhorn.io <node> -o jsonpath='{.status.diskStatus}' | jq
```

After a volume is created, check which disks its replicas use:

```bash
kubectl -n longhorn-system get replicas.longhorn.io -o wide
```

## Notes

- If the secondary disk is missing or not mounted on a node, Longhorn reports that disk as not ready. The root disk still works, so the cluster stays usable.
- The first-boot script runs on every boot. It only mounts the disk; it does not reformat a disk that already has a filesystem or partition table.
- To run the Longhorn benchmarks in sv-tests against these nodes, see `docs/LONGHORN_SECONDARY_DISKS.md` in sv-tests.
