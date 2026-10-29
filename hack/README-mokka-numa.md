# Mokka NUMA CI experiment

This change extends the GPU Operator + Mokka draft in upstream PR #2543.
The dedicated `E2E - Mokka NUMA experiment` workflow builds KAI from the PR.
It uses a GitHub-hosted runner so it can run in the fork.

The `numa-full` layout has four GPU workers. Each worker has eight A100 GPUs,
split between two NUMA zones (four GPUs per zone). Two workers use
`single-numa-node`; one uses `restricted`; one uses `best-effort`.
The CPU-only worker has no Mokka or NRT report.

Mokka is pinned to `51e4d79be7fe377804269c00194ca60efca25dd8` in the public
`JRosenboimNVIDIA/mokka` fork. This includes Roman's GPU Operator support,
the memory-limit API fix, and the opt-in NUMA simulation. Three disjoint
Mokka releases set `numaSimulation.enabled=true`, `configureKubelet=true`,
and the required `topologyManagerPolicy`. Mokka changes each selected
kind node's sysfs view and restarts its kubelet. Only disposable kind nodes
are used.

GPU Operator v26.7.2 runs its driver, toolkit, and device plugin. Its NFD
Topology Updater publishes the NRT objects. KAI's NUMA plugin is enabled.
Its placement exporter uses the real kubelet pod-resources socket and `/sys`.
There is no FGO, fake socket, or manually created NRT object.

The full `numa` label is selected, including nightly cases. The existing
expectations are unchanged. Failures remain failures. Ginkgo JSON/JUnit and
cluster logs are uploaded even if setup or tests fail.

## Current limits

CPU Manager is `none` and Memory Manager is `None`. NFD excludes CPU and
memory resources. Cases that require these resources can skip. This run
does not prove CPU or memory locality.

CPU locality needs real CPU IDs per zone, a working static CPU Manager,
reserved CPUs, and suitable Guaranteed pod requests. Memory locality also
needs memory NUMA nodes that the Linux kernel can use. Sysfs files alone
do not create those kernel memory nodes. A NUMA-capable VM or kernel NUMA
emulation must be tested before enabling static Memory Manager and NFD's
CPU/memory reports. This is separate work in the node environment and
Mokka's kubelet configuration.

The existing `Burstable cross-zone request passes through` case can fail:
real kubelet GPU topology checks also apply to Burstable pods. The result
must remain visible; the test is not changed to hide the difference.

## Run locally on a disposable Docker host

```bash
export CLUSTER_NAME=mokka-numa-ci GPU_STACK=mokka FEATURE_CONFIG=numa-full
export PACKAGE_VERSION=0.0.0-numa-local DOCKER_BUILDX_ADDITIONAL_ARGS=--load
./hack/setup-e2e-cluster.sh --local-images-build --skip-kai-install --feature-config numa-full
python3 hack/check-mokka-numa.py
helm upgrade --install kai-scheduler "./charts/kai-scheduler-$PACKAGE_VERSION.tgz" \
  --namespace kai-scheduler --create-namespace \
  --values hack/kai-scheduler-mokka-values.yaml \
  --values hack/kai-scheduler-mokka-numa-values.yaml \
  --set global.registry=localhost:30100 --set prometheus.enabled=true \
  --wait --timeout 10m
go tool ginkgo --keep-going --trace -vv --label-filter numa --timeout 45m \
  --output-dir=numa-results --json-report=report.json --junit-report=junit.xml \
  ./test/e2e/suites/numa
kind delete cluster --name "$CLUSTER_NAME"
```
