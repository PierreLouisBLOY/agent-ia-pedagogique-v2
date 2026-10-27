"""Disposable UI/crash host for qualification, never a product entry point."""
import argparse
import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('synthetic_323a_host_fixture',Path(__file__).with_name('normal_on_323a_fixture.py'))
f=importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--control-root',type=Path,required=True)
    parser.add_argument('--scenario',choices=('complete','crash-after-reservation'),default='complete')
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    assert os.environ.get('OPENAI_API_KEY')==f.FAKE_KEY
    assert not os.isatty(0)
    args.control_root.mkdir(parents=True,exist_ok=True)
    control=f.Control()
    control.transport_wait_seconds=1800
    control.release.clear()
    patch=pytest.MonkeyPatch()
    real_bind=f.profile_factory.P0NormalProductComposition.bind
    def observe(owner,service,endpoint):
        real_bind(owner,service,endpoint)
        actual=owner.generation.progress
        def progress(phase,evidence):
            if actual is not None:
                actual(phase,evidence)
            if args.scenario=='crash-after-reservation' and phase=='BUDGET_RESERVED':
                (args.control_root/'CRASH_RESERVED.json').write_text(json.dumps({
                    'phase':phase,'evidence':dict(evidence),'transport_calls':control.calls,
                    'synthetic':True,'real_history_writes':0}),encoding='utf-8')
                os._exit(92)  # Exit this disposable test host, never a user process.
        owner.generation.progress=progress
    patch.setattr(f.profile_factory.P0NormalProductComposition,'bind',observe)
    existing=None
    if args.reuse:
        path=args.root/'SYNTHETIC-envelope.json'
        envelope=json.loads(path.read_bytes())
        profile=envelope['profile']
        rt=profile['runtime']
        existing=(path,f.Read15RuntimeTarget(Path(rt['path']),Path(rt['data_root']),rt['sha256']),
                  Path(profile['saved_root']),Path(profile['receipt_root']))
    try:
        with f.running(args.root,patch,control,existing=existing) as (port,config):
            (args.control_root/'READY.json').write_text(json.dumps({'port':port,'url':f'http://127.0.0.1:{port}/',
                'source_root':str(f.ROOT),'scenario':args.scenario,'synthetic':True,
                'console':False,'real_key_read':False,'provider_calls':0,
                'root':str(args.root),'configuration_path':str(config[0])}),encoding='utf-8')
            deadline=time.monotonic()+3600
            while not (args.control_root/'STOP.flag').exists() and time.monotonic()<deadline:
                if (args.control_root/'RELEASE.flag').exists():
                    control.release.set()
                if control.entered.is_set() and not (args.control_root/'TRANSPORT_ENTERED.json').exists():
                    (args.control_root/'TRANSPORT_ENTERED.json').write_text(json.dumps({
                        'transport_double_attempts':control.calls,'provider_calls':0,
                        'phase':'TRANSPORT_ENTERED','source_root':str(f.ROOT)}),encoding='utf-8')
                time.sleep(.1)
            (args.control_root/'RESULT.json').write_text(json.dumps({'transport_double_attempts':control.calls,
                'transport_double_builds':control.builds,'prompt_calls':control.prompt_calls,
                'provider_calls':0,'real_history_writes':0,'service_closed_by_owned_fixture':True}),encoding='utf-8')
    finally:
        patch.undo()

if __name__=='__main__':
    main()
