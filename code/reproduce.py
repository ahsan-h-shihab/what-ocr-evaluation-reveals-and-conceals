"""Portable offline adapter. All evaluation targets/results remain frozen.

No source discovery, inference, cloud calls, text exports or invented annotations.
Missing/mismatched restricted inputs block evaluation before any scoring.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import platform
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]

def read_json(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))

def rows(name):
    with (ROOT/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def write_output(path, result):
    target = Path(path).resolve()
    target.relative_to((ROOT/'work').resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(result['status'])

def close(actual, expected, label):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12):
        raise AssertionError(f'{label}: computed {actual!r}, preserved {expected!r}')

def pct(values, q):
    data = sorted(values); pos=(len(data)-1)*q; lo=int(pos); hi=min(lo+1,len(data)-1)
    return data[lo]*(1-(pos-lo))+data[hi]*(pos-lo)

def page_reanalysis(data):
    draw=random.Random(20260602)
    indices=[[draw.randrange(7) for _ in range(7)] for _ in range(2000)]
    out={}
    for system in dict.fromkeys(r['system'] for r in data):
        pages=[r for r in data if r['system']==system]
        assert [int(r['page']) for r in pages]==list(range(10,17))
        result={}
        for prefix, edits, denom in [('CER','character_edits','reference_characters'),('WER','word_edits','reference_tokens')]:
            def ratio(ids):
                return sum(int(pages[i][edits]) for i in ids)/sum(int(pages[i][denom]) for i in ids)
            samples=[ratio(ids) for ids in indices]
            result.update({prefix:ratio(range(7)),prefix+'_low':pct(samples,.025),prefix+'_high':pct(samples,.975)})
        for key in ['character_edits','reference_characters','word_edits','reference_tokens']:
            result[key]=sum(int(p[key]) for p in pages)
        out[system]=result
    return out

def verify():
    manifest=read_json('MANIFEST.json'); checked=[]
    for item in manifest['files']:
        p=ROOT/item['path']
        assert p.is_file(), f'Missing package member {item["path"]}'
        assert digest(p)==item['sha256'], f'Changed package member {item["path"]}'
        checked.append(item['path'])
    a_counts=rows('results/benchmark_a/primary_S_D_counts.csv')
    a_rates=rows('results/benchmark_a/reference_sensitivity.csv')
    assert len(a_counts)==10 and len(a_rates)==5
    for r in a_counts:
        for unit, metric in [('character','CER'),('word','WER')]:
            edits=sum(int(r[unit+'_'+x]) for x in ['S','D','I'])
            assert edits==int(r[unit+'_edits'])
            close(edits/int(r[unit+'_N']),r[metric],'A count/rate')
            version='legacy_reference_' if r['reference_version'].startswith('S_') else 'single_copy_'
            target=next(x for x in a_rates if x['system']==r['system'])
            close(r[metric],target[version+metric],'A displayed sensitivity')
    page_data=rows('results/benchmark_a/page_counts.csv')
    recalculated=page_reanalysis(page_data)
    for r in rows('results/benchmark_a/pooled_metrics_and_page_intervals.csv'):
        for key,value in recalculated[r['system']].items():
            close(value,r[key],'A additive page/range '+key)
    b_counts=rows('results/benchmark_b/unchanged_original_score_verification.csv')
    align=rows('results/benchmark_b/benchmark_b_alignment_counts.csv')
    names={'DeepSeek':'DeepSeek-OCR','DP2':'DP-2-mini / LandingAI','Tesseract':'Tesseract'}
    for r in b_counts:
        assert sum(int(r[k]) for k in ['S','D','I'])==int(r['edits'])
        close(int(r['edits'])/int(r['N']),r['rate'],'B count/rate')
        target=next(x for x in rows('results/benchmark_b/qara_sozder_bootstrap_ci.csv') if x['system']==names[r['system']])
        close(r['rate'],target['cer' if r['unit']=='character' else 'wer_uniform_unicode'],'B displayed rate')
        if r['unit']=='character':
            old=next(x for x in align if x['system']==names[r['system']] and x['alignment']=='case_sensitive')
            for key in ['S','D','I','edits']:
                close(r[key],old[key],'B case-consistent operations')
    error_rows=rows('results/benchmark_b/qara_sozder_error_classes.csv')
    for r in error_rows:
        old=next(x for x in align if x['system']==r['system'] and x['alignment']=='lowercase_diagnostic')
        close(int(r['count'])/int(old['edits']),r['share_of_edit_ops'],'B lowercase share')
    retrieval=rows('results/benchmark_b/qara_sozder_retrieval_sensitivity_bm25.csv')
    assert len(retrieval)==9
    for r in retrieval:
        assert int(float(r['queries']))==(45 if r['mode']=='fixed_window_chunks' else {'DeepSeek-OCR':32,'DP-2-mini / LandingAI':31,'Tesseract':32}[r['system']])
        assert 0<=float(r['mrr'])<=1
    for r in read_json('results/correction/saved_correction_scores.json'):
        close(r['character_edits']/r['reference_characters'],r['CER'],'saved correction CER')
        close(r['word_edits']/r['reference_tokens'],r['WER'],'saved correction WER')
    windows=read_json('metadata/benchmark_b/source_difference_windows.json')
    for system in ['DeepSeek','DP2']:
        selected=[r for r in windows if r['system']==system and r['issue']!='section_44_window']
        assert sum(sum(int(r.get('full_alignment_window_'+k,0)) for k in ['S','D','I']) for r in selected)==74
        assert sum(sum(int(r.get('word_alignment_window_'+k,0)) for k in ['S','D','I'])+int(r.get('word_alignment_edits_at_reference_token',0)) for r in selected)==16
    notes=read_json('metadata/benchmark_b/nonbody_regions.json')
    glossary=next(r for r in notes if r['region']=='section_38_glossary')
    assert glossary['original_character_alignment_I']==4095 and glossary['original_word_alignment_I']==650
    return {'status':'PASS','package_members_verified':len(checked),'A_primary_S_D_rows':10,'A_page_count_rows':len(page_data),
            'B_original_operation_rows':len(b_counts),'legacy_retrieval_rows':len(retrieval),
            'scope':'Integrity, aggregate arithmetic, preserved page-count resampling, numeric source-effect records. Does not verify a gold target, source images, human judgments or retrieval effectiveness.'}

def environment():
    result={'status':'PASS','Python':platform.python_version(),'dependencies':{}}
    for name in ['rapidfuzz','numpy','matplotlib']:
        try:
            module=__import__(name);result['dependencies'][name]=module.__version__
        except ImportError:
            result['dependencies'][name]='MISSING';result['status']='BLOCKED'
    return result

def evaluate(input_root, repository_root):
    paths={}; problems=[]
    for item in read_json('metadata/restricted_inputs.json')['inputs']:
        key='repository_path' if repository_root else 'input_path'
        base=Path(repository_root or input_root)
        p=base/item[key]
        if not p.is_file():
            problems.append({'input':item['input_path'],'problem':'missing'})
        elif digest(p)!=item['sha256']:
            problems.append({'input':item['input_path'],'problem':'different preserved-file hash; refusing new evaluation'})
        else:
            paths[item['input_path']]=p
    if problems:
        return {'status':'BLOCKED','inputs':problems,'performance_metrics':None,
                'reason':'Obtain author-approved lawful access; no source files or access permissions are supplied by this package.'}
    import rapidfuzz
    from rapidfuzz.distance import Levenshtein
    if rapidfuzz.__version__!='3.14.6':
        raise RuntimeError('Use RapidFuzz 3.14.6 for preserved edit-operation tie behavior')
    a=load('archived_a','code/a_scoring.py'); b=load('archived_b','code/b_scoring.py')
    c=load('archived_correction','code/correction_scoring.py')
    text=lambda name:paths[name].read_text(encoding='utf-8-sig')
    ref_s=text('benchmark_a/reference_S.txt')
    change=read_json('metadata/benchmark_a/reference_change.json')
    start,end=change['removed_original_codepoint_span'];ref_d=ref_s[:start]+ref_s[end:]
    names={'Tesseract':'Tesseract.txt','Gemma 3 27B':'Gemma_27B_output.txt','Gemma 3 12B':'Gemma_12B_output.txt','Llama 4 Scout':'Llama4_Scout_output.txt','Gemma 3 4B':'Gemma_4B_output.txt'}
    bounds=read_json('metadata/benchmark_a/page_boundaries.json')
    refpages=[ref_d[r['start_codepoint']:r['end_codepoint']] for r in bounds['reference_D']]
    assert ''.join(refpages)==ref_d
    actual_pages=[];a_hyp={}
    for system,file in names.items():
        p=paths['benchmark_a/'+file]
        if system=='Tesseract':
            full=p.read_text(encoding='utf-8-sig')
            pages=[full[r['start_codepoint']:r['end_codepoint']] for r in bounds['Tesseract_export']]
            assert ''.join(pages)==full
        else:
            pages=a.load_page_marked_hypothesis(p);full='\n'.join(pages)
        a_hyp[system]=pages
        for row in [r for r in rows('results/benchmark_a/primary_S_D_counts.csv') if r['system']==system]:
            ref=ref_s if row['reference_version'].startswith('S_') else ref_d
            for unit,rr,hh,metric in [('character',a.normalize_text(ref),a.normalize_text(full),'CER'),('word',a.tokenize(a.normalize_text(ref)),a.tokenize(a.normalize_text(full)),'WER')]:
                ops=Levenshtein.editops(rr,hh);counts=collections.Counter(o.tag for o in ops)
                for key,tag in [('S','replace'),('D','delete'),('I','insert')]:
                    close(counts[tag],row[unit+'_'+key],'A full count '+system)
                close(len(rr),row[unit+'_N'],'A full denominator')
                close(len(ops)/len(rr),row[metric],'A full rate')
        for i,(rp,hp) in enumerate(zip(refpages,pages)):
            rn,hn=a.normalize_text(rp),a.normalize_text(hp);rt,ht=a.tokenize(rn),a.tokenize(hn)
            actual_pages.append({'system':system,'page':str(i+10),'reference_characters':len(rn),'hypothesis_characters':len(hn),
                                 'character_edits':Levenshtein.distance(rn,hn),'reference_tokens':len(rt),'hypothesis_tokens':len(ht),'word_edits':Levenshtein.distance(rt,ht)})
    for actual in actual_pages:
        old=next(r for r in rows('results/benchmark_a/page_counts.csv') if r['system']==actual['system'] and r['page']==actual['page'])
        for k in actual:
            if k!='system':close(actual[k],old[k],'A physical-page count')
    legacy=read_json('metadata/benchmark_a/legacy_reference_segments.json')
    legacy_ref=[ref_s[s:e].strip() for s,e in zip(legacy['start_codepoints'],legacy['end_codepoints'])]
    old_boot=rows('results/benchmark_a/benchmark_a_original_bootstrap.csv')
    for old in old_boot:
        print('Checking preserved legacy A bootstrap:',old['system'],old['resamples'],flush=True)
        for metric,fn in [('CER',a.cer),('WER',a.wer)]:
            value,low,high=a.bootstrap_ci(legacy_ref,a_hyp[old['system']],fn,n=int(old['resamples']),seed=int(old['seed']))
            for key,x in [(metric,value),(metric+'_low',low),(metric+'_high',high)]:close(x,old[key],'A defective legacy bootstrap')
    print('A archived-output checks passed',flush=True)
    ref=b.crop_to_qara_sozder(text('benchmark_b/reference_pravda.txt'))
    hyps={system:b.crop_to_qara_sozder(text('benchmark_b/'+file)) for system,file in {
        'DeepSeek-OCR':'DeepSeek_OCR_prediction.txt','DP-2-mini / LandingAI':'DP2_mini_LandingAI_prediction.txt','Tesseract':'Tesseract_Abai_Karasoz_201096.txt'}.items()}
    rnorm=b.normalize_text(ref);rt=b.tokens(ref);charops={};wordops={}
    for system,h in hyps.items():
        hn=b.normalize_text(h);ht=b.tokens(h)
        charops[system]=Levenshtein.editops(rnorm,hn);wordops[system]=Levenshtein.editops(rt,ht)
        for row in [r for r in rows('results/benchmark_b/benchmark_b_alignment_counts.csv') if r['system']==system]:
            rn1,hn1=(rnorm,hn) if row['alignment']=='case_sensitive' else (rnorm.lower(),hn.lower())
            ops=Levenshtein.editops(rn1,hn1);count=collections.Counter(o.tag for o in ops)
            for key,tag in [('S','replace'),('D','delete'),('I','insert')]:close(count[tag],row[key],'B operation class')
            close(len(ops),row['edits'],'B edits');close(len(ops)/len(rn1),row['CER'],'B CER')
        tag={'DeepSeek-OCR':'DeepSeek','DP-2-mini / LandingAI':'DP2','Tesseract':'Tesseract'}[system]
        oldword=next(r for r in rows('results/benchmark_b/unchanged_original_score_verification.csv') if r['system']==tag and r['unit']=='word')
        for key,op in [('S','replace'),('D','delete'),('I','insert')]:close(sum(x.tag==op for x in wordops[system]),oldword[key],'B word operations')
        row=next(r for r in rows('results/benchmark_b/qara_sozder_bootstrap_ci.csv') if r['system']==system)
        for level,prefix in [('char','cer'),('word','wer')]:
            value,low,high=b.bootstrap_edit_bins(ref,h,level=level,bins=45,n=500)
            for key,x in [(prefix+'_ci_low',low),(prefix+'_ci_high',high)]:close(x,row[key],'B edit-bin range')
            close(value,row['cer' if level=='char' else 'wer_uniform_unicode'],'B bin point')
        summary,_=b.error_summary(ref,h)
        for row in [r for r in rows('results/benchmark_b/qara_sozder_error_classes.csv') if r['system']==system]:
            close(summary[row['error_class']],row['count'],'B lowercase classes')
        for actual in b.retrieval_sensitivity(ref,h):
            old=next(r for r in rows('results/benchmark_b/qara_sozder_retrieval_sensitivity_bm25.csv') if r['system']==system and r['mode']==actual['mode'])
            for key in ['queries','recall_at_1','recall_at_3','recall_at_5','mrr','ref_units','hyp_units']:
                close(actual[key],old[key],'legacy diagnostic '+key)
        print('B archived-output checks passed:',system,flush=True)
    names={'DeepSeek':'DeepSeek-OCR','DP2':'DP-2-mini / LandingAI','Tesseract':'Tesseract'}
    for row in read_json('metadata/benchmark_b/source_difference_windows.json'):
        system=names[row['system']];ra,rb=row['reference_start'],row['reference_end']
        count=collections.Counter(o.tag for o in charops[system] if ra<=o.src_pos<rb)
        for key,tag in [('S','replace'),('D','delete'),('I','insert')]:close(count[tag],row['full_alignment_window_'+key],'B source window')
        wa,wb=len(b.tokens(rnorm[:ra])),len(b.tokens(rnorm[:rb]))
        if row['issue']=='section_45_orthography':
            close(sum(o.src_pos==wa for o in wordops[system]),row['word_alignment_edits_at_reference_token'],'B orthography word operations')
        else:
            wc=collections.Counter(o.tag for o in wordops[system] if wa<=o.src_pos<wb)
            for key,tag in [('S','replace'),('D','delete'),('I','insert')]:close(wc[tag],row['word_alignment_window_'+key],'B source word window')
    tn=b.normalize_text(hyps['Tesseract']);import re
    spans=list(re.finditer(r'\w+',tn.lower()))
    for row in read_json('metadata/benchmark_b/nonbody_regions.json'):
        start,end=row['normalized_hypothesis_start'],row['normalized_hypothesis_end']
        ids={i for i,m in enumerate(spans) if start<=m.start()<end}
        co=collections.Counter(o.tag for o in charops['Tesseract'] if start<=o.dest_pos<end)
        wo=collections.Counter(o.tag for o in wordops['Tesseract'] if o.dest_pos in ids)
        for key,tag in [('S','replace'),('D','delete'),('I','insert')]:
            close(co[tag],row['original_character_alignment_'+key],'B annotation operation')
            close(wo[tag],row['original_word_alignment_'+key],'B annotation word operation')
    tess_raw=text('benchmark_b/Tesseract_Abai_Karasoz_201096.txt')
    for row in rows('results/benchmark_b/benchmark_B_scope_sensitivity.csv'):
        hh=b.crop_to_qara_sozder(tess_raw[:int(row['raw_end_codepoint'])])
        rr,hs=(rnorm,b.normalize_text(hh)) if row['unit']=='character' else (rt,b.tokens(hh))
        ops=Levenshtein.editops(rr,hs);counts=collections.Counter(o.tag for o in ops)
        for key,tag in [('S','replace'),('D','delete'),('I','insert')]:close(counts[tag],row[key],'existing Tesseract crop diagnostic')
        close(len(ops)/len(rr),row['rate'],'existing crop rate')
    token=lambda x:c.tokenize_kazakh(c.normalize_text(x))
    cr=token(text('correction/Abay_olender.txt'))
    for row in read_json('results/correction/saved_correction_scores.json'):
        h=token(text('correction/'+row['input_name']))
        close(Levenshtein.distance(cr,h),row['word_edits'],'saved correction edits')
        close(Levenshtein.distance(' '.join(cr),' '.join(h)),row['character_edits'],'saved correction token-string edits')
    return {'status':'PASS','exact_restricted_inputs_verified':len(paths),'A_S_D_rows_verified':10,'A_physical_page_rows_verified':35,
            'A_legacy_bootstrap_rows_verified':len(old_boot),'B_systems_verified':3,'legacy_MRR_rows_verified':9,
            'source_difference_windows_verified':len(read_json('metadata/benchmark_b/source_difference_windows.json')),
            'annotation_regions_verified':len(read_json('metadata/benchmark_b/nonbody_regions.json')),
            'saved_correction_variants_verified':4,'new_OCR_runs':0,'replacement_scores':0,
            'scope':'Same archived-output computations only. Visual source decisions and human approvals are not supplied. No book text is written to outputs.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['environment','verify','figures','gate','evaluate'])
    parser.add_argument('--output',required=True,help='Output path below this package work/ directory')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--input-root',default='authorized_inputs',help='External permitted input directory, mapped by metadata/restricted_inputs.json')
    group.add_argument('--repository-root',help='Maintainer-only: read exact existing input paths from an authorized original repository')
    args=parser.parse_args()
    if args.command=='environment':result=environment()
    elif args.command=='verify':result=verify()
    elif args.command=='figures':
        target=Path(args.output).resolve();target.relative_to((ROOT/'work').resolve())
        module=load('release_figures','code/render_figures.py')
        result=module.render(ROOT,target)
        args.output=str(target/'figure_data_check.json')
    elif args.command=='gate':
        module=load('prospective_retrieval','code/prospective/retrieval_evaluation.py')
        template=ROOT/'templates/retrieval_bundle_PENDING.json'
        result=module.run(read_json('templates/retrieval_bundle_PENDING.json'),template.parent)
        assert result['status']=='BLOCKED' and result['performance_metrics'] is None
        result['expected_blocked_template']=True
        # This wrapper succeeds when the intended empty-template gate is tested.
    else:result=evaluate(args.input_root,args.repository_root)
    write_output(args.output,result)
    if result['status']=='BLOCKED' and args.command!='gate':return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())
