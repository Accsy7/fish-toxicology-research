"""Generic protein graph rendering. Scientific names, directions and observations are data."""
from pathlib import Path
import numpy as np
import plot_primitives as old
from matplotlib.patches import Ellipse, Polygon, Rectangle, FancyArrowPatch, PathPatch
from matplotlib.path import Path as MPath
plt,MM,panel,out,score_matrix=old.plt,old.MM,old.panel,old.out,old.score_matrix
INK='#27313A';EDGE='#69747C';BLUE='#D2E6F1';BLUE_INK='#195E87';PURPLE='#795D96'

def rounded_path(points,radius=1.2):
    pts=np.array(points,dtype=float);verts=[pts[0]];codes=[MPath.MOVETO]
    for i in range(1,len(pts)-1):
        a,b,c=pts[i-1],pts[i],pts[i+1];u=b-a;v=c-b
        if np.linalg.norm(u)==0 or np.linalg.norm(v)==0:continue
        r=min(radius,np.linalg.norm(u)/3,np.linalg.norm(v)/3)
        before=b-u/np.linalg.norm(u)*r;after=b+v/np.linalg.norm(v)*r
        verts.extend([before,b,after]);codes.extend([MPath.LINETO,MPath.CURVE3,MPath.CURVE3])
    verts.append(pts[-1]);codes.append(MPath.LINETO)
    return MPath(verts,codes)

def relation(ax,e):
    pts=e['points'];kind=e['kind'];path=rounded_path(pts)
    arrow=kind in ['activation','regulation','indirect']
    linestyle=(0,(2.2,2)) if kind=='indirect' else '-'
    obj=FancyArrowPatch(path=path,arrowstyle='-|>' if arrow else '-',mutation_scale=6,
        linewidth=.68,color=EDGE,linestyle=linestyle,zorder=1)
    obj.set_gid('relation-'+e['id']);ax.add_patch(obj)
    if kind=='inhibition':
        v=np.array(pts[-1])-pts[-2];v=v/np.linalg.norm(v);normal=np.array([-v[1],v[0]])*1.7
        a=np.array(pts[-1])-normal;b=np.array(pts[-1])+normal
        ax.plot([a[0],b[0]],[a[1],b[1]],color=EDGE,lw=.85,zorder=2)[0].set_gid('relation-'+e['id']+'-bar')

def protein(ax,n,observations,calculation):
    x,y=n['xy'];w,h=n['size'];role=n['role']
    changed=any(a['measurement_level'] not in ['interaction_interruption','phosphorylation_unchanged'] for a in observations)
    face=BLUE if changed else 'white';outline=PURPLE if calculation else EDGE
    props=dict(facecolor=face,edgecolor=outline,linewidth=1.25 if calculation else .65,zorder=3)
    if role=='ligand':shape=Polygon([(x-w/2,y),(x,y-h/2),(x+w/2,y),(x,y+h/2)],closed=True,**props)
    elif role=='tf':shape=Rectangle((x-w/2,y-h/2),w,h,**props)
    else:shape=Ellipse((x,y),w,h,**props)
    shape.set_gid('protein-'+n['id']+'-shape');ax.add_patch(shape)
    fs=8 if len(n['label'])<12 else 7
    ax.text(x,y,n['label'],size=fs,ha='center',va='center',color=INK,zorder=5).set_gid('protein-'+n['id'])
    for a in observations:
        if a['measurement_level']=='interaction_interruption':continue
        yy=y+h/2+3.2
        ax.text(x,yy,a['label'],ha='center',va='center',size=6.6,color=BLUE_INK if changed else '#6B7479',
            bbox=dict(fc='white',ec='none',pad=.18),zorder=5).set_gid('evidence-'+a['id'])

def protein_network(ax,data,panel_id,ids,extent):
    ax.set(xlim=extent[:2],ylim=extent[2:][::-1]);ax.set_aspect('equal');ax.axis('off')
    for e in data['edges']:
        if e['panel']==panel_id and (not e['candidate_id'] or e['candidate_id'] in ids):relation(ax,e)
    for n in data['nodes']:
        if n['panel']!=panel_id:continue
        anns=[a for a in data['annotations'] if a['node']==n['id'] and a['candidate_id'] in ids]
        protein(ax,n,anns,n['id'] in data['calculation_nodes'])
    node_ids={n['id'] for n in data['nodes'] if n['panel']==panel_id}
    for a in data['annotations']:
        if a['node'] in node_ids and a['candidate_id'] in ids and a.get('leader_points'):
            x,y=a['xy'];ax.text(x,y,a['label'],ha='center',va='center',size=8,weight='bold',color=BLUE_INK).set_gid('evidence-'+a['id'])
            relation(ax,{'id':'assay_interruption','points':a['leader_points'],'kind':'inhibition'})
    for note in data['panel_notes']:
        if note['panel']==panel_id and (not note['candidate_id'] or note['candidate_id'] in ids):
            ax.text(*note['xy'],note['text'],ha='center',va='center',size=6.8,color=BLUE_INK if note['candidate_id'] else INK)

def legend(ax):
    ax.set(xlim=(0,113),ylim=(31,0));ax.set_aspect('equal');ax.axis('off')
    for x,kind,text in [(0,'activation','激活／转录调控'),(61,'inhibition','抑制'),(0,'association','结合／组装'),(61,'indirect','间接联系')]:
        y=3 if kind in ['activation','inhibition'] else 11
        relation(ax,{'id':'legend_'+kind,'points':[[x,y],[x+10,y]],'kind':kind})
        ax.text(x+13,y,text,va='center',size=6.8)
    ax.add_patch(Ellipse((5,21),10,4,fc=BLUE,ec=EDGE,lw=.65));ax.text(13,21,'相应检测下降',va='center',size=6.8)
    ax.add_patch(Ellipse((66,21),10,4,fc='white',ec=PURPLE,lw=1.25));ax.text(74,21,'受体计算对象',va='center',size=6.8)
    ax.text(0,30,'菱形：配体；方形：转录调节；椭圆：其他蛋白／复合体。',size=6.4,color=EDGE,va='center')

def draw_plate(d,network,ids,destination):
    fig=plt.figure(figsize=(180/MM,200/MM))
    box=lambda x,y,w,h:[x/180,y/200,w/180,h/200]
    for letter,rect in [('a',(5,48,111,139)),('b',(124,113,50,73)),('c',(124,69,50,35))]:
        ps=network['panel_specs'][letter]
        subtitle=ps['subtitle'] if not ps['candidate_id'] or ps['candidate_id'] in ids else ps['inactive_subtitle']
        ax=panel(fig,box(*rect),letter,ps['title'],subtitle)
        protein_network(ax,network,letter,ids,ps['extent'])
    l=fig.add_axes(box(5,13,111,31));l.set_gid('network-legend');legend(l)
    q=panel(fig,box(130,17,44,30),'d',network['panel_specs']['d']['title'],header_y=1.48)
    im=score_matrix(q,d['comparisons'],ids,d['receptors'],d['config']['names'],d['config']['colors'])
    q.tick_params(axis='x',labelsize=6.4,pad=4);q.tick_params(axis='y',labelsize=7,pad=4)
    cb=fig.colorbar(im,cax=fig.add_axes(box(130,11,44,2)),orientation='horizontal',ticks=[-2,0,2.5])
    cb.ax.set_gid('calculation-colorbar');cb.ax.tick_params(labelsize=6,length=2,pad=2)
    cb.solids.set_rasterized(False)
    fig.text(124/180,1.5/200,'Δ＝参照 − 候选（kcal/mol）',size=6.5)
    out(fig,destination)
    return fig
