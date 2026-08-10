"""Command-line application for the CMPT 354 community-library database."""
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sqlite3

DB_PATH=Path(__file__).resolve().parent/'library.db'
class LibraryError(Exception): pass

def connect(path=DB_PATH):
    c=sqlite3.connect(path); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys = ON'); return c
def now_text(value=None): return (value or datetime.now()).replace(microsecond=0).isoformat(' ')
def transactional(conn, action):
    try:
        conn.execute('BEGIN IMMEDIATE'); result=action(); conn.commit(); return result
    except (sqlite3.Error, LibraryError) as e:
        conn.rollback()
        if isinstance(e,LibraryError): raise
        raise LibraryError(str(e)) from e

def search_items(conn, field='title', value='', available_only=False):
    fields={'title':'c.title','creator':'cr.creatorName','subject':'c.subject','material type':'c.typeName','catalogue number':'CAST(c.catalogueNo AS TEXT)','standard id':'c.standardID','availability':'u.status'}
    key=field.lower()
    if key not in fields: raise LibraryError('Invalid search field')
    sql=f'''SELECT DISTINCT c.catalogueNo,c.title,c.typeName,c.subject,c.standardID,u.unitID,u.status,
      p.barcode,p.shelfLocation,d.licenceNo,d.accessURL,d.licenceLimit,
      CASE WHEN p.unitID IS NOT NULL THEN u.status='available'
           ELSE u.status NOT IN ('withdrawn','lost') AND (SELECT count(*) FROM Loan l WHERE l.unitID=u.unitID AND l.returnedAt IS NULL)<d.licenceLimit END available
      FROM CatalogueItem c JOIN CreatedBy cb USING(catalogueNo) JOIN Creator cr USING(creatorID)
      JOIN LibraryUnit u USING(catalogueNo) LEFT JOIN PhysicalCopy p USING(unitID) LEFT JOIN DigitalLicence d USING(unitID)
      WHERE {fields[key]} LIKE ?'''
    if available_only or key=='availability' and value.lower()=='available': sql+=' AND ((p.unitID IS NOT NULL AND u.status=\'available\') OR (d.unitID IS NOT NULL AND u.status NOT IN (\'withdrawn\',\'lost\') AND (SELECT count(*) FROM Loan l WHERE l.unitID=u.unitID AND l.returnedAt IS NULL)<d.licenceLimit))'
    return conn.execute(sql,(f'%{value}%',)).fetchall()

def borrow_item(conn, member_no, unit_id, when=None, employee_no=None):
    borrowed=now_text(when)
    def action():
        row=conn.execute('SELECT mt.defaultLoanDays FROM LibraryUnit u JOIN CatalogueItem c USING(catalogueNo) JOIN MaterialType mt USING(typeName) WHERE u.unitID=?',(unit_id,)).fetchone()
        if not row: raise LibraryError('Library unit not found')
        due=(datetime.fromisoformat(borrowed)+timedelta(days=row['defaultLoanDays'])).isoformat(' ')
        cur=conn.execute('INSERT INTO Loan(memberNo,unitID,processedByEmployeeNo,borrowedAt,dueAt) VALUES(?,?,?,?,?)',(member_no,unit_id,employee_no,borrowed,due))
        if conn.execute('SELECT 1 FROM PhysicalCopy WHERE unitID=?',(unit_id,)).fetchone(): conn.execute("UPDATE LibraryUnit SET status='on loan' WHERE unitID=?",(unit_id,))
        return {'loanID':cur.lastrowid,'dueAt':due}
    return transactional(conn,action)

