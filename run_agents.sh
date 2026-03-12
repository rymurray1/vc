#!/bin/bash
# Run parallel Haiku agents on pending batches
# Usage: ./run_agents.sh [concurrency=4]

CONCURRENCY=${1:-4}
BATCHES_DIR="/Users/ryanmurray/programming/vc/batches"
LOGS_DIR="/Users/ryanmurray/programming/vc/logs"
mkdir -p "$LOGS_DIR"

# Find batches that still have incomplete entries
PENDING=()
for f in "$BATCHES_DIR"/batch_*.json; do
  batch=$(basename "$f")
  filled=$(python3 -c "
import json
d=json.load(open('$f'))
print(sum(1 for v in d.values() if v['founders']))
")
  total=$(python3 -c "import json; d=json.load(open('$f')); print(len(d))")
  if [ "$filled" -lt "$total" ]; then
    PENDING+=("$batch")
  fi
done

echo "Found ${#PENDING[@]} pending batches. Running $CONCURRENCY at a time."
echo ""

RUNNING=0
PIDS=()
BATCH_FOR_PID=()

for batch in "${PENDING[@]}"; do
  # Wait if at concurrency limit
  while [ "$RUNNING" -ge "$CONCURRENCY" ]; do
    for i in "${!PIDS[@]}"; do
      if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] Finished: ${BATCH_FOR_PID[$i]}"
        unset 'PIDS[$i]'
        unset 'BATCH_FOR_PID[$i]'
        RUNNING=$((RUNNING - 1))
      fi
    done
    sleep 5
  done

  echo "[$(date '+%H:%M:%S')] Launching: $batch"
  bash /Users/ryanmurray/programming/vc/process_batch.sh "$batch" &
  PID=$!
  PIDS+=($PID)
  BATCH_FOR_PID+=("$batch")
  RUNNING=$((RUNNING + 1))
done

# Wait for all remaining
echo "Waiting for remaining agents to finish..."
wait
echo ""
echo "All done. Running merge..."
python3 /Users/ryanmurray/programming/vc/split_batches.py merge
echo ""
python3 /Users/ryanmurray/programming/vc/split_batches.py status
