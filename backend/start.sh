#!/bin/bash
cd /opt/data/home/housing-tracker/backend
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3001