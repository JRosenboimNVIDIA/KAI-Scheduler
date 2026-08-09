#!/usr/bin/env python3
# Copyright 2026 NVIDIA CORPORATION
# SPDX-License-Identifier: Apache-2.0

import json
import pathlib
import tempfile
import unittest

from generate_image_catalog import load_build_metadata
from generate_image_catalog import load_chart_images
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

    def test_render_catalog_includes_fips_digest(self):
        catalog = render_catalog(
            "v1.2.3",
            "ghcr.io/kai-scheduler/kai-scheduler",
            ["linux/amd64", "linux/arm64"],
            {"scheduler": "sha256:standard"},
            {"scheduler": "sha256:fips"},
        )
        self.assertIn(
            'image: "ghcr.io/kai-scheduler/kai-scheduler/scheduler:v1.2.3"',
            catalog,
        )
        self.assertIn(
            'image: "ghcr.io/kai-scheduler/kai-scheduler/scheduler:v1.2.3-fips"',
            catalog,
        )
        self.assertIn('digest: "sha256:fips"', catalog)


if __name__ == "__main__":
    unittest.main()
