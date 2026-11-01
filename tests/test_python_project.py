import unittest
from titan.python_project import normalize,harness,summary
class PythonProject(unittest.TestCase):
 def test_valid_package(self):
  files={'calc/__init__.py':'','calc/math.py':'def add(a,b):return a+b','test_math.py':'import unittest\nfrom calc.math import add\nclass T(unittest.TestCase):\n def test_sum(self):self.assertEqual(add(2,3),5)'}
  self.assertEqual(len(normalize({'files':files})),3);self.assertIn('TITAN_TEST_SUMMARY',harness(files))
 def test_path_and_package_boundaries(self):
  for path in ('../escape.py','/root.py','x//bad.py','x.py/child.py','_titan_secret.py'):
   with self.assertRaises(ValueError):normalize({'files':{path:'','test_a.py':''}})
  with self.assertRaises(ValueError):normalize({'files':{'pkg/code.py':'','test_a.py':''}})
 def test_missing_tests_and_budget(self):
  with self.assertRaises(ValueError):normalize({'files':{'solution.py':''}})
  with self.assertRaises(ValueError):normalize({'files':{'test_a.py':'#'+'x'*20001}})
 def test_legacy_and_independent_acceptance(self):
  files=normalize({'source':'x=1','tests':'import unittest'})
  self.assertIn('test__titan_acceptance.py',harness(files,'import unittest'))
 def test_summary_rejects_early_exit_and_skip(self):
  self.assertIsNone(summary({'exit_code':0,'output':''}))
  self.assertIsNone(summary({'exit_code':0,'output':'TITAN_TEST_SUMMARY={"tests_run":1,"failures":0,"errors":0,"skipped":1}'}))
  self.assertEqual(summary({'exit_code':0,'output':'TITAN_TEST_SUMMARY={"tests_run":1,"failures":0,"errors":0,"skipped":0}'})['tests_run'],1)
