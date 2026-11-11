"""Generate figures directly from the raw final-test CSV files."""
import csv
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('results')
fig,axes=plt.subplots(1,2,figsize=(12,4.5))
for ax,name,metric in [(axes[0],'synthetic','test_mse'),(axes[1],'digits','accuracy')]:
    data=[r for r in csv.DictReader((p/f'{name}.csv').open()) if r['split']=='test']
    for method in sorted({r['method'] for r in data}):
        if method=='oracle': continue
        group=[r for r in data if r['method']==method]
        x=np.mean([float(r['new_params']) for r in group]); y=np.mean([float(r[metric]) for r in group])
        ax.scatter(x,y,s=35)
        shift = {'independent_8':(-75,-14), 'predicted_scalar':(-70,-16), 'selected_reuse':(-60,6)}.get(method, (4,3)) if name == 'synthetic' else (4,3)
        ax.annotate(method,(x,y),xytext=shift,textcoords='offset points',fontsize=7)
    ax.set_xscale('symlog',linthresh=3); ax.set_xlabel('New task trainable scalars (log-like scale)')
    ax.set_ylabel('Test MSE (lower is better)' if name=='synthetic' else 'Test accuracy (higher is better)')
    ax.set_title(name.title()); ax.grid(alpha=.2)
fig.tight_layout(); fig.savefig(p/'accuracy_vs_parameters.png',dpi=170); plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(9,4))
for ax,name in zip(axes,['synthetic','digits']):
    data=[r for r in csv.DictReader((p/f'{name}.csv').open()) if r['split']=='test' and r['method']=='predicted_spectrum']; ranks=[0,1,2,4]; c=np.zeros((4,4),dtype=int)
    for r in data: c[ranks.index(int(r['empirical_rank'])),ranks.index(int(r['predicted_rank']))]+=1
    ax.imshow(c,cmap='Blues'); ax.set_xticks(range(4),ranks); ax.set_yticks(range(4),ranks); ax.set_xlabel('Predicted rank'); ax.set_ylabel('Validation-sufficient rank'); ax.set_title(name.title())
    for i in range(4):
        for j in range(4): ax.text(j,i,str(c[i,j]),ha='center',va='center')
fig.tight_layout(); fig.savefig(p/'rank_confusion.png',dpi=170)
