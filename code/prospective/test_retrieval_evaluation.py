"""Synthetic software checks only. These are not literary judgments/results."""
import unittest
from pathlib import Path
from retrieval_evaluation import bm25, literal_headings, chunk_id, metrics, run, human_record

class RetrievalContracts(unittest.TestCase):
    def test_compound_ordinal_does_not_match_suffix(self):
        raw='Он сегізінші сөз\nbody Сегізінші сөз body\nСегізінші сөз\n'
        rows=literal_headings(raw,['Сегізінші','Он сегізінші'])
        self.assertEqual([x['candidate_section_id'] for x in rows],[2,1])
        for x in rows:self.assertTrue(raw[x['start_codepoint']:x['end_codepoint']].startswith(x['literal']))
    def test_no_confusable_folding(self):
        self.assertEqual(literal_headings('Bірінші сөз\n',['Бірінші']),[])
    def test_markdown_is_explicit(self):
        self.assertEqual(len(literal_headings('## **Бірінші сөз**\n',['Бірінші'])),1)
    def test_zero_overlap_abstains(self):
        self.assertEqual(bm25('alpha',[{'chunk_id':'a','text':'beta'}]),[])
    def test_stable_ties_and_empty_documents(self):
        ds=[{'chunk_id':'z','text':'alpha'},{'chunk_id':'a','text':'alpha'}]
        self.assertEqual([x[0] for x in bm25('alpha',ds)],['a','z'])
        self.assertEqual(bm25('x',[{'chunk_id':'e','text':''}]),[])
    def test_missing_relevant_target_is_zero_in_common_denominator(self):
        r=metrics(['q1','q2'],{'q1':[('a',1.)]}, {'q1':{'a':2},'q2':{'a':0}})
        self.assertEqual(r['n_queries'],2);self.assertEqual(r['macro']['RR'],.5)
        self.assertEqual(r['per_query'][1]['RR'],0.)
    def test_zero_queries_undefined(self):
        with self.assertRaises(ValueError):metrics([],{}, {})
    def test_id_bound_to_source_and_span(self):
        self.assertNotEqual(chunk_id('a',0,1,'x'),chunk_id('b',0,1,'x'))
        self.assertNotEqual(chunk_id('a',0,1,'x'),chunk_id('a',1,2,'x'))
    def test_identical_text_in_distinct_collections_has_distinct_ids(self):
        self.assertNotEqual(chunk_id('a',0,1,'x','system-a'),chunk_id('a',0,1,'x','system-b'))
    def test_missing_approval_file_cannot_open_gate(self):
        self.assertFalse(human_record({'status':'approved'},Path.cwd()))
    def test_missing_human_evidence_blocks_metrics(self):
        r=run({},Path.cwd());self.assertEqual(r['status'],'BLOCKED');self.assertIsNone(r['performance_metrics'])

if __name__=='__main__':unittest.main(verbosity=2)
