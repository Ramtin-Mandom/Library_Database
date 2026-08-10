import shutil, sqlite3, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import library_app as app

class LibraryAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'test.db'; shutil.copy2(ROOT/'library.db',self.db); self.c=app.connect(self.db)
    def tearDown(self): self.c.close(); self.tmp.cleanup()
    def eligible(self): return 1017
    def test_search_success(self): self.assertTrue(app.search_items(self.c,'title','Handmaid'))
    def test_borrow_success(self): self.assertIn('loanID',app.borrow_item(self.c,self.eligible(),5000,datetime(2027,2,1)))
    def test_suspended_rejected(self):
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,1001,5000,datetime(2027,2,1))
    def test_expired_rejected(self):
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,1002,5000,datetime(2027,2,1))
    def test_sixth_active_rejected(self):
        for unit in range(5013,5018): app.borrow_item(self.c,self.eligible(),unit,datetime(2027,2,1))
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,self.eligible(),5018,datetime(2027,2,1))
    def test_overdue_rejected(self):
        app.borrow_item(self.c,self.eligible(),5013,datetime(2026,1,1))
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,self.eligible(),5014,datetime(2027,2,1))
    def test_unpaid_fines_rejected(self):
        loan=self.c.execute('SELECT loanID FROM Loan WHERE memberNo=? AND returnedAt IS NOT NULL LIMIT 1',(self.eligible(),)).fetchone()[0]
        self.c.execute("INSERT INTO Fine(loanID,amount,assessedDate,reason,paymentStatus) VALUES(?,20,'2026-07-01 10:00:00','Replacement','unpaid')",(loan,)); self.c.commit()
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,self.eligible(),5013,datetime(2027,2,1))
    def test_two_physical_loans_rejected(self):
        app.borrow_item(self.c,self.eligible(),5000,datetime(2027,2,1))
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,1016,5000,datetime(2027,2,1))
    def test_digital_limit(self):
        app.borrow_item(self.c,self.eligible(),5013,datetime(2027,2,1)); app.borrow_item(self.c,1016,5013,datetime(2027,2,1)); app.borrow_item(self.c,1015,5013,datetime(2027,2,1))
        with self.assertRaises(app.LibraryError): app.borrow_item(self.c,1014,5013,datetime(2027,2,1))
    def test_return_success(self):
        loan=app.borrow_item(self.c,self.eligible(),5000,datetime(2027,2,1))['loanID']; app.return_item(self.c,loan,'good',when=datetime(2027,2,5)); self.assertEqual(self.c.execute('SELECT status FROM LibraryUnit WHERE unitID=5000').fetchone()[0],'available')
    def test_late_fine(self):
        loan=app.borrow_item(self.c,self.eligible(),5000,datetime(2027,2,1))['loanID']; app.return_item(self.c,loan,'good',when=datetime(2027,2,10)); self.assertEqual(self.c.execute("SELECT amount FROM Fine WHERE loanID=? AND reason='Automatic late return'",(loan,)).fetchone()[0],.5)
    def test_duplicate_registration(self):
        app.register_for_event(self.c,self.eligible(),9000,datetime(2026,9,1))
        with self.assertRaises(app.LibraryError): app.register_for_event(self.c,self.eligible(),9000,datetime(2026,9,1))
    def test_full_event(self):
        current=self.c.execute("SELECT count(*) FROM Registration WHERE eventNo=9003 AND status='registered'").fetchone()[0]
        self.c.execute('UPDATE Event SET maximumAttendance=? WHERE eventNo=9003',(current,)); self.c.commit()
        with self.assertRaises(app.LibraryError): app.register_for_event(self.c,self.eligible(),9003,datetime(2026,9,1))
    def test_cancelled_event(self):
        with self.assertRaises(app.LibraryError): app.register_for_event(self.c,self.eligible(),9001,datetime(2026,9,1))
    def test_room_capacity(self):
        with self.assertRaises(sqlite3.IntegrityError): self.c.execute("INSERT INTO Event VALUES(9990,'Too Large','workshop','x','2028-01-01 10:00:00','2028-01-01 11:00:00',999,'scheduled',8000,2001)")
    def test_room_overlap(self):
        with self.assertRaises(sqlite3.IntegrityError): self.c.execute("INSERT INTO Event VALUES(9991,'Overlap','workshop','x','2027-01-05 19:00:00','2027-01-05 21:00:00',10,'scheduled',8000,2001)")
    def test_subtype_exclusivity(self):
        with self.assertRaises(sqlite3.IntegrityError): self.c.execute("INSERT INTO DigitalLicence VALUES(5000,'X','https://x',1)")
    def test_donation(self): self.assertGreater(app.donate_item(self.c,self.eligible(),'A Northern Story','Jane Doe','print book','Toronto, 2025'),0)
    def test_volunteer(self): self.assertGreater(app.volunteer(self.c,self.eligible(),'Saturdays','Bilingual','general library work'),0)
    def test_help(self): self.assertGreater(app.ask_for_help(self.c,self.eligible(),'research','Need local-history sources.'),0)
    def test_resolved_help_requires_response(self):
        with self.assertRaises(sqlite3.IntegrityError): self.c.execute("UPDATE HelpRequest SET status='resolved',assignedEmployeeNo=2001,completedAt='2026-08-01 10:00:00',response=NULL WHERE requestNo=13000")
    def test_injection_is_data(self):
        self.assertEqual(app.search_items(self.c,'title',"%' OR 1=1; DROP TABLE Member;--"),[]); self.assertEqual(self.c.execute('SELECT count(*) FROM Member').fetchone()[0],18)

if __name__=='__main__': unittest.main()
