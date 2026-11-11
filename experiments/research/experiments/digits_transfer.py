"""Stratified source-image splits, deterministic transforms, CPU-only digit pilot."""
import argparse,csv,json,time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from scipy.ndimage import shift, rotate, gaussian_filter
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from src.adapters import MLP, train_update, fit_coefficients, combine
from src.selection import gradient,retrieve,features

torch.set_num_threads(1); torch.set_num_interop_threads(1); DEVICE=torch.device('cpu')

def transform(images, ops):
    out=[]
    for image in images:
        a=image.copy()
        for op in ops:
            if op=='left': a=shift(a,(0,-1),order=1,mode='constant',prefilter=False)
            elif op=='right': a=shift(a,(0,1),order=1,mode='constant',prefilter=False)
            elif op=='up': a=shift(a,(-2,0),order=1,mode='constant',prefilter=False)
            elif op=='plus': a=rotate(a,15,reshape=False,order=1,mode='constant',prefilter=False)
            elif op=='minus': a=rotate(a,-15,reshape=False,order=1,mode='constant',prefilter=False)
            elif op=='strongrot': a=rotate(a,45,reshape=False,order=1,mode='constant',prefilter=False)
            elif op=='contrast': a=a*.45
            elif op=='blur': a=gaussian_filter(a,.65)
        out.append(a.reshape(-1))
    return torch.tensor(np.array(out),dtype=torch.float32)

def acc(model,x,y,w=None):
    with torch.no_grad(): return (model(x,w).argmax(1)==y).float().mean().item()
def loss(model,x,y,w=None):
    with torch.no_grad(): return F.cross_entropy(model(x,w),y).item()

