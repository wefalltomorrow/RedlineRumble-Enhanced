#!/usr/bin/env python3
"""Exhaustive static resource/bytecode diff for Redline Rumble corrected visual traffic v35.

Does NOT run Macromedia Director and cannot certify 3D runtime semantics.
"""
from pathlib import Path
import hashlib,struct,zipfile,sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
import build_redline_v35 as b

def main():
 with zipfile.ZipFile(b.BASE) as base,zipfile.ZipFile(b.OUT) as new:
  assert base.testzip() is None and new.testzip() is None
  olddir=base.read('game.dir');newdir=new.read('game.dir')
  old=b.resource(olddir,b.INDEX);mod=b.resource(newdir,b.INDEX)
  assert hashlib.sha256(olddir).hexdigest()==b.EXPECTED_BASE
  assert b.resource(olddir,1506)==b.resource(newdir,1506)
  assert b.resource(olddir,1512)==b.resource(newdir,1512)
  assert b.resource(olddir,1509)!=b.resource(newdir,1509)
  assert b.rewrite(old)[0]==mod
  for i in range(b.N):
   if i!=b.INDEX:
    off=b.MAP+i*b.REC_SZ
    assert olddir[off:off+20]==newdir[off:off+20]
  def handler(src,n):
   hdr=struct.unpack_from('>I',src,74)[0]+n*46
   size,pos=struct.unpack_from('>II',src,hdr+4)
   return b.decode(src[pos:pos+size])
  orig0,orig1=handler(old,0),handler(old,1)
  new0,new1=handler(mod,0),handler(mod,1)
  hooks=((orig0,new0,[(0x09be,b.init_hook())]),
         (orig1,new1,[(0x0580,b.ongoing_hook()),(0x09e7,b.oncoming_hook())]))
  for orig,patched,inserts in hooks:
   found={x['s']:x for x in orig}
   orig_idx=0;new_idx=0;addrmap={}
   for inst in orig:
    for start,payload in inserts:
     if start==inst['s']:
      injected=b.decode(payload,allow_end=True)
      compare=patched[new_idx:new_idx+len(injected)]
      for aa,bb in zip(injected,compare):
       assert aa['raw']==bb['raw'],('injection byte changed',aa,bb)
      new_idx+=len(injected)
    match=patched[new_idx]
    assert inst['op']==match['op'] and inst['w']==match['w']
    if inst['target'] is None:
     assert inst['raw']==match['raw'],('original instruction changed',inst,match)
    addrmap[inst['s']]=match['s']
    orig_idx+=1;new_idx+=1
   assert new_idx==len(patched)
   for inst in orig:
    if inst['target'] is not None:
     match=next(m for m in patched if m['s']==addrmap[inst['s']])
     assert match['target']==addrmap[inst['target']],('original branch changed',inst,match)
   print('Handler preservation:',len(orig),'original instructions unchanged (excluding rebased jumps),',len(patched)-len(orig),'new instructions')
  a={x['s']:x for x in orig1}
  assert a[0x057A]['val']==100 and a[0x09E0]['val']==200
  assert a[0x0736]['val']==500 and a[0x08A1]['val']==500
  print('Original recycle and damage-distance checks preserved')
  # Unlimited-retention check: visual hooks must not delete any models or list entries.
  for code in (b.ongoing_hook(), b.oncoming_hook()):
   calls=[(x['op'],x['val']) for x in b.decode(code,allow_end=True)]
   assert (0x67,397) not in calls, 'deleteModel still used by visual hook'
   assert (0x67,432) not in calls, 'deleteAt still used by visual hook'
   assert (0x62,105) not in calls, 'unsafe worldPosition setter still used'
   assert (0x4a,399) not in calls and (0x50,399) not in calls, 'reused prevTrafficDifficulty'
   assert all(x['val']%8==0 for x in b.decode(code,allow_end=True) if x['op'] in (0x4c,0x52)), 'invalid local operand'
  for code in (b.ongoing_hook(), b.oncoming_hook()):
   assert (0x52,8) in [(x['op'],x['val']) for x in b.decode(code,allow_end=True)]
   assert (0x4c,0) in [(x['op'],x['val']) for x in b.decode(code,allow_end=True)]
  assert any(x['op']==0x52 and x['val']==16 for x in b.decode(b.ongoing_hook(),allow_end=True)), 'loop iterator must use local 2'
  assert not any(x['op']==0x50 and x['val']==399 for x in b.decode(b.init_hook(),allow_end=True)), 'init overwrote gameplay counter'
  print('No visual clone cap or count-based deletion calls')
  for n in base.namelist():
   if n in ('game.dir','Projector.ini','README v28.txt'):continue
   assert base.read(n)==new.read(n)
  assert b'DisplayFullLingoErrorText=1' in new.read('Projector.ini')
  assert b';DisplayFullLingoErrorText=1' in base.read('Projector.ini')
  assert new.read('Projector.ini').replace(b'DisplayFullLingoErrorText=1',b';DisplayFullLingoErrorText=1',1)==base.read('Projector.ini')
  print('All other ZIP files and all 1599 other resources preserved; native verbose errors enabled')
  print('All opcode and branch targets aligned')
  print('ZIP integrity: PASS')
  print('Game runtime behaviour: NOT YET TESTED')

if __name__=='__main__':main()