"""Test-admin setup only. Not imported by the customer API; no reset of old data."""
import argparse,hashlib,json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from app.runtime.pg import dsn

def create_user(uid,**fault):
    salt=hashlib.sha256(uid.encode()).hexdigest()
    password=hashlib.scrypt(b'synthetic-test',salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    with psycopg.connect(**dsn('postgres')) as db:
        db.execute('INSERT INTO authority.users VALUES(%s,%s,%s)',(uid,salt,password))
        db.execute('INSERT INTO provider.fault_settings VALUES(%s,%s)',(uid,json.dumps({'book_branch':'book_success','seed':4,**fault})))
    return uid

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--user',required=True);a=p.parse_args()
    print(json.dumps({'user':create_user(a.user,book_branch='timeout_after_success',quote_delta=37),'password':'synthetic-test'}))
