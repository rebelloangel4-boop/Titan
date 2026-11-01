import json,zipfile,hashlib
from pathlib import Path
from test_platform import Base
from titan.workspace import Workspace
from titan.store import Database
from titan.snapshot import create,restore

class SnapshotTests(Base):
 def setUp(self):
  super().setUp();self.ws=Workspace(self.db);self.zip=Path(self.temp.name)/'snapshot.zip'
 def test_roundtrip_database_and_artifact(self):
  a=self.ws.artifact('default','test','proof.txt',b'verified')
  self.ws.remember('default','memory','persisted')
  create(self.path,self.ws.root,self.zip);target=Path(self.temp.name)/'restored'
  db=Database(restore(self.zip,target));ws=Workspace(db)
  self.assertEqual(ws.read_artifact(a['artifact_id'])[1],b'verified')
  self.assertEqual(ws.search('default','persisted')[0]['value'],'persisted')
 def test_existing_destination_preserved(self):
  target=Path(self.temp.name)/'existing';target.mkdir();(target/'keep').write_text('safe')
  with self.assertRaises(FileExistsError):restore(self.zip,target)
  self.assertEqual((target/'keep').read_text(),'safe')
 def test_corrupt_artifact_rejected(self):
  a=self.ws.artifact('default','test','proof.txt',b'verified');(self.ws.root/a['artifact_id']).write_bytes(b'bad')
  with self.assertRaises(ValueError):create(self.path,self.ws.root,self.zip)
  self.assertFalse(self.zip.exists())
 def test_symlink_rejected(self):
  a=self.ws.artifact('default','test','proof.txt',b'verified');p=self.ws.root/a['artifact_id'];p.unlink();p.symlink_to(self.path)
  with self.assertRaises(OSError):create(self.path,self.ws.root,self.zip)
 def test_traversal_and_cleanup(self):
  with zipfile.ZipFile(self.zip,'w') as z:
   z.writestr('manifest.json',json.dumps({'version':1,'files':{name:{'size':3,'sha256':hashlib.sha256(b'bad').hexdigest()} for name in ('state.db','../escape')}}))
   z.writestr('state.db','bad');z.writestr('../escape','bad')
  target=Path(self.temp.name)/'restored'
  with self.assertRaises((ValueError,KeyError)):restore(self.zip,target)
  self.assertFalse(target.exists());self.assertFalse((target.parent/'escape').exists())

 def test_archive_hash_tampering_rejected(self):
  create(self.path,self.ws.root,self.zip)
  bad=Path(self.temp.name)/'tampered.zip'
  with zipfile.ZipFile(self.zip) as src,zipfile.ZipFile(bad,'w') as dst:
   for name in src.namelist():dst.writestr(name,b'corrupt' if name=='state.db' else src.read(name))
  target=Path(self.temp.name)/'restored'
  with self.assertRaises(ValueError):restore(bad,target)
  self.assertFalse(target.exists())
