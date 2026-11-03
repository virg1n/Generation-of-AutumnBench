from collections import deque,Counter
import argparse,hashlib,time
from worlds import *

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def bfs(table,start):
    parents={int(start):None};distance={int(start):0};q=deque([int(start)])
    while q:
        s=q.popleft()
        for a,ns in enumerate(table[s]):
            ns=int(ns)
            if ns not in parents:parents[ns]=(s,a);distance[ns]=distance[s]+1;q.append(ns)
    return parents,distance
def path(parents,s):
    seq=[]
    while parents[s] is not None:s,a=parents[s];seq.append(a)
    return seq[::-1]
def rollout(w,seq,start=None,disabled=()):
    states=[w.initial if start is None else start]
    for a in seq:states.append(step(w,states[-1],a,disabled))
    return states
def cert(w,seq,start=None,disabled=()):
    states=rollout(w,seq,start,disabled)
    return {'actions':[action(w,a) if isinstance(a,int) else a for a in seq],'states':states,'frames':[render(w,s) for s in states]}

def analyze_candidate(w):
    prepared=prepare_rules(w);table=transition_table(w,prepared=prepared);parents,dist=bfs(table,w.initial)
    eligible=[s for s,d in dist.items() if 4<=d<=12];random.Random(w.seed+80000).shuffle(eligible)
    record={'name':w.name,'seed':w.seed,'sites':w.n,'rules':len(w.rules),'reachable':len(dist),'diameter_from_initial':max(dist.values()),'admitted':False}
    if not eligible:return record,[],table,None
    ablated=[transition_table(w,(j,),prepared) for j in range(len(w.rules))]
    altered=[bfs(t,w.initial)[1] for t in ablated]
    anchor=None
    for target in eligible[:48]:
        seq=path(parents,target);states=rollout(w,seq);cuts=[];fired=[step(w,s,a,trace=True)[1] for s,a in zip(states,seq)]
        for j,t in enumerate(ablated):
            ss=w.initial;visit=[ss]
            for a in seq:ss=int(t[ss,a]);visit.append(ss)
            if target not in visit:
                cuts.append({'rule':j,'distance_without':altered[j].get(target),'shortest_distance_increases':altered[j].get(target,10000)>len(seq),'globally_unreachable':target not in altered[j]})
        if len(cuts)<2:continue
        links=[]
        for c in cuts:
            j=c['rule'];ss=rollout(w,seq,disabled=(j,));changed=[step(w,s,a,(j,),True)[1] for s,a in zip(ss,seq)]
            writes={i for i,e in w.rules[j]['assign']}
            for cc in cuts:
                k=cc['rule']
                if j==k:continue
                inputs=reads(w.rules[k]['when']).union(*(reads(e) for i,e in w.rules[k]['assign']))
                shared=writes&inputs
                times=[t+1 for t,(a,b) in enumerate(zip(fired,changed)) if k in a and k not in b and any((states[t]^ss[t])>>i&1 for i in shared)]
                if shared and times:links.append({'from_rule':j,'to_rule':k,'shared_sites':sorted(shared),'suppressed_effective_steps':times})
        if links:
            anchor={'start':w.initial,'target':target,'plan':seq,'distance':len(seq),'cuts':cuts,'links':links};break
    if anchor is None:return record,[],table,None
    tasks=[dict(anchor,id='task_0')]
    # Additional evaluation tasks fixed BEFORE exploration, from changed starts.
    rng=random.Random(w.seed+90000);reachable=list(dist)
    for attempt in range(100):
        if len(tasks)>=4:break
        start=rng.choice(reachable);pp,dd=bfs(table,start);candidates=[s for s,d in dd.items() if 3<=d<=10]
        if not candidates:continue
        target=rng.choice(candidates)
        if any(t['start']==start and t['target']==target for t in tasks):continue
        seq=path(pp,target);tasks.append({'id':f'task_{len(tasks)}','start':start,'target':target,'plan':seq,'distance':len(seq),'start_prefix':path(parents,start)})
    reachable_array=np.array(reachable);trans=table[reachable_array];pop=np.array([i.bit_count() for i in range(1<<w.n)])
    changes=pop[trans ^ reachable_array[:,None]]/w.n
    degrees=np.array([len(set(map(int,row))) for row in trans])
    # Fixed normalization bounds; NOT the old black-box descriptors.
    descriptors=[len(dist)/(1<<w.n),min(max(dist.values()),32)/32,float(degrees.mean()/w.action_count),
                 float(changes.mean()),float((changes>.5).mean()),float((trans==reachable_array[:,None]).mean()),
                 float(np.std(pop[reachable_array]/w.n)),len(anchor['cuts'])/len(w.rules),
                 min(len(anchor['links']),16)/16,float(sum(c['globally_unreachable'] for c in anchor['cuts'])/len(w.rules))]
    record.update(admitted=True,descriptor=descriptors,anchor=anchor,task_count=len(tasks),active_rules=len({j for s in reachable for a in range(w.action_count) for j in step(w,s,a,trace=True)[1]}))
    return record,tasks,table,ablated

