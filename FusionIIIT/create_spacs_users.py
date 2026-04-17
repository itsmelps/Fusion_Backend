"""
Direct database script to create SPACS users.
Bypasses Django entirely - uses psycopg2 + Django password hashing logic.
"""
import hashlib, base64, os, secrets

# --- Django-compatible password hasher ---
def make_password(raw_password):
    """Create a PBKDF2 hash identical to Django's default."""
    salt = secrets.token_hex(12)
    iterations = 260000
    dk = hashlib.pbkdf2_hmac('sha256', raw_password.encode(), salt.encode(), iterations)
    hash_b64 = base64.b64encode(dk).decode('ascii')
    return f'pbkdf2_sha256${iterations}${salt}${hash_b64}'

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'psycopg2-binary'])
    import psycopg2

PASSWORD = 'fusion123'
hashed = make_password(PASSWORD)

conn = psycopg2.connect(
    dbname='fusionlab',
    user='fusion_admin',
    password='hello123',
    host='localhost'
)
conn.autocommit = True
cur = conn.cursor()

def create_user(username, first_name, last_name, designation_name, user_type):
    # 1) auth_user
    cur.execute("SELECT id FROM auth_user WHERE username = %s", (username,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        print(f"  [=] User '{username}' already exists (id={user_id})")
    else:
        cur.execute("""
            INSERT INTO auth_user (username, password, first_name, last_name, email,
                                   is_staff, is_active, is_superuser, date_joined)
            VALUES (%s, %s, %s, %s, %s, false, true, false, NOW())
            RETURNING id
        """, (username, hashed, first_name, last_name, f'{username}@iiitdmj.ac.in'))
        user_id = cur.fetchone()[0]
        print(f"  [+] Created User '{username}' (id={user_id})")

    # 2) globals_extrainfo
    cur.execute("SELECT id FROM globals_extrainfo WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        print(f"  [=] ExtraInfo exists")
    else:
        cur.execute("""
            INSERT INTO globals_extrainfo (id, user_id, user_type, phone_no, address, about_me, user_status, sex, date_of_birth, title)
            VALUES (%s, %s, %s, 9999999999, '', 'NA', 'PRESENT', 'M', '1990-01-01', 'Mr.')
        """, (username, user_id, user_type))
        print(f"  [+] Created ExtraInfo (type={user_type})")

    # 3) globals_designation
    cur.execute("SELECT id FROM globals_designation WHERE name = %s", (designation_name,))
    row = cur.fetchone()
    if row:
        desig_id = row[0]
        print(f"  [=] Designation '{designation_name}' exists (id={desig_id})")
    else:
        cur.execute("""
            INSERT INTO globals_designation (name, full_name)
            VALUES (%s, %s) RETURNING id
        """, (designation_name, designation_name))
        desig_id = cur.fetchone()[0]
        print(f"  [+] Created Designation '{designation_name}' (id={desig_id})")

    # 4) globals_holdsdesignation
    cur.execute("""
        SELECT id FROM globals_holdsdesignation
        WHERE user_id = %s AND designation_id = %s
    """, (user_id, desig_id))
    if cur.fetchone():
        print(f"  [=] Already holds designation")
    else:
        cur.execute("""
            INSERT INTO globals_holdsdesignation (user_id, working_id, designation_id, held_at)
            VALUES (%s, %s, %s, NOW())
        """, (user_id, user_id, desig_id))
        print(f"  [+] Assigned designation '{designation_name}' to '{username}'")

    return user_id

print("\n=== Creating SPACS Convenor ===")
create_user('spacsconvenor1', 'SPACS', 'Convenor', 'spacsconvenor', 'faculty')

print("\n=== Creating SPACS Assistant ===")
create_user('spacsassistant1', 'SPACS', 'Assistant', 'spacsassistant', 'staff')

# Also create auth tokens for API access
cur.execute("SELECT id FROM auth_user WHERE username = 'spacsconvenor1'")
uid1 = cur.fetchone()[0]
cur.execute("SELECT id FROM auth_user WHERE username = 'spacsassistant1'")
uid2 = cur.fetchone()[0]

for uid, name in [(uid1, 'convenor'), (uid2, 'assistant')]:
    cur.execute("SELECT key FROM authtoken_token WHERE user_id = %s", (uid,))
    row = cur.fetchone()
    if row:
        print(f"  [=] Token for {name} already exists: {row[0]}")
    else:
        token = secrets.token_hex(20)
        cur.execute("INSERT INTO authtoken_token (key, user_id, created) VALUES (%s, %s, NOW())", (token, uid))
        print(f"  [+] Created token for {name}: {token}")

cur.close()
conn.close()

print("\n" + "="*50)
print("Done! Login credentials:")
print(f"  Convenor  -> username: spacsconvenor1   password: {PASSWORD}")
print(f"  Assistant -> username: spacsassistant1   password: {PASSWORD}")
print("="*50)
