#!/bin/bash
# Double-click to start MediOps, then open http://localhost:4173 in your browser.
cd "$(dirname "$0")"
echo "Starting MediOps..."
echo "When it says 'MediOps backend on ...', open this in your browser:"
echo "    http://localhost:4173"
echo "Leave this window open during the demo. Press Ctrl-C to stop."
echo
python3 server.py
