# Edge clusters with dual-stack networking

## Introduction

This directory contains some sample CAPI manifest files that enable the creation of Edge clusters where the bare metal hosts, and the executing containers on top, are connected through both IPv4 and IPv6, with the following characteristics:
- multi host scenario
- DHCP autoconfiguration for IPv4
- various autoconfiguration approaches for IPv6

This implies provisioning a bare metal host with a dual-stack network configuration first, through one of the provided BareMetalHost definitions, and a properly configured Kubernetes cluster, through Cluster and RKE2ControlPlane definitions according to the desidered CNI provider and setup. Both aspects are covered in the following two sections.


## BareMetalHost (BMH) examples

The BMH definitions can be found within the `bmh-example_*.yaml` files. While the same DHCP configuration is applied for IPv4, each file provides different IPv6 configuration approaches (which may require mode specific information), as described below:

- `bmh-example_v4dhcp-v6dhcp+route.yaml` - use in environments where Router Advertisements (RAs) are not enabled in the network (or should not be used) and IPv6 should only rely on DHCP for the address and DNS servers; note that a default route must also be provided.
    Requires:
        - `${CONTROLPLANE_GATEWAY_V6}` - the IPv6 address of the gateway for the traffic matching the default route
        - `${CONTROLPLANE_INTERFACE}` - the name of the interface to be used for the egressing traffic matching the default route

- `bmh-example_v4dhcp-v6ra+dhcp.yaml` - both RAs and DHCP are enabled for autoconfiguration, resulting in stateless address and default route assignments, and DHCP provided DNS information (when not optionally provided by the RAs); this is most likely the only configuration you will ever need, as no further input is required.

- `bmh-example_v4dhcp-v6ra+dhcp_v4v6dns.yaml` - this configuration is identical to the `bmh-example_v4dhcp-v6ra+dhcp.yaml` above, with the exception of statically provided DNS servers; it can be useful in networks where only RAs are avaiable (and no DNS option configured).
     Requires:
         - `${DNS_SERVER_V4}` and/or `${DNS_SERVER_V6}` - the IP address(es) of the DNS server(s) to use, as a single or multiple entries; both IPv4 and/or IPv6 addresses can be specified

**Note**:
 * When multiple hosts are deployed, each host needs the data above to be unique and specific to it.
 * Due to limitations in [nmstate](https://nmstate.io/devel/yaml_api.html#ipv6-autoconf), it is not possible to enable SLAAC but disable DHCPv6; for this reason DHCP will always be enabled in the provided examples.
 * The network configuration will only apply to the provisioned BMH and not yet on the inspection phase of the host to gather hardware information. This is due to a bug that will force the use of DHCP and RA for IPv4 and IPv6 respectively with the default settings; a resolution is expected soon.

Once the required BMH file has been selected and refined, in order for it to work, it must also be filled with some values common to all the BMH definitions in addition to the network specific ones previously mentioned. For more information on these values or on how to enroll a Bare Metal Host, please refer to the main Edge Cluster documentation for multi host deployments [here](https://github.com/suse-edge/telco-cloud-examples/tree/main/telco-examples/edge-clusters#example-2---deploy-a-multi-node-ha-cluster-using-metal3-metallb-and-the-image-generated).


## Cluster definitions

The definition files come with any CNI plugin specific configuration that may be required and are organized as follow:

- `single-cni`:
    | Filename                                  | Primary CNI | Primary IPAM |
    |:------------------------------------------|:-----------:|:------------:|
    | `Telco-capi-v4v6-calico.yaml`             |    Calico   |    Calico    |
    | `Telco-capi-v4v6-canal.yaml`              |    Canal    |     Canal    |
    | `Telco-capi-v4v6-cilium.yaml`             |    Cilium   |    Cilium    |

    **Note**:
    * Regardless of the address management method for the secondary interface, make sure to update the network blocks within the manifest according to your operational needs.

Regardless of the selected file, it should be edited to define at least the following values:
- `${EDGE_CONTROL_PLANE_IP_V4}` - the IPv4 address to be used as the endpoint for the edge cluster (should match with the kubeapi-server endpoint)
- `${EDGE_CONTROL_PLANE_IP_V6}` - the additional IPv6 address the edge cluster is reacheable from (should match with the kubeapi-server endpoint)
- `${RKE2_VERSION}` - the RKE2 version to be installed during the provisioning by CAPI
- `http://imagecache.local:8080/eibimage-slmicro60rt.raw` - the URL where the generated EIB image can be located and downloaded during the provisioning; the checksum URL must be updated accordingly as well

It is also recommended that you change the following items:
- `Cluster.spec.clusterNetwork.pods.cidrBlocks` - a list containing the IPv4 and IPv6 networks that will be used for assigning addresses to PODs; the examples use RFC1918 and ULA ranges for IPv4 and IPv6 respectively, which may or may not be suitable for your environment
- `Cluster.spec.clusterNetwork.services.cidrBlocks` - a list containing the IPv4 and IPv6 networks that will be used for assigning addresses to Kubernetes Services; the examples use RFC1918 and ULA ranges for IPv4 and IPv6 respectively, which may or may not be suitable for your environment

**Note**:
* in a dual-stack scenario IPv4 CIDRs should always be provided as the first item of the list; this is due Kubernetes limitations.
* make sure to use Metal3 version 0.9.0 or higher on the management cluster

Note that containers will be provided with the `resolv.conf` file included in the manifest, you are invited to replace the nameservers according to your preferences or network infrastructure.

Once the file has been modified the cluster can be deployed by running:

`$ kubectl apply -f modified-v4v6-cluster.yaml`

You can then test the new Kubernetes cluster by creating a Pod or a Deployment and a dual-stack Service.

For more information on the files provided to the cluster file at RKE2 install time and related configurations, you can review the "Networking" section of the [RKE2 documentation](https://docs.rke2.io/networking/basic_network_options?CNIplugin=Canal+CNI+plugin#dual-stack-configuration).
