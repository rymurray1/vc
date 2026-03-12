#!/bin/bash
# Usage: ./process_batch.sh batch_002.json
BATCH=$1
LOGFILE="/Users/ryanmurray/programming/vc/logs/agent_${BATCH%.json}.log"
PROMPT=$(sed "s/BATCH_FILE/$BATCH/g" /Users/ryanmurray/programming/vc/agent_prompt.txt)

echo "[$(date '+%H:%M:%S')] Starting $BATCH" | tee -a "$LOGFILE"

unset CLAUDECODE
claude -p "$PROMPT" \
  --model claude-haiku-4-5-20251001 \
  --allowedTools "WebSearch,Read,Write" \
  --max-turns 200 \
  >> "$LOGFILE" 2>&1

echo "[$(date '+%H:%M:%S')] Done $BATCH (exit: $?)" | tee -a "$LOGFILE"
