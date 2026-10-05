import argparse
import json
from pathlib import Path
from .engine import Engine
from .adapters import XAdapter,get_adapter
from .contracts import Review,PLATFORMS
from .integration import LocalRegistrySink, AgentOpsSink

def main():
    p=argparse.ArgumentParser(description='Local multi-platform official intelligence — no account operations')
    p.add_argument('--data',default='data')
    sub=p.add_subparsers(dest='command',required=True)
    monitor=sub.add_parser('monitor'); monitor.add_argument('--force',action='store_true')
    monitor.add_argument('--platform',choices=PLATFORMS+('all',),default='X')
    review=sub.add_parser('review'); review.add_argument('file')
    sub.add_parser('status')
    replay=sub.add_parser('replay'); replay.add_argument('--until',type=int)
    distribute=sub.add_parser('distribute'); distribute.add_argument('--inbox',required=True); distribute.add_argument('--consumer',required=True)
    ops=sub.add_parser('ops'); ops.add_argument('--source',required=True); ops.add_argument('--inbox',required=True)
    radar=sub.add_parser('import-radar'); radar.add_argument('--file',required=True)
    serve=sub.add_parser('serve'); serve.add_argument('--port',type=int,default=8768)
    args=p.parse_args(); e=Engine(args.data)
    try:
        if args.command=='monitor':
            selected=PLATFORMS if args.platform=='all' else (args.platform,)
            result=[r for platform in selected for r in e.monitor(get_adapter(platform),args.force)]
        elif args.command=='import-radar':
            from .legacy_radar import LegacyRadarAdapter
            result=LegacyRadarAdapter().collect(e,args.file)
        elif args.command=='review': result=e.verify(Review(**json.loads(Path(args.file).read_text(encoding='utf-8'))))
        elif args.command=='replay': result=e.replay(args.until)
        elif args.command=='distribute': result=e.distribute(LocalRegistrySink(args.inbox),args.consumer)
        elif args.command=='ops': result=e.ops(AgentOpsSink(args.source,args.inbox))
        elif args.command=='serve':
            from .web import serve
            e.store.close(); serve(Path(args.data).resolve(),args.port); return
        else: result=e.envelope()
        degraded=args.command=='monitor' and any(r['status']=='UNAVAILABLE' for r in result)
        if args.command=='import-radar':
            result={k:result[k] for k in ('status','action_eligible','version','snapshot_hash','source')}
        print(json.dumps({'code':1 if degraded else 0,'msg':'degraded' if degraded else 'ok','data':result},ensure_ascii=False,indent=2))
    finally:
        if args.command!='serve': e.store.close()

if __name__=='__main__': main()
