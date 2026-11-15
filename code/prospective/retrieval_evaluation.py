"""Prospective retrieval evaluator. No benchmark qrels or queries are inferred.

`python retrieval_evaluation.py gate bundle.json output.json` validates first.
An incomplete bundle emits BLOCKED, never a replacement performance score.
Approval metadata are assertions by named humans, not cryptographic proof.
"""
from __future__ import annotations
import collections, datetime, hashlib, json, math, re, sys
from pathlib import Path

def tokenize(text):
    return re.findall(r'\w+', text.lower(), flags=re.UNICODE)

def chunk_id(source_sha256, start, end, text, collection_id=''):
    payload = f'{collection_id}:{source_sha256}:{start}:{end}:'.encode() + text.encode('utf-8')
    return 'chunk-' + hashlib.sha256(payload).hexdigest()

def literal_headings(raw, ordinals):
    """Full raw-line matches; preserves compound ordinals and original offsets.

    Markdown wrappers, case and horizontal spacing are explicit formatting
    allowances. No confusable folding, suffix search, fuzzy match or fallback.
    A literal label is a candidate, not an approved content mapping.
    """
    lookup = {x.casefold(): i for i, x in enumerate(ordinals, 1)}
    rows = []; offset = 0
    for n, line in enumerate(raw.splitlines(keepends=True), 1):
        t = line.strip().lstrip('#').strip().strip('*').strip()
        t = re.sub(r'[ \t]+', ' ', t).rstrip(':').strip()
        if t.casefold().endswith(' сөз'):
            ordinal = t[:-4].strip().casefold()
            if ordinal in lookup:
                rows.append({'candidate_section_id': lookup[ordinal], 'line': n,
                             'start_codepoint': offset, 'end_codepoint': offset + len(line),
                             'literal': line.rstrip('\r\n'), 'status': 'UNADJUDICATED_LITERAL_CANDIDATE'})
        offset += len(line)
    return rows

def bm25(query, documents, k1=1.5, b=.75):
    """Only positive evidence is ranked; ties sort by stable ID ascending."""
    if not documents: return []
    ds = [(x['chunk_id'], tokenize(x['text'])) for x in documents]
    avg = sum(len(ts) for _, ts in ds) / len(ds)
    if not avg: return []
    df = collections.Counter(t for _, ts in ds for t in set(ts))
    terms = set(tokenize(query)); ranked = []
    for doc_id, ts in ds:
        tf = collections.Counter(ts); score = 0.
        for t in terms:
            if not tf[t]: continue
            idf = math.log(1 + (len(ds) - df[t] + .5)/(df[t] + .5))
            score += idf * tf[t]*(k1+1)/(tf[t] + k1*(1-b+b*len(ts)/avg))
        if score > 0: ranked.append((doc_id, score))
    return sorted(ranked, key=lambda x: (-x[1], x[0]))

def metrics(query_ids, rankings, judgments):
    """Fixed common denominator, binary relevant grade>=1, graded nDCG@10.

    Requires complete candidate judgments, checked by the bundle gate.
    Abstentions/empty collections/missing relevant material contribute zero.
    """
    if not query_ids: raise ValueError('No approved queries; metrics undefined')
    per = []
    for q in query_ids:
        ranked = [x[0] for x in rankings.get(q, [])]
        rel = judgments[q]
        hits = [i for i,d in enumerate(ranked,1) if rel.get(d,0)>=1]
        ideal = sorted(rel.values(), reverse=True)[:10]
        dcg = sum((2**rel[d]-1)/math.log2(i+1) for i,d in enumerate(ranked[:10],1))
        idcg = sum((2**g-1)/math.log2(i+1) for i,g in enumerate(ideal,1))
        per.append({'query_id':q, 'RR':1/hits[0] if hits else 0.,
                    'hit_at_1':float(any(i<=1 for i in hits)),
                    'hit_at_3':float(any(i<=3 for i in hits)),
                    'hit_at_5':float(any(i<=5 for i in hits)),
                    'nDCG_at_10':dcg/idcg if idcg else 0.})
    return {'n_queries':len(per), 'per_query':per,
            'macro':{k:sum(x[k] for x in per)/len(per) for k in per[0] if k!='query_id'}}

