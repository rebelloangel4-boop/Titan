import json,sqlite3,sys,time

def healthy(path):
 try:
  with sqlite3.connect('file:'+path+'?mode=ro',uri=True,timeout=2) as c:
   row=c.execute("SELECT value FROM settings WHERE key='worker_heartbeat'").fetchone()
  return bool(row) and time.time()-float(row[0])<75
 except (sqlite3.Error,ValueError):return False
if __name__=='__main__':raise SystemExit(0 if healthy(sys.argv[1]) else 1)
