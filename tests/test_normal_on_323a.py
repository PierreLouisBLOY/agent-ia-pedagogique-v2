"""Actual normal CLI/HTTP/factories with explicitly synthetic effects and stores."""
from __future__ import annotations

import copy
import importlib.util
import json
import threading
import time
import xml.etree.ElementTree as ET
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from secrets import token_hex
from zipfile import ZipFile

import pytest

from backend.infrastructure.composition.factories.p0_normal_profile import (
    P0NormalProductComposition,
)

spec=importlib.util.spec_from_file_location('normal_fixture_323a',Path(__file__).with_name('normal_on_323a_fixture.py'))
f=importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def call(port,method,path,body=None,nonce=None):
    status,raw=f.request(port,method,path,body,nonce)
    return status,json.loads(raw)

def prepare(port):
    status,metadata=call(port,'GET','/api/v2/p0')
    assert status==200,metadata
    nonce=metadata['data']['transport_nonce']
    status,result=call(port,'POST','/api/v2/p0/prepare',{'command_id':token_hex(16),'context':f.context(),
        'reference':{'notion_id':'notion:shared','passage_ref':f.SOURCE['passage_ref']}},nonce)
    assert status==200,result
    prepared=result['data']
    command={'command_id':token_hex(16),'preparation_ref':prepared['preparation_ref'],
             'preparation_sha256':prepared['preparation_sha256']}
    status,shown=call(port,'POST','/api/v2/p0/consent-preview',command,nonce)
    assert status==200,shown
    return nonce,command,shown['data']

def accept(command,shown):
    return {**command,'command_id':token_hex(16),'preview_sha256':shown['preview_sha256'],
        'transfer_accepted':True,'cost_bound_accepted':True}

def terminal(port,command_id):
    # Local native guards and Application persistence precede/follow the bounded
    # transport. This harness deadline is not the provider timeout (still 120s).
    deadline=time.monotonic()+300
    view={}
    while time.monotonic()<deadline:
        status,result=call(port,'GET','/api/v2/p0/commands/'+command_id)
        assert status==200,result
        view=result['data']
        if view['state']!='LOCAL_COMMAND_RUNNING':
            return view
        time.sleep(.75)
    raise AssertionError(('SYNTHETIC_COMMAND_DID_NOT_FINISH',view))

def text(raw):
    with ZipFile(BytesIO(raw)) as z:
        root=ET.fromstring(z.read('word/document.xml'))
    return ''.join(root.itertext())

