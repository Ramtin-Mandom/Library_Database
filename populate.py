"""Build library.db atomically from schema.sql and tab-separated data files."""
from pathlib import Path
import argparse, csv, sqlite3

ROOT=Path(__file__).resolve().parent; DB=ROOT/'library.db'; SCHEMA=ROOT/'schema.sql'; DATA=ROOT/'data'
TABLES=['Member','Employee','Creator','MaterialType','CatalogueItem','CreatedBy','PeriodicalIssue','LibraryUnit','PhysicalCopy','DigitalLicence','RepresentsIssue','Loan','Fine','Room','Event','Audience','RecommendedFor','Registration','ItemProposal','ResultsIn','VolunteerApplication','HelpRequest']

def read_rows(conn, table):
    path=DATA/f'{table}.txt'
    with path.open(encoding='utf-8',newline='') as f:
        reader=csv.reader(f,delimiter='\t'); header=next(reader,None)
        expected=[r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
        if header!=expected: raise ValueError(f'{path.name}: header {header!r}, expected {expected!r}')
        rows=[]
        for line,row in enumerate(reader,2):
            if len(row)!=len(header): raise ValueError(f'{path.name}:{line}: expected {len(header)} fields, got {len(row)}')
            rows.append(tuple(None if v==r'\N' else v for v in row))
        return header,rows

def build(reset=False, db_path=DB):
    db_path=Path(db_path)
    if db_path.exists():
        if not reset: raise FileExistsError(f'{db_path} already exists; use --reset')
        db_path.unlink()
    conn=sqlite3.connect(db_path); conn.execute('PRAGMA foreign_keys = ON')
    try:
        conn.executescript(SCHEMA.read_text(encoding='utf-8'))
        conn.execute('BEGIN')
        counts={}
        for table in TABLES:
            header,rows=read_rows(conn,table)
            marks=','.join('?' for _ in header); columns=','.join(f'"{c}"' for c in header)
            conn.executemany(f'INSERT INTO "{table}" ({columns}) VALUES ({marks})',rows); counts[table]=len(rows)
        fk=list(conn.execute('PRAGMA foreign_key_check'))
        if fk: raise RuntimeError(f'foreign key violations: {fk}')
        conn.commit()
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok': raise RuntimeError(f'integrity_check: {integrity}')
        print('Population complete:')
        for t in TABLES: print(f'  {t:<22} {counts[t]:>4}')
        print('foreign_key_check: ok\nintegrity_check: ok')
    except Exception:
        conn.rollback(); conn.close()
        if db_path.exists(): db_path.unlink()
        raise
    conn.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--reset',action='store_true'); build(p.parse_args().reset)
