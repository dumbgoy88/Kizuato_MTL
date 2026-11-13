#!/usr/bin/env python3
"""Join a reviewed route choice list to hash-pinned original graph and v6 English edits.

Output contains game text and belongs only in ignored work/ or build/.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
GRAPH_HASH='beec74329493a72fcdb61c914539d3d210f0193d714fdc583189aec1e9a5cace'
EDITS_HASH='a1e846b6d25d4fc0d12ac2a5918a5d2451bd6d3b3269936be1ea2efb7d34a26b'
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('choices',type=Path);p.add_argument('graph',type=Path);p.add_argument('edits',type=Path);p.add_argument('output',type=Path)
 a=p.parse_args();config=json.loads(a.choices.read_text());g=json.loads(a.graph.read_text());raw=a.edits.read_bytes()
 if g['source_sha256']!=GRAPH_HASH or hashlib.sha256(raw).hexdigest()!=EDITS_HASH:raise ValueError('wrong original graph or v6 edit set')
 e={r['id']:''.join(r['text_runs']) for r in json.loads(raw)};scenes={s['scene']:s for s in g['scenes']};rows=[]
 for n,c in enumerate(config['choices'],1):
  b=scenes[c['scene']]['blocks'][c['block']]
  matches=[x for x in b['commands'] if 'choice' in x and len(x['choice']['options'])==c['option_count']]
  if len(matches)!=1:raise ValueError(f"ambiguous/missing choice at {c['scene']} block {c['block']}")
  options=[]
  for i,opt in enumerate(matches[0]['choice']['options']):
   mid=f"MAX2_SCN/{c['scene']}/text/{opt['message']:03d}"
   if mid not in e:raise ValueError(f'no English text for {mid}')
   options.append({'index':i,'id':mid,'english':e[mid]})
  if not 0<=c['selected']<len(options):raise ValueError(f'bad selection in {c["scene"]}')
  rows.append({'sequence':n,'scene':c['scene'],'block':c['block'],'selected':c['selected'],'options':options})
 out={'route':config['route'],'guide':config['source_guide'],'choices':rows,'ending_id':config['ending_id']}
 if a.output.exists():raise ValueError('refusing to overwrite plan')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
 print('wrote',a.output,'with',len(rows),'choices')
if __name__=='__main__':main()
