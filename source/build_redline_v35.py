#!/usr/bin/env python3
"""Redline Rumble v35: corrected Director locals and safe visual-traffic clones.

Forks the *known working v28*, not v32. Reinstates the original v28 +100/+200
traffic recycle points and all original spawn/collision/bookkeeping behaviour.

Immediately before each normal recycling event, clones the existing car model(s)
into the same parent moving traffic group. Clones are **not** inserted into any
traffic, collision, race or AI lists. There is no artificial cap or count-based deletion of visual clones.
All captured visual models remain until Director cleans up the scene or race ends.

Static checks pass does NOT mean runtime safety. Director 3D model clone and
parenting semantics MUST be checked in the live game. This build is EXPERIMENTAL.
"""
from __future__ import annotations
import hashlib,json,struct,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'RedlineRumble_4K_v28_CameraFix.zip'
OUT=ROOT/'RedlineRumble_4K_v35_TrafficFix.zip'
REPORT=ROOT/'RedlineRumble_v35_validation.json'
INDEX=1509
N=1600
MAP=136
REC_SZ=20
EXPECTED_BASE='063733277ca3e2a37334fa2c1a9ebfaa310675d5d19a1ded2551b8cf803874d4'


def resource(movie,index):
 r=MAP+REC_SZ*index
 tag,size,offset,u1,u2=struct.unpack_from('<4sIIII',movie,r)
 assert tag==b'rcsL' and (u1,u2)==(0,0)
 assert movie[offset:offset+8]==tag+struct.pack('<I',size)
 return movie[offset+8:offset+8+size]


def decode(code,allow_end=False):
 out=[]; i=0
 while i<len(code):
  s=i; raw=code[i];i+=1
  op=raw if raw<0x40 else 0x40+raw%0x40
  w=0 if raw<0x40 else 4 if raw>=0xc0 else 2 if raw>=0x80 else 1
  assert i+w<=len(code)
  v=int.from_bytes(code[i:i+w],'big') if w else None;i+=w
  target=(s-v if op==0x54 else s+v) if op in (0x53,0x54,0x55) else None
  out.append(dict(s=s,e=i,op=op,w=w,val=v,target=target,raw=code[s:i]))
 assert i==len(code)
 starts={x['s'] for x in out}
 assert all(x['target'] is None or x['target'] in starts or (allow_end and x['target']==len(code)) for x in out)
 return out


def op(opcode,arg=None,width=None):
 if arg is None:
  assert opcode<0x40
  return bytes([opcode])
 if width is None:width=1 if -128<=arg<128 else 2 if -32768<=arg<32768 else 4
 assert width in (1,2,4) and 0x40<=opcode<0x80
 lead=opcode+(0 if width==1 else 0x40 if width==2 else 0x80)
 return bytes([lead])+int(arg).to_bytes(width,'big',signed=arg<0)


class Seq:
 def __init__(self):self.buf=bytearray();self.labels={};self.jumps=[]
 def label(self,name):
  assert name not in self.labels
  self.labels[name]=len(self.buf)
 def emit(self,oc,arg=None,width=None):self.buf.extend(op(oc,arg,width))
 def jmp(self,oc,target):
  assert oc in (0x53,0x54,0x55)
  at=len(self.buf);self.buf.extend(op(oc,0,2));self.jumps.append((at,oc,target))
 def resolved(self):
  for at,oc,target in self.jumps:
   dest=self.labels[target]
   delta=at-dest if oc==0x54 else dest-at
   assert 0<=delta<65536,(at,oc,target,delta)
   self.buf[at+1:at+3]=delta.to_bytes(2,'big')
  decode(bytes(self.buf),allow_end=True)
  return bytes(self.buf)


