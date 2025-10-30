# Release Manifest Version Updater

This script updates Helm chart and Kubernetes versions in YAML files based on a SUSE Edge release manifest extracted from a container image.

## Requirements

- Python 3.x
- pyyaml library (pip install pyyaml)
- podman installed and configured to pull SUSE Edge images

## Usage

```bash
./generator.py <version> [--root <path>] [--registry <internal|public>]
```

where:

- `<version>`: Release version in X.Y.Z format (e.g., 3.3.1).
- `--root`: Optional. Root directory to recursively scan for YAML files. Defaults to ../.
- `--registry`: Registry type to pull the release manifest from: 'internal' or 'public' where internal uses the internal registry and public uses the public registry. Defaults to 'public'.


## Example
Update YAML files using release manifest from version 3.3.1. By default, it will scan the parent directory for YAML files assuming you are running the script from within a subdirectory of the repository.:

```bash 
chomd +x generator.py
./generator.py 3.3.1
```

Scan a specific directory for YAML files:

```bash
./generator.py 3.3.1 --root ./my-yamls
```


## Notes

- The EIB definition file `eib.yaml` is used to be replaced with the new version. To avoid issues, the helm charts description should start with `- name: <helm-chart-name>` and the version shouldn't be the key in the array structure:

```yaml 
kubernetes:
  version: v1.32.4+rke2r1
  helm:
    charts:
      - name: cert-manager
        repositoryName: jetstack
        version: 1.15.3
        targetNamespace: cert-manager
        valuesFile: certmanager.yaml
        createNamespace: true
        installationNamespace: kube-system
      - version: 1.9.2
        name: suse-storage
        repositoryName: rancher-application-collection
        targetNamespace: longhorn-system
        createNamespace: true
        installationNamespace: kube-system
```
First element will be replaced properly, but the second one will not be replaced as it doesn't have the `name` key at the first level of the array.