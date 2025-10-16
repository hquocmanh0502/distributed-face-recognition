import redis
from celery import Celery
import sqlite3
from pathlib import Path

def check_redis():
    """Kiểm tra Redis connection"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis: Connected")
        return True
    except Exception as e:
        print(f"❌ Redis: {e}")
        return False

def check_celery():
    """Kiểm tra Celery connection"""
    try:
        from tasks import app as celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if stats:
            print(f"✅ Celery: {len(stats)} workers active")
            return True
        else:
            print("❌ Celery: No workers found")
            return False
    except Exception as e:
        print(f"❌ Celery: {e}")
        return False

def check_database():
    """Kiểm tra Database"""
    try:
        db_path = Path('database/results.db')
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processing_results")
            count = cursor.fetchone()[0]
            conn.close()
            print(f"✅ Database: {count} records")
            return True
        else:
            print("❌ Database: File not found")
            return False
    except Exception as e:
        print(f"❌ Database: {e}")
        return False

def check_folders():
    """Kiểm tra thư mục"""
    folders = ['static/uploads', 'static/results', 'static/known_faces']
    all_ok = True
    for folder in folders:
        path = Path(folder)
        if path.exists():
            files = list(path.glob('*'))
            print(f"✅ {folder}: {len(files)} files")
        else:
            print(f"❌ {folder}: Not found")
            all_ok = False
    return all_ok

if __name__ == '__main__':
    print("🔍 SYSTEM CHECK")
    print("=" * 50)
    
    redis_ok = check_redis()
    celery_ok = check_celery()
    db_ok = check_database()
    folders_ok = check_folders()
    
    print("\n📊 SUMMARY:")
    if all([redis_ok, celery_ok, db_ok, folders_ok]):
        print("✅ System is ready!")
    else:
        print("❌ System has issues!")
        print("\nTROUBLESHOOTING:")
        if not redis_ok:
            print("  1. Start Redis: redis-server")
        if not celery_ok:
            print("  2. Start Celery: celery -A tasks worker --loglevel=info --pool=solo")
        if not db_ok:
            print("  3. Check database initialization")
        if not folders_ok:
            print("  4. Check folder permissions")