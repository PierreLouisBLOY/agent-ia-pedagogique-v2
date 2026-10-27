"""Declared test data/effects only. Real CLI, source coverage, SDK and native ledger.

This module is never imported by the product. It supplies synthetic source ports,
tokenizer evidence and Responses effect to the actual production composition.
"""
from __future__ import annotations

import copy
import getpass
import http.client
import json
import os
import socket
import sqlite3
import subprocess
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from backend.adapters.inbound.application.stmg_alignment import STMGAlignmentInbound
from backend.adapters.inbound.cli import local_browser as cli
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_policy import P1_HASHES
from backend.adapters.outbound.openai.contracts import (
    OpenAIIncompleteReason,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.composition.factories import institutional_catalog as catalog_factory
from backend.infrastructure.composition.factories import p0_normal_profile as profile_factory
from backend.infrastructure.composition.factories import r6_all_notions
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_saved_application,
)
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES

ROOT = Path(cli.__file__).resolve().parents[4]
FAKE_KEY = 'SYNTHETIC_FRESH_OWNER_323A_NOT_A_CREDENTIAL'
SOURCE_TEXT = 'Source synthétique déclarée : la perception sélectionne et interprète des informations.'
SOURCE = {'object_ref':'notion:shared','object_kind':'NOTION','passage_ref':'search-chunk:synthetic323a',
    'version_or_checksum':'a'*64,'excerpt':SOURCE_TEXT,'excerpt_truncated':False,
    'provenance':{'source_kind':'canonical_search_chunk','freshness':'CURRENT','admission_policy':'F2A',
                  'authority_absolute':False,'content_trust':'UNTRUSTED_CONTENT','channel':'EXACT_ID'}}
CONTENT = {'title':'Exercice synthétique sur la perception',
    'sections':[{'section_id':'S1','heading':'Situation fictive','text':'FICTIF : Nora écrit que les dossiers sont attendus à 17 heures. Inès croit à un reproche ; Sami comprend un rappel collectif.'}],
    'questions':[{'question_id':'Q1','prompt':'Relevez un fait observable dans ce message.','options':[]},
                 {'question_id':'Q2','prompt':'Distinguez le message de son interprétation par Inès.','options':[]}],
    'corrections':[{'question_id':'Q1','expected_answer':'SENTINELLE_PROFESSEUR : le message mentionne 17 heures.','rationale':'C’est une information présente dans le message.'},
                   {'question_id':'Q2','expected_answer':'SENTINELLE_PROFESSEUR : Inès suppose un reproche.','rationale':'Le message ne formule aucun reproche explicite.'}],
    'marking':[], 'limitations':['SYNTHETIC_QUALIFICATION_NOT_PROVIDER_OUTPUT']}

class Catalog:
    def __init__(self):
        self.data = {key:[] for key in ('official_framework','official_framework_version','official_framework_element',
            'institutional_attachment','pedagogical_context','notion_context','notion','document','document_reference','source')}
        self.data['notion']=[{'id':'notion:shared','canonical_label':'Perception synthétique','identity_status':'CANONICAL'}]
        for frame,spec in STMG_FRAMES.items():
            self.data['official_framework'].append({'id':'program:'+frame,'code':spec[5],'issuing_source_id':'source:'+frame})
            self.data['official_framework_version'].append({'id':'version:'+frame,'framework_id':'program:'+frame,
                'version_label':'SYNTHETIC-V1','lifecycle_status':'PUBLISHED','official_document_id':'document:'+frame})
            self.data['source'].append({'id':'source:'+frame,'status':'ADMITTED'})
            self.data['document'].append({'id':'document:'+frame,'sha256':sha(frame.encode()),'document_status':'ADMITTED'})
            self.data['document_reference'].append({'id':'locator:'+frame,'document_id':'document:'+frame})
            self.data['official_framework_element'] += [
                {'id':'question:'+frame,'framework_version_id':'version:'+frame,'parent_element_id':None,
                 'element_type':'QUESTION','official_label':'1.1 Question synthétique '+frame,'document_reference_id':'locator:'+frame},
                {'id':'capacity:'+frame,'framework_version_id':'version:'+frame,'parent_element_id':'question:'+frame,
                 'element_type':'CAPACITY','official_label':'Analyser les interprétations synthétiques','document_reference_id':'locator:'+frame}]
            self.data['institutional_attachment'].append({'id':'attachment:'+frame,'notion_id':'notion:shared',
                'framework_element_id':'question:'+frame,'attachment_type':'EXPLICIT','status':'ADMITTED',
                'origin_type':'OFFICIAL_DOCUMENT','depth_level':'APPLICATION'})
    def read_institutional_catalog(self):
        return copy.deepcopy(self.data)
    def read_reference_contexts(self, object_ref):
        return ()

