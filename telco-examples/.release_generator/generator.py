#!/usr/bin/env python3
"""
SUSE Edge Release Generator
---------------------------

This script extracts release information from a container image,
updates Kubernetes and Helm chart versions in YAML files,
and replaces image references based on the extracted data.

Usage:
    python generator.py <version> [--root <path>] [--registry <internal|public>]

Arguments:
    version: Release version in X.Y.Z format (e.g., 3.3.1)
    root: Root path to recursively scan for .yaml files (default: "../")
    registry: Registry type to pull the release manifest from: 'internal' or 'public'
              where 'internal' uses the internal registry and 'public' uses the public registry.

Requirements:
    - Python 3.x
    - PyYAML
    - Podman installed and configured

Created by SUSE Edge Team
"""
import yaml
import os
import subprocess
import sys
import re
import argparse
import copy


class IndentedDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(IndentedDumper, self).increase_indent(flow, False)


def get_release_files(image: str) -> tuple:
    """
    Extract release_manifest.yaml & release_images.yaml from container
    :param image:
    :return: tuple of (release_manifest, release_images)
    """
    file_paths = ["/release_manifest.yaml", "/release_images.yaml"]
    contents = {}

    try:
        subprocess.run(["podman", "pull", image], check=True)

        for path in file_paths:
            result = subprocess.run(
                ["podman", "run", "--rm", image, "cat", path],
                check=True,
                stdout=subprocess.PIPE,
                universal_newlines=True
            )
            contents[path] = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error extracting files from image: {e}", file=sys.stderr)
        sys.exit(1)

    manifest = yaml.safe_load(contents["/release_manifest.yaml"])
    images = yaml.safe_load(contents["/release_images.yaml"])
    return manifest, images

def build_release_versions(manifest):
    """
    Build release version map and image map
    :param manifest: manifest dictionary from release manifest
    :return:
    """
    versions = {}
    helm_charts = manifest.get("spec", {}).get("components", {}).get("workloads", {}).get("helm", [])
    for chart in helm_charts:
        versions[chart["releaseName"]] = chart["version"]
        for dep in chart.get("dependencyCharts", []):
            versions[dep["releaseName"]] = dep["version"]
        for addon in chart.get("addonCharts", []):
            versions[addon["releaseName"]] = addon["version"]
    k8s_version = manifest.get("spec", {}).get("components", {}).get("kubernetes", {}).get("rke2", {}).get("version")
    versions["__k8s_version__"] = k8s_version
    os_version = manifest.get("spec", {}).get("components", {}).get("operatingSystem", {}).get("version")
    versions["__os_version__"] = os_version
    return versions

def build_image_map(images_yaml):
    image_map = {}
    for entry in images_yaml.get("images", []):
        full_image = entry["name"]
        match = re.match(r"(.*/)?([^:/]+)(:.*)?$", full_image)
        if match:
            image_name = match.group(2)
            image_map[image_name] = full_image
    return image_map

