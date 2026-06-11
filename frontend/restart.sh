#!/bin/bash
# Kill all existing next processes
pkill -9 -f "next dev" 2>/dev/null
pkill -9 -f "next-server" 2>/dev/null
sleep 2

# Verify port is free
if fuser 3002/tcp >/dev/null 2>&1; then
    fuser -k -9 3002/tcp 2>/dev/null
    sleep 1
fi

# Clean .next cache
rm -rf /opt/data/home/housing-tracker/frontend/.next

# Start fresh
cd /opt/data/home/housing-tracker/frontend
npx next dev -p 3002