def test_normal_complete_persist_modify_reopen_and_both_word_exports(tmp_path,monkeypatch):
    control=f.Control()
    with f.running(tmp_path/'case',monkeypatch,control) as (port,config):
        nonce,command,shown=prepare(port)
        assert control.calls==control.builds==control.prompt_calls==0
        decision=accept(command,shown)
        status,result=call(port,'POST','/api/v2/p0/consent-generate',decision,nonce)
        assert status==202,result
        done=terminal(port,decision['command_id'])
        assert done['state']=='LOCAL_COMMAND_COMPLETED',done
        assert done['phase']=='APPLICATION_SAVED'
        assert control.calls==control.builds==1
        parent=done['result']['view']
        publication=done['result']['publication']
        assert publication['state']=='APPLICATION_SAVED'
        status,metadata=call(port,'GET','/api/v2/conversation/saved')
        assert status==200
        r4nonce=metadata['data']['transport_nonce']
        oldpin=publication['record_sha256']
        edits={'questions':copy.deepcopy(f.CONTENT['questions']),'corrections':copy.deepcopy(f.CONTENT['corrections'])}
        edits['questions'][0]['prompt']='Citez précisément l’horaire annoncé, sans ajouter une interprétation.'
        edits['corrections'][0]['expected_answer']='SENTINELLE_PROFESSEUR : l’horaire écrit est 17 heures.'
        status,changed=call(port,'POST','/api/v2/p0/revise',{'command_id':token_hex(16),
            'production_ref':parent['production_ref'],'version_ref':parent['version_ref'],
            'bundle_sha256':parent['bundle_sha256'],'edits':edits},nonce)
        assert status==200,changed
        child=changed['data']['view']
        assert child['lineage']['parent_version_ref']==parent['version_ref']
        status,saved=call(port,'POST','/api/v2/conversation/saved',{
            'production_ref':child['production_ref'],'version_ref':child['version_ref']},r4nonce)
        assert status==200,saved
        child_pin=saved['data']['record_sha256']
        assert child_pin!=oldpin
        assert control.calls==1
    reopened=f.Control()
    with f.running(tmp_path/'case',monkeypatch,reopened,existing=config) as (port,_):
        assert reopened.calls==reopened.builds==0
        base='/api/v2/productions/'+child['production_ref']+'/versions/'
        status,opened=call(port,'GET',base+child['version_ref']+'/saved')
        assert status==200 and opened['data']['record_sha256']==child_pin
        status,parent_again=call(port,'GET',base+parent['version_ref']+'/saved')
        assert status==200 and parent_again['data']['record_sha256']==oldpin
        for kind in ('student','correction'):
            status,raw=f.request(port,'GET',base+child['version_ref']+'/word/'+kind)
            assert status==200
            body=text(raw)
            if kind=='student':
                assert edits['questions'][0]['prompt'] in body
            else:
                assert edits['corrections'][0]['expected_answer'] in body
            assert ('SENTINELLE_PROFESSEUR' in body)==(kind=='correction')
        assert reopened.calls==reopened.builds==reopened.prompt_calls==0

@pytest.mark.parametrize('scenario',['truncated','401','network','timeout'])
def test_failures_keep_one_slot_capture_and_no_replay_after_restart(tmp_path,monkeypatch,scenario):
    control=f.Control(scenario)
    with f.running(tmp_path/'case',monkeypatch,control) as (port,config):
        nonce,command,shown=prepare(port)
        decision=accept(command,shown)
        status,_=call(port,'POST','/api/v2/p0/consent-generate',decision,nonce)
        assert status==202
        done=terminal(port,decision['command_id'])
        assert done['state']=='LOCAL_COMMAND_UNCERTAIN',done
        assert control.calls==1
        slots=control.owner.generation.ledger.slots()
        assert len(slots)==1
        if scenario=='truncated':
            receipt=next(iter(control.owner.generation.adapters.values())).receipt
            assert receipt.exists('RESULT') and receipt.exists('RESPONSE_CAPTURED') and receipt.exists('PARSING_REJECTED')
    restarted=f.Control()
    with f.running(tmp_path/'case',monkeypatch,restarted,existing=config) as (port,_):
        status,listing=call(port,'GET','/api/v2/conversation/saved')
        assert status==200 and listing['data']['versions']==[]
        status,retained=call(port,'GET','/api/v2/p0/commands/'+decision['command_id'])
        assert status==200,retained
        assert retained['data']['retry_authorized'] is False
        assert retained['data']['billed_cost']=='NOT_ESTABLISHED'
        nonce,command,shown=prepare(port)
        attempted=accept(command,shown)
        status,_=call(port,'POST','/api/v2/p0/consent-generate',attempted,nonce)
        assert status==202
        denied=terminal(port,attempted['command_id'])
        assert denied['state']=='LOCAL_COMMAND_UNCERTAIN'
        assert len(restarted.owner.generation.ledger.slots())==1
        assert restarted.calls==restarted.builds==restarted.prompt_calls==0

@pytest.mark.parametrize('field',['transfer_accepted','cost_bound_accepted'])
def test_each_missing_consent_has_no_slot_or_effect(tmp_path,monkeypatch,field):
    control=f.Control()
    with f.running(tmp_path/'case',monkeypatch,control) as (port,_):
        nonce,command,shown=prepare(port)
        decision=accept(command,shown)
        decision[field]=False
        status,result=call(port,'POST','/api/v2/p0/consent-generate',decision,nonce)
        assert status==409,result
        assert control.owner.generation.ledger.slots()==[]
        assert control.calls==control.builds==0

