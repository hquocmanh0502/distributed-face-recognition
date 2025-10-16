#!/usr/bin/env python3
"""
Kiểm tra số lượng workers đang hoạt động
"""
import time
from tasks import app as celery_app

def check_workers():
    """Kiểm tra workers đang hoạt động"""
    try:
        inspect = celery_app.control.inspect()
        
        # Get worker info
        active = inspect.active() or {}
        registered = inspect.registered() or {}
        stats = inspect.stats() or {}
        
        print("🏭 CELERY WORKERS STATUS")
        print("=" * 60)
        
        worker_names = list(stats.keys())
        total_workers = len(worker_names)
        
        if total_workers == 0:
            print("❌ Không có workers nào đang hoạt động!")
            print("\nCách khởi động workers:")
            print("  celery -A tasks worker --loglevel=info --pool=solo -n worker1@%h")
            print("  celery -A tasks worker --loglevel=info --pool=solo -n worker2@%h")
            print("  celery -A tasks worker --loglevel=info --pool=solo -n worker3@%h")
            print("  celery -A tasks worker --loglevel=info --pool=solo -n worker4@%h")
            return
        
        print(f"✅ TỔNG SỐ WORKERS: {total_workers}")
        print()
        
        # Chi tiết từng worker
        for i, worker_name in enumerate(worker_names, 1):
            worker_active_tasks = active.get(worker_name, [])
            worker_stats = stats.get(worker_name, {})
            
            print(f"👷 WORKER {i}: {worker_name}")
            print(f"  📊 Trạng thái: {'🟢 HOẠT ĐỘNG' if worker_name in stats else '🔴 OFFLINE'}")
            print(f"  🔥 Tasks đang xử lý: {len(worker_active_tasks)}")
            
            # Show active tasks
            if worker_active_tasks:
                for j, task in enumerate(worker_active_tasks[:3], 1):  # Show max 3 tasks
                    task_name = task.get('name', 'Unknown').replace('tasks.', '')
                    task_id = task.get('id', 'No ID')[:8] + '...'
                    print(f"    🔄 Task {j}: {task_name} ({task_id})")
                
                if len(worker_active_tasks) > 3:
                    print(f"    ... và {len(worker_active_tasks) - 3} tasks khác")
            else:
                print(f"    💤 Đang chờ tasks...")
            
            # Worker stats
            pool_info = worker_stats.get('pool', {})
            if pool_info:
                print(f"  ⚙️ Pool type: {pool_info.get('implementation', 'N/A')}")
                print(f"  🚀 Max concurrency: {pool_info.get('max-concurrency', 'N/A')}")
            
            print()
        
        # Total tasks trong queue
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            queue_length = r.llen('celery')
            print(f"📋 TASKS TRONG QUEUE: {queue_length}")
        except:
            print(f"📋 TASKS TRONG QUEUE: Không thể kết nối Redis")
        
        print()
        print("🎯 PHÂN PHỐI WORKLOAD:")
        total_active = sum(len(active.get(w, [])) for w in worker_names)
        if total_active > 0:
            for worker_name in worker_names:
                worker_tasks = len(active.get(worker_name, []))
                percentage = (worker_tasks / total_active) * 100
                bar = "█" * int(percentage / 5)  # 20 chars max
                print(f"  {worker_name}: {bar:<20} {worker_tasks} tasks ({percentage:.1f}%)")
        else:
            print("  📝 Tất cả workers đang rảnh")
        
        # Recommendations
        print("\n💡 KHUYẾN NGHỊ:")
        if total_workers == 1:
            print("  🔄 Thêm workers để tăng tốc độ xử lý")
        elif total_workers < 4:
            print(f"  ⚡ Có {total_workers} workers - Có thể thêm để xử lý nhiều tasks hơn")
        else:
            print(f"  🚀 Có {total_workers} workers - Tốt cho xử lý parallel!")
        
        if total_active == 0:
            print("  📤 Upload ảnh để test workers")
        
        return total_workers
        
    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra workers: {e}")
        return 0

def live_monitor():
    """Monitor workers real-time"""
    print("🔴 MONITOR REAL-TIME (Ctrl+C để thoát)")
    print("=" * 60)
    
    try:
        while True:
            # Clear screen (Windows)
            import os
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print(f"⏰ {time.strftime('%H:%M:%S')} - WORKER MONITOR")
            print("=" * 60)
            
            check_workers()
            
            print("\n🔄 Refresh sau 5 giây... (Ctrl+C để thoát)")
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n👋 Tạm biệt!")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'monitor':
        live_monitor()
    else:
        check_workers()
        
        choice = input("\nBạn có muốn monitor real-time không? (y/n): ").lower()
        if choice == 'y':
            live_monitor()