def export(w,record,tasks,table,folder=None):
    folder=ROOT/'generated'/w.name if folder is None else folder
    save(folder/'world.json',w.to_dict());save(folder/'tasks.json',tasks)
    # These certificates are owned by this generator. Remove stale cuts from an
    # earlier run if an improved causal check selected a different anchor task.
    for p in folder.glob('cut_*'):
        if p.suffix in ('.json','.sexp'):p.unlink()
    (folder/'world.sexp').write_text(compile_autumn(w),encoding='utf-8');np.save(folder/'oracle.npy',table)
    r=random.Random(w.seed+20000);seq=[r.randrange(w.action_count) for _ in range(96)]
    save(folder/'validation.json',cert(w,seq))
    # Test ALL state-action pairs at the Python scalar/vector boundary.
    assert all(step(w,s,a)==int(table[s,a]) for s in range(1<<w.n) for a in range(w.action_count))
    for task in tasks:
        ww=World.from_dict(w.to_dict());ww.initial=task['start']
        save(folder/(task['id']+'.json'),cert(ww,task['plan']));(folder/(task['id']+'.sexp')).write_text(compile_autumn(ww),encoding='utf-8')
    for cut in record['anchor']['cuts']:
        j=cut['rule'];save(folder/f'cut_{j}.json',cert(w,record['anchor']['plan'],disabled=(j,)))
        (folder/f'cut_{j}.sexp').write_text(compile_autumn(w,(j,)),encoding='utf-8')

def select(rows,count):
    xs=np.array([r['descriptor'] for r in rows]);selected=[0];nearest=np.linalg.norm(xs-xs[0],axis=1)
    while len(selected)<min(count,len(rows)):
        nearest[selected]=-1;j=int(nearest.argmax());selected.append(j);nearest=np.minimum(nearest,np.linalg.norm(xs-xs[j],axis=1))
    return [rows[i]['name'] for i in selected]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=192);p.add_argument('--keep',type=int,default=32);p.add_argument('--seed',type=int,default=31000);args=p.parse_args()
    rows=[];start=time.time()
    for i in range(args.count):
        w=generate(args.seed+i,i);row,tasks,table,ab=analyze_candidate(w);rows.append(row)
        if row['admitted']:export(w,row,tasks,table)
        save(ROOT/'generation_ledger.json',rows)
        if i%8==0:print(json.dumps({'done':i+1,'admitted':sum(r['admitted'] for r in rows),'seconds':round(time.time()-start)}),flush=True)
    admitted=[r for r in rows if r['admitted']];chosen=select(admitted,args.keep)
    random_control=random.Random(20261102).sample([r['name'] for r in admitted],min(args.keep,len(admitted)))
    save(ROOT/'selection.json',{'selected':chosen,'random_control':random_control,'selection_rule':'farthest-point Euclidean on ten fixed transition/causal descriptors; first admitted is initial anchor','all_admitted':[r['name'] for r in admitted]})