def context():
    spec=STMG_FRAMES['SGN_PREMIERE']
    return {'contract_id':'P0-CONTEXT-2.0','resource_type':'EXERCISE','question_mode':None,
        'level':spec[0],'discipline':spec[6],'topics':['Perception et interprétation d’un message professionnel'],
        'objectives':['Distinguer faits et interprétations dans une situation fictive'],'difficulty':'STANDARD',
        'language':'fr','duration_minutes':None,'total_points':None,
        'institutional':{'contract_id':'STMG-INSTITUTIONAL-CONTEXT-1.0','frame':'SGN_PREMIERE',
            'education_level':spec[1],'series':'STMG','teaching_subject':spec[2],'program_ref':'program:SGN_PREMIERE',
            'program_version':'version:SGN_PREMIERE','program_component':spec[3],'specific_track':spec[4],
            'theme_ref':'theme:1','question_ref':'question:SGN_PREMIERE','capacity_refs':['capacity:SGN_PREMIERE'],
            'notion_refs':['notion:shared'],'depth':'APPLICATION'},
        'institutional_resolution':None,'local_progression':{'chapter':None,'sequence':None,'week':None}}

def artifact(root, name, value, binary=False):
    path=root/name
    raw=value if binary else canonical(value)
    path.write_bytes(raw)
    return {'path':str(path),'sha256':sha(raw)}

class Control:
    def __init__(self, scenario='complete'):
        self.scenario=scenario
        self.calls=0
        self.builds=0
        self.token_delta=0
        self.entered=threading.Event()
        self.release=threading.Event()
        self.release.set()
        self.owner=None
        self.server=None
        self.stdin_is_tty=os.isatty(0)
        self.prompt_calls=0
        self.transport_wait_seconds=90
    def forbidden_prompt(self,*args,**kwargs):
        self.prompt_calls += 1
        raise AssertionError('NO_CONSOLE_PROMPT')
    def build(self,*,secret,timeout_seconds):
        assert secret.reveal_for_transport()==FAKE_KEY
        assert timeout_seconds==120.0
        self.builds+=1
        return self
    def create(self,*,request):
        self.calls+=1
        self.entered.set()
        assert self.release.wait(self.transport_wait_seconds)
        if self.scenario=='401':
            raise OpenAITransportError(OpenAITransportErrorCode.AUTHENTICATION)
        if self.scenario=='network':
            raise OpenAITransportError(OpenAITransportErrorCode.CONNECTION)
        if self.scenario=='timeout':
            raise TimeoutError('SYNTHETIC_TIMEOUT')
        status=OpenAIResponseStatus.INCOMPLETE if self.scenario=='truncated' else OpenAIResponseStatus.COMPLETED
        return OpenAIResponsesResponse(status, canonical(CONTENT).decode() if status is OpenAIResponseStatus.COMPLETED else '{"title":"capture partielle"',
            OpenAIResponseUsage(1000,0,100,1100,reasoning_tokens=0),service_tier='default',
            incomplete_reason=OpenAIIncompleteReason.MAX_OUTPUT_TOKENS if status is OpenAIResponseStatus.INCOMPLETE else OpenAIIncompleteReason.NONE)

