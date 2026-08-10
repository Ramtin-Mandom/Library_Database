"""Validate structure, data volume, referential integrity, and business rules."""
from pathlib import Path
import sqlite3, sys
from populate import TABLES
DB=Path(__file__).resolve().parent/'library.db'

def validate(path=DB):
    c=sqlite3.connect(path); c.execute('PRAGMA foreign_keys = ON')
    errors=[]; actual={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing=set(TABLES)-actual
    if missing: errors.append(f'missing tables: {sorted(missing)}')
    counts={t:c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in TABLES if t in actual}
    errors += [f'{t} has only {n} rows' for t,n in counts.items() if n<10]
    checks={
      'units without exactly one subtype':"SELECT unitID FROM LibraryUnit u WHERE (EXISTS(SELECT 1 FROM PhysicalCopy p WHERE p.unitID=u.unitID))+(EXISTS(SELECT 1 FROM DigitalLicence d WHERE d.unitID=u.unitID))<>1",
      'active physical duplicates':"SELECT unitID FROM Loan l JOIN PhysicalCopy USING(unitID) WHERE returnedAt IS NULL GROUP BY unitID HAVING count(*)>1",
      'digital limit violations':"SELECT d.unitID FROM DigitalLicence d JOIN Loan l ON l.unitID=d.unitID AND l.returnedAt IS NULL GROUP BY d.unitID HAVING count(*)>d.licenceLimit",
      'event room capacity violations':"SELECT eventNo FROM Event e JOIN Room r USING(roomNo) WHERE maximumAttendance>capacity",
      'invalid fine dates':"SELECT fineID FROM Fine f JOIN Loan l USING(loanID) WHERE assessedDate<borrowedAt OR (paymentDate IS NOT NULL AND paymentDate<assessedDate)",
      'invalid help requests':"SELECT requestNo FROM HelpRequest WHERE status IN ('resolved','closed') AND (response IS NULL OR trim(response)='' OR completedAt IS NULL OR assignedEmployeeNo IS NULL)",
      'invalid results':"SELECT r.proposalNo FROM ResultsIn r JOIN ItemProposal p USING(proposalNo) WHERE decisionStatus<>'accepted'",
      'self supervisors':"SELECT employeeNo FROM Employee WHERE employeeNo=supervisorNo"}
    for label,q in checks.items():
        rows=list(c.execute(q));
        if rows: errors.append(f'{label}: {rows}')
    fk=list(c.execute('PRAGMA foreign_key_check')); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close()
    if fk: errors.append(f'foreign_key_check: {fk}')
    if integrity!='ok': errors.append(f'integrity_check: {integrity}')
    for t in TABLES: print(f'{t:<22} {counts.get(t,0):>4}')
    print('foreign_key_check:', 'ok' if not fk else 'FAILED'); print('integrity_check:',integrity)
    if errors: raise AssertionError('\n'.join(errors))
    print('business-rule checks: ok'); return counts

if __name__=='__main__':
    try: validate()
    except Exception as e: print(f'VALIDATION FAILED: {e}',file=sys.stderr); raise SystemExit(1)
