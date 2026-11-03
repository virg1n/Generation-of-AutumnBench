import crypto from 'node:crypto';
import {Autumn,replay} from './runtime.mjs';
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const random=seed=>()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

export function measure(source) {
 const output={};
function representatives(frame) {
  // One point per visible 4-connected same-color component; no object IDs or
  // generator metadata. This treats a large sprite and a one-cell button alike.
  const seen=new Set(), points=[];
  for(let y=0;y<frame.h;y++) for(let x=0;x<frame.w;x++) {
    const key=y*frame.w+x,color=frame.grid[y][x];
    if(color===frame.bg||seen.has(key)) continue;
    points.push({x,y});seen.add(key);
    const queue=[[x,y]];
    while(queue.length) {
      const [cx,cy]=queue.pop();
      for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
        const nx=cx+dx,ny=cy+dy,k=ny*frame.w+nx;
        if(nx>=0&&ny>=0&&nx<frame.w&&ny<frame.h&&!seen.has(k)&&frame.grid[ny][nx]===color) {seen.add(k);queue.push([nx,ny]);}
      }
    }
  }
  return points.length?points:[{x:0,y:0}];
}

function probe(policy, policySeed, envSeed=42, count=96) {
  const env=new Autumn(source,envSeed), rng=random(policySeed);
  try {
    let frame=env.render();
    const frames=[frame], actions=[];
    const systematic=representatives(frame);
    for(let t=0;t<count;t++) {
      let type=policy==='noop'?'noop':['noop','left','right','up','down','click'][Math.floor(rng()*6)];
      if(policy==='systematic') type=t%4===0?'click':'noop';
      let a={type};
      if(type==='click') {
        const points=representatives(frame);
        const cell=policy==='systematic'?systematic[Math.floor(t/4)%systematic.length]:policy==='guided'&&rng()<.8?points[Math.floor(rng()*points.length)]:null;
        a={type,x:cell?cell.x:Math.floor(rng()*frame.w),y:cell?cell.y:Math.floor(rng()*frame.h)};
      }
      actions.push(a); frame=env.step(a); frames.push(frame);
    }
    return {frames,actions};
  } finally {env.close();}
}
function transitionStats(run) {
  let changed=0, turnover=0, growth=0, shrink=0;
  const active=f=>f.grid.flat().filter(x=>x!==f.bg).length;
  for(let t=1;t<run.frames.length;t++) {
    const a=run.frames[t-1],b=run.frames[t];
    let diff=0, union=0;
    for(let y=0;y<a.h;y++) for(let x=0;x<a.w;x++) {
      diff+=a.grid[y][x]!==b.grid[y][x];
      union+=a.grid[y][x]!==a.bg||b.grid[y][x]!==b.bg;
    }
    changed+=diff>0;turnover+=diff/Math.max(1,union);
    growth+=active(b)>active(a); shrink+=active(b)<active(a);
  }
  const n=run.actions.length;
  return {change:changed/n,turnover:turnover/n,growth:growth/n,shrink:shrink/n};
}
  const runs=[probe('uniform',100),probe('uniform',101),probe('guided',100),probe('guided',101),probe('systematic',0)];
  const noop=probe('noop',0);
  const stats=runs.map(transitionStats);
  const average=key=>stats.reduce((s,x)=>s+x[key],0)/stats.length;
  const sameActions=replay(source,runs[0].actions,43);
  const stochastic=sameActions.slice(1).filter((f,i)=>!equal(f.grid,runs[0].frames[i+1].grid)).length/96;
  const prefix=runs[2].actions.slice(0,16);
  const origin=replay(source,prefix).at(-1);
  const waits=Array.from({length:13},()=>({type:'noop'}));
  const reference=replay(source,[...prefix,...waits]).slice(prefix.length+1);
  const points=representatives(origin);
  const stimuli=[...['left','right','up','down'].map(type=>({type})),
    ...Array.from({length:32},(_,i)=>({type:'click',...points[Math.floor(i*points.length/32)]}))];
  const effects=stimuli.map(a=>{
    const trace=replay(source,[...prefix,a,...waits.slice(1)]).slice(prefix.length+1);
    const ds=trace.map((f,i)=>!equal(f.grid,reference[i].grid));
    return {first:ds.indexOf(true),last:ds.at(-1),any:ds.some(Boolean),signature:hash(trace.map(f=>f.grid))};
  });
  const lookup=new Map();let alias=0,total=0;
  for(const run of runs) for(let i=0;i<run.actions.length;i++) {
    const key=hash([run.frames[i].grid,run.actions[i]]),out=hash(run.frames[i+1].grid);
    if(lookup.has(key)) {total++; if(lookup.get(key)!==out) alias++;} else lookup.set(key,out);
  }
  output.features={
    autonomous_change:transitionStats(noop).change,
    driven_change:average('change'), turnover:average('turnover'),
    growth:average('growth'),shrink:average('shrink'),
    action_effect:effects.filter(e=>e.any).length/effects.length,
    delayed_effect:effects.filter(e=>e.first>0).length/effects.length,
    persistent_effect:effects.filter(e=>e.last).length/effects.length,
    stochastic_difference:stochastic,
    observation_aliasing:total?alias/total:0,
  };
  output.details={noop_unique:new Set(noop.frames.map(f=>hash(f.grid))).size,
    driven:stats,probe_policy_names:['uniform100','uniform101','guided100','guided101','systematic'],effects,alias_comparisons:total,
    trace_signature:hash([...runs,noop].map(r=>r.frames.map(f=>f.grid)))};
  output.preview={initial:runs[2].frames[0].grid,after:runs[2].frames.at(-1).grid};

return output;
}
