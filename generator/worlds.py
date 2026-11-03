"""Synthesize typed Boolean rule programs, without benchmark templates.

World state is a set of occupied sites. Rules have an event, a condition AST,
and simultaneous assignments of Boolean expression ASTs. All expressions read
old state; later enabled rules win conflicting writes. No named game mechanic
or fixed agent/room transition pipeline is embedded in the semantics.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import random, json
import numpy as np
ROOT=Path(__file__).resolve().parent
EVENTS=['noop','left','right','up','down']
COLORS=['orange','cyan','gold','lime','violet','red','blue','white']

@dataclass
class World:
    name:str
    seed:int
    sites:list
    initial:int
    rules:list
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**d)
    @property
    def n(self):return len(self.sites)
    @property
    def action_count(self):return 6+self.n

def evaluate(e,state):
    op=e[0]
    if op=='bit':return bool(state>>e[1]&1)
    if op=='const':return bool(e[1])
    if op=='not':return not evaluate(e[1],state)
    if op=='and':return evaluate(e[1],state) and evaluate(e[2],state)
    if op=='or':return evaluate(e[1],state) or evaluate(e[2],state)
    if op=='xor':return evaluate(e[1],state)!=evaluate(e[2],state)
    if op=='count':return sum(bool(state>>i&1) for i in e[1])>=e[2]
    raise ValueError(op)

def reads(e):
    if e[0]=='bit':return {e[1]}
    if e[0]=='const':return set()
    if e[0]=='count':return set(e[1])
    return set().union(*(reads(x) for x in e[1:]))

def step(w,state,action,disabled=(),trace=False):
    out=state;fired=[]
    for j,r in enumerate(w.rules):
        if j in disabled or (r['event']!=-1 and r['event']!=action) or not evaluate(r['when'],state):continue
        before=out
        for dst,expr in r['assign']:
            out=(out&~(1<<dst))|(int(evaluate(expr,state))<<dst)
        if out!=before:fired.append(j)
    return (out,fired) if trace else out

def prepare_rules(w):
    states=range(1<<w.n);ops=[]
    for r in w.rules:
        guard=np.array([evaluate(r['when'],int(s)) for s in states],dtype=bool)
        mask=sum(1<<i for i,e in r['assign']);bits=np.zeros(1<<w.n,dtype=np.uint16)
        for i,e in r['assign']:bits|=np.array([evaluate(e,int(s)) for s in states],dtype=np.uint16)<<i
        ops.append((guard,mask,bits,r['event']))
    return ops

def transition_table(w,disabled=(),prepared=None):
    """Vector implementation, independently checked against scalar semantics."""
    states=np.arange(1<<w.n,dtype=np.uint16);table=np.repeat(states[:,None],w.action_count,axis=1)
    for j,(guard,mask,bits,event) in enumerate(prepare_rules(w) if prepared is None else prepared):
        if j in disabled:continue
        columns=range(w.action_count) if event==-1 else [event]
        for a in columns:table[guard,a]=(table[guard,a]&np.uint16(((1<<w.n)-1)^mask))|bits[guard]
    return table

def action(w,a):
    if a<5:return {'type':EVENTS[a]}
    if a==5+w.n:return {'type':'click','x':15,'y':15}
    site=w.sites[a-5];return {'type':'click','x':site['x'],'y':site['y']}
def abstract(w,a):
    if a['type']!='click':return EVENTS.index(a['type'])
    for i,s in enumerate(w.sites):
        if s['x']<=a['x']<s['x']+s['size'] and s['y']<=a['y']<s['y']+s['size']:return i+5
    return 5+w.n  # off-site clicks differ from waiting when a noop rule exists

def render(w,state):
    g=[['black']*16 for _ in range(16)]
    for i,s in enumerate(w.sites):
        if state>>i&1:
            for y in range(s['y'],s['y']+s['size']):
                for x in range(s['x'],s['x']+s['size']):g[y][x]=s['color']
    return g

def decode_observation(w,grid):
    # Public site positions are the interface schema, not hidden rules/state.
    return sum((grid[s['y']][s['x']]!='black')<<i for i,s in enumerate(w.sites))

def expression(r,n,depth=1):
    if depth==0 or r.random()<.42:return ['bit',r.randrange(n)]
    kind=r.choice(['not','and','or','xor','count'])
    if kind=='count':
        sites=r.sample(range(n),r.randint(2,min(4,n)));return ['count',sites,r.randint(1,len(sites))]
    if kind=='not':return ['not',expression(r,n,depth-1)]
    return [kind,expression(r,n,depth-1),expression(r,n,depth-1)]

def generate(seed,index=0):
    r=random.Random(seed);n=r.randint(6,10);positions=r.sample([(x,y) for y in range(0,16,4) for x in range(0,16,4)],n)
    size=r.choice([1,1,2,3]);sites=[{'x':x,'y':y,'size':size if r.random()<.7 else r.randint(1,3),'color':r.choice(COLORS)} for x,y in positions]
    rules=[]
    for j in range(r.randint(n+2,2*n+4)):
        event=-1 if r.random()<.22 else r.randrange(5+n)
        cond=['const',1] if r.random()<.38 else expression(r,n,r.choice([1,1,2]))
        targets=r.sample(range(n),r.choices([1,2,3],[.65,.28,.07])[0]);assign=[]
        for dst in targets:
            mode=r.randrange(5)
            rhs=['not',['bit',dst]] if mode==0 else ['const',r.randrange(2)] if mode==1 else expression(r,n,r.choice([0,1,2]))
            assign.append([dst,rhs])
        rules.append({'event':event,'when':cond,'assign':assign})
    return World(f'world_{index:03d}',seed,sites,r.randrange(1,1<<n),rules)

def compile_autumn(w,disabled=()):
    def E(op,*args):return '('+op+' '+' '.join(map(str,args))+')'
    def I(c,a,b):return f'(if {c} then {a} else {b})'
    def expr(e):
        op=e[0]
        if op=='bit':return E('==',f'(prev b{e[1]})',1)
        if op=='const':return 'true' if e[1] else 'false'
        if op=='not':return E('!',expr(e[1]))
        if op in ('and','or','xor'):return E({'and':'&','or':'|','xor':'!='}[op],expr(e[1]),expr(e[2]))
        terms=[f'(prev b{i})' for i in e[1]];total=terms[0]
        for term in terms[1:]:total=E('+',total,term)
        return E('>=',total,e[2])
    lines=['(program','(= GRID_SIZE 16)','(= background "black")']
    event_cache={}
    for ev in set(r['event'] for r in w.rules):
        if ev==-1:cond='true'
        elif ev==0:cond=E('&',E('!', '((clicked))'),E('&',E('!', '((left))'),E('&',E('!', '((right))'),E('&',E('!', '((up))'),E('!', '((down))')))))
        elif ev<5:cond=f'(({EVENTS[ev]}))'
        else:
            s=w.sites[ev-5];x,y,size=s['x'],s['y'],s['size']
            cond=I('((clicked))',E('&',E('&',E('>=','(.. click x)',x),E('<','(.. click x)',x+size)),E('&',E('>=','(.. click y)',y),E('<','(.. click y)',y+size))),'false')
        name=f'event{ev+1}';lines.append(f'(= {name} (fn () {cond}))');event_cache[ev]=f'(({name}))'
    for j,r in enumerate(w.rules):
        cond='false' if j in disabled else E('&',event_cache[r['event']],expr(r['when']))
        lines.append(f'(= rule{j} (fn () {cond}))')
    for i in range(w.n):
        rhs=f'(prev b{i})'
        for j,r in enumerate(w.rules):
            for dst,e in r['assign']:
                if dst==i:rhs=I(f'((rule{j}))',I(expr(e),1,0),rhs)
        lines.extend([f'(: b{i} Number)',f'(= b{i} (initnext {(w.initial>>i)&1} {rhs}))'])
    parts=[]
    for i,s in enumerate(w.sites):
        cells=' '.join(f'(Cell {x} {y} "{s["color"]}")' for y in range(s['size']) for x in range(s['size']))
        lines.append(f'(object Site{i} (list {cells}))')
        parts.append(I(f'(== b{i} 1)',f'(list (Site{i} (Position {s["x"]} {s["y"]})))','(list)'))
    scene='(concat (list '+' '.join(parts)+'))';lines.append(f'(= scene (initnext {scene} {scene}))');lines.append(')')
    return '\n'.join(lines)+'\n'
