"""Render a reviewed projection and protein graph using the approved visual grammar."""
from pathlib import Path
import argparse,json
from network_components import draw_plate
def main():
    p=argparse.ArgumentParser();p.add_argument('projection',type=Path);p.add_argument('network',type=Path);p.add_argument('--ids',nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();read=lambda f:json.loads(f.read_text('utf-8-sig'));d=read(a.projection);n=read(a.network)
    if not set(a.ids)<=set(d['config']['names']):raise ValueError('Unknown candidate identity')
    for r in d['comparisons']:
        if r['candidate_id'] in a.ids and not -2<=r['delta']<=2.5:raise ValueError('Data exceed the accepted score scale; explicitly adapt the scale before rendering.')
    draw_plate(d,n,a.ids,a.output)
if __name__=='__main__':main()
