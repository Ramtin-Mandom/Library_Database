CMPT 354 COMMUNITY LIBRARY MINI-PROJECT
Ramtin Rezaei, Student Number 301582747
Team member(s): [add names and student numbers if applicable]

PURPOSE
This Python/SQLite project implements the BCNF community-library design from Steps 1-3. It stores members, personnel, catalogue and lendable units, loans and fines, rooms and events, proposals, volunteering, and librarian help requests.

REQUIREMENTS
Python 3.10 or newer. Only the Python standard library is required to build, validate, test, and run the application.

FILES
mp.pdf: Steps 1, 2, and 3 in order.
schema.sql: 22-table SQLite schema, views, indexes, checks, and triggers.
data/*.txt: all sample tuples, one UTF-8 TSV file per relation.
populate.py: transactional database builder and TSV loader.
library.db: populated SQLite database.
library_app.py: testable database functions and minimal Tkinter graphical interface.
validate_db.py: structural, referential, integrity, count, and business-rule validation.
tests/test_library_app.py: unittest suite using disposable temporary databases.

COMMANDS (may be run from any working directory)
  python C:\Users\Ramtin\Desktop\coding\cmpt-354\Mini-Project\code\Library_Database\populate.py --reset
  python C:\Users\Ramtin\Desktop\coding\cmpt-354\Mini-Project\code\Library_Database\validate_db.py
  python -m unittest discover -s C:\Users\Ramtin\Desktop\coding\cmpt-354\Mini-Project\code\Library_Database\tests -v
  python C:\Users\Ramtin\Desktop\coding\cmpt-354\Mini-Project\code\Library_Database\library_app.py

DATA FORMAT
Each data file is UTF-8, tab-separated text. Its first row contains column names exactly matching the schema. The literal \N represents SQL NULL; an empty field remains an empty string. populate.py parses files with csv.reader(delimiter="\t"), validates headers and field counts, converts \N to None, and uses parameterized executemany calls. No sample tuple is hardcoded in the loader, schema, or application.

INTEGRITY AND SECURITY
Primary, composite, alternate, and foreign keys implement the Step 3 design. CHECK constraints restrict statuses, Booleans, dates, positive limits/capacities, and monetary values. Triggers enforce borrowing, subtype, event, registration, chronology, and workflow rules on inserts and relevant updates. Every connection enables PRAGMA foreign_keys. All user values are bound parameters; dynamic search columns come only from fixed whitelists. Borrowing, returns, registration, donations, volunteer applications, and help requests use atomic transactions, with BEGIN IMMEDIATE for concurrency-sensitive operations.

APPLICATION OPERATIONS
1. Find an item by title, creator, subject, material type, catalogue number, standard ID, or availability.
2. Borrow an eligible physical copy or digital licence.
3. Return an active loan, update physical condition/status, and assess late/replacement fines.
4. Submit a member-donation item proposal.
5. Find an event by title, type, date, audience, or availability.
6. Register an eligible member atomically while enforcing status, time, duplicates, and capacity.
7. Submit a general or event-specific volunteer application.
8. Submit an open librarian help request.

RECREATE DATABASE BUTTON
The graphical application includes a "Recreate database" button. After confirmation, it closes its active database connection, deletes only this project's library.db, executes schema.sql, reloads every tuple from the unchanged data/*.txt files in one transaction, runs foreign-key and integrity checks, and reconnects the application. This permanently discards loans, returns, proposals, registrations, applications, requests, and other changes made since the last rebuild. If another copy of the application has library.db open, close it before retrying.

QUICK UI TEST EXAMPLE
1. Rebuild the sample database with populate.py --reset, then launch library_app.py.
2. Select "Find an item". Enter title for Search field and Canadian for Search text, then click Run. Matching items and unit details should appear.
3. Select "Borrow an item". Enter member number 1017 and unit ID 5000, then click Run. The result shows a new loanID and dueAt value.
4. Select "Return a borrowed item". Enter that new loanID, condition good, and replacement charge 0, then click Run. The result should report Success.
The example changes library.db. Click "Recreate database" afterward (and confirm) to restore the original sample data. The equivalent command is populate.py --reset.

ASSUMPTIONS
Dates/timestamps use ISO-8601 text in local library time. Monetary amounts use two-decimal values; application calculations use Decimal before storage. A returned historical loan is accepted regardless of the member's current eligibility. Digital licences stay available until their concurrent-loan limit is reached. Total LibraryUnit subtype participation is checked after population and by validate_db.py; subtype disjointness is enforced immediately by triggers. The named Step .tex sources, lecture PDFs, and SQLite/Python notebooks were not present in the accessible project folders; mp.pdf therefore combines the supplied completed Step 1 (Project_overview.pdf), Step 2 (ER_Diagram.pdf), and Step 3 (BCNF.pdf) without rewriting them.
