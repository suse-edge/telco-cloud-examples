# Edge clusters with IPv6 networking

## Introduction

This directory contains some sample CAPI manifest files that enable the creation of Edge clusters where the bare metal hosts, and the executing containers on top, are exlcusively connected through IPv6, with the following characteristics:
- single host cluster
- statically assigned network configuration

This implies provisioning a bare metal host with an IPv6 network configuration first and a properly configured Kubernetes cluster, through Cluster and RKE2ControlPlane definitions according to the desidered CNI provider and setup. Both aspects are covered in the following two sections.


## BareMetalHost (BMH) example

A sample BMH definitions can be found within the `bmh-example.yaml` file. Before use, the manifest must be edited and the following values must be entered:

- `${CONTROLPLANE_IP}` - the IPv6 address to assign to the host
- `${CONTROLPLANE_PREFIX}` - the IPv6 prefix of the network the host IP belongs to
- `${CONTROLPLANE_GATEWAY}` - the IPv6 address of the gateway for the traffic matching the default route
- `${CONTROLPLANE_INTERFACE}` - the name of the interface to assign the address to and to use for the egressing traffic matching the default route
- `${DNS_SERVER}` - the IPv6 address(es) of the DNS server(s) to use, as a single or multiple entries


**Note**:
 * When RAs and DHCPs are available on the network segment, the above network configuration will only apply to the provisioned BMH and not yet on the inspection phase of the host to gather hardware information. This is due to a bug that will force the use of RA/DHCP with the default settings; a resolution is expected soon.

Once the required BMH file has been selected and refined, in order for it to work, it must also be filled with some values common to all the BMH definitions in addition to the network specific ones previously mentioned. For more information on these values or on how to enroll a Bare Metal Host, please refer to the main Edge Cluster documentation for single host deployments [here](https://github.com/suse-edge/telco-cloud-examples/tree/main/telco-examples/edge-clusters#example-1---deploy-a-single-node-edge-cluster-with-the-image-generated-and-telco-profiles).


## Cluster definitions

The required cluster manifests are shared with the DHCP examples, please refer to [this section](../../../dhcp/dual-stack/single-node/README.md#Cluster-definitions).