def install_boundaries(monkeypatch, control):
    catalog=Catalog()
    query=STMGAlignmentInbound(ReadSTMGAlignment(catalog))
    def stmg(target,*,selection=None,reference=None,matrix=False,mode='LEGACY',question_fingerprints=False,focus_witness=False):
        target.validate()
        return query.resolve(selection,reference,mode=mode,focus_witness=focus_witness) if selection is not None else query.matrix() if matrix else query.catalog(question_fingerprints=question_fingerprints)
    monkeypatch.setattr(catalog_factory,'stmg_alignment',stmg)
    monkeypatch.setattr(catalog_factory,'bts_alignment',lambda *a,**kw:{'bts_frameworks':[]})
    monkeypatch.setattr(catalog_factory,'inspect_institutional_catalog',lambda *a,**kw:catalog.read_institutional_catalog())
    @contextmanager
    def exact(target):
        target.validate()
        yield SimpleNamespace(inspect=lambda notion:{'notion_id':notion,'status':'CANONICAL',
            'retrieval_path':'EXACT_ID_AND_EXPLICIT_LINKS','items':[copy.deepcopy(SOURCE)] if notion=='notion:shared' else []})
    monkeypatch.setattr(r6_all_notions,'exact_notion_evidence',exact)
    class Tokenizer:
        def __init__(self,manifest,manifest_sha256,**_):
            self.pin=manifest_sha256
        def __call__(self,body):
            return {'schema':'P0-NORMAL-TOKENIZER-PROOF-1.0','model':'gpt-5.6-terra',
                'recognition':'OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER','encoding':'o200k_base',
                'manifest_sha256':self.pin,'request_sha256':sha(body),'model_mapping_sha256':'1'*64,
                'encoding_sha256':'2'*64,'all_string_values_and_keys_tokens':1000+control.token_delta,
                'serialized_json_tokens':1100+control.token_delta,'network_forbidden_during_count':True,'provider_calls':0}
    monkeypatch.setattr(profile_factory,'LocalTokenizerHelper',Tokenizer)
    monkeypatch.setattr(profile_factory,'OpenAISDKResponsesTransportFactory',lambda **_:control)
    monkeypatch.setattr(getpass,'getpass',control.forbidden_prompt)
    original_connect=socket.socket.connect
    def local_only(sock,address):
        if isinstance(address,tuple) and address[0] not in {'127.0.0.1','::1','localhost'}:
            raise AssertionError('NO_EXTERNAL_NETWORK_DURING_SYNTHETIC_QUALIFICATION')
        return original_connect(sock,address)
    monkeypatch.setattr(socket.socket,'connect',local_only)
    original_bind=profile_factory.P0NormalProductComposition.bind
    def observed_bind(owner,service,endpoint):
        original_bind(owner,service,endpoint)
        control.owner=owner
    monkeypatch.setattr(profile_factory.P0NormalProductComposition,'bind',observed_bind)
    return catalog

