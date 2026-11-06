#!/usr/bin/env python3
"""Qualify the optional scalar cache implementation; never measure its speed here."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'.local/venv/bin/python'
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.provenance import source_identity


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',required=True,type=Path)
    parser.add_argument('--results',required=True,type=Path)
    args=parser.parse_args()
    if args.work.exists():raise ValueError('preserve previous attempt; choose a new work directory')
    queue=json.loads((ROOT/'.local/jobs/halfkp-scalar-speed-v1.json').read_text())
    if (queue['status']!='complete' or queue['pid']!=493003 or queue['step']!=12
            or queue['plan_sha256']!='3d3af231ac57446d21d7d5ba4dcd2cd05c685cd2df3c0c7802cfab888e82d6be'):
        raise ValueError('all six prior timing trials must finish first')
    try:process=Path('/proc/493003/stat').read_text().split(') ',1)[1].split()
    except FileNotFoundError:process=None
    if process and process[0]!='Z' and process[19]=='6258900':
        raise ValueError('timing producer has not exited')
    identity=source_identity();build=json.loads((ROOT/'.local/last-engine-build.json').read_text())
    binary=ROOT/'.local/guest-root/shogi'
    if (identity['source_worktree_dirty'] or build['source_worktree_dirty']
            or build['source_tree_sha256']!=identity['source_tree_sha256']
            or build['engine_sha256']!=sha(binary)):
        raise ValueError('commit and build the optional implementation before qualification')
    development_plan=ROOT/'manifests/halfkp-scalar-development-selection-plan-v1.json'
    plan=json.loads(development_plan.read_text());models=[]
    for item in plan['models']:
        spec=item['qualified_runtimes']['width-kernel'];manifest=ROOT/spec['path']
        if sha(manifest)!=spec['sha256']:raise ValueError('old runtime manifest changed')
        old=json.loads(manifest.read_text());model=Path(old['model_origin'])
        if sha(model)!=spec['model_sha256']:raise ValueError('trained weights changed')
        key=item['model'];name=f'halfkp-nnue-{key}-packed-accumulator-v1'
        profile=ROOT/'.local/profiles'/name;frozen=ROOT/'manifests'/(name+'-candidate.json')
        if profile.exists() or frozen.exists() or (ROOT/'.local/candidates'/name).exists():
            raise ValueError('preserve existing candidate: '+name)
        reference=ROOT/'.local/evaluation'/f'halfkp-nnue-{key}-width-kernel-v1-native-nodes10000-quick256.json'
        # The original width8/64m general reference has the same searched tree.
        if not reference.exists() and key=='w8-h0':
            reference=ROOT/'.local/evaluation/halfkp-nnue-w8-h0-output32-v1-native-nodes10000-quick256.json'
        ref=json.loads(reference.read_text())
        if not ref['complete'] or len(ref['details'])!=256 or ref['model_sha256']!=spec['model_sha256']:
            raise ValueError('old native reference is not complete/identical')
        models.append((key,name,model,profile,frozen,reference,old['model_sha256']))
    args.work.mkdir(parents=True);args.results.mkdir(parents=True,exist_ok=True)
    report_path=args.results/'halfkp-nnue-packed-accumulator-validation-v1.json'
    if report_path.exists():raise ValueError('preserve prior qualification report')
    state={'status':'executing','pid':os.getpid(),'started_at_utc':now(),'source_identity':identity,
           'build':build,'driver_sha256':sha(Path(__file__)),'selection_plan_sha256':sha(development_plan),
           'timing_completion_sha256':sha(ROOT/'.local/jobs/halfkp-scalar-speed-v1.json'),'steps':[]}
    state_path=args.work/'state.json'
    artifacts={};qualified=[]

    def save():
        temporary=state_path.with_suffix('.partial');temporary.write_text(json.dumps(state,indent=2)+'\n');temporary.replace(state_path)

    def run(label,argv,result=None,stdout_json=False):
        state.update(current_step=label,current_argv=[str(value) for value in argv]);save()
        log=args.work/(label+'.log')
        with log.open('x') as stream:
            subprocess.run([str(value) for value in argv],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        if stdout_json:
            contents=json.loads(log.read_text())
            with result.open('x') as stream:json.dump(contents,stream,indent=2);stream.write('\n')
        if result is not None:
            contents=json.loads(result.read_text())
            if contents.get('passed') is False:raise ValueError('failed result: '+str(result))
            artifacts[str(result)]=sha(result)
        state['steps'].append({'label':label,'log':str(log),'log_sha256':sha(log),'finished_at_utc':now()});save()

    def test(label,script,arguments):
        result=args.results/(label+'.json')
        run(label,[PYTHON,ROOT/'tests'/script,*arguments,'--output',result],result)
        return json.loads(result.read_text())

    validation_data=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/training/halfkp-qsearch-v1/raw-validation/shuffled/shuffled.bin')
    quick=Path(plan['dataset']).with_name('quick.jsonl')
    try:
        save()
        header=subprocess.check_output(['readelf','-h',str(binary)],text=True)
        segments=subprocess.check_output(['readelf','-l',str(binary)],text=True)
        if ('ELF32' not in header or 'Intel 80386' not in header
                or 'EXEC (Executable file)' not in header or 'INTERP' in segments):
            raise ValueError('expected a static32 x86 target executable')
        assembly=subprocess.check_output(['objdump','-d','--no-show-raw-insn',str(binary)],text=True)
        forbidden=re.compile(r'(?:cmov\w*|fcmov\w*|fcomip?|fucomip?|rdrand|rdseed|rdpmc|sysenter|syscall|prefetch\w*|ldmxcsr|stmxcsr|fxsave\w*|fxrstor\w*|xsave\w*|xrstor\w*|fisttp\w*|popcnt\w*|lzcnt\w*|tzcnt\w*|emms|[sml]fence|clflush\w*|xgetbv|xsetbv|vzeroupper|vzeroall)',re.I)
        hits=[]
        for line in assembly.splitlines():
            if not re.match(r'^\s*[0-9a-f]+:',line):continue
            instruction=line.split(':',1)[1].split('#',1)[0].strip()
            if instruction and (forbidden.fullmatch(instruction.split()[0])
                                or re.search(r'%(?:[xyz]mm\d+|mm[0-7])\b',instruction,re.I)):
                hits.append(line)
        (args.work/'target-readelf.log').write_text(header+segments)
        (args.work/'target-objdump.log').write_text(assembly)
        if hits:raise ValueError('known post-Pentium instructions: '+repr(hits[:8]))
        target=args.results/'halfkp-packed-accumulator-target-binary-v1.json'
        with target.open('x') as stream:
            json.dump({'passed':True,'engine_sha256':sha(binary),'elf32_static_x86':True,
                       'known_post_pentium_opcode_hits':hits,'scope':'build target/static format and known-opcode scan; actual target execution is checked separately'},stream,indent=2);stream.write('\n')
        artifacts[str(target)]=sha(target)
        test('halfkp-packed-accumulator-cpp-arithmetic-v1','packed_accumulator_arithmetic.py',[])
        for width in (8,16):
            label=f'halfkp-packed-accumulator-boundaries-w{width}-v1'
            test(label,'nnue_packed_accumulator.py',['--data',validation_data,'--width',width,'--work',args.work/label])
        for width in (2,8,16,32):
            for script in ('nnue_output_accumulation.py','nnue_packed_fc.py'):
                label=f'halfkp-packed-accumulator-{Path(script).stem}-w{width}-v1'
                arguments=['--data',validation_data,'--width',width,'--work',args.work/label]
                if script=='nnue_output_accumulation.py':
                    arguments+=['--expected-kernel-width',width if width in (8,16) else 0]
                test(label,script,arguments)
        for key,name,model,profile,frozen,old_reference,model_sha in models:
            width=16 if key.startswith('w16-') else 8;hidden=8 if 'h8' in key else 0
            difference=f'標準HalfKP {key}、同じ収束済み重み、幅固定・packedFCに値域証明付き2要素のscalar加減算キャッシュを追加。速度・棋力は未測定'
            run(name+'-package',[PYTHON,ROOT/'scripts/package-candidate.py','--name',name,'--model',model,'--feature-difference',difference])
            candidate=ROOT/'.local/candidates'/name/'manifest.json'
            run(name+'-profile',[PYTHON,ROOT/'scripts/prepare-usi-profile.py','--manifest',candidate,'--output',profile])
            shutil.copyfile(profile/'manifest.json',frozen);artifacts[str(frozen)]=sha(frozen)
            manifest=json.loads(frozen.read_text())
            if manifest['engine_sha256']!=sha(binary) or manifest['model_sha256']!=model_sha:
                raise ValueError('packaged artifacts differ')
            values=args.results/(name+'-trained-values.json')
            run(name+'-values',[PYTHON,ROOT/'tests/tiny_parity.py','--model',model,'--data',validation_data,'--count',512,
                               '--binary',profile/'shogi','--log-prefix',args.work/(name+'-values.engine')],values,True)
            native=args.work/(name+'-native-nodes10000-quick256.json')
            run(name+'-native',[PYTHON,ROOT/'scripts/evaluate-accuracy.py','--dataset',quick,'--output',native,
                               '--engine-command',json.dumps([str(profile/'shogi')]),'--engine-id',name+'-native',
                               '--engine-sha256',manifest['engine_sha256'],'--engine-options',json.dumps({'EvalFile':str((profile/'model.bin').resolve())}),
                               '--engine-manifest',frozen,'--backend','native','--nodes',10000,'--search-diagnostics'],native)
            old=json.loads(old_reference.read_text());new=json.loads(native.read_text())
            if not new['complete'] or len(new['details'])!=256 or any(new[k] for k in ('errors','illegal_moves','time_overruns')):
                raise ValueError('native run incomplete or failed')
            for field in ('dataset_sha256','sample_ids','mode','milliseconds','nodes','options','backend'):
                if old[field]!=new[field]:raise ValueError('native condition differs: '+field)
            if old['environment']['signature']!=new['environment']['signature']:
                raise ValueError('native environment differs')
            for a,b in zip(old['details'],new['details']):
                for field in ('id','sfen','expected','actual','final_nodes','completed_depth'):
                    if a[field]!=b[field]:raise ValueError('old/new search differs: '+field)
            verification=test(name+'-trained-search-parity','tiny_incremental.py',[
                '--model',model,'--binary',profile/'shogi','--reference',native,'--expected-kernel-width',width,
                '--expected-fc-packed',int(hidden>0),'--expected-fc-bits',32 if hidden else 0,
                '--expected-accumulator-packed',1,'--expected-accumulator-bits',16])
            guest=test(name+'-guest-auto-model','guest_auto_model.py',['--profile',profile,'--data',validation_data])
            test(name+'-guest-nodes-parity','guest_nodes_parity.py',[
                '--manifest',frozen,'--reference',native,'--automatic-model','--expected-output-bits',32,
                '--expected-kernel-width',width,'--expected-fc-packed',int(hidden>0),'--expected-fc-bits',32 if hidden else 0,
                '--expected-accumulator-packed',1,'--expected-accumulator-bits',16])
            qualified.append({'model':key,'manifest':str(frozen),'engine_sha256':manifest['engine_sha256'],
                              'model_sha256':model_sha,'old_reference_sha256':sha(old_reference),
                              'verified_accumulators':verification['counters']['verified'],'guest_memory':guest['guest_memory']})
        report={'complete':True,'passed':True,'started_at_utc':state['started_at_utc'],'verified_at_utc':now(),
                'build':build,'driver_sha256':state['driver_sha256'],'models':qualified,'artifacts':artifacts,
                'all_five_models_same256_bestmoves_finalnodes_completeddepths_as_frozen_old_runtime':True,
                'adopted':False,'speed_or_strength_measured':False,
                'scope':'independent integer/native and real Pentium operation/RAM qualification only; timing is not a speed or strength result'}
        with report_path.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        state.update(status='complete',report=str(report_path),report_sha256=sha(report_path))
    except BaseException as error:
        state.update(status='stopped',error=str(error));raise
    finally:state['finished_at_utc']=now();save()


if __name__=='__main__':main()
