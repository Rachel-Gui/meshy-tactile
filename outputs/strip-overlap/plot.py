import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
out=Path(__file__).parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
a=np.linspace(.1,89.9,4000)
y=1/np.sin(np.deg2rad(2*a))
fig,axes=plt.subplots(1,2,figsize=(10,4.3),layout='constrained')
for ax in axes:
 ax.plot(a,y,color='#176B9A',lw=2.3)
 ax.axvline(45,color='#999999',lw=1,ls='--')
 ax.scatter([45],[1],color='#D55E00',zorder=3)
 ax.set_xlabel(r'Half-angle $\alpha=\theta/2$ (degrees)')
 ax.set_ylabel(r'Normalized overlap area $A/(w_1w_2)$')
 ax.grid(alpha=.18)
axes[0].set(xlim=(0,90),ylim=(0,10),xticks=np.arange(0,91,15),title='Full half-angle range (0° < α < 90°)')
axes[0].text(45,2.3,'Minimum: α = 45°\nA = w₁w₂',ha='center',fontsize=10)
axes[1].set(xlim=(15,75),ylim=(.95,2.1),xticks=np.arange(15,76,15),title='Detail near the minimum')
fig.suptitle(r'Strip overlap: $A=w_1w_2/|\sin(2\alpha)|$',fontsize=15)
fig.savefig(out/'half-angle-overlap.png',dpi=300)
fig.savefig(out/'half-angle-overlap.svg')
fig.savefig(out/'half-angle-overlap.pdf')
print(out.resolve()/'half-angle-overlap.png')
