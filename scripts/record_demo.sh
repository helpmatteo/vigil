#!/usr/bin/env bash
# Record a scripted demo of vigil --demo using asciinema + tmux.
# Outputs: demo.cast (asciicast) and docs/demo.gif
set -euo pipefail
cd "$(dirname "$0")/.."

COLS=120
ROWS=35
CAST=demo.cast
GIF=docs/demo.gif

# Clean up any leftover tmux session
tmux kill-session -t vigil-demo 2>/dev/null || true

# Start a detached tmux session at the right size
tmux new-session -d -s vigil-demo -x "$COLS" -y "$ROWS"

# Start asciinema recording inside the tmux pane
tmux send-keys -t vigil-demo "asciinema rec $CAST --overwrite --cols $COLS --rows $ROWS -c 'uv run vigil --demo'" Enter

# Wait for vigil to fully boot — uv resolve + Textual render
echo "Waiting for vigil to boot..."
for i in $(seq 1 30); do
    sleep 1
    # Check if the pane contains dashboard content
    if tmux capture-pane -t vigil-demo -p 2>/dev/null | grep -q "Dashboard"; then
        echo "  vigil is up (after ${i}s)"
        break
    fi
done

# Let metrics stream for a bit
sleep 8

# Focus panel 1
echo "Focusing panel 1..."
tmux send-keys -t vigil-demo '1'
sleep 5

# Unfocus
echo "Unfocusing..."
tmux send-keys -t vigil-demo Escape
sleep 3

# Open metrics overview
echo "Opening metrics overview..."
tmux send-keys -t vigil-demo 'm'
sleep 4

# Close it
tmux send-keys -t vigil-demo Escape
sleep 2

# Open help overlay
echo "Opening help..."
tmux send-keys -t vigil-demo '?'
sleep 4

# Close help
tmux send-keys -t vigil-demo Escape
sleep 2

# Quit vigil (ends asciinema recording)
echo "Quitting..."
tmux send-keys -t vigil-demo 'q'
sleep 3

# Kill tmux session
tmux kill-session -t vigil-demo 2>/dev/null || true

# Convert to GIF
mkdir -p docs
agg "$CAST" "$GIF" \
    --cols "$COLS" \
    --rows "$ROWS" \
    --font-size 14 \
    --fps-cap 60 \
    --idle-time-limit 0.5 \
    --speed 1.2 \
    --last-frame-duration 1

echo ""
echo "Done! Files created:"
echo "  $CAST"
echo "  $GIF"
ls -lh "$CAST" "$GIF"