@pytest.mark.parametrize('scenario',['missing-key','preflight','identity','expired-preview'])
def test_precommit_refusals_preserve_empty_budget(tmp_path,monkeypatch,scenario):
    control=f.Control(scenario)
    with f.running(tmp_path/'case',monkeypatch,control) as (port,_):
        nonce,command,shown=prepare(port)
        decision=accept(command,shown)
        if scenario=='preflight':
            control.token_delta=1
        elif scenario=='identity':
            decision['preparation_sha256']='0'*64
        elif scenario=='expired-preview':
            clock=control.owner.generation.clock
            control.owner.generation.clock=lambda:clock()+timedelta(minutes=16)
        status,_=call(port,'POST','/api/v2/p0/consent-generate',decision,nonce)
        assert status==202
        denied=terminal(port,decision['command_id'])
        assert denied['state']=='LOCAL_COMMAND_UNCERTAIN',denied
        assert control.owner.generation.ledger.slots()==[]
        assert control.calls==control.builds==control.prompt_calls==0
        if scenario=='missing-key':
            assert denied['code']=='P0_NORMAL_OPENAI_API_KEY_MISSING_OR_INVALID'

def test_slow_operation_two_submissions_and_consultation_stay_single_attempt(tmp_path,monkeypatch):
    control=f.Control()
    control.release.clear()
    with f.running(tmp_path/'case',monkeypatch,control) as (port,_):
        nonce,command,shown=prepare(port)
        decision=accept(command,shown)
        results=[]
        barrier=threading.Barrier(3)
        def send():
            barrier.wait()
            results.append(call(port,'POST','/api/v2/p0/consent-generate',decision,nonce)[0])
        threads=[threading.Thread(target=send) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(10)
            assert not thread.is_alive()
        assert sorted(results)==[202,409]
        # This includes local pinned source/preflight work before the transport;
        # it is not the transport's separate 120-second provider deadline.
        assert control.entered.wait(300)
        for _ in range(3):
            start=time.monotonic()
            status,progress=call(port,'GET','/api/v2/p0/commands/'+decision['command_id'])
            assert status==200 and progress['data']['phase']=='TRANSPORT_ENTERED'
            assert progress['data']['evidence']['provider_arrival']=='NOT_ESTABLISHED'
            assert time.monotonic()-start<3
            status,_=call(port,'GET','/api/v2/conversation/saved')
            assert status==200
        assert control.calls==1
        control.release.set()
        assert terminal(port,decision['command_id'])['phase']=='APPLICATION_SAVED'

def test_proposed_mode_has_body_cost_no_secret_resolver_or_effect(tmp_path,monkeypatch):
    control=f.Control()
    with f.running(tmp_path/'case',monkeypatch,control,proposed=True) as (port,config):
        nonce,command,shown=prepare(port)
        assert shown['state']=='OWNER_NORMAL_ADOPTION_REQUIRED'
        assert shown['admission_status']=='OWNER_DECISION_PENDING'
        assert shown['request_bytes']==len(shown['request_body_utf8'].encode())
        assert shown['effect_enabled'] is False
        assert not control.owner.has_resolver and control.owner.generation is None
        assert list(config[3].iterdir())==[]
        status,denied=call(port,'POST','/api/v2/p0/consent-generate',{
            **command,'preview_sha256':'a'*64,'transfer_accepted':True,'cost_bound_accepted':True},nonce)
        assert status==409 and denied['error']['code']=='P0_NORMAL_OWNER_ADOPTION_REQUIRED'
        assert list(config[3].iterdir())==[] and control.calls==control.builds==control.prompt_calls==0
        with pytest.raises(ValueError,match='OWNER_DECISION_REQUIRED'):
            P0NormalProductComposition(path=config[0],target=config[1],saved_root=config[2],
                application_root=f.ROOT,credential_source='OPENAI_API_KEY')
