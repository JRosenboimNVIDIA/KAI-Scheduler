#!/usr/bin/env bash
# Copyright 2026 NVIDIA CORPORATION
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

# On four-CPU runners a two-zone integer CPU probe can need every exclusive CPU.
# Put control services on the CPU worker and account GPU-node agents in the
# reserved shared CPU instead of consuming the exclusive CPU request budget.
kubectl get nodes -l mokka.nvidia.com/e2e-cpu=true -o name | grep -q .
kubectl -n kube-system set resources daemonset/kindnet --requests=cpu=0
kubectl get deployments -A -o json | python3 -c '
import json,sys
for deployment in json.load(sys.stdin)["items"]:
    print(deployment["metadata"]["namespace"], deployment["metadata"]["name"])
' | while read -r namespace name; do
  kubectl -n "$namespace" patch deployment "$name" --type=merge \
    -p '{"spec":{"template":{"spec":{"nodeSelector":{"mokka.nvidia.com/e2e-cpu":"true"}}}}}'
  kubectl -n "$namespace" rollout status "deployment/$name" --timeout=3m
done