def update_versions_in_mgmt_file(doc, release_versions, image_map):
    """
    Update Kubernetes and Helm chart versions in the management file
    :param doc: YAML document to update
    :param release_versions: release versions dictionary
    :param image_map: image map dictionary
    :return:
    """
    if "kubernetes" in doc and "version" in doc["kubernetes"]:
        doc["kubernetes"]["version"] = release_versions.get("__k8s_version__", doc["kubernetes"]["version"])

    charts = doc.get("kubernetes", {}).get("helm", {}).get("charts", [])
    for chart in charts:
        name = chart.get("name")
        if name in release_versions:
            chart["version"] = release_versions[name]

    # Walk through any keys and try to replace image values
    def replace_images(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    match = re.match(r".*/([^:/]+):[^:]+", v)
                    if match:
                        image_name = match.group(1)
                        if image_name in image_map:
                            obj[k] = image_map[image_name]
                else:
                    replace_images(v)
        elif isinstance(obj, list):
            for item in obj:
                replace_images(item)

    replace_images(doc)

def update_versions_in_readme(doc_path, release_versions, image_map):
    with open(doc_path, "r") as f:
        doc = f.read()

    image_ref_regex=re.compile(
        r"\b(?P<full_name>[a-z0-9]+(?:(?:\.|_|__|-+)[a-z0-9]+)*(?:\/(?P<name>[a-z0-9]+(?:(?:\.|_|__|-+)[a-z0-9]+)*))+)"
        r":(?P<tag>[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127})\b"
    )
    chart_ref_regex=re.compile(
        r"\b(?P<full_name>[a-z0-9]+(?:(?:\.|_|__|-+)[a-z0-9]+)*(?:\/charts/(?P<name>[a-z0-9]+(?:(?:\.|_|__|-+)[a-z0-9]+)*))+)"
        r":(?P<tag>[a-zA-Z0-9_][a-zA-Z0-9._+-]{0,127})\b"
    )
    sl_micro_regex=re.compile(r"((?:SUSE Linux|SL) Micro) \d+\.\d+")

    def replace_image(match):
        name = match.group("name")
        if name in image_map:
            if "." in match.group("full_name"):
                return image_map[name]
            else: # correctly handle edge-save-images.sh expected input
                return f"{image_map[name].split('/', 1)[-1]}"

        return match.group(0)
    
    def replace_chart(match):
        name = match.group("name")
        if name in release_versions:
            return f"{match.group('full_name')}:{release_versions[name]}"
        return match.group(0)

    doc = image_ref_regex.sub(replace_image, doc)
    doc = chart_ref_regex.sub(replace_chart, doc)
    doc = sl_micro_regex.sub(rf"\1 {release_versions['__os_version__']}", doc)

    with open(doc_path, "w") as f:
        f.write(doc)

def preserve_placeholders(yaml_text):
    """
    Replace ${key} placeholders with unique tokens to preserve them during YAML processing.
    Preprocess placeholders: ${...}
    :param yaml_text: Original YAML text
    :return: Tuple of cleaned YAML text and a dictionary of placeholders
    """
    placeholders = {}
    def replacer(match):
        key = match.group(1)
        token = f"__PLACEHOLDER_{len(placeholders)}__"
        placeholders[token] = f"${{{key}}}"
        return token

    cleaned = re.sub(r"\$\{([^}]+)\}", replacer, yaml_text)
    return cleaned, placeholders

def restore_placeholders(yaml_text, placeholders):
    for token, original in placeholders.items():
        yaml_text = yaml_text.replace(token, original)
    return yaml_text

def update_inline_versions_in_text(text, release_versions):
    """
    Inline text block update for version substitution
    :param text: Original text containing inline blocks
    :param release_versions: Dictionary of release versions
    """
    def replace_inline_block(match):
        """
        Replace versions in an inline block of text.
        :param match: Regex match object containing the inline block
        """
        block = match.group(0)
        lines = block.splitlines(keepends=True)

        new_lines = []
        buffer = []
        current_release = None

        for line in lines:
            name_match = re.match(r"^\s*name:\s*(\S+)", line)
            version_match = re.match(r"^(\s*)version:\s*([^\n]+)", line)

            buffer.append(line)

            if name_match:
                current_release = name_match.group(1)

            if version_match:
                indent = version_match.group(1)
                original_version = version_match.group(2)

                if current_release and current_release in release_versions:
                    new_version = release_versions[current_release]
                    if original_version != new_version:
                        buffer[-1] = f"{indent}version: {new_version}\n"

            if line.strip() == "" or line.strip() == "---":
                new_lines.extend(buffer)
                buffer = []
                current_release = None

        new_lines.extend(buffer)
        return ''.join(new_lines)

    pattern = re.compile(r'(?<=inline:\s\|)\n((?:^[ ]{6,}.*\n?)+)', re.MULTILINE)
    return pattern.sub(lambda m: replace_inline_block(m), text)


def process_yaml_file(filepath, release_versions, image_map):
    """
    Process a single YAML file to update management structure versions and inline text blocks.
    :param filepath: Path to the YAML file
    :param release_versions: Dictionary of release versions
    :param image_map: Dictionary mapping image names to full image paths
    """
    try:
        with open(filepath, "r") as f:
            raw_text = f.read()
    except Exception as e:
        print(f"Skipping {filepath} — could not read: {e}")
        return False

    cleaned_text, placeholders = preserve_placeholders(raw_text)

    try:
        documents = list(yaml.safe_load_all(cleaned_text))
    except yaml.YAMLError as e:
        print(f"Skipping {filepath} — YAML error: {e}")
        return False

    changed = False
    updated_documents = []

    # Phase 1: update mgmt structure versions
    for doc in documents:
        if not isinstance(doc, dict):
            updated_documents.append(doc)
            continue

        before = yaml.dump(doc, Dumper=IndentedDumper, default_flow_style=False, sort_keys=False)
        new_doc = copy.deepcopy(doc)

        update_versions_in_mgmt_file(new_doc, release_versions, image_map)

        after = yaml.dump(new_doc, Dumper=IndentedDumper, default_flow_style=False, sort_keys=False)

        if before != after:
            changed = True

        updated_documents.append(new_doc)

    if changed:
        output_yaml = yaml.dump_all(updated_documents, Dumper=IndentedDumper, default_flow_style=False, sort_keys=False)
        output_yaml = restore_placeholders(output_yaml, placeholders)

        with open(filepath, "w") as f:
            f.write(output_yaml)
        print(f"Updated mgmt versions: {filepath}")
    else:
        print(f"No mgmt changes: {filepath}")

    # Phase 2: update inline text blocks for downstream clusters manifests
    try:
        with open(filepath, "r") as f:
            updated_text = f.read()
    except Exception as e:
        print(f"Skipping inline update for {filepath} — could not read: {e}")
        return changed

    updated_text_with_inline = update_inline_versions_in_text(updated_text, release_versions)

    if updated_text_with_inline != updated_text:
        with open(filepath, "w") as f:
            f.write(updated_text_with_inline)
        print(f"Updated inline versions: {filepath}")
        return True

    print(f"No inline changes: {filepath}")
    return changed


def main():
    """
    Main function to parse arguments and process YAML files
    """
    parser = argparse.ArgumentParser(description="Update Helm, Kubernetes, and image versions from release files")
    parser.add_argument("version", help="Release version in X.Y.Z format (e.g., 3.3.1)")
    parser.add_argument("--root", default="../", help="Root path to recursively scan for .yaml files")
    parser.add_argument("--registry", choices=["factory", "production"], default="public",
                        help="Registry type to pull the release manifest from: 'internal' or 'public'")
    args = parser.parse_args()

    if not re.match(r"^\d+\.\d+\.\d+$", args.version):
        print("Error: Invalid version format. Expected X.Y.Z (e.g., 3.3.1)", file=sys.stderr)
        sys.exit(1)

    # Build image path dynamically based on registry type (commented out)
    major_minor = ".".join(args.version.split(".")[:2])
    if args.registry == "factory":
        image = f"registry.opensuse.org/isv/suse/edge/{major_minor}/test_manifest_images/{major_minor}/release-manifest:{args.version}"
    else:  # production
        image = f"registry.suse.com/edge/{major_minor}/release-manifest:{args.version}"

    release_manifest, release_images = get_release_files(image)
    release_versions = build_release_versions(release_manifest)
    image_map = build_image_map(release_images)

    for root, _, files in os.walk(args.root):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                process_yaml_file(os.path.join(root, file), release_versions, image_map)
            elif file == "README.md":
                update_versions_in_readme(os.path.join(root, file), release_versions, image_map)


if __name__ == "__main__":
    main()