def prop(b,n):b.emit(0x4a,n)
def setprop(b,n):b.emit(0x50,n)
# Director 8.5 and earlier uses *8 for local-slot bytecode operands.
# 0 -> local 0, 8 -> local 1, 16 -> local 2.
# The v34 bug used 0,1,2; these ALL selected local 0, corrupting loop indices.
def loc(b,n):
 assert n in (0,1,2), ('Handler 1 only has three locals', n)
 b.emit(0x4c,n*8)
def setloc(b,n):
 assert n in (0,1,2), ('Handler 1 only has three locals', n)
 b.emit(0x52,n*8)
def push(b,n):b.emit(0x41,n)
def sym(b,n):b.emit(0x45,n)
def cons(b,n):b.emit(0x44,n)
def args(b,n):b.emit(0x42,n)
def argret(b,n):b.emit(0x43,n)
def call(b,n):b.emit(0x67,n)
def chained(b,n):b.emit(0x70,n)
def getobj(b,n):b.emit(0x61,n)
def setobj(b,n):b.emit(0x62,n)

def model_from_group_child(b):
 """Returns gTrafficList[local0].child[local2] (scene model)."""
 prop(b,403);loc(b,0);argret(b,2);call(b,65)
 sym(b,434);loc(b,2);argret(b,3);call(b,36)

def model_from_oncoming(b):
 """Returns mTrafficList1[local0] (scene model)."""
 prop(b,386);loc(b,0);argret(b,2);call(b,65)

def create_one_visual(b,from_oncoming:bool):
 """Clone an existing model into its moving parent (not a traffic/AI list).

 Cloning inherits the current transform; reparenting with #preserveWorld
 maintains the cloned model's position. Do not assign worldPosition again:
 the extra v34 setObjProp path triggered `Vector expected: #worldPosition`.
 Local 1 is the clone temporary; local 0 remains the traffic group index.
 """
 if from_oncoming:model_from_oncoming(b)
 else:model_from_group_child(b)
 # Names are stable and unique, derived from the list count; there is no cap
 # or deletion. Do NOT overwrite property 399 (prevTrafficDifficulty).
 cons(b,11);cons(b,14);b.emit(0x0a)
 prop(b,438);getobj(b,66);push(b,1);b.emit(0x05);b.emit(0x0a)
 argret(b,2);call(b,153)  # originalModel.clone(uniqueName)
 setloc(b,1)             # bytecode value 8; never overwrite local 0
 # Keep clone directly under the moving traffic parent, rather than the
 # recycled gTrafficList member. preserveWorld prevents any teleport.
 prop(b,402 if from_oncoming else 401);loc(b,1);sym(b,436)
 args(b,3);call(b,316)   # gTraffic*.addChild(clone,#preserveWorld)
 prop(b,438);loc(b,1);args(b,2);call(b,78) # visualModels.add(clone)

def ongoing_hook():
 b=Seq()
 push(b,1);setloc(b,2)
 b.label('ongoing_loop')
 loc(b,2)
 prop(b,403);loc(b,0);argret(b,2);call(b,65)
 sym(b,434);argret(b,2);call(b,66) # .count(#child)
 b.emit(0x0d) # lte
 b.jmp(0x55,'ongoing_done')
 create_one_visual(b,False)
 push(b,1);loc(b,2);b.emit(0x05);setloc(b,2)
 b.jmp(0x54,'ongoing_loop')
 b.label('ongoing_done')
 return b.resolved()


def oncoming_hook():
 b=Seq();create_one_visual(b,True);return b.resolved()


def init_hook():
 # List of visual clones; existing gameplay property 399 stays untouched.
 b=Seq();argret(b,0);b.emit(0x1e);setprop(b,438)
 return b.resolved()


