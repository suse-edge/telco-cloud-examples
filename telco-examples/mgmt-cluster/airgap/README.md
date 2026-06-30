
# Management Cluster in a single-node setup (air-gap scenario)

This is an example of using Edge Image Builder (EIB) to generate a management cluster iso image for SUSE Telco Cloud in an air-gap scenario. The management cluster will contain the following components:
- SUSE Linux Micro 6.2 Kernel (SL Micro 6.2)
- RKE2
- CNI plugins (e.g. Multus, Cilium)
- Rancher Prime
- Neuvector
- SUSE Storage (Longhorn)
- SUSE Private Registry
- Static IPs or DHCP network configuration
- Metal3 and the CAPI provider (if you want to add support for aarch64 architecture, the changes will be explained in `Optional modifications` section of this document)
- Metallb is only needed if you want to use the suse private registry feature included in the examples. 

You need to modify the following values in the `mgmt-cluster-airgap.yaml` file:

- `${ROOT_PASSWORD}` - The root password for the management cluster. This could be generated using `openssl passwd -6 PASSWORD` and replacing PASSWORD with the desired password, and then replacing the value in the `mgmt-cluster-airgap.yaml` file. The final rancher password will be configured based on the file `custom/files/basic-setup.sh`.
- `${SCC_REGISTRATION_CODE}` - The registration code for the SUSE Customer Center for the SLE Micro product. This could be obtained from the SUSE Customer Center and replacing the value in the `mgmt-cluster-airgap.yaml` file.
- `${PRIVATE_REGISTRY_USERNAME}` - The username retrieved from [SUSE Private Registry official docs](https://documentation.suse.com/cloudnative/suse-private-registry/html/private-registry/pr-deployment.html#pr-deployment-kube-secrets)
- `${PRIVATE_REGISTRY_PASSWORD}` - The password retrieved from [SUSE Private Registry official docs](https://documentation.suse.com/cloudnative/suse-private-registry/html/private-registry/pr-deployment.html#pr-deployment-kube-secrets)

> **_IMPORTANT:_**  
> Keep in mind that the `embeddedArtifactRegistry` is a set of images based on a specific helm repositories version (rancher, metal3 and rke2-capi-provider). If you want to use a different version of the helm repositories, you need to modify the `embeddedArtifactRegistry` values in the `mgmt-cluster-airgap.yaml` file.

You need to modify the following values in the `network/mgmt-cluster-network.yaml` file :

- `${MGMT_GATEWAY}` - This is the gateway IP of your management cluster network.
- `${MGMT_DNS}` - This is the DNS IP of your management cluster network.
- `${MGMT_CLUSTER_IP}` - This is the static IP of your management cluster single node.
- `${MGMT_MAC}` - This is the MAC address of your management cluster node.

You need to modify the `${MGMT_CLUSTER_IP}` with the Node IP in the following files:

- `kubernetes/helm/values/metal3.yaml`

## Rancher Hostname Configuration in Air-Gapped Environments

This example uses **Option 1 (Recommended)**: Configure your internal DNS server to resolve the Rancher hostname.

In `kubernetes/helm/values/rancher.yaml`, replace `your-domain.internal` with your actual internal domain:

```yaml
hostname: rancher.your-domain.internal
```

Make sure your DNS server resolves `rancher.your-domain.internal` to the appropriate IP address.

### Alternative Option 2: Static /etc/hosts Injection

If internal DNS is not available, you can inject static entries via EIB by creating `eib/os-files/etc/hosts`:

```shell
# Static DNS resolution for Rancher in air-gapped environment
${INGRESS_VIP} rancher-${INGRESS_VIP}.sslip.io
```

Then update `kubernetes/helm/values/rancher.yaml`:

```yaml
hostname: rancher-${INGRESS_VIP}.sslip.io
```

> **_IMPORTANT:_**  
> With Option 2, the `/etc/hosts` file will need to be present on any system that needs to access the Rancher UI, not just the management cluster nodes.

You need to modify the `${MGMT_CLUSTER_REGISTRY_IP}` with a reserved static IP for the SUSE Private Registry in the following file:

- `kubernetes/manifests/metallb-registry.yaml`
- `kubernetes/helm/values/privateregistry.yaml`

You need to modify the `${DOCKER_CONFIG_JSON_BASE64}`, `${TLS_CRT_BASE64}` and `${TLS_KEY_BASE64}` in the following file:

- `kubernetes/manifests/suse-private-registry-creds.yaml` 

To modify the docker config json (base64) properly you can do the following:

```
# ${DOCKER_CONFIG_JSON_BASE64} CONTENT
echo -n "{"auths": {"192.168.x.x": {"username": "xxxxxxx", "password": "yyyyyyy", "auth": "zzzzzzzzzzzzzz"}}}" | base64
```

where the IP is the same we configured before `${MGMT_CLUSTER_REGISTRY_IP}`, and the `username`, `password` and `auth` can be retrieved from [SUSE Private Registry official docs](https://documentation.suse.com/cloudnative/suse-private-registry/html/private-registry/pr-deployment.html#pr-deployment-kube-secrets)

To modify the tls_crt_base64 and tls_key_base64 variables you can create your own ones doing:

```
# Generate a self-signed certificate and key
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes

# Convert them to base64 for the suse-private-registry-creds.yaml file
cat cert.pem | base64 -w 0
cat key.pem | base64 -w 0
```

> **_IMPORTANT:_**  
> Note that the `custom/scripts/99-register.sh` file is not needed in this scenario.

You need to modify the following folder:

- `base-images` - To include the raw image generated by Kiwi as:

```
mkdir output
sudo podman run --privileged -v /etc/zypp/repos.d:/micro-sdk/repos/ -v $(pwd)/output:/tmp/output -it registry.suse.com/edge/3.6/kiwi-builder:10.2.29.1 build-image -p Default-SelfInstall
```

The resulting iso image needs to be copied over to the `base-image` folder and used as a reference in the `eib/telco-downstream-cluster.yaml` file:

``` 
cp $(pwd)/output/*.iso base-images/
```

> **_Note:_** For more information about this process you can follow the [full guide instructions in official docs](https://documentation.suse.com/suse-edge/3.6/html/edge/guides-kiwi-builder-images.html)

## Optional modifications

### Add certificates to use HTTPS server to provide images using TLS

This is an optional step to add certificates to the management cluster to provide images using HTTPS Server (Helm Chart metal3 Version >= 0.7.1)

1. Modify the `kubernetes/helm/values/metal3.yaml` file to set to true the following value in the global section:

```yaml
global:
  additionalTrustedCAs: true
```

2. If you are deploying a mgmt-cluster from scratch using EIB, then add the secret to the manifests folder `kubernetes/manifests/metal3-cacert-secret.yaml` to automate the creation of the secret in the management cluster:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: metal3-system
---
apiVersion: v1
kind: Secret
metadata:
  name: tls-ca-additional
  namespace: metal3-system
type: Opaque
data:
  ca-additional.crt: {{ additional_ca_cert | b64encode }}
```

3. Alternatively, you can use the following command to create the secret manually:

```bash
kubectl -n meta3-system create secret generic tls-ca-additional --from-file=ca-additional.crt=./ca-additional.crt
```

where `ca-additional.crt` is the certificate file that you want to use to provide images using HTTPS.

## Building the Management Cluster Image using EIB

1. Clone this repo and navigate to the `telco-examples/mgmt-cluster/airgap/eib` directory.

```bash 
$ git clone https://github.com/suse-edge/telco-cloud-examples.git
$ cd telco-examples/mgmt-cluster/airgap/eib
```

2. Modify the files described above.

3. Run the image building process.

```bash
$ sudo podman run --rm --privileged -it -v $PWD:/eib \
registry.suse.com/edge/3.6/edge-image-builder:1.3.3.1 \
build --definition-file mgmt-cluster-airgap.yaml
```

## Deploy the Management Cluster

Once the build process is finished, you will find the modified ISO image in the `eib` directory. You can then proceed to provision a VM or a baremetal server with it.