def configuration(root, *, proposed=False):
    root.mkdir(parents=True,exist_ok=True)
    # Synthetic fixture only; never a user database or historical incident store.
    database=root/'SYNTHETIC-runtime.sqlite'
    if not database.exists():
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE resource(id TEXT PRIMARY KEY, resource_type TEXT, canonical_title TEXT, identity_status TEXT)')
    target=Read15RuntimeTarget(database,root,sha(database.read_bytes()))
    saved=root/'SYNTHETIC-saved'
    if not saved.exists():
        build_saved_application(saved,create=True,word_profile='product-v7')
    receipts=root/'SYNTHETIC-private-receipts'
    receipts.mkdir(exist_ok=True)
    files={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for directory in ROOT.iterdir()
        if directory.name in profile_factory._CODE_ROOTS for p in directory.rglob('*')
        if p.is_file() and p.suffix in profile_factory._CODE_SUFFIXES and '__pycache__' not in p.parts}
    exact_package=os.environ.get('V2_TEST_EXTRACTED_PACKAGE')
    if exact_package:
        source=ROOT/'P0_NORMAL_SOURCE_MANIFEST.json'
        data=json.loads(source.read_bytes())
        assert data['files']==files
        source_desc={'path':str(source),'sha256':sha(source.read_bytes())}
        package=Path(exact_package)
        baseline=data['source_commit']
    else:
        baseline, source_tree = '1'*40, '2'*40
        if (ROOT / '.git').exists():
            checkout = subprocess.run(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'],
                cwd=ROOT, capture_output=True, text=True, check=True, timeout=10)
            baseline, source_tree = checkout.stdout.splitlines()
        source_desc=artifact(root,'SYNTHETIC-full-source-manifest.json',{'schema':'P0-NORMAL-SOURCE-MANIFEST-2.0',
            'source_commit':baseline,'source_tree':source_tree,'files':files})
        package=root/'SYNTHETIC-full-source.zip'
        with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name in files:
                archive.write(ROOT/name,'source/'+name)
            archive.writestr('source/P0_NORMAL_SOURCE_MANIFEST.json',Path(source_desc['path']).read_bytes())
    entry={'notion_ref':'notion:shared','source_ref':SOURCE['object_ref'],'object_kind':'NOTION',
        'locator':SOURCE['passage_ref'],'checksum_or_version':SOURCE['version_or_checksum'],'excerpt_sha256':sha(SOURCE_TEXT.encode()),
        'provenance':SOURCE['provenance'],'source_status':{},'available_authority':'UNKNOWN','authority_basis':'NOT_ATTESTED_BY_APPLICATION'}
    entry['admission_scope_sha256']=sha(canonical(entry))
    sources={'schema':'P0-SOURCE-ADMISSION-MANIFEST-1.0','status':'NON_ADOPTE','application_inventory_sha256':'b'*64,
        'catalogue_sha256':'c'*64,'source_scope_sha256':sha(canonical([entry])),'entries':[entry],'exclusions':[]}
    now=datetime.now(UTC)
    price=artifact(root,'SYNTHETIC-price-evidence.txt',b'SYNTHETIC ONLY - NOT A REAL PRICE ADMISSION',binary=True)
    tariff={'schema':'P0-NORMAL-TARIFF-1.0','provider':'OPENAI','model':'gpt-5.6-terra','tier':'default',
        'input_usd_per_million':'2.00','output_usd_per_million':'12.00','input_multiplier':'1.25',
        'evidence_sha256':price['sha256'],'owner_admission_sha256':'e'*64,'retrieved_at_utc':(now-timedelta(days=1)).isoformat()}
    operator=profile_factory.windows_operator()
    profile={'schema':'P0-NORMAL-PROFILE-1.0','baseline_commit':baseline,'source_manifest':source_desc,
        'package':{'path':str(package),'sha256':sha(package.read_bytes())},
        'runtime':{'path':str(database),'data_root':str(root),'sha256':target.expected_sha256},
        'saved_root':str(saved),'receipt_root':str(receipts),
        'source_admission_manifest':artifact(root,'SYNTHETIC-source-admission.json',sources),
        'operator_delegation':artifact(root,'SYNTHETIC-delegation.json',{'schema':'P0-LOCAL-OPERATOR-DELEGATION-1.0',
            **operator,'credential_ref':'openai.p0.normal','local_operator_delegation_accepted':True}),
        'tokenizer_manifest':artifact(root,'SYNTHETIC-tokenizer.json',{'schema':'DECLARED_SYNTHETIC_NOT_REAL_TOKENIZER'}),
        'tariff':artifact(root,'SYNTHETIC-tariff.json',tariff),'tariff_evidence':price,
        'institutional_catalog_sha256':sha(canonical(Catalog().read_institutional_catalog())),'credential_ref':'openai.p0.normal'}
    pin=P0NormalReceipt(receipts,'3'*64)
    permission={key:'0'*64 for key in P1_HASHES}
    permission.update(schema='P0-PRODUCT-CREATE-PERMISSION-1.0',baseline_commit=baseline,
        source_tree_sha256=source_desc['sha256'],package_sha256=profile['package']['sha256'],
        runtime_sha256=target.expected_sha256,profile_sha256=sha(canonical(profile)),output_schema_sha256='0'*64,
        receipt_root_sha256=pin.root_sha256,permission_namespace_sha256='3'*64,
        institutional_catalog_sha256=profile['institutional_catalog_sha256'],issued_at_utc=(now-timedelta(minutes=1)).isoformat(),
        expires_at_utc=(now+timedelta(days=1)).isoformat(),allowed_families=['EXERCISE'],allowed_levels=['FIRST_STMG'],
        selected_admitted_sources_only=True,excluded_oracles_and_private_evidence=True,require_exact_local_consent=True,
        local_operator_delegation_accepted=True,provider='OPENAI',model='gpt-5.6-terra',endpoint='https://api.openai.com/v1/responses',
        reasoning='low',tier='default',max_output_tokens=4096,max_calls=1,count_calls=0,review_calls=0,modify_calls=0,
        retry=0,fallback='NONE',parallelism=1,per_call_ceiling_usd='0.140000',cumulative_ceiling_usd='0.140000',
        live_authorized=True,transfer_authorized=True)
    from backend.adapters.outbound.generation.openai.p0_content import content_schema
    permission['output_schema_sha256']=sha(canonical(content_schema()))
    for name in ('source_admission_manifest','operator_delegation','tokenizer_manifest','tariff'):
        permission[name+'_sha256']=profile[name]['sha256']
    decision={'schema':'P0-NORMAL-OWNER-DECISION-1.0','status':'PROPOSED' if proposed else 'ADOPTED',
        'profile_sha256':permission['profile_sha256'],
        'permission_policy_sha256':sha(canonical({k:v for k,v in permission.items() if k!='owner_decision_sha256'})),
        'excluded_oracles_and_private_evidence':True,'source_authority_unknown_preserved':True,'local_operator_delegation_accepted':True}
    for name in ('source_admission_manifest','operator_delegation','tokenizer_manifest','tariff'):
        decision[name+'_sha256']=profile[name]['sha256']
    decision_desc=artifact(root,'SYNTHETIC-decision-NOT-OWNER-ACCORD.json',decision)
    permission['owner_decision_sha256']=decision_desc['sha256']
    envelope={'schema':'P0-NORMAL-PROFILE-ENVELOPE-1.0','profile':profile,
        'permission':artifact(root,'SYNTHETIC-permission-NOT-LIVE.json',permission),'decision':decision_desc}
    path=Path(artifact(root,'SYNTHETIC-envelope.json',envelope)['path'])
    return path,target,saved,receipts

