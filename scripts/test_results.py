"""Execute real unittest tests and emit per-test outcomes, not G4 agent evaluations."""
import csv
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class Results(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.rows=[]
        self.outcomes={}

    def addSuccess(self,test):
        super().addSuccess(test)
        self.outcomes.setdefault(test.id(),'PASS')

    def addFailure(self,test,err):
        super().addFailure(test,err)
        self.outcomes[test.id()]='FAIL'

    def addError(self,test,err):
        super().addError(test,err)
        self.outcomes[test.id()]='ERROR'

    def addSkip(self,test,reason):
        super().addSkip(test,reason)
        self.outcomes[test.id()]='SKIP'

    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err: self.outcomes[test.id()]='FAIL'

    def stopTest(self,test):
        actual=self.outcomes.get(test.id(),'ERROR')
        self.rows.append(dict(scenario=test.id(),expected='All executable assertions and state invariants hold',
                              actual=actual,pass_fail=actual,
                              notes='G2 acceptance test' if 'test_g2_' in test.id() else 'G1 provider regression'))
        super().stopTest(test)

if __name__=='__main__':
    out=Path(sys.argv[1])
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(suite)
    report=dict(tests_run=result.testsRun,passed=sum(r['pass_fail']=='PASS' for r in result.rows),
                failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
                rows=result.rows)
    (out/'test_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    with (out/'test_results.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['scenario','expected','actual','pass_fail','notes'])
        writer.writeheader()
        writer.writerows(result.rows)
    raise SystemExit(0 if result.wasSuccessful() else 1)
