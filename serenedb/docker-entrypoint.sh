#!/bin/sh
set -eu

DATA_DIR="${SERENEDB_DATA_DIR:-/var/lib/serenedb}"
LISTEN="${SERENEDB_LISTEN:-postgres://0.0.0.0:7890,http://0.0.0.0:4318?api=otel}"

# Soft footprint (NOT a Railway hard OOM kill):
# Parallel search-table writes scale with threads × segment_memory_max.
# Default SereneDB auto-detects a large host CPU count (we saw threads=24).
CPU_THREADS="${SERENEDB_CPU_THREADS:-2}"
IO_THREADS="${SERENEDB_IO_THREADS:-2}"

mkdir -p "$DATA_DIR"

exec serened "$DATA_DIR" \
  --listen="$LISTEN" \
  --cpu_threads="$CPU_THREADS" \
  --io_threads="$IO_THREADS"
