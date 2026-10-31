"""Actual local throughput measurement; not a cloud load test or model benchmark."""
import json,statistics,tempfile,time
from pathlib import Path
from titan.store import Database
from titan.engine import Worker
with tempfile.TemporaryDirectory() as d:
 db=Database(Path(d)/'measure.db');latencies=[]
 start=time.perf_counter()
 for i in range(100):db.submit('Measured arithmetic '+str(i),'analysis',{'values':list(range(100))})
 enqueue=time.perf_counter()-start;worker=Worker(db);start=time.perf_counter()
 for i in range(100):
  t=time.perf_counter();assert worker.once();latencies.append(time.perf_counter()-t)
 elapsed=time.perf_counter()-start
 assert all(j['status']=='completed' for j in db.list())
 result={'missions':100,'input_numbers_per_mission':100,'enqueue_seconds':enqueue,'execution_seconds':elapsed,'missions_per_second':100/elapsed,'median_worker_ms':statistics.median(latencies)*1000,'p95_worker_ms':sorted(latencies)[94]*1000,'external_model_calls':0,'scope':'Single process local SQLite deterministic analysis; no cloud or model SLA'}
 Path('docs/evidence/performance.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
