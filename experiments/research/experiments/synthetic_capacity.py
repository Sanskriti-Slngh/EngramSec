"""CPU pilot. Run from project root: python -m experiments.synthetic_capacity [--smoke]."""
import argparse, csv, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.tree import DecisionTreeClassifier
from src.adapters import MLP, train_update, fit_coefficients, combine
from src.selection import gradient, retrieve, features

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
DEVICE = torch.device('cpu')
RANKS = [0,1,2,4]
PROBE_SIZE = 64
PRIMITIVE_STEPS = 300

def mse(model, x, y, w=None):
    with torch.no_grad(): return F.mse_loss(model(x, w), y).item()

def task_delta(primitives, rank, gen, category):
    # Inputs and labels reveal no category; all novel factors are projected into
    # the complement of the primitive left and right vector spaces.
    coef = torch.randn(6, generator=gen) * .55
    keep = torch.randperm(6, generator=gen)[:2]
    mask = torch.zeros(6); mask[keep] = 1
    coef *= mask
    if category == 'distractor': coef *= 0
    result = torch.einsum('k,kij->ij', coef, primitives)
    if rank:
        left = torch.cat([torch.linalg.svd(p, full_matrices=False).U[:,:2] for p in primitives], 1)
        right = torch.cat([torch.linalg.svd(p, full_matrices=False).Vh[:2].T for p in primitives], 1)
        ql = torch.linalg.qr(left).Q; qr = torch.linalg.qr(right).Q
        a = torch.randn(64, rank, generator=gen); b = torch.randn(64, rank, generator=gen)
        a = torch.linalg.qr(a-ql@(ql.T@a)).Q[:,:rank]
        b = torch.linalg.qr(b-qr@(qr.T@b)).Q[:,:rank]
        result += (a @ b.T) * 1.5
    return result

