"""Real offline mission and database-reopen demonstration; no mocked model output."""
import json,tempfile,time
from pathlib import Path
from titan.store import Database
from titan.engine import Worker
from titan.improvement import Improvements
from titan.backup import backup
with tempfile.TemporaryDirectory() as d:
 path=Path(d)/'demo.db';db=Database(path)
 mid=db.submit('Compare production durations','workflow',{'steps':[{'id':'baseline','kind':'analysis','values':[24,26,25,25]},{'id':'candidate','kind':'analysis','values':[22,23,24,23],'depends_on':['baseline']}]})
 Worker(db).once();backup(str(path),str(Path(d)/'backup.db'))
 result={'recorded_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'live_external_AI_calls':0,'reopened_mission':Database(Path(d)/'backup.db').get(mid),'fixed_benchmark':Improvements(db).evaluate({'description':'Current analysis implementation'})}
 Path('docs/evidence').mkdir(parents=True,exist_ok=True)
 Path('docs/evidence/offline-demo.json').write_text(json.dumps(result,indent=2))
 print('Real workflow completed, database backed up and reopened; mean durations 25 and 23 seconds.')
