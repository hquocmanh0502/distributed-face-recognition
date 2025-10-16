#!/usr/bin/env python3
"""
Clear stuck tasks in Redis
"""
import redis

def clear_redis_queues():
    """Clear all stuck tasks in Redis"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Get all queues
        queues = ['celery', 'face_detection', 'face_management', 'default']
        
        total_cleared = 0
        for queue in queues:
            length_before = r.llen(queue)
            if length_before > 0:
                print(f"📋 Queue '{queue}': {length_before} tasks")
                r.delete(queue)
                print(f"🗑️ Cleared {length_before} tasks from '{queue}'")
                total_cleared += length_before
            else:
                print(f"✅ Queue '{queue}': already empty")
        
        # Clear task metadata
        task_keys = r.keys('celery-task-meta-*')
        if task_keys:
            r.delete(*task_keys)
            print(f"🗑️ Cleared {len(task_keys)} task metadata records")
        
        print(f"\n✅ Total cleared: {total_cleared} tasks + {len(task_keys)} metadata")
        return True
        
    except Exception as e:
        print(f"❌ Error clearing Redis: {e}")
        return False

def check_queues_after_clear():
    """Verify queues are empty"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        queues = ['celery', 'face_detection', 'face_management', 'default']
        for queue in queues:
            length = r.llen(queue)
            print(f"📋 Queue '{queue}': {length} tasks")
        
        task_keys = r.keys('celery-task-meta-*')
        print(f"🏃 Task metadata: {len(task_keys)} records")
        
    except Exception as e:
        print(f"❌ Error checking queues: {e}")

if __name__ == '__main__':
    print("🧹 CLEARING REDIS QUEUES")
    print("=" * 40)
    
    if clear_redis_queues():
        print("\n🔍 VERIFICATION:")
        check_queues_after_clear()
        print("\n✅ Redis queues cleared successfully!")
        print("Now restart Celery worker and try uploading again.")
    else:
        print("\n❌ Failed to clear Redis queues.")