def request(port, method, path, body=None, nonce=None, timeout=90):
    headers={'X-Local-Intent':'conversation-v1'}
    if method=='POST':
        headers.update({'Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json; charset=utf-8','X-R2-Nonce':nonce or ''})
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=timeout)
    try:
        connection.request(method,path,body=canonical(body) if body is not None else None,headers=headers)
        response=connection.getresponse()
        return response.status,response.read()
    finally:
        connection.close()

@contextmanager
def running(root,monkeypatch,control,*,proposed=False,existing=None,extra_args=()):
    install_boundaries(monkeypatch,control)
    if control.scenario=='missing-key':
        monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    else:
        monkeypatch.setenv('OPENAI_API_KEY',FAKE_KEY)
    path,target,saved,receipts=existing or configuration(root,proposed=proposed)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    from backend.infrastructure.composition.factories import local_browser as factory
    original=factory.build_local_read15
    def observed(*args,**kwargs):
        built=original(*args,**kwargs)
        control.server=built
        return built
    # Observing wrapper calls the actual factory unchanged; no guard is doubled.
    monkeypatch.setattr(cli,'build_local_read15',observed)
    errors=[]
    args=['--port',str(port),'--runtime',str(target.runtime_path),'--data-root',str(target.data_root),
        '--runtime-sha256',target.expected_sha256,'--saved-root',str(saved),'--word-profile','product-v7',
        '--p0-normal-profile',str(path),'--p0-normal-mode','prepare-only' if proposed else 'enabled',
        '--observability-root',str(root/'SYNTHETIC-observability')]
    args.extend(extra_args)
    def launch():
        try:
            errors.append(cli.main(args))
        except BaseException as error:
            errors.append(type(error).__name__)
    thread=threading.Thread(target=launch,daemon=True)
    thread.start()
    deadline=time.monotonic()+600
    while control.server is None and thread.is_alive() and time.monotonic()<deadline:
        time.sleep(.05)
    assert control.server is not None, errors
    assert control.server.server._running.wait(10)
    try:
        yield port,(path,target,saved,receipts)
    finally:
        control.release.set()
        control.server.close()
        thread.join(10)
        assert not thread.is_alive()
        assert control.prompt_calls==0