def run(seed, smoke=False):
    torch.manual_seed(seed); np.random.seed(seed); gen = torch.Generator().manual_seed(seed+12345)
    model = MLP().to(DEVICE).eval()
    for p in model.parameters(): p.requires_grad_(False)
    # Mutually orthogonal factors make primitive update directions distinguishable.
    ql = torch.linalg.qr(torch.randn(64,12,generator=gen)).Q
    qr = torch.linalg.qr(torch.randn(64,12,generator=gen)).Q
    primitives = torch.stack([1.5 * ql[:,2*i:2*i+2] @ qr[:,2*i:2*i+2].T for i in range(6)])
    xtrain = torch.randn(384,32,generator=gen)
    updates=[]; primitive_errors=[]
    for p in primitives:
        with torch.no_grad(): y = model(xtrain,p)
        u = train_update(model,xtrain,y,2,steps=120 if smoke else PRIMITIVE_STEPS)
        updates.append(u); primitive_errors.append(mse(model,xtrain,y,u))
    updates = torch.stack(updates)
    records=[]; rows=[]
    cats = [('pure',0),('small',1),('moderate',2),('large',4),('distractor',4)]
    for split, count in [('calibration',1 if smoke else 5),('test',1 if smoke else 3)]:
      for cat, rank in cats:
       for n in range(count):
        delta=task_delta(primitives,rank,gen,cat)
        x=torch.randn(384,32,generator=gen)
        with torch.no_grad(): y=model(x,delta); effect=mse(model,x,y)
        support=(x[:64],y[:64]); probe=(x[64:64+PROBE_SIZE],y[64:64+PROBE_SIZE]); val=(x[128:256],y[128:256]); test=(x[256:],y[256:])
        t=time.perf_counter(); g=gradient(model,*probe); idx=retrieve(g,updates,3); retrieve_time=time.perf_counter()-t
        selected=updates[idx]; t=time.perf_counter(); c=fit_coefficients(model,*support,selected,steps=80 if smoke else 160); coeff_time=time.perf_counter()-t
        offset=combine(selected,c); t=time.perf_counter(); gp=gradient(model,*probe,offset=offset); f=features(gp,selected); feature_time=time.perf_counter()-t
        candidates={0:offset}; times={0:0.}
        for r in RANKS[1:]:
            t=time.perf_counter(); candidates[r]=offset+train_update(model,*support,r,steps=100 if smoke else 220,offset=offset); times[r]=time.perf_counter()-t
        valerr={r:mse(model,*val,w) for r,w in candidates.items()}; best=min(valerr.values())
        # Practical sufficiency: within 10% of best validation MSE + a fixed
        # absolute numerical tolerance, never consulting final test.
        sufficient=next(r for r in RANKS if valerr[r] <= best*1.1+1e-6)
        rec=dict(seed=seed,split=split,category=cat,constructed_rank=rank,empirical_rank=sufficient,feature0=f[0].item(),feature1=f[1].item(),feature2=f[2].item(),effect=effect,selected=','.join(map(str,idx.tolist())))
        records.append(rec)
        methods={'base':(None,0,0.), 'selected_reuse':(offset,3,retrieve_time+coeff_time)}
        t=time.perf_counter(); allc=fit_coefficients(model,*support,updates,steps=80 if smoke else 160); methods['all_reuse']=(combine(updates,allc),6,time.perf_counter()-t)
        t=time.perf_counter(); ridx=torch.randperm(6,generator=gen)[:3]; rc=fit_coefficients(model,*support,updates[ridx],steps=80 if smoke else 160); methods['random_reuse']=(combine(updates[ridx],rc),3,time.perf_counter()-t)
        t=time.perf_counter(); singles=[]
        for j in range(6):
            sc=fit_coefficients(model,*support,updates[j:j+1],steps=80 if smoke else 160); sw=combine(updates[j:j+1],sc); singles.append((mse(model,*val,sw),sw))
        methods['best_single']=(min(singles,key=lambda a:a[0])[1],1,time.perf_counter()-t)
        for r in [2,4,8]:
            t=time.perf_counter(); w=train_update(model,*support,r,steps=100 if smoke else 220); methods[f'independent_{r}']=(w,r*128,time.perf_counter()-t)
        oracle=min(valerr,key=valerr.get); methods['oracle']=(candidates[oracle],3+oracle*128,retrieve_time+coeff_time+feature_time+sum(times.values()))
        for name,(w,params,sec) in methods.items():
            rows.append({**rec,'method':name,'test_mse':mse(model,*test,w),'new_params':params,'seconds':sec,'retrieval_seconds':retrieve_time if name in ('selected_reuse','oracle') else 0.,'coefficient_seconds':coeff_time if name in ('selected_reuse','oracle') else 0.,'probe_seconds':feature_time if name=='oracle' else 0.,'train_seconds':sum(times.values()) if name=='oracle' else 0.,'predicted_rank':oracle if name=='oracle' else ''})
        rec['_candidates']=candidates; rec['_times']=times; rec['_test']=test; rec['_base_time']=retrieve_time+coeff_time+feature_time; rec['_parts']=(retrieve_time,coeff_time,feature_time)
        print(f'seed {seed} {split} {cat} {n} sufficient={sufficient} effect={effect:.6f}',flush=True)
    cal=[r for r in records if r['split']=='calibration']; testrecs=[r for r in records if r['split']=='test']
    for mode,cols in [('scalar',[0]),('spectrum',[0,1,2])]:
        X=[[r[f'feature{i}'] for i in cols] for r in cal]; Y=[r['empirical_rank'] for r in cal]
        tree=DecisionTreeClassifier(max_depth=2,min_samples_leaf=2 if not smoke else 1,random_state=seed).fit(X,Y)
        for rec in testrecs:
            t=time.perf_counter(); pred=int(tree.predict([[rec[f'feature{i}'] for i in cols]])[0]); prediction_time=time.perf_counter()-t
            parts=rec['_parts']; w=rec['_candidates'][pred]; clean={k:v for k,v in rec.items() if not k.startswith('_')}
            rows.append({**clean,'method':'predicted_'+mode,'test_mse':mse(model,*rec['_test'],w),'new_params':3+pred*128,'seconds':rec['_base_time']+rec['_times'][pred]+prediction_time,'retrieval_seconds':parts[0],'coefficient_seconds':parts[1],'probe_seconds':parts[2]+prediction_time,'train_seconds':rec['_times'][pred],'predicted_rank':pred})
    return rows, primitive_errors

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--smoke',action='store_true'); ap.add_argument('--seeds',default='0,1,2'); ap.add_argument('--probe-size',type=int,default=64,choices=[16,32,64]); ap.add_argument('--primitive-steps',type=int,default=300); ap.add_argument('--tag',default=None); args=ap.parse_args()
    global PROBE_SIZE, PRIMITIVE_STEPS
    PROBE_SIZE, PRIMITIVE_STEPS = args.probe_size, args.primitive_steps
    out=Path('results'); out.mkdir(exist_ok=True); rows=[]; errors={}
    for seed in ([0] if args.smoke else map(int,args.seeds.split(','))):
        r,e=run(seed,args.smoke); rows+=r; errors[seed]=e
    tag=args.tag or ('smoke' if args.smoke else 'synthetic')
    with (out/f'{tag}.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    (out/f'{tag}_metadata.json').write_text(json.dumps({'primitive_train_mse':errors,'device':'cpu','threads':1,'probe_size':PROBE_SIZE,'primitive_steps':PRIMITIVE_STEPS,'sufficiency':'validation MSE <= 1.1 * best + 1e-6','torch':torch.__version__},indent=2))
if __name__=='__main__': main()
