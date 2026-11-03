import argparse
from worlds import *
from generate import analyze_candidate,export,save
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise SystemExit('Choose a fresh output directory.')
    w=generate(a.seed);row,tasks,table,ab=analyze_candidate(w);save(a.out/'generation.json',row)
    if row['admitted']:export(w,row,tasks,table,a.out)
    else:
        save(a.out/'world.json',w.to_dict());(a.out/'world.sexp').write_text(compile_autumn(w),encoding='utf-8')
    print(json.dumps({'seed':a.seed,'admitted':row['admitted'],'tasks':len(tasks),'out':str(a.out.resolve())}))
