#!/usr/bin/env python3
# Copyright 2026 NVIDIA CORPORATION
# SPDX-License-Identifier: Apache-2.0

import json
import pathlib
import tempfile
import unittest

from generate_image_catalog import catalog_path
from generate_image_catalog import load_build_metadata
from generate_image_catalog import load_chart_images
from generate_image_catalog import load_platform_manifests
from generate_image_catalog import render_catalog


class GenerateImageCatalogTest(unittest.TestCase):
    def test_load_build_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)
            (path / "scheduler.json").write_text(
                json.dumps({"containerimage.digest": "sha256:scheduler"})
            )
            (path / "binder.json").write_text(
                json.dumps(
                    {
                        "containerimage.descriptor": {
                            "digest": "sha256:binder"
                        }
                    }
                )
            )
            self.assertEqual(
                {
                    "binder": "sha256:binder",
                    "scheduler": "sha256:scheduler",
                },
                load_build_metadata(path),
            )

    def test_load_platform_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)
            (path / "scheduler.json").write_text(
                json.dumps(
                    {
                        "manifests": [
                            {
                                "digest": "sha256:amd64",
                                "platform": {
                                    "os": "linux",
                                    "architecture": "amd64",
                                },
                            },
                            {
                                "digest": "sha256:arm64",
                                "platform": {
                                    "os": "linux",
                                    "architecture": "arm64",
                                },
                            },
                        ]
                    }
                )
            )
            self.assertEqual(
                {
                    "scheduler": {
                        "linux/amd64": "sha256:amd64",
                        "linux/arm64": "sha256:arm64",
                    }
                },
                load_platform_manifests(path),
            )

    def test_load_chart_images_includes_optional_images(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "values.yaml"
            path.write_text(
                """
operator:
  enabled: true
  image:
    name: operator
optionalComponent:
  enabled: false
  resourceReservationImage:
    name: resourcereservation
global:
  imagePullSecrets:
    - name: ignored
"""
            )
            self.assertEqual(
                {"operator", "resourcereservation"},
                load_chart_images(path),
            )

    def test_render_catalog_selects_variant_and_platform(self):
        catalog = render_catalog(
            "v1.2.3",
            "ghcr.io/kai-scheduler/kai-scheduler",
            "fips",
            "linux/arm64",
            {"scheduler": "sha256:index"},
            {"scheduler": {"linux/arm64": "sha256:arm64"}},
        )
        self.assertEqual("fips", catalog["spec"]["variant"])
        self.assertEqual(
            {"os": "linux", "architecture": "arm64"},
            catalog["spec"]["platform"],
        )
        self.assertEqual(
            "ghcr.io/kai-scheduler/kai-scheduler/scheduler:v1.2.3-fips",
            catalog["spec"]["images"][0]["source"],
        )
        self.assertEqual(
            "sha256:arm64",
            catalog["spec"]["images"][0]["digest"],
        )

    def test_catalog_path(self):
        output = pathlib.Path("dist")
        self.assertEqual(
            output / "kai-scheduler-v1.2.3-linux-amd64.yaml",
            catalog_path(output, "v1.2.3", "standard", "linux/amd64"),
        )
        self.assertEqual(
            output / "kai-scheduler-v1.2.3-fips-linux-arm64.yaml",
            catalog_path(output, "v1.2.3", "fips", "linux/arm64"),
        )


if __name__ == "__main__":
    unittest.main()
