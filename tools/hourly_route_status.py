#!/usr/bin/env python3
"""Append hourly local route progress snapshots; this does not send chat messages."""
from __future__ import annotations
import argparse,json,os,time
from datetime import datetime,timezone
from pathlib import Path

def alive(pid:int)->bool:
 try:os.kill(pid,0);return True
 except ProcessLookupError:return False

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('state',type=Path);p.add_argument('runner_pid',type=int)
 p.add_argument('log',type=Path);p.add_argument('--interval',type=int,default=3600)
 a=p.parse_args()
 if a.interval<60:raise SystemExit('interval must be at least 60 seconds')
 a.log.parent.mkdir(parents=True,exist_ok=True)
 while True:
  state=json.loads(a.state.read_text()) if a.state.exists() else {}
  row={'utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'runner_alive':alive(a.runner_pid),
       'choice_index':state.get('choice_index'),'presses':state.get('presses'),'status':state.get('status')}
  with a.log.open('a') as out:out.write(json.dumps(row)+'\n')
  if not row['runner_alive']:break
  time.sleep(a.interval)
if __name__=='__main__':main()
