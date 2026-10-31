import argparse,json,os
from .store import Database
from .engine import Worker

def main():
 from .security import load_secret_files
 load_secret_files()
 p=argparse.ArgumentParser();p.add_argument('objective',nargs='?');p.add_argument('--providers',default='gemini,groq');p.add_argument('--db',default=os.getenv('TITAN_DB','titan.db'));p.add_argument('--worker',action='store_true');p.add_argument('--once',action='store_true');a=p.parse_args();db=Database(a.db)
 if a.objective:print(db.submit(a.objective,payload={'providers':a.providers.split(',')}))
 if a.worker:Worker(db).run()
 elif a.once:Worker(db).once()
if __name__=='__main__':main()