def inject(original,where):
 ins=decode(original)
 idx={x['s']:x for x in ins}
 assert all(p in idx for p in where)
 result=bytearray();locmap={};branches=[];report=[]
 for x in ins:
  if x['s'] in where:
   piece=where[x['s']];pos=len(result)
   result.extend(piece)
   report.append({'before_original_byte':x['s'],'new_byte_offset':pos,'inserted_bytes':len(piece)})
  locmap[x['s']]=len(result)
  if x['target'] is not None:branches.append((len(result),x))
  result.extend(x['raw'])
 for newpos,x in branches:
  dest=locmap[x['target']]
  dist=newpos-dest if x['op']==0x54 else dest-newpos
  assert 0<=dist<2**(8*x['w']),(newpos,x,dist)
  result[newpos+1:newpos+1+x['w']]=dist.to_bytes(x['w'],'big')
 chk=decode(bytes(result));assert len(chk)==len(ins)+sum(len(decode(v,allow_end=True)) for v in where.values())
 return bytes(result),{'original_instructions':len(ins),'patched_instructions':len(chk),'original_branches':len(branches),'insertions':report}


def rewrite(original):
 ho=struct.unpack_from('>I',original,74)[0];hn=struct.unpack_from('>H',original,72)[0]
 assert hn==2 and ho==158
 h0,h1=ho,ho+46
 osz0,ofs0=struct.unpack_from('>II',original,h0+4)
 osz1,ofs1=struct.unpack_from('>II',original,h1+4)
 assert (osz0,ofs0,osz1,ofs1)==(2495,250,2775,3018)
 code0=original[ofs0:ofs0+osz0]
 code1=original[ofs1:ofs1+osz1]
 orig1={x['s']:x for x in decode(code1)}
 assert orig1[0x057A]['raw']==bytes.fromhex('41 64')
 assert orig1[0x09E0]['raw']==bytes.fromhex('ae 00 c8')
 assert orig1[0x073B]['raw']==bytes.fromhex('95 01 1f')
 assert orig1[0x08A5]['op']==0x55
 hook0=init_hook();og=ongoing_hook();oc=oncoming_hook()
 new0,r0=inject(code0,{0x09BE:hook0})
 new1,r1=inject(code1,{0x0580:og,0x09E7:oc})
 assert len(new0)>len(code0) and len(new1)>len(code1)
 d0=len(new0)-len(code0);d1=len(new1)-len(code1)
 out=bytearray(original[:ofs0]+new0+original[ofs0+osz0:ofs1]+new1+original[ofs1+osz1:])
 # Original LSCR fields are fixed-offset metadata and must track inserted bytes.
 def shifted(oldpos):
  return oldpos+(d0 if oldpos>=ofs0+osz0 else 0)+(d1 if oldpos>=ofs1+osz1 else 0)
 for at in (8,12):
  assert struct.unpack_from('>I',original,at)[0]==len(original)
  struct.pack_into('>I',out,at,len(out))
 for at in (52,80,88):
  val=struct.unpack_from('>I',original,at)[0]
  assert val>=ofs0+osz0
  struct.pack_into('>I',out,at,shifted(val))
 for h,sz in ((h0,len(new0)),(h1,len(new1))):
  struct.pack_into('>I',out,h+4,sz)
  for delta in (8,14,20,26,38):
   pos=h+delta
   val=struct.unpack_from('>I',original,pos)[0]
   if val==0:continue
   assert val>=ofs0
   struct.pack_into('>I',out,pos,shifted(val))
 assert out[shifted(ofs0):shifted(ofs0)+len(new0)]==new0
 assert out[shifted(ofs1):shifted(ofs1)+len(new1)]==new1
 assert out[shifted(ofs1)+len(new1):]==original[ofs1+osz1:]
 # All old handler instructions remain bytewise identical except branch deltas.
 for old,new in ((code0,new0),(code1,new1)):
  io=decode(old);ni=decode(new)
  assert sum(x['op']==0x55 for x in ni)>=sum(x['op']==0x55 for x in io)
 report={'resource_bytes_original':len(original),'resource_bytes_patched':len(out),'init_handler':r0,'race_handler':r1,'main_recycle_threshold_unchanged':100,'oncoming_recycle_threshold_unchanged':200,'visual_clone_limit':'unrestricted (no fixed cap or count-triggered deletion)', 'preserved_prevTrafficDifficulty':True, 'fixed_local_operands':[0,8,16], 'no_extra_worldPosition_assignment':True}
 return bytes(out),report


