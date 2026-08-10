#!/usr/bin/env python3
# Copyright 2026 NVIDIA CORPORATION
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import pathlib
import re

import yaml


def load_build_metadata(directory):
    images = {}
    if directory is None:
        return images
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text())
        digest = data.get("containerimage.digest")
        if digest is None:
            digest = data.get("containerimage.descriptor", {}).get("digest")
        if not digest:
            raise ValueError(f"missing container image digest in {path}")
        images[path.stem] = digest
    return images


def load_platform_manifests(directory):
    images = {}
    if directory is None:
        return images
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text())
        platforms = {}
        for manifest in data.get("manifests", []):
            platform = manifest.get("platform", {})
            os_name = platform.get("os")
            architecture = platform.get("architecture")
            digest = manifest.get("digest")
            if os_name and architecture and digest:
                platforms[f"{os_name}/{architecture}"] = digest
        if not platforms:
            raise ValueError(f"missing platform manifests in {path}")
        images[path.stem] = platforms
    return images


def load_chart_images(path):
    images = set()
    stack = []
    for line in path.read_text().splitlines():
        content = line.split("#", 1)[0].rstrip()
        if not content:
            continue
        indent = len(content) - len(content.lstrip())
        stripped = content.strip()
        match = re.match(r"([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$", stripped)
        if not match:
            continue
        key, value = match.groups()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if key == "name" and value and stack:
            parent = stack[-1][1].lower()
            if parent == "image" or parent.endswith("image"):
                images.add(value.strip().strip("\"'"))
        if not value:
            stack.append((indent, key))
    return images


def validate_variant(name, metadata, manifests, platforms):
    if not metadata:
        raise ValueError(f"{name} image metadata is empty")
    if set(metadata) != set(manifests):
        missing = sorted(set(metadata) - set(manifests))
        extra = sorted(set(manifests) - set(metadata))
        raise ValueError(
            f"{name} manifest mismatch: missing={missing}, extra={extra}"
        )
    for image_name, image_platforms in manifests.items():
        missing = sorted(set(platforms) - set(image_platforms))
        if missing:
            raise ValueError(
                f"{name} image {image_name} is missing platforms {missing}"
            )


def catalog_path(output_dir, version, variant, platform):
    os_name, architecture = platform.split("/", 1)
    variant_part = "" if variant == "standard" else f"{variant}-"
    return output_dir / (
        f"kai-scheduler-{version}-{variant_part}{os_name}-{architecture}.yaml"
    )


def render_catalog(version, registry, variant, platform, metadata, manifests):
    os_name, architecture = platform.split("/", 1)
    tag = version if variant == "standard" else f"{version}-{variant}"
    images = []
    for name, index_digest in sorted(metadata.items()):
        images.append(
            {
                "name": name,
                "source": f"{registry}/{name}:{tag}",
                "indexDigest": index_digest,
                "digest": manifests[name][platform],
            }
        )
    return {
        "apiVersion": "artifacts.kai.scheduler/v1alpha1",
        "kind": "ImageLock",
        "metadata": {
            "name": "kai-scheduler",
            "version": version,
        },
        "spec": {
            "variant": variant,
            "platform": {
                "os": os_name,
                "architecture": architecture,
            },
            "images": images,
        },
    }


def generate(args):
    standard_metadata = load_build_metadata(args.standard_metadata)
    standard_manifests = load_platform_manifests(args.standard_manifests)
    validate_variant(
        "standard",
        standard_metadata,
        standard_manifests,
        args.platform,
    )

    fips_metadata = load_build_metadata(args.fips_metadata)
    fips_manifests = load_platform_manifests(args.fips_manifests)
    if fips_metadata or fips_manifests:
        validate_variant(
            "FIPS",
            fips_metadata,
            fips_manifests,
            args.platform,
        )
        if set(fips_metadata) != set(standard_metadata):
            missing = sorted(set(standard_metadata) - set(fips_metadata))
            extra = sorted(set(fips_metadata) - set(standard_metadata))
            raise ValueError(
                f"FIPS image mismatch: missing={missing}, extra={extra}"
            )

    chart_images = load_chart_images(args.chart_values)
    unpublished = sorted(chart_images - set(standard_metadata))
    if unpublished:
        raise ValueError(f"chart images were not published: {unpublished}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    variants = [
        ("standard", standard_metadata, standard_manifests),
    ]
    if fips_metadata:
        variants.append(("fips", fips_metadata, fips_manifests))

    paths = []
    for variant, metadata, manifests in variants:
        for platform in args.platform:
            path = catalog_path(
                args.output_dir,
                args.version,
                variant,
                platform,
            )
            catalog = render_catalog(
                args.version,
                args.registry.rstrip("/"),
                variant,
                platform,
                metadata,
                manifests,
            )
            path.write_text(yaml.safe_dump(catalog, sort_keys=False))
            paths.append(path)
    return paths


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--standard-metadata", required=True, type=pathlib.Path)
    parser.add_argument("--standard-manifests", required=True, type=pathlib.Path)
    parser.add_argument("--fips-metadata", type=pathlib.Path)
    parser.add_argument("--fips-manifests", type=pathlib.Path)
    parser.add_argument("--chart-values", required=True, type=pathlib.Path)
    parser.add_argument("--platform", action="append", required=True)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    return parser.parse_args()


if __name__ == "__main__":
    generate(parse_args())
