#!/usr/bin/env bash
# 7 independent studies per (config × sampler), interleaved by config then sampler.
# Each round runs one fresh 60-trial study of each combination:
#   OLTP+TPS SMAC → OLTP+TPS TPE → OLTP+Latency SMAC → ... → OLAP+TPS TPE
# Repeat 7 times.

set -uo pipefail

ROUNDS=3
TRIALS=40
DURATION=120   # seconds per pgbench run (2 min)

CONFIGS=(
    "oltp tps"
    "oltp latency"
    "olap tps"
)

SAMPLERS=("smac" "tpe")

for round in $(seq 1 "$ROUNDS"); do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf  "  Round %d / %d\n" "$round" "$ROUNDS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for config in "${CONFIGS[@]}"; do
        workload="${config%% *}"
        objective="${config##* }"

        for sampler in "${SAMPLERS[@]}"; do
            echo "  ── $workload / $objective / $sampler ──"
            uv run python main.py \
                --trials "$TRIALS" \
                --workload "$workload" \
                --objective "$objective" \
                --sampler "$sampler" \
                --duration "$DURATION" \
            || echo "  [FAILED] study skipped — workload=$workload objective=$objective sampler=$sampler round=$round"
        done
    done
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done. $((${#CONFIGS[@]} * ${#SAMPLERS[@]} * ROUNDS)) studies, $TRIALS trials each."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