def human_record(x, base):
    if not isinstance(x,dict) or x.get('status')!='approved' or not all(x.get(k) for k in ['reviewer_id','timestamp_utc','evidence_path','evidence_sha256']):return False
    try:
        stamp=datetime.datetime.fromisoformat(x['timestamp_utc'].replace('Z','+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset()!=datetime.timedelta(0):return False
        p=(base/x['evidence_path']).resolve();p.relative_to(base.resolve())
        return hashlib.sha256(p.read_bytes()).hexdigest()==x['evidence_sha256']
    except (ValueError,TypeError,OSError):return False

def validate(bundle, base):
    errors=[]
    for field in ['target_reference_approval','region_policy_approval','source_equivalence_approval','query_protocol_approval']:
        if not human_record(bundle.get(field),base): errors.append(field+' missing human approval/evidence')
    queries=bundle.get('queries',[]); docs=bundle.get('documents',[]); qs=bundle.get('qrels',[])
    systems=bundle.get('systems',[])
    if not systems or len(systems)!=len(set(systems)): errors.append('systems missing/duplicated')
    if not queries: errors.append('independent queries absent')
    if not docs: errors.append('source-verified collections absent')
    if not qs: errors.append('content-based relevance judgments absent')
    qids=[q.get('query_id') for q in queries]; dids=[d.get('chunk_id') for d in docs]
    if len(qids)!=len(set(qids)) or None in qids: errors.append('invalid/duplicate query IDs')
    if len(dids)!=len(set(dids)) or None in dids: errors.append('invalid/duplicate chunk IDs')
    for q in queries:
        if not q.get('text','').strip() or q.get('origin')!='independent_information_need' or not human_record(q.get('approval'),base):
            errors.append('invalid query provenance: '+str(q.get('query_id')))
    for d in docs:
        if d.get('system') not in systems or not d.get('content_anchors') or not human_record(d.get('mapping_approval'),base):
            errors.append('unverified content mapping: '+str(d.get('chunk_id')))
        try:
            p=(base/d['source_file']).resolve(); p.relative_to(base.resolve())
            raw=p.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
            text=raw.decode('utf-8-sig'); start=d['start_codepoint']; end=d['end_codepoint']
            assert 0<=start<=end<=len(text)
            if start==end: assert d.get('missing_source_unit') is True and d['text']==''
            assert sha==d['source_sha256'] and text[start:end]==d['text']
            assert chunk_id(sha,start,end,d['text'],d['system'])==d['chunk_id']
        except Exception as e: errors.append('chunk source/hash/span validation failed: '+str(d.get('chunk_id')))
    seen=set()
    for q in qs:
        key=(q.get('query_id'),q.get('chunk_id'))
        if key in seen or key[0] not in qids or key[1] not in dids: errors.append('duplicate/unknown qrel '+str(key))
        seen.add(key)
        r1=q.get('reviewer_1',{});r2=q.get('reviewer_2',{});adj=q.get('adjudication',{})
        if not human_record(r1,base) or not human_record(r2,base) or r1.get('reviewer_id')==r2.get('reviewer_id') or not human_record(adj,base):
            errors.append('incomplete independent review/adjudication '+str(key))
        if any(type(r.get('grade')) is not int or r['grade'] not in (0,1,2) for r in [r1,r2]):
            errors.append('independent reviewer grades absent '+str(key))
        if adj.get('grade')!=q.get('grade') or not adj.get('reason'):
            errors.append('adjudicated grade/reason absent '+str(key))
        if type(q.get('grade')) is not int or q['grade'] not in (0,1,2) or not q.get('content_evidence'):
            errors.append('invalid grade/content evidence '+str(key))
    # Complete judgments make unknown relevance distinct from nonrelevance.
    if seen!={(q,d) for q in qids for d in dids}: errors.append('incomplete query-by-candidate judgment coverage')
    if not bundle.get('clean_reference_system') in systems: errors.append('clean-reference baseline absent')
    # Primary experiment holds semantic retrieval units fixed across collections.
    # A separate segmentation experiment needs its own frozen protocol/qrels.
    unit_sets={}
    doc_units={}
    for system in systems:
        units=[]
        for d in docs:
            if d.get('system')!=system: continue
            anchors=d.get('content_anchors',[])
            if len(anchors)!=1 or not isinstance(anchors[0],str):
                errors.append('primary controlled evaluation requires one canonical unit per chunk')
                continue
            units.append(anchors[0]);doc_units[d['chunk_id']]=anchors[0]
        if not units or len(units)!=len(set(units)): errors.append('missing/duplicate canonical units in '+system)
        unit_sets[system]=set(units)
    if len({tuple(sorted(x)) for x in unit_sets.values()})>1:
        errors.append('canonical unit sets differ; missing units require explicit empty placeholders')
    grades={}
    for q in qs:
        if q.get('chunk_id') not in doc_units: continue
        key=(q.get('query_id'),doc_units[q['chunk_id']])
        if key in grades and grades[key]!=q.get('grade'):
            errors.append('inconsistent canonical relevance across systems')
        grades[key]=q.get('grade')
    return sorted(set(errors))

def run(bundle, base):
    errors=validate(bundle,base)
    if errors: return {'status':'BLOCKED','reasons':errors,'performance_metrics':None}
    result={'status':'READY_CONDITIONAL_ON_HUMAN_RECORDS','systems':{}}
    ids=[q['query_id'] for q in bundle['queries']]
    for system in bundle['systems']:
        docs=[d for d in bundle['documents'] if d['system']==system]
        rankings={q['query_id']:bm25(q['text'],docs) for q in bundle['queries']}
        judgments={q:{r['chunk_id']:r['grade'] for r in bundle['qrels'] if r['query_id']==q and any(d['chunk_id']==r['chunk_id'] for d in docs)} for q in ids}
        result['systems'][system]={'metrics':metrics(ids,rankings,judgments),'rankings':rankings}
    return result

if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='gate': raise SystemExit('usage: retrieval_evaluation.py gate bundle.json output.json')
    p=Path(sys.argv[2]); b=json.loads(p.read_text(encoding='utf-8'))
    out=run(b,p.parent)
    Path(sys.argv[3]).write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(out['status']);raise SystemExit(2 if out['status']=='BLOCKED' else 0)
