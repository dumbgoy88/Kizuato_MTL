#!/usr/bin/env python3
"""Guarded, OCR-driven route probe for a live X11 Neko Project window.

The route plan is generated separately from the original event graph and guide.
This tool records video, advances text, stops at unknown choices, and selects
only the next explicitly listed option. It is experimental until emulator-tested.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, signal, subprocess, sys, time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from PIL import Image
STOP=False

def stop(_sig,_frame):
 global STOP;STOP=True

def norm(s):return re.sub(r'[^A-Z0-9]','',s.upper())
def cmd(*args):return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT).strip()
def save(path,obj):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)
def focus(window):
 try:cmd('xdotool','windowactivate','--sync',window)
 except subprocess.CalledProcessError:cmd('xdotool','windowfocus','--sync',window)
def press(window,key,hold=.12):
 cmd('xdotool','keydown',key);time.sleep(hold);cmd('xdotool','keyup',key)
def screen(window,display,path):
 subprocess.run(['ffmpeg','-loglevel','error','-y','-f','x11grab','-window_id',window,'-i',display,'-frames:v','1',str(path)],check=True)
 raw=subprocess.check_output(['tesseract',str(path),'stdout','--psm','6'],text=True,stderr=subprocess.DEVNULL).strip()
 # White PC-98 letters often cross detailed art. A luminance mask gives OCR
 # a clean second pass while preserving the unmodified capture for review.
 im=Image.open(path).convert('L')
 enhanced=path.with_name('ocr-mask.png')
 im.point(lambda x:0 if x>=165 else 255).resize((im.width*3,im.height*3)).save(enhanced)
 masked=subprocess.check_output(['tesseract',str(enhanced),'stdout','--psm','11'],text=True,stderr=subprocess.DEVNULL).strip()
 return raw+'\n'+masked

def arrow_y(path):
 im=Image.open(path).convert('RGB')
 counts=[sum(min(im.getpixel((x,y)))>180 for x in range(15,48)) for y in range(im.height)]
 shape=(8,9,11,12,13,12,11,9,8)
 hits=[]
 for y in range(50,im.height-5):
  if counts[y]>=11 and sum(abs(counts[y-4+j]-shape[j]) for j in range(9))<=5:
   hits.append(y)
 return hits[0] if len(hits)==1 else None

def visible_arrow(window,display,folder,label):
 path=folder/f'{label}.png'
 # The PC-98 selection arrow blinks slowly. A 1.4 s sampling window can
 # coincide entirely with its hidden phase, even on a valid choice screen.
 for _ in range(32):
  screen_capture=['ffmpeg','-loglevel','error','-y','-f','x11grab','-window_id',window,'-i',display,'-frames:v','1',str(path)]
  subprocess.run(screen_capture,check=True)
  y=arrow_y(path)
  if y is not None:return y
  time.sleep(.12)
 return None
def select_option(window,display,folder,label,count,selected):
 # Arrow visibility and key movement are independent: a key can merely
 # reveal a hidden arrow. Discover every row, then move to the requested row.
 positions=[]
 def canonical(y):
  for known in positions:
   if abs(known-y)<=5:return known
  positions.append(y)
  return y
 y=visible_arrow(window,display,folder,f'{label}-cursor-start')
 current=canonical(y) if y is not None else None
 for attempt in range(count*8):
  if len(positions)==count:break
  press(window,'Down',hold=.3);time.sleep(.25)
  y=visible_arrow(window,display,folder,f'{label}-cursor-scan-{attempt+1}')
  if y is not None:current=canonical(y)
  if len(positions)>count:return False,'too_many_cursor_rows',positions
 if len(positions)!=count or current is None:return False,'cursor_rows_incomplete',positions
 target=sorted(positions)[selected]
 for attempt in range(count*8):
  if current==target:return True,'selected',sorted(positions)
  press(window,'Down',hold=.3);time.sleep(.25)
  y=visible_arrow(window,display,folder,f'{label}-cursor-select-{attempt+1}')
  if y is not None:
   current=next((known for known in positions if abs(known-y)<=5),None)
   if current is None:return False,'unexpected_cursor_row',sorted(positions)
 return False,'cursor_did_not_reach_option',sorted(positions)
def score(option,ocr):
 e=norm(option);o=norm(ocr)
 if not e or not o:return 0
 if e in o:return 1
 # Sum ordered matching stretches; a few OCR errors should not invalidate
 # a long choice option whose other words remain legible.
 return sum(m.size for m in SequenceMatcher(None,e,o,autojunk=False).get_matching_blocks())/len(e)
def contiguous_score(option,ocr):
 e=norm(option);o=norm(ocr)
 return SequenceMatcher(None,e,o,autojunk=False).find_longest_match().size/len(e) if e and o else 0
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('plan',type=Path);ap.add_argument('--window-id',required=True);ap.add_argument('--output-dir',type=Path,default=Path('build/auto-route'))
 ap.add_argument('--max-presses',type=int,default=2500);ap.add_argument('--interval',type=float,default=.7);ap.add_argument('--resume-live',action='store_true')
 ap.add_argument('--endpoints',type=Path,default=Path('config/route_endpoints_v6.json'));ap.add_argument('--dry-run',action='store_true')
 a=ap.parse_args();raw=a.plan.read_bytes();plan=json.loads(raw);endings={e['id']:e for e in json.loads(a.endpoints.read_text())['endings']}
 assert 0<a.max_presses<=10000 and .2<=a.interval<=10
 assert plan['choices'] and plan['ending_id'] in endings
 if a.dry_run:
  for c in plan['choices']:
   print(c['sequence'],c['scene'],c['selected'],[x['english'].replace('\n',' ')[:45] for x in c['options']])
  return
 for t in ('ffmpeg','xdotool','tesseract'):
  if not shutil.which(t):raise RuntimeError(f'missing {t}')
 display=os.environ['DISPLAY'];window=str(int(a.window_id,0));pid=cmd('xdotool','getwindowpid',window)
 folder=a.output_dir/plan['route'];folder.mkdir(parents=True,exist_ok=True);statefile=folder/'state.json';digest=hashlib.sha256(raw).hexdigest()
 if a.resume_live:
  state=json.loads(statefile.read_text())
  if (state['plan_sha256'],state['window'],state['pid'])!=(digest,window,pid):raise RuntimeError('changed plan or emulator')
  state['status']='running';save(statefile,state)
 else:
  if statefile.exists():raise RuntimeError('existing state; use --resume-live with same emulator')
  state={'plan_sha256':digest,'window':window,'pid':pid,'choice_index':0,'presses':0,'status':'running'};save(statefile,state)
 focus(window)
 video=folder/f"segment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.mkv"
 ff=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-f','x11grab','-framerate','10','-window_id',window,'-i',display,'-c:v','libx264','-preset','ultrafast','-crf','28',str(video)],stdin=subprocess.PIPE)
 time.sleep(.3)
 if ff.poll() is not None:raise RuntimeError('ffmpeg failed to start')
 print(f'RECORDING {video}',flush=True)
 recent_frames=[]
 try:
  while not STOP and state['presses']<a.max_presses:
   if cmd('xdotool','getwindowpid',window)!=pid:raise RuntimeError('emulator changed')
   if ff.poll() is not None:raise RuntimeError('video recording stopped')
   png=folder/'current.png';ocr=screen(window,display,png)
   if len(re.findall(r'(?m)^\s*A>\s*$',ocr))>=3:
    state['status']='dos_exit';save(statefile,state);shutil.copyfile(png,folder/'dos-exit.png');print('STOP: game exited to DOS',flush=True);break
   recent_frames.append(hashlib.sha256(png.read_bytes()).digest())
   recent_frames=recent_frames[-16:]
   if len(recent_frames)==16 and len(set(recent_frames))<=4:
    state['status']='stalled_screen';save(statefile,state);shutil.copyfile(png,folder/'stalled-screen.png');print('STOP: screen stopped changing',flush=True);break
   with (folder/'ocr.jsonl').open('a') as log:log.write(json.dumps({'presses':state['presses'],'choice_index':state['choice_index'],'text':ocr})+'\n')
   ending=endings[plan['ending_id']]
   if state['choice_index']>=len(plan['choices']):
    if norm(ending['marker']) in norm(ocr):
     state['status']='ending_marker_seen';save(statefile,state);shutil.copyfile(png,folder/'ending-marker.png');print('ENDING MARKER',ending['id'],flush=True);break
   else:
    expected=plan['choices'][state['choice_index']]
    scores=[score(x['english'],ocr) for x in expected['options']]
    contiguous=[contiguous_score(x['english'],ocr) for x in expected['options']]
    # Ordered fragments alone can spuriously match a long narration screen.
    # A genuine option must also contain one substantial uninterrupted span.
    hits=sum(total>=.75 and span>=.4 for total,span in zip(scores,contiguous))
    numbered=len(re.findall(r'(?m)^\s*[1-5][oO.,]\s*',ocr))
    readable_words=len(re.findall(r'\b[A-Za-z]{4,}\b',ocr))
    # Narrative can share many short words with options. One printed number
    # plus two matching option bodies is sufficient; OCR sometimes loses the
    # other number on a genuine two-option screen.
    if hits>=2 and numbered>=1:
     shutil.copyfile(png,folder/f"choice-{state['choice_index']+1:02d}.png")
     print(f"CHOICE {state['choice_index']+1}/{len(plan['choices'])} {expected['scene']} scores {[round(x,2) for x in scores]} select {expected['selected']+1}",flush=True)
     label=f"choice-{state['choice_index']+1:02d}"
     selected,reason,rows=select_option(window,display,folder,label,len(expected['options']),expected['selected'])
     if not selected:
      state['status']=reason;save(statefile,state);print('STOP:',reason,'rows',rows,flush=True);break
     print('CURSOR ROWS',rows,'target',expected['selected']+1,flush=True)
     press(window,'Return',hold=.2);state['choice_index']+=1;save(statefile,state);time.sleep(a.interval);continue
    # Stop on a plausible choice whose text is not the expected one.
    if numbered>=2 and readable_words>=3:
     state['status']='unknown_choice';save(statefile,state);shutil.copyfile(png,folder/'unknown-choice.png');print('STOP: unknown choice',repr(ocr[:350]),flush=True);break
    if hits>=2:
     state['status']='ambiguous_choice';save(statefile,state);shutil.copyfile(png,folder/'ambiguous-choice.png');print('STOP: likely choice without readable option numbers',flush=True);break
   press(window,'Return');state['presses']+=1;save(statefile,state)
   if state['presses']%25==0:print('ADVANCED',state['presses'],'choices',state['choice_index'],'ocr',repr(ocr[:75]),flush=True)
   time.sleep(a.interval)
  else:
   state['status']='stopped' if STOP else 'press_cap';save(statefile,state);print('STOP',state['status'],flush=True)
 finally:
  if ff.poll() is None and ff.stdin:
   try:ff.stdin.write(b'q\n');ff.stdin.flush();ff.wait(timeout=10)
   except (BrokenPipeError,subprocess.TimeoutExpired):ff.terminate();ff.wait(timeout=5)
 print('STATE',statefile,flush=True)
if __name__=='__main__':
 signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
 try:main()
 except Exception as e:print('auto_route_probe:',e,file=sys.stderr);raise SystemExit(2)
