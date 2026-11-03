"""Compare frozen descriptors or measure newly generated worlds with the same probes."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import tempfile
from metrics import FEATURES, distances, within, energy_test, np, plt

ROOT = Path(__file__).resolve().parent

def measure(jobs):
    with tempfile.TemporaryDirectory(prefix='autumn_probes_') as tmp:
        p=Path(tmp)/'jobs.json';p.write_text(json.dumps(jobs),encoding='utf-8')
        run=subprocess.run(['node',str(ROOT/'measure_worlds.mjs'),str(p)],
                           capture_output=True,text=True,check=True)
        return json.loads(run.stdout)

def matrix(rows):
    x=np.array([[r['features'][f] for f in FEATURES] for r in rows],dtype=float)
    assert len(x) and np.isfinite(x).all() and ((x>=0)&(x<=1)).all()
    return x

def discover(folder):
    folder=folder.resolve()
    if (folder/'world.sexp').is_file():return [{'name':folder.name,'path':str(folder/'world.sexp')}]
    selection=folder.parent/'selection.json'
    if selection.is_file():
        names=json.loads(selection.read_text(encoding='utf-8'))['selected']
        jobs=[{'name':n,'path':str(folder/n/'world.sexp')} for n in names]
    else:
        jobs=[{'name':p.parent.name,'path':str(p)} for p in sorted(folder.glob('*/world.sexp'))]
    if not jobs:raise SystemExit('No worlds found; pass a world folder or a generated/ folder.')
    return jobs

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worlds',type=Path,help='One generated world or a directory of worlds; default: frozen 32-world dataset.')
    parser.add_argument('--refresh-autumn',action='store_true',help='Remeasure all 20 bundled public worlds instead of using frozen descriptors.')
    parser.add_argument('--out',type=Path,default=ROOT/'results')
    args=parser.parse_args()
    frozen=json.loads((ROOT/'baseline_features.json').read_text(encoding='utf-8'))
    ours=measure(discover(args.worlds)) if args.worlds else frozen['ours_selected']
    original=(measure([{'name':r['name'],'path':str(ROOT/'autumnbench'/f"{r['name']}.sexp")} for r in frozen['autumn_public']])
              if args.refresh_autumn else frozen['autumn_public'])
    x,y=matrix(ours),matrix(original)
    self_d=distances(y,y);np.fill_diagonal(self_d,np.inf)
    baseline=float(self_d.min(axis=1).mean());size=min(19,len(x))
    rng=np.random.default_rng(20261103);d=distances(y,x)
    values=np.array([d[:,rng.choice(len(x),size,replace=False)].min(axis=1).mean() for _ in range(1000)])
    result={'ours_worlds':len(x),'autumn_worlds':len(y),'candidate_archive_size':size,
        'ours_within_L1':within(x) if len(x)>1 else None,'autumn_within_L1':within(y),
        'nearest_ours_mean':float(values.mean()),'nearest_autumn_leave_one_out':baseline,
        'nearest_ratio':float(values.mean()/baseline),
        'equal_archive_size':size==19,
        'distribution_check':energy_test(x,y) if len(x)>1 else None,
        'mean_features':{'ours':dict(zip(FEATURES,map(float,x.mean(axis=0)))),
                         'autumn':dict(zip(FEATURES,map(float,y.mean(axis=0))))},
        'limitations':['Behavior descriptors do not measure human interest or mechanism coverage.',
                      'Only 20 public AutumnBench worlds are compared.',
                      'Nearest distances use equal candidate counts only when at least 19 generated worlds are supplied.',
                      'The distribution test is exploratory, unadjusted and uses selected worlds.'],
        'source':'fresh generated-world probes' if args.worlds else 'frozen existing probe descriptors'}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (args.out/'features.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['group','world',*FEATURES])
        for group,rows in [('ours',ours),('autumn',original)]:
            for row in rows:writer.writerow([group,row['name'],*[row['features'][k] for k in FEATURES]])
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    positions=np.arange(10)
    for a,offset,label in [(x,-.18,'Generated'),(y,.18,'AutumnBench public')]:
        axes[0].barh(positions+offset,a.mean(axis=0),height=.34,label=label)
    axes[0].set(yticks=positions,yticklabels=[f.replace('_',' ') for f in FEATURES],xlim=(0,1))
    axes[0].invert_yaxis();axes[0].legend(fontsize=8)
    axes[1].bar(['Generated archive','Other AutumnBench'],[values.mean(),baseline])
    axes[1].set(ylabel='Nearest mean L1 distance (lower = closer)',title=f'Archive sizes: {size} vs 19')
    fig.suptitle('Behavior descriptors; not an overall quality score')
    fig.tight_layout();fig.savefig(args.out/'comparison.png',dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
