"""Portable approved plotting primitives; scientific values come from reviewed inputs."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
for name in ['arial.ttf','arialbd.ttf','msyh.ttc']:
    font=Path('C:/Windows/Fonts')/name
    if font.is_file(): font_manager.fontManager.addfont(str(font))
plt.rcParams.update({'font.family':['Arial','Microsoft YaHei'],'font.size':8,'axes.labelsize':8,'axes.linewidth':.65,'xtick.labelsize':7,'ytick.labelsize':7.5,'lines.linewidth':.8,'figure.facecolor':'white','savefig.facecolor':'white','svg.fonttype':'none','pdf.fonttype':42,'text.color':'#242C32','axes.labelcolor':'#242C32'})
INK='#242C32';MUTED='#67737B';RULE='#D5DDE1';MM=25.4


def panel(fig,box,letter,title,subtitle=None,header_y=None):
 ax=fig.add_axes(box);ax.set_gid('panel-'+letter)
 y=1 if header_y is None else header_y;offset=(13 if subtitle else 5) if header_y is None else 0
 ax.annotate(letter,(0,y),xycoords='axes fraction',xytext=(0,offset),textcoords='offset points',weight='bold',size=10.5,va='bottom')
 ax.annotate(title,(0,y),xycoords='axes fraction',xytext=(17,offset),textcoords='offset points',weight='bold',size=8.5,va='bottom')
 if subtitle:ax.annotate(subtitle,(0,1),xycoords='axes fraction',xytext=(17,1),textcoords='offset points',color=MUTED,size=7,va='bottom')
 return ax

def out(fig,path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 for ext in ['svg','pdf','png']:fig.savefig(path.with_suffix('.'+ext),dpi=350)
 plt.close(fig)

def score_matrix(ax,rows,ids,receptors,names,palette):
 mat=np.array([[next(r['delta'] for r in rows if r['candidate_id']==cid and r['receptor_id']==t['id']) for t in receptors] for cid in ids])
 cm=colors.LinearSegmentedColormap.from_list('score',['#487B9A','#F9FAFA','#BC7755']);norm=colors.TwoSlopeNorm(vmin=-2,vcenter=0,vmax=2.5)
 im=ax.pcolormesh(np.arange(mat.shape[1]+1)-.5,np.arange(mat.shape[0]+1)-.5,mat,cmap=cm,norm=norm,edgecolors='white',linewidth=1.5)
 ax.set_xlim(-.5,mat.shape[1]-.5);ax.set_ylim(mat.shape[0]-.5,-.5)
 ax.set_yticks(range(len(ids)),[names[x] for x in ids]);ax.set_xticks(range(len(receptors)),[t['label']+'\n'+t['species_label'] for t in receptors]);ax.tick_params(length=0,pad=5)
 ax.xaxis.tick_top();ax.tick_params(axis='x',labelsize=7)
 for (i,j),v in np.ndenumerate(mat):
  r=next(r for r in rows if r['candidate_id']==ids[i] and r['receptor_id']==receptors[j]['id'])
  t=ax.text(j,i,f'{v:+.2f}'+('†' if not r['classification_stable'] else ''),ha='center',va='center',size=8,color='white' if abs(v)>1.35 else INK);t.set_gid('candidate-'+ids[i]+f'-score-{j}')
 for s in ax.spines.values():s.set_visible(False)
 ax.set_xticks(np.arange(-.5,len(receptors),1),minor=True);ax.set_yticks(np.arange(-.5,len(ids),1),minor=True);ax.grid(which='minor',color='white',linewidth=2);ax.tick_params(which='minor',length=0)
 return im
