#!/usr/bin/env python3
"""Build Redline Rumble v28 (far chase + safe hold B rear) by replacing only LSCR #1506.

Inputs are unpacked historical snapshots, not modified. Pure file transformation.
Runtime gameplay must be tested on Windows: validation here is structural, not execution.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import struct
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'historical' / 'files'
DEST = HERE / 'RedlineRumble_4K_v28_CameraFix'
ZIP = HERE / 'RedlineRumble_4K_v28_CameraFix.zip'
ENTRY = 1506
HANDLER_START = 0x5D4
OLD_CODE_END = 0xE61  # relative to handler start, v26
OLD_TAIL_START = 0xCAA
EXPECTED_V22_SHA = '6d5cdfa46cc4c4e059c5cd8f381f8c398df3c861a216b05efe3a09c7769fa396'

class Asm:
    def __init__(self):
        self.data = bytearray()
        self.labels = {}
        self.fixes = []
    def here(self, name):
        assert name not in self.labels, name
        self.labels[name] = len(self.data)
    def op(self, name, value=None):
        """Emit Director v8 single-byte/operand instruction with automatic operand width."""
        if isinstance(name, bytes):
            assert value is None
            self.data += name
            return
        code = {
            'ret':1,'zero':3,'add':5,'sub':6,'mod':8,'lt':12,'eq':15,'gte':17,
            'getprop':0x4A,'setprop':0x50,'getlocal':0x4C,'setlocal':0x52,
            'push':0x41,'args':0x43,'argsNoRet':0x42,'sym':0x45,
            'extCall':0x57,'getObjProp':0x61,'setObjProp':0x62,'getChainedProp':0x70,'objCall':0x67,
        }[name]
        if value is None:
            assert code < 0x40
            self.data.append(code)
        else:
            if name == 'push' and not (-128 <= value <= 127):
                self.data.append(0xAE)
                self.data += struct.pack('>h',value)
            elif name == 'push':
                self.data.append(0x41)
                self.data += struct.pack('>b',value)
            elif 0 <= value < 256:
                self.data += bytes((code, value))
            elif 0 <= value <= 65535:
                self.data.append(code + 0x40)
                self.data += struct.pack('>H',value)
            else:
                raise ValueError((name, value))
    def branch(self, op, label):
        assert op in ('jmp','jmpIfZ')
        pos=len(self.data)
        self.data += bytes((0x93 if op=='jmp' else 0x95,0,0))
        self.fixes.append((pos,label))
    def finish(self):
        for pos,name in self.fixes:
            assert name in self.labels, name
            delta = self.labels[name]-pos
            assert 0<=delta<=65535,(name,delta)
            struct.pack_into('>H',self.data,pos+1,delta)
        return bytes(self.data)

A = Asm()

def key(code):
    A.op('push',code);A.op('args',1);A.op('extCall',171)  # keyPressed; Mac C=8, B=11

def pget(i): A.op('getprop',i)
def pset(i): A.op('setprop',i)
def num(i): A.op('push',i)

def car_world():
    pget(301); A.op('getObjProp',105)  # mRaceCar.worldPosition

def vec(x,y,z):
    for n in (x,y,z):num(n)
    A.op('args',3);A.op('extCall',104)

def camera_at_car(dx,dy,dz):
    pget(96);car_world();vec(dx,dy,dz);A.op('add');A.op('setObjProp',105)

def point_camera_at_car(dx,dy,dz,fov):
    pget(96);car_world();vec(dx,dy,dz);A.op('add')
    A.op('argsNoRet',2);A.op('objCall',162)
    pget(96);num(fov);A.op('setObjProp',296)

def save_original_local_position():
    # Save a NEW vector by extracting xyz from camera.transform.position.
    # This avoids duplicate() on the Director 3D transform type.
    for axis in (119,115,114):  # x,y,z
        pget(96);A.op('getChainedProp',106);A.op('getChainedProp',110)
        A.op('getObjProp',axis)
    A.op('args',3);A.op('extCall',104);pset(337)  # cam1 stores vanilla LOCAL position

def restore_original_local_position():
    pget(96);A.op('getChainedProp',106);pget(337)
    A.op('setObjProp',110)  # cam.transform.position = cam1
    pget(96);num(70);A.op('setObjProp',296)

# Property 336 = gCaryHandle is unused IN THE ORIGINAL SCRIPT. We only use it
# for latch/mode and do not modify property 281 = ownAllCars (v27 regression).
# States: 0 stock idle; 1 chase idle; 2 stock C-held; 3 chase C-held.
# At startup property 336 is void; comparison-based tests treat that as stock.

pget(282);A.op('sym',315);A.op('eq');A.branch('jmpIfZ','done')
pget(273);num(360);A.op('lt');A.branch('jmpIfZ','done')

# Handle C key with edge-trigger latch; all decisions are equality comparisons
# so the initially-void property does not get passed to mod/add/compare-math.
key(8);A.branch('jmpIfZ','c_up')
pget(336);num(2);A.op('eq');A.branch('jmpIfZ','try_chase_held')
A.branch('jmp','c_complete')
A.here('try_chase_held')
pget(336);num(3);A.op('eq');A.branch('jmpIfZ','toggle_camera')
A.branch('jmp','c_complete')
A.here('toggle_camera')
pget(336);num(1);A.op('eq');A.branch('jmpIfZ','to_chase')
# Chase -> stock. Restore the original LOCAL offset, not an old world position.
num(2);pset(336)
restore_original_local_position()
A.branch('jmp','c_complete')
A.here('to_chase')
# Stock -> chase. Record stock local position while vanilla runtime is active.
save_original_local_position()
num(3);pset(336)
A.branch('jmp','c_complete')
A.here('c_up')
pget(336);num(2);A.op('eq');A.branch('jmpIfZ','test_release_chase')
num(0);pset(336)
A.branch('jmp','c_complete')
A.here('test_release_chase')
pget(336);num(3);A.op('eq');A.branch('jmpIfZ','c_complete')
num(1);pset(336)
A.here('c_complete')

# B is purely hold-controlled: no transform duplication or B-latch needed.
# Vanilla runtime recomputes its ordinary transform rotation every race frame.
key(11);A.branch('jmpIfZ','b_up')
# B while chasing: show the FRONT of player car and the road behind it.
pget(336);num(1);A.op('eq');A.branch('jmpIfZ','b_test_latched_chase')
A.branch('jmp','chase_rear')
A.here('b_test_latched_chase')
pget(336);num(3);A.op('eq');A.branch('jmpIfZ','stock_rear')
A.here('chase_rear')
camera_at_car(0,320,-800)
point_camera_at_car(0,80,450,75)
A.branch('jmp','done')
A.here('stock_rear')
# Preserve stock position. Look backwards just for this frame.
point_camera_at_car(0,90,900,70)
A.branch('jmp','done')

A.here('b_up')
# Use the older far-chase pose (v26 mode 2), visually confirmed to show
# the entire purple car in screenshot 093, rather than the clipped close view.
pget(336);num(1);A.op('eq');A.branch('jmpIfZ','chase_test_latched')
A.branch('jmp','chase_forward')
A.here('chase_test_latched')
pget(336);num(3);A.op('eq');A.branch('jmpIfZ','done')
A.here('chase_forward')
camera_at_car(0,320,800)
point_camera_at_car(0,80,-300,75)
A.here('done')
A.op('ret')
CODE=A.finish()

def rsrc(blob):
    name,sz,off,unused1,unused2=struct.unpack_from('<4sIIII',blob,136+ENTRY*20)
    assert name==b'rcsL' and unused1==unused2==0
    assert blob[off:off+8]==b'rcsL'+struct.pack('<I',sz)
    return blob[off+8:off+8+sz]

def putbe(b,at,num,fmt='I'):
    struct.pack_into('>'+fmt,b,at,num)

def mutate_lscr(original):
    orig=bytes(original)
    assert len(orig)==6482 and orig[HANDLER_START+OLD_CODE_END-1] == 1
    handler_off=struct.unpack_from('>I',orig,74)[0]
    assert handler_off==170
    handler2=handler_off+46
    assert struct.unpack_from('>I',orig,handler2+8)[0]==HANDLER_START
    assert struct.unpack_from('>I',orig,handler2+4)[0]==OLD_CODE_END
    new=bytearray(orig[:HANDLER_START+OLD_TAIL_START]+CODE+orig[HANDLER_START+OLD_CODE_END:])
    delta=len(CODE)-(OLD_CODE_END-OLD_TAIL_START)
    assert len(new)==len(orig)+delta
    for off in (8,12):putbe(new,off,len(new))
    # All known absolute offsets beyond code end: literals, data, and handler 2
    # argument/local/global table and line data. Handler 1 remains untouched.
    for off in (80,88,handler2+14,handler2+20,handler2+26,handler2+38):
        oldval=struct.unpack_from('>I',orig,off)[0]
        assert oldval>=HANDLER_START+OLD_CODE_END,(off,oldval)
        putbe(new,off,oldval+delta)
    putbe(new,handler2+4,OLD_TAIL_START+len(CODE))
    # v25/v26 accidentally retained the pre-expansion handler-vector offset.
    # In Director this is a 16-entry, 32-byte table at the END of the chunk.
    # Fix the offset to its true location instead of inheriting that error.
    assert struct.unpack_from('>I',orig,52)[0]==6012
    assert orig[-32:-2]==b'\xff'*30 and orig[-2:]==b'\x00\x01'
    putbe(new,52,len(new)-32)
    assert new[len(new)-32:]==orig[-32:]
    # Enforce exact remainder invariants.
    assert new[HANDLER_START:HANDLER_START+OLD_TAIL_START]==orig[HANDLER_START:HANDLER_START+OLD_TAIL_START]
    return bytes(new)

def parse_jumps(c):
    hand_off=struct.unpack_from('>I',c,74)[0]; out=[]
    for hi in (0,1):
        hr=hand_off+46*hi
        length,start=struct.unpack_from('>II',c,hr+4)
        end=start+length
        assert end <= len(c)
        i=start; ins=[]
        while i<end:
            pos=i;op=c[i];i+=1
            if op>=0xC0:val=struct.unpack_from('>I',c,i)[0];i+=4
            elif op>=0x80:val=struct.unpack_from('>H',c,i)[0];i+=2
            elif op>=0x40:val=c[i];i+=1
            else:val=None
            ins.append((pos,op,val))
        assert i==end
        borders={p for p,op,val in ins}|{end}
        for pos,op,val in ins:
            if (0x40+op%0x40 if op>=0x40 else op) in (0x53,0x55):
                assert pos+val in borders,('jump not aligned',hi,hex(pos),hex(pos+val))
                assert pos+val<=end
        out.append({'handler':hi,'compiled_start':start,'compiled_length':length,'instruction_count':len(ins)})
    return out


def main():
    base=next(ROOT.glob('080-RedlineRumble_4K_v22'))
    source=next(ROOT.glob('099-RedlineRumble_4K_v26_Cameras_StockRestore'))
    a=(base/'game.dir').read_bytes(); v26=(source/'game.dir').read_bytes()
    assert hashlib.sha256(a).hexdigest()==EXPECTED_V22_SHA
    assert v26[:0x4]==a[:0x4]
    # v26 keeps the original v22 movie intact; only outer container header and
    # LSCR map entry are updated, with patched LSCR appended at EOF.
    assert v26[0x763C:len(a)]==a[0x763C:]
    assert v26[:0x4]==a[:0x4]
    c=mutate_lscr(rsrc(v26))
    validate=parse_jumps(c)
    if DEST.exists():shutil.rmtree(DEST)
    shutil.copytree(base,DEST)
    target=bytearray(a)
    off=len(target)
    target+=b'rcsL'+struct.pack('<I',len(c))+c
    struct.pack_into('<II',target,136+ENTRY*20+4,len(c),off)
    struct.pack_into('<I',target,4,len(target)-8)
    (DEST/'game.dir').write_bytes(target)
    assert rsrc(bytes(target))==c
    assert target[0x763c:len(a)]==a[0x763c:]
    assert all((DEST/x).read_bytes()==(base/x).read_bytes() for x in ['Projector.exe','Projector.ini','dgVoodoo.conf','FixFullscreen_v18.ps1','Dirapi.dll'])
    # Verify the original v22 car and traffic resources are untouched.
    for entry in (1510,1512):
        offset=136+entry*20
        assert target[offset:offset+20]==a[offset:offset+20]
    # No rocket-car data, as movie matches clean v22 except one Lscr chunk.
    readme='''Redline Rumble 4K v28 — Camera Fix (experimental)\n\nC: Toggle original/stock camera and proper distant third-person chase.\nHold B: Look backwards. Releasing B returns to selected camera.\n\nBuilt from clean v22. No rocket-car changes. All other game files\nare unchanged. Camera Lingo bytecode only; Windows gameplay test needed.
The stock local camera position is saved and restored on C toggles.
The B key no longer executes duplicate() or touches ownAllCars.\n\nIf you encounter a broken camera or crash, revert to v22.\n\n'''
    (DEST/'README v28.txt').write_text(readme,encoding='utf-8')
    with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(DEST.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(DEST).as_posix())
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        assert z.read('game.dir')==bytes(target)
    report={
        'status':'structural validation completed; game not run on Windows',
        'base_v22_sha256':hashlib.sha256(a).hexdigest(),
        'game_dir_v28_sha256':hashlib.sha256(target).hexdigest(),
        'zip_sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),
        'new_bytecode_length':len(CODE),
        'bytecode_labels':A.labels,
        'lscr_new_size':len(c),
        'game_dir_new_size':len(target),
        'handlers':validate,
        'modified_resources':[1506],
        'camera_setup':'v26 far chase (0,320,800) forward target (0,80,-300)',
        'state_property_336':'gCaryHandle (unused in base script)',
        'stock_camera_local_position_saved_to':'cam1',
        'output':str(ZIP),
    }
    (HERE / 'RedlineRumble_v28_validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()