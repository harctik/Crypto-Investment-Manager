import database
database.init_db()
from database import conn

with conn() as c:
    users = c.execute('SELECT id, username, role FROM users').fetchall()
    for u in users:
        print(f"  id={u[0]} user={u[1]} role={u[2]}")

for user, pwd in [('admin','admin123'), ('admin2','admin123'), ('demo','demo'), ('trader','trade456')]:
    r = database.verify_user(user, pwd)
    status = "OK" if r else "FAIL"
    print(f"  verify({user}/{pwd}): {status}")
