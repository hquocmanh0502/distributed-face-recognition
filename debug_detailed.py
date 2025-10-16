#!/usr/bin/env python3
"""
Debug chi tiết hệ thống Face Recognition
"""
import redis
import time
import json
from pathlib import Path
import sqlite3
from celery import Celery
from tasks import detect_faces

def check_redis_detailed():
    """Kiểm tra Redis chi tiết"""
    print("🔍 CHECKING REDIS...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Basic connection
        r.ping()
        print("✅ Redis connection: OK")
        
        # Check queues
        queue_lengths = {}
        for queue in ['celery', 'face_detection', 'face_management']:
            length = r.llen(queue)
            queue_lengths[queue] = length
            print(f"  📋 Queue '{queue}': {length} pending tasks")
        
        # Check active tasks
        active_keys = r.keys('celery-task-meta-*')
        print(f"  🏃 Active task records: {len(active_keys)}")
        
        return True, queue_lengths
    except Exception as e:
        print(f"❌ Redis error: {e}")
        return False, {}

def check_celery_detailed():
    """Kiểm tra Celery chi tiết"""
    print("\n🔍 CHECKING CELERY...")
    try:
        from tasks import app as celery_app
        inspect = celery_app.control.inspect()
        
        # Active workers
        active = inspect.active()
        print(f"✅ Active workers: {len(active) if active else 0}")
        if active:
            for worker, tasks in active.items():
                print(f"  👷 Worker '{worker}': {len(tasks)} active tasks")
                for task in tasks[:3]:  # Show first 3 tasks
                    print(f"    - {task.get('name', 'Unknown')} ({task.get('id', 'No ID')[:8]}...)")
        
        # Registered tasks
        registered = inspect.registered()
        if registered:
            for worker, tasks in registered.items():
                print(f"  📝 Worker '{worker}' has {len(tasks)} registered tasks")
                for task in tasks:
                    if 'detect_faces' in task:
                        print(f"    ✅ {task}")
        
        # Worker stats
        stats = inspect.stats()
        if stats:
            for worker, stat in stats.items():
                pool = stat.get('pool', {})
                print(f"  📊 Worker '{worker}': {pool.get('processes', 'N/A')} processes")
        
        return True
    except Exception as e:
        print(f"❌ Celery error: {e}")
        return False

def check_task_execution():
    """Test thực tế task execution"""
    print("\n🧪 TESTING TASK EXECUTION...")
    try:
        # Tạo test file
        test_file = Path("static/uploads/test_image.txt")
        test_file.write_text("test content")
        
        print(f"📝 Created test file: {test_file}")
        
        # Gửi test task
        print("🚀 Sending test task...")
        result = detect_faces.delay(str(test_file), "test_image.txt")
        task_id = result.id
        print(f"📬 Task sent with ID: {task_id}")
        
        # Wait và check kết quả
        print("⏳ Waiting for result (timeout 30s)...")
        for i in range(30):
            state = result.state
            print(f"  {i+1}s: Task state = {state}")
            
            if state == 'SUCCESS':
                print("✅ Task completed successfully!")
                print(f"📄 Result: {result.result}")
                break
            elif state == 'FAILURE':
                print("❌ Task failed!")
                print(f"💥 Error: {result.info}")
                break
            elif state == 'PROGRESS':
                print(f"🔄 Progress: {result.info}")
            
            time.sleep(1)
        else:
            print("⏰ Task timeout after 30s")
            print(f"Final state: {result.state}")
        
        # Cleanup
        if test_file.exists():
            test_file.unlink()
            print("🗑️ Cleaned up test file")
            
        return result.state == 'SUCCESS'
        
    except Exception as e:
        print(f"❌ Task execution error: {e}")
        return False

def check_files_detailed():
    """Kiểm tra files chi tiết"""
    print("\n📁 CHECKING FILES...")
    
    folders = {
        'uploads': Path('static/uploads'),
        'results': Path('static/results'),
        'known_faces': Path('static/known_faces')
    }
    
    for name, folder in folders.items():
        if folder.exists():
            files = list(folder.glob('*'))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            print(f"📂 {name}: {len(files)} files, {total_size/1024:.1f} KB")
            
            # Show recent files
            image_files = [f for f in files if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']]
            image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for i, f in enumerate(image_files[:3]):
                age_min = (time.time() - f.stat().st_mtime) / 60
                print(f"  📸 {f.name} ({f.stat().st_size/1024:.1f} KB, {age_min:.1f}m ago)")
        else:
            print(f"❌ {name}: Folder not found")

def check_database_detailed():
    """Kiểm tra database chi tiết"""
    print("\n🗃️ CHECKING DATABASE...")
    
    db_path = Path('database/results.db')
    if not db_path.exists():
        print("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Table structure
        cursor.execute("PRAGMA table_info(processing_results)")
        columns = cursor.fetchall()
        print(f"📋 Table has {len(columns)} columns")
        
        # Total records
        cursor.execute("SELECT COUNT(*) FROM processing_results")
        total = cursor.fetchone()[0]
        print(f"📊 Total records: {total}")
        
        if total > 0:
            # Status breakdown
            cursor.execute("SELECT status, COUNT(*) FROM processing_results GROUP BY status")
            status_counts = cursor.fetchall()
            for status, count in status_counts:
                print(f"  📈 {status}: {count}")
            
            # Recent records
            cursor.execute("""
                SELECT filename, status, created_at, error_message 
                FROM processing_results 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            recent = cursor.fetchall()
            print(f"📝 Recent records:")
            for record in recent:
                print(f"  - {record[0]}: {record[1]} ({record[2]})")
                if record[3]:
                    print(f"    Error: {record[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def check_celery_logs():
    """Kiểm tra Celery logs trong Redis"""
    print("\n📜 CHECKING CELERY LOGS...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Get recent task IDs
        task_keys = r.keys('celery-task-meta-*')
        print(f"🔍 Found {len(task_keys)} task records in Redis")
        
        for key in task_keys[-5:]:  # Last 5 tasks
            task_data = r.get(key)
            if task_data:
                try:
                    data = json.loads(task_data)
                    task_id = key.decode().replace('celery-task-meta-', '')
                    print(f"📋 Task {task_id[:8]}...")
                    print(f"  Status: {data.get('status', 'Unknown')}")
                    print(f"  Result: {str(data.get('result', 'None'))[:100]}...")
                    if 'traceback' in data:
                        print(f"  Error: {data['traceback'][:200]}...")
                except:
                    print(f"📋 Task {key.decode()}: Invalid JSON data")
        
        return True
    except Exception as e:
        print(f"❌ Redis logs error: {e}")
        return False

def main():
    """Main diagnostic function"""
    print("🔬 DETAILED SYSTEM DIAGNOSTIC")
    print("=" * 60)
    
    redis_ok, queues = check_redis_detailed()
    celery_ok = check_celery_detailed()
    check_files_detailed()
    db_ok = check_database_detailed()
    check_celery_logs()
    
    # Test actual execution
    if redis_ok and celery_ok:
        execution_ok = check_task_execution()
    else:
        execution_ok = False
    
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY:")
    print(f"  Redis: {'✅' if redis_ok else '❌'}")
    print(f"  Celery: {'✅' if celery_ok else '❌'}")
    print(f"  Database: {'✅' if db_ok else '❌'}")
    print(f"  Task Execution: {'✅' if execution_ok else '❌'}")
    
    if not execution_ok:
        print("\n🔧 TROUBLESHOOTING SUGGESTIONS:")
        if not redis_ok:
            print("  1. Restart Redis server")
        if not celery_ok:
            print("  2. Restart Celery worker with: celery -A tasks worker --loglevel=debug")
        if not db_ok:
            print("  3. Check database permissions and initialization")
        if queues and any(length > 0 for length in queues.values()):
            print("  4. Clear stuck tasks in Redis")
        print("  5. Check Python imports and dependencies")
        print("  6. Verify file permissions in static folders")

if __name__ == '__main__':
    main()