def main():
 with zipfile.ZipFile(BASE) as base:
  assert base.testzip() is None
  game=base.read('game.dir');assert hashlib.sha256(game).hexdigest()==EXPECTED_BASE
  original=resource(game,INDEX)
  patched,details=rewrite(original)
  result=bytearray(game)
  pos=len(result)
  result.extend(b'rcsL'+struct.pack('<I',len(patched))+patched)
  struct.pack_into('<II',result,MAP+INDEX*REC_SZ+4,len(patched),pos)
  struct.pack_into('<I',result,4,len(result)-8)
  assert resource(result,INDEX)==patched
  for i in range(N):
   if i==INDEX:continue
   off=MAP+i*REC_SZ
   assert result[off:off+REC_SZ]==game[off:off+REC_SZ],('other resource changed',i)
  notes='''Redline Rumble v35 - Visual Traffic Debug Fix (EXPERIMENTAL)

Built directly on confirmed working v28 (NOT v32).
The original +100/+200 traffic recycling, spawn/spacing, difficulty and
collision logic are preserved byte-for-byte apart from rebased branches.
Adds separate CLONED VISUAL CAR MODELS behind when real cars recycle,
across both traffic directions. v34 corrupted traffic loop indices by using
local operands 0,1,2 rather than 0,8,16; this is corrected in v35.
The unnecessary worldPosition assignment has been removed.
No existing difficulty/camera/gameplay property is repurposed. No 18-car limit and no count-based deletion.
Visual copies do NOT join traffic lists, obstacle/collision calculations,
pass counting, spawn pools or race completion logic.

This is a new Director model-cloning path, NOT yet tested in the game.
If Director displays Script Error, select NO and send a screenshot of the
VERBOSE error; revert to v28. No actual gameplay testing was possible here.
Performance may change with extra models even when driving difficulty does not.
B/C and previous hood sky-pan remain as in v28. Graphics/HUD/audio untouched.

Check that overtaken traffic stays behind AND traffic ahead appears just like
before, race completes normally, no new collision or sound errors occur.
'''
  with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for entry in base.infolist():
    if entry.filename=='README v28.txt':continue
    if entry.filename=='game.dir': payload=bytes(result)
    elif entry.filename=='Projector.ini':
     ini=base.read(entry.filename)
     assert b';DisplayFullLingoErrorText=1' in ini
     payload=ini.replace(b';DisplayFullLingoErrorText=1', b'DisplayFullLingoErrorText=1',1)
    else: payload=base.read(entry.filename)
    z.writestr(entry,payload)
   z.writestr('README v35.txt',notes)
 with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(OUT) as dst:
  assert dst.testzip() is None
  assert dst.read('game.dir')==bytes(result)
  for n in src.namelist():
   if n in ('game.dir','Projector.ini','README v28.txt'):continue
   assert src.read(n)==dst.read(n)
  assert set(dst.namelist())==(set(src.namelist())-{'README v28.txt'})|{'README v35.txt'}
 report={'status':'STATIC VALIDATION PASSED, NOT TESTED IN GAME','input':str(BASE),'output':str(OUT),'input_sha256':hashlib.sha256(game).hexdigest(),'game_sha256':hashlib.sha256(result).hexdigest(),'archive_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'resource_modified':INDEX,'other_resources_unchanged':1599,'graphics_camera_audio_unchanged':True,'verbose_projector_errors_enabled':True,'race_spawning_logic_modified':False,'collision_logic_modified':False,'visual_only_ghosts':True,'gameplay_tested':False,**details}
 REPORT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()