def run(seed,smoke=False):
    torch.manual_seed(seed); np.random.seed(seed)
    data=load_digits(); images=data.images/16.; labels=data.target
    train,rest=train_test_split(np.arange(len(labels)),test_size=.4,stratify=labels,random_state=seed)
    val,test=train_test_split(rest,test_size=.5,stratify=labels[rest],random_state=seed)
    assert not(set(train)&set(val) or set(train)&set(test) or set(val)&set(test))
    rng=np.random.RandomState(seed); train=rng.permutation(train)
    support,probe=train[:240],train[240:360]
    Y=torch.tensor(labels,dtype=torch.long)
    model=MLP((64,128,64,10)).to(DEVICE); opt=torch.optim.Adam(model.parameters(),lr=.005)
    X=transform(images,[])
    for _ in range(100 if smoke else 300):
        opt.zero_grad(); l=F.cross_entropy(model(X[train]),Y[train]); l.backward(); opt.step()
    model.eval()
    for p in model.parameters(): p.requires_grad_(False)
    primitives={'left':('left',),'right':('right',),'plus':('plus',),'minus':('minus',),'contrast':('contrast',),'blur':('blur',)}
    updates=[]; old=[]
    for name,ops in primitives.items():
        xx=transform(images,ops); u=train_update(model,xx[train],Y[train],4,steps=90 if smoke else 180,loss='ce'); updates.append(u); old.append(acc(model,xx[test],Y[test],u))
    updates=torch.stack(updates)
    tasks=[('cal_lr',('left','minus')),('cal_rb',('right','blur')),('cal_pc',('plus','contrast')),('cal_lc',('left','contrast')),('cal_mb',('minus','contrast')),('cal_pb',('plus','blur')),('left_plus',('left','plus')),('right_contrast',('right','contrast')),('minus_blur',('minus','blur')),('left_blur',('left','blur')),('strongrot',('strongrot',)),('up',('up',))]
    if smoke: tasks=tasks[:2]+tasks[6:8]
    recs=[]; rows=[]
    for ti,(name,ops) in enumerate(tasks):
        split='calibration' if name.startswith('cal_') else 'test'; x=transform(images,ops)
        t=time.perf_counter(); g=gradient(model,x[probe],Y[probe],loss='ce'); idx=retrieve(g,updates,3); rt=time.perf_counter()-t
        selected=updates[idx]; t=time.perf_counter(); c=fit_coefficients(model,x[support],Y[support],selected,steps=80,loss='ce'); ct=time.perf_counter()-t; offset=combine(selected,c)
        t=time.perf_counter(); gp=gradient(model,x[probe],Y[probe],offset=offset,loss='ce'); ft=features(gp,selected); pt=time.perf_counter()-t
        cand={0:offset}; times={0:0.}
        for rank in [1,2,4]:
            t=time.perf_counter(); cand[rank]=offset+train_update(model,x[support],Y[support],rank,steps=80 if smoke else 140,offset=offset,loss='ce'); times[rank]=time.perf_counter()-t
        vl={r:loss(model,x[val],Y[val],w) for r,w in cand.items()}; best=min(vl.values()); sufficient=next(r for r in [0,1,2,4] if vl[r]<=best*1.05+.005)
        rec={'seed':seed,'split':split,'task':name,'empirical_rank':sufficient,'feature0':ft[0].item(),'feature1':ft[1].item(),'feature2':ft[2].item()}; recs.append((rec,cand,times,(rt,ct,pt),x))
        methods={'base':(None,0,0.),'selected_reuse':(offset,3,rt+ct)}
        t=time.perf_counter(); ac=fit_coefficients(model,x[support],Y[support],updates,steps=80,loss='ce'); methods['all_reuse']=(combine(updates,ac),6,time.perf_counter()-t)
        t=time.perf_counter(); ri=torch.randperm(6)[:3]; rc=fit_coefficients(model,x[support],Y[support],updates[ri],steps=80,loss='ce'); methods['random_reuse']=(combine(updates[ri],rc),3,time.perf_counter()-t)
        t=time.perf_counter(); single=[]
        for j in range(6):
            c1=fit_coefficients(model,x[support],Y[support],updates[j:j+1],steps=80,loss='ce'); w=combine(updates[j:j+1],c1); single.append((loss(model,x[val],Y[val],w),w))
        methods['best_single']=(min(single,key=lambda a:a[0])[1],1,time.perf_counter()-t)
        for rank in [4,8]:
            t=time.perf_counter(); w=train_update(model,x[support],Y[support],rank,steps=80 if smoke else 140,loss='ce'); methods[f'independent_{rank}']=(w,rank*(128+64),time.perf_counter()-t)
        orank=min(vl,key=vl.get); methods['oracle']=(cand[orank],3+orank*192,rt+ct+pt+sum(times.values()))
        for method,(w,params,sec) in methods.items(): rows.append({**rec,'method':method,'accuracy':acc(model,x[test],Y[test],w),'new_params':params,'seconds':sec,'predicted_rank':orank if method=='oracle' else ''})
        print(f'{seed} {split} {name} sufficient={sufficient}',flush=True)
    cal=[r for r in recs if r[0]['split']=='calibration']; testrecs=[r for r in recs if r[0]['split']=='test']
    for mode,cols in [('scalar',[0]),('spectrum',[0,1,2])]:
        tree=DecisionTreeClassifier(max_depth=2,min_samples_leaf=1,random_state=seed).fit([[a[0][f'feature{i}'] for i in cols] for a in cal],[a[0]['empirical_rank'] for a in cal])
        for rec,cand,times,parts,x in testrecs:
            t=time.perf_counter(); rank=int(tree.predict([[rec[f'feature{i}'] for i in cols]])[0]); elapsed=time.perf_counter()-t
            rows.append({**rec,'method':'predicted_'+mode,'accuracy':acc(model,x[test],Y[test],cand[rank]),'new_params':3+rank*192,'seconds':sum(parts)+times[rank]+elapsed,'predicted_rank':rank})
    return rows,{'old_task_accuracy':dict(zip(primitives,old)),'clean_test_accuracy':acc(model,X[test],Y[test]),'library_params':6*4*192,'base_params':sum(p.numel() for p in model.parameters()),'split_counts':[len(train),len(val),len(test)]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--smoke',action='store_true'); ap.add_argument('--seeds',default='0,1,2'); a=ap.parse_args(); rows=[]; meta={}
    for seed in ([0] if a.smoke else map(int,a.seeds.split(','))):
        r,m=run(seed,a.smoke); rows+=r; meta[seed]=m
    out=Path('results'); out.mkdir(exist_ok=True); tag='digits_smoke' if a.smoke else 'digits'
    with (out/f'{tag}.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    (out/f'{tag}_metadata.json').write_text(json.dumps(meta,indent=2))
if __name__=='__main__': main()
