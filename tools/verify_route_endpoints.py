#!/usr/bin/env python3
"""Check candidate ending markers against the pinned PC-98 graph and v6 edits."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path


def normalized(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, default=Path("config/route_endpoints_v6.json"))
    p.add_argument("--graph", type=Path, default=Path("work/event_graph-route-v1.json"))
    p.add_argument("--edits", type=Path, default=Path("build/all-english-diagnostic-20261111-v6-unsafe-intermediate-edits.json"))
    a = p.parse_args()
    m = json.loads(a.manifest.read_text())
    g = json.loads(a.graph.read_text())
    raw = a.edits.read_bytes()
    if g['source_sha256'] != m['original_scene_pak_sha256'] or hashlib.sha256(raw).hexdigest() != m['edit_set_sha256']:
        raise ValueError('Original event graph or English edit set has changed')
    edits = {row['id']: ''.join(row['text_runs']) for row in json.loads(raw)}
    scene_map = {s['scene']: s for s in g['scenes']}
    ids = [x['id'] for x in m['endings']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate ending ID')
    for e in m['endings']:
        scene = scene_map[e['scene']]
        block = scene['blocks'][1]
        commands = block['commands']
        tail = [c['opcode'] for c in commands[-5:]]
        if tail != ['96','94','95','24','20']:
            raise ValueError(f"{e['id']}: unexpected ending command tail {tail}")
        loads = [c.get('load') for c in commands if 'load' in c]
        if loads[-1] != {'scene':169,'block':1}:
            raise ValueError(f"{e['id']}: does not load common credits scene")
        displayed = [c['message'] for c in commands if 'message' in c]
        if not e['final_message'].startswith(f"MAX2_SCN/{e['scene']}/text/") or int(e['final_message'][-3:]) != displayed[-1]:
            raise ValueError(f"{e['id']}: marker is not final displayed message")
        text = edits[e['final_message']]
        pages = text.split('\x0c')
        marker = normalized(e['marker'])
        if not marker or marker not in normalized(text):
            raise ValueError(f"{e['id']}: English marker missing")
        matches = [key for key, value in edits.items() if marker in normalized(value)]
        if matches != [e['final_message']]:
            raise ValueError(f"{e['id']}: marker is not unique across the edit set: {matches}")
        if e['post_presses'] == 0 and marker not in normalized(pages[-1]):
            raise ValueError(f"{e['id']}: marker is not on final page")
        if e['post_presses'] == 1:
            if len(pages) < 2 or marker not in normalized(pages[-2]) or normalized(e['post_marker']) not in normalized(pages[-1]):
                raise ValueError(f"{e['id']}: post-page check does not match")
        print(f"{e['id']:16} {e['scene']} final {e['final_message'][-3:]} -> 169; marker unique")
    print(f"Verified {len(ids)} static ending markers. OCR and route reachability still need emulator checks.")


if __name__ == '__main__':
    main()
