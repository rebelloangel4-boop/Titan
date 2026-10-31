"""Consistent SQLite backup, including committed WAL contents."""
import argparse,sqlite3
from pathlib import Path

def backup(source,destination):
 if Path(source).resolve()==Path(destination).resolve():raise ValueError('Use a different destination')
 if not Path(source).is_file():raise ValueError('Source database missing')
 if Path(destination).exists():raise ValueError('Destination already exists')
 with sqlite3.connect(source) as src,sqlite3.connect(destination) as dst:
  src.backup(dst)
  if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failure')
 Path(destination).chmod(0o600)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args();backup(a.source,a.destination)
