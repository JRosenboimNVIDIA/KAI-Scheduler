#!/usr/bin/env python3
# Copyright 2026 NVIDIA CORPORATION
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import pathlib
import re


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


def quote(value):
    return json.dumps(value)


def render_catalog(version, registry, platforms, standard, fips):
    lines = [
        "apiVersion: artifacts.kai.scheduler/v1alpha1",
        "kind: ImageCatalog",
        "metadata:",
        "  name: kai-scheduler",
        f"  version: {quote(version)}",
        "spec:",
        f"  registry: {quote(registry)}",
        "  platforms:",
    ]
    lines.extend(f"    - {quote(platform)}" for platform in platforms)
    lines.append("  images:")
    for name, digest in sorted(standard.items()):
        lines.extend(
            [
                f"    - name: {quote(name)}",
                f"      image: {quote(f'{registry}/{name}:{version}')}",
                f"      digest: {quote(digest)}",
            ]
        )
        if name in fips:
            lines.extend(
                [
                    "      fips:",
                    f"        image: {quote(f'{registry}/{name}:{version}-fips')}",
                    f"        digest: {quote(fips[name])}",
                ]
            )
    return "\n".join(lines) + "\n"


def generate(args):
    standard = load_build_metadata(args.standard_metadata)
    fips = load_build_metadata(args.fips_metadata)
    if not standard:
        raise ValueError("standard image metadata is empty")
    if fips and set(fips) != set(standard):
        missing = sorted(set(standard) - set(fips))
        extra = sorted(set(fips) - set(standard))
        raise ValueError(f"FIPS image mismatch: missing={missing}, extra={extra}")
    chart_images = load_chart_images(args.chart_values)
    unpublished = sorted(chart_images - set(standard))
    if unpublished:
        raise ValueError(f"chart images were not published: {unpublished}")
    args.output.write_text(
        render_catalog(
            args.version,
            args.registry.rstrip("/"),
            args.platform,
            standard,
            fips,
        )
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--standard-metadata", required=True, type=pathlib.Path)
    parser.add_argument("--fips-metadata", type=pathlib.Path)
    parser.add_argument("--chart-values", required=True, type=pathlib.Path)
    parser.add_argument("--platform", action="append", required=True)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    return parser.parse_args()


if __name__ == "__main__":
    generate(parse_args())
