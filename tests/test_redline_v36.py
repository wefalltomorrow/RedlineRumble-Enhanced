import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('v36', str(Path(__file__).resolve().parents[1] / 'source' / 'build_redline_v36.py')); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ops=m.decode_bytecode(m.assemble()[0])

class Env:
    def __init__(self):
        self.keyset=set()
        self.props={282:('sym',315),273:100,336:None,
                    96:{'transform':{'position':{'x':1,'y':2,'z':3},'rotation':(25,0,0)},'worldPosition':(0,0,0)},
                    301:{'worldPosition':(10,20,30)},337:None}
        self.events=[]
    def tick(self, keys):
        self.keyset=set(keys);self.events=[];stack=[];pc=0;itercount=0
        while True:
            itercount+=1;assert itercount<500
            op,v,nxt=ops[pc];pc=nxt
            if op==1:
                assert not stack,('stack return',stack)
                break
            if op==0x41 or op==0x6e:
                if op==0x41 and v>=128: v-=256
                if op==0x6e and v>=32768:v-=65536
                stack.append(v)
            elif op==0x45: stack.append(('sym',v))
            elif op==0x4a:stack.append(self.props.get(v))
            elif op==0x50:self.props[v]=stack.pop()
            elif op==0x0f:b=stack.pop();a=stack.pop();stack.append(a==b)
            elif op==0x0c:b=stack.pop();a=stack.pop();stack.append(a<b)
            elif op==0x05:b=stack.pop();a=stack.pop();stack.append(tuple(x+y for x,y in zip(a,b)))
            elif op==0x53:pc=(nxt-3)+v
            elif op==0x55:
                condition=stack.pop()
                if not condition:pc=(nxt-3)+v
            elif op==0x43 or op==0x42:
                args=stack[-v:] if v else []
                if v:del stack[-v:]
                stack.append(('args',args,op==0x42))
            elif op==0x57:
                a=stack.pop();assert a[0]=='args'
                if v==171:
                    assert len(a[1])==1
                    stack.append(bool(('C' if a[1][0]==8 else 'B') in self.keyset))
                elif v==104:stack.append(tuple(a[1]))
                else:raise Exception(('ext',v))
            elif op==0x70 or op==0x61:
                o=stack.pop()
                k={106:'transform',110:'position',105:'worldPosition',119:'x',115:'y',114:'z'}[v]
                stack.append(o[k] if isinstance(o,dict) else o[{'x':0,'y':1,'z':2}[k]])
            elif op==0x62:
                value=stack.pop();o=stack.pop()
                k={105:'worldPosition',107:'rotation',110:'position',296:'fov'}[v];o[k]=value
                self.events.append(('set',k,value))
            elif op==0x67:
                args=stack.pop();assert args[0]=='args'
                assert v==162
                self.events.append(('pointAt',args[1][-1]))
            else:raise Exception(('opcode',op,v))
        return self.props[336],list(self.events)

# Normal sequence, including both views and double-hold.
e=Env()
assert e.tick([])[0] is None
assert e.tick(['B'])[0]==4
assert e.props[337] == (1,2,3), e.props[337]
assert ('pointAt',(10,140,1580)) in e.events, e.events
# Change the physical camera while looking back; stored hood position must not be overwritten.
e.props[96]['transform']['position'] = (777,888,999)
assert e.tick(['B'])[0]==4
assert e.props[337] == (1,2,3), e.props[337]
state,ev=e.tick([])
assert state==0 and ('set','rotation',(0,0,0)) in ev,(state,ev)
assert ('set','position',(1,2,3)) in ev, ev
assert e.tick([])[1]==[]
assert e.tick(['C'])[0]==3
assert e.tick(['C'])[0]==3
assert e.tick([])[0]==1
assert e.tick(['B'])[0]==1
assert ('pointAt',(10,100,480)) in e.events
assert e.tick([])[0]==1
assert ('pointAt',(10,100,-270)) in e.events
assert e.tick(['C'])[0]==2
assert e.tick([])[0]==0
assert e.tick(['B','C'])[0]==3
assert e.tick(['B','C'])[0]==3
assert e.tick(['B'])[0]==1
assert e.tick([])[0]==1
# B before C while held: no uncontrolled state; release B in chase is valid.
e=Env()
assert e.tick(['B'])[0]==4
assert e.tick(['B','C'])[0]==3
assert e.tick(['B'])[0]==1
assert e.tick([])[0]==1
# C to hood while holding B: first release immediately applies hood return.
e=Env()
assert e.tick(['C'])[0]==3
assert e.tick([])[0]==1
assert e.tick(['B','C'])[0]==6
assert e.tick(['B'])[0]==4
assert e.tick([])[0]==0
# Switching to chase while looking back must NOT overwrite the original stored hood position.
e=Env()
assert e.tick(['B'])[0]==4
e.props[96]['transform']['position']=(333,444,555)
assert e.tick(['B','C'])[0]==3
assert e.props[337]==(1,2,3),e.props[337]
assert e.tick([])[0]==1
assert e.tick(['C'])[0]==2
assert e.props[96]['transform']['position']==(1,2,3)
# Switching from chase into hood while B remains held must restore hood baseline first.
e=Env()
assert e.tick(['C'])[0]==3
assert e.tick([])[0]==1
e.props[96]['transform']['position']=(222,333,444)
assert e.tick(['B','C'])[0]==6
assert e.props[337]==(1,2,3)
assert e.tick(['B'])[0]==4
state,events=e.tick([])
assert state==0 and ('set','position',(1,2,3)) in events
print('PASS: C/B sequences, saved hood position, rear camera placement, rotation recovery, and stack checks')