def return_item(conn, loan_id, condition='good', replacement_charge=None, when=None):
    returned=now_text(when)
    if condition not in {'new','good','fair','damaged','lost'}: raise LibraryError('Invalid condition')
    try: charge=Decimal(str(replacement_charge or 0)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    except InvalidOperation as e: raise LibraryError('Invalid replacement charge') from e
    if charge<0: raise LibraryError('Replacement charge cannot be negative')
    def action():
        loan=conn.execute('SELECT * FROM Loan WHERE loanID=? AND returnedAt IS NULL',(loan_id,)).fetchone()
        if not loan: raise LibraryError('Active loan not found')
        conn.execute('UPDATE Loan SET returnedAt=? WHERE loanID=?',(returned,loan_id))
        physical=conn.execute('SELECT 1 FROM PhysicalCopy WHERE unitID=?',(loan['unitID'],)).fetchone()
        if physical:
            status='lost' if condition=='lost' else 'damaged' if condition=='damaged' else 'available'
            conn.execute('UPDATE PhysicalCopy SET condition=? WHERE unitID=?',(condition,loan['unitID'])); conn.execute('UPDATE LibraryUnit SET status=? WHERE unitID=?',(status,loan['unitID']))
            late=max(0,(datetime.fromisoformat(returned).date()-datetime.fromisoformat(loan['dueAt']).date()).days)
            if late and not conn.execute("SELECT 1 FROM Fine WHERE loanID=? AND reason='Automatic late return'",(loan_id,)).fetchone(): conn.execute("INSERT INTO Fine(loanID,amount,assessedDate,reason,paymentStatus) VALUES(?,?,?,?, 'unpaid')",(loan_id,float(Decimal(late)*Decimal('.25')),returned,'Automatic late return'))
        if charge and not conn.execute("SELECT 1 FROM Fine WHERE loanID=? AND reason='Replacement charge'",(loan_id,)).fetchone(): conn.execute("INSERT INTO Fine(loanID,amount,assessedDate,reason,paymentStatus) VALUES(?,?,?,?, 'unpaid')",(loan_id,float(charge),returned,'Replacement charge'))
        return {'lateDays': max(0,(datetime.fromisoformat(returned).date()-datetime.fromisoformat(loan['dueAt']).date()).days), 'replacementCharge':str(charge)}
    return transactional(conn,action)

def donate_item(conn,member_no,title,creator,material_type,publication_information,condition='good',notes='',when=None):
    def action():
        cur=conn.execute("INSERT INTO ItemProposal(title,creator,materialType,publicationInformation,sourceType,dateSubmitted,condition,notes,decisionStatus,memberNo) VALUES(?,?,?,?, 'member donation',?,?,?,'pending',?)",(title,creator,material_type,publication_information,now_text(when),condition,notes,member_no)); return cur.lastrowid
    return transactional(conn,action)

def search_events(conn,field='title',value='',available_only=False):
    fields={'title':'e.title','event type':'e.eventType','date':'date(e.startTime)','recommended audience':'a.audienceName','availability':'e.status'}; key=field.lower()
    if key not in fields: raise LibraryError('Invalid event search field')
    sql=f'''SELECT DISTINCT e.eventNo,e.title,e.eventType,e.startTime,e.endTime,e.status,r.roomName,e.maximumAttendance,
      (SELECT count(*) FROM Registration g WHERE g.eventNo=e.eventNo AND g.status='registered') registrationCount,
      e.maximumAttendance-(SELECT count(*) FROM Registration g WHERE g.eventNo=e.eventNo AND g.status='registered') remainingCapacity
      FROM Event e JOIN Room r USING(roomNo) LEFT JOIN RecommendedFor rf USING(eventNo) LEFT JOIN Audience a USING(audienceName) WHERE {fields[key]} LIKE ?'''
    if available_only or key=='availability' and value.lower()=='available': sql+=" AND e.status='scheduled' AND e.startTime>datetime('now') AND (SELECT count(*) FROM Registration g WHERE g.eventNo=e.eventNo AND g.status='registered')<e.maximumAttendance"
    return conn.execute(sql,(f'%{value}%',)).fetchall()

def register_for_event(conn,member_no,event_no,when=None):
    stamp=now_text(when)
    def action():
        cur=conn.execute("INSERT INTO Registration(eventNo,memberNo,registrationTime,status,attended) VALUES(?,?,?,'registered',0)",(event_no,member_no,stamp)); return cur.lastrowid
    return transactional(conn,action)
def volunteer(conn,member_no,availability,skills,area_of_interest,event_no=None,when=None):
    def action():
        cur=conn.execute("INSERT INTO VolunteerApplication(memberNo,applicationDate,areaOfInterest,availability,skills,status,eventNo) VALUES(?,?,?,?,?,'pending',?)",(member_no,now_text(when),area_of_interest,availability,skills,event_no)); return cur.lastrowid
    return transactional(conn,action)
def ask_for_help(conn,member_no,category,description,priority='normal',when=None):
    def action():
        cur=conn.execute("INSERT INTO HelpRequest(memberNo,category,questionDescription,submittedAt,priority,status) VALUES(?,?,?,?,?,'open')",(member_no,category,description,now_text(when),priority)); return cur.lastrowid
    return transactional(conn,action)

OPERATIONS={
 'Find an item':['Search field','Search text','Available only (yes/no)'],
 'Borrow an item':['Member number','Unit ID'],
 'Return a borrowed item':['Loan ID','Condition (good/fair/damaged/lost)','Replacement charge'],
 'Donate an item':['Member number','Title','Creator','Material type','Publication information','Condition','Notes'],
 'Find an event':['Search field','Search text','Available only (yes/no)'],
 'Register for an event':['Member number','Event number'],
 'Volunteer for the library':['Member number','Availability','Skills','Area of interest','Event number (optional)'],
 'Ask a librarian for help':['Member number','Category','Description','Priority']}

def _as_int(value,label,optional=False):
    if optional and not value.strip(): return None
    try: return int(value)
    except ValueError as e: raise LibraryError(f'{label} must be a whole number') from e

def launch_gui(path=DB_PATH):
    """Launch the minimal Tkinter interface; importing this module never opens a window."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    root=tk.Tk(); root.title('Community Library'); root.geometry('820x620'); root.minsize(680,500)
    conn=connect(path); entries={}
    outer=ttk.Frame(root,padding=14); outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='Community Library',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(outer,text='Choose an operation, enter the fields, then select Run.').pack(anchor='w',pady=(0,10))
    operation=tk.StringVar(value=next(iter(OPERATIONS)))
    picker=ttk.Combobox(outer,textvariable=operation,values=list(OPERATIONS),state='readonly',width=34); picker.pack(anchor='w')
    form=ttk.Frame(outer); form.pack(fill='x',pady=10)
    output=tk.Text(outer,height=15,wrap='word',state='disabled',font=('Consolas',10)); output.pack(fill='both',expand=True,pady=(8,0))

    def write(text):
        output.configure(state='normal'); output.delete('1.0','end'); output.insert('end',text); output.configure(state='disabled')
    def rebuild(*_):
        for child in form.winfo_children(): child.destroy()
        entries.clear()
        for row,label in enumerate(OPERATIONS[operation.get()]):
            ttk.Label(form,text=label+':').grid(row=row,column=0,sticky='w',padx=(0,10),pady=3)
            entry=ttk.Entry(form,width=62); entry.grid(row=row,column=1,sticky='ew',pady=3); entries[label]=entry
        form.columnconfigure(1,weight=1)
    def values(): return {k:v.get().strip() for k,v in entries.items()}
    def run():
        v=values(); op=operation.get()
        try:
            if op=='Find an item': result=search_items(conn,v['Search field'] or 'title',v['Search text'],v['Available only (yes/no)'].lower() in ('y','yes'))
            elif op=='Borrow an item': result=borrow_item(conn,_as_int(v['Member number'],'Member number'),_as_int(v['Unit ID'],'Unit ID'))
            elif op=='Return a borrowed item': result=return_item(conn,_as_int(v['Loan ID'],'Loan ID'),v['Condition (good/fair/damaged/lost)'] or 'good',v['Replacement charge'] or '0')
            elif op=='Donate an item': result={'proposalNo':donate_item(conn,_as_int(v['Member number'],'Member number'),v['Title'],v['Creator'],v['Material type'],v['Publication information'],v['Condition'] or 'good',v['Notes'])}
            elif op=='Find an event': result=search_events(conn,v['Search field'] or 'title',v['Search text'],v['Available only (yes/no)'].lower() in ('y','yes'))
            elif op=='Register for an event': result={'registrationID':register_for_event(conn,_as_int(v['Member number'],'Member number'),_as_int(v['Event number'],'Event number'))}
            elif op=='Volunteer for the library': result={'applicationNo':volunteer(conn,_as_int(v['Member number'],'Member number'),v['Availability'],v['Skills'],v['Area of interest'],_as_int(v['Event number (optional)'],'Event number',True))}
            else: result={'requestNo':ask_for_help(conn,_as_int(v['Member number'],'Member number'),v['Category'],v['Description'],v['Priority'] or 'normal')}
            if isinstance(result,list): text='No matches.' if not result else '\n\n'.join(' | '.join(f'{k}: {row[k]}' for k in row.keys()) for row in result)
            else: text='Success\n'+ '\n'.join(f'{k}: {val}' for k,val in result.items())
            write(text)
        except LibraryError as e: messagebox.showerror('Operation failed',str(e),parent=root)
        except Exception as e: messagebox.showerror('Invalid input',str(e),parent=root)
    def recreate_database():
        """Discard application changes and rebuild library.db from schema.sql and data/*.txt."""
        nonlocal conn
        if not messagebox.askyesno(
            'Recreate database',
            'This permanently removes all changes made through the application and reloads the original text-file data. Continue?',
            icon='warning', parent=root):
            return
        conn.close()
        try:
            from populate import build
            build(reset=True)
            conn=connect(path)
            write('Database recreated successfully from schema.sql and data/*.txt.')
            messagebox.showinfo('Recreate database','The original sample database has been restored.',parent=root)
        except Exception as e:
            try:
                if Path(path).exists(): conn=connect(path)
            except Exception: pass
            messagebox.showerror('Rebuild failed',f'Could not recreate the database:\n{e}\n\nClose any other running copy of the application and try again.',parent=root)
    picker.bind('<<ComboboxSelected>>',rebuild); rebuild()
    buttons=ttk.Frame(outer); buttons.pack(fill='x',pady=(8,0))
    ttk.Button(buttons,text='Recreate database',command=recreate_database).pack(side='left')
    ttk.Button(buttons,text='Run',command=run).pack(side='right')
    def close(): conn.close(); root.destroy()
    root.protocol('WM_DELETE_WINDOW',close); root.mainloop()

def main(): launch_gui()

if __name__=='__main__': main()
