#!/usr/bin/env python3
"""Fix popup onclick to properly quote trade.id as a string."""
path = '/opt/data/home/housing-tracker/frontend/app/components/FindMapInner.js'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix: add quotes around trade.id in the onclick handler
old = 'onclick="window.__showTradeDetail(${trade.id})"'
new = "onclick=\"window.__showTradeDetail('${trade.id}')\""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed: added quotes around trade.id in onclick")
else:
    print("Pattern not found - may already be fixed")
