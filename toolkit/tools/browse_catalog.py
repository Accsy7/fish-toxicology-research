"""Open the approved local workspace against the project's read-only catalog."""
from pathlib import Path
import argparse,json,webbrowser
from http.server import ThreadingHTTPServer
from research import ROOT,load,config_path
from serve_workspace import Handler,WorkspaceAPI

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--port',type=int,default=8771);p.add_argument('--no-open',action='store_true')
    p.add_argument('--frontend-dir',type=Path,help='独立安装的已认可数据库前端目录；软件包不附带或替换前端')
    a=p.parse_args()
    config=load(config_path(a.root));catalog=(a.root/config['database']['catalog']).resolve()
    configured=(config.get('database') or {}).get('frontend_directory')
    static=a.frontend_dir or ((a.root/configured) if configured else None)
    if static is None or not (static/'index.html').is_file():
        raise SystemExit('请通过 --frontend-dir 指定独立前端1.13.1-local.1；软件更新不会安装或替换数据库界面。')
    try:server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    except OSError:server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.catalog=catalog;server.static=static.resolve();server.api=WorkspaceAPI(catalog)
    url=f'http://127.0.0.1:{server.server_port}/?view=1&tab=search'
    print(url,flush=True)
    if not a.no_open:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
