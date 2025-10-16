#!/usr/bin/env python3
"""
Demo Worker Scaling - Test với nhiều ảnh
"""
import time
from tasks import detect_faces
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont
import os

def create_demo_images(count=30):
    """Tạo demo images để test"""
    upload_folder = Path('static/uploads')
    upload_folder.mkdir(exist_ok=True)
    
    print(f"🎨 Creating {count} demo images...")
    
    for i in range(1, count + 1):
        # Create simple image with text
        img = Image.new('RGB', (400, 300), color=f'hsl({random.randint(0, 360)}, 70%, 60%)')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        draw.text((150, 130), f"Image {i}", fill='white', font=font)
        draw.rectangle([100, 80, 300, 220], outline='white', width=3)
        
        filename = f"demo_image_{i:02d}.jpg"
        img.save(upload_folder / filename, quality=90)
        
    print(f"✅ Created {count} demo images in {upload_folder}")
    return [str(upload_folder / f"demo_image_{i:02d}.jpg") for i in range(1, count + 1)]

def test_worker_scaling():
    """Test scaling với nhiều workers"""
    print("🚀 WORKER SCALING TEST")
    print("=" * 50)
    
    # Create demo images
    image_paths = create_demo_images(30)
    
    print(f"📊 Testing with {len(image_paths)} images")
    print("📋 Tasks will be distributed among available workers")
    print("🔍 Monitor Redis and worker terminals to see distribution")
    
    # Send all tasks
    tasks = []
    start_time = time.time()
    
    for i, image_path in enumerate(image_paths, 1):
        filename = f"demo_result_{i:02d}.jpg"
        task = detect_faces.delay(image_path, filename)
        tasks.append((task, filename))
        print(f"📤 Sent task {i}/30: {task.id[:8]}... for {filename}")
        time.sleep(0.1)  # Small delay to see distribution
    
    print(f"\n⏱️ All tasks sent in {time.time() - start_time:.2f}s")
    print("🏃 Workers are now processing...")
    
    # Monitor progress
    completed = 0
    failed = 0
    
    for task, filename in tasks:
        try:
            result = task.get(timeout=60)  # Wait max 60s per task
            if result and result.get('status') == 'success':
                completed += 1
                print(f"✅ {completed}/30: {filename} completed by {result.get('worker', 'unknown')}")
            else:
                failed += 1
                print(f"❌ {failed}: {filename} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {failed}: {filename} timeout/error: {e}")
    
    total_time = time.time() - start_time
    
    # Results
    print("\n" + "=" * 50)
    print("📊 SCALING TEST RESULTS:")
    print(f"  ✅ Completed: {completed}/30")
    print(f"  ❌ Failed: {failed}/30")
    print(f"  ⏱️ Total time: {total_time:.2f}s")
    print(f"  📈 Avg per image: {total_time/30:.2f}s")
    print(f"  🚀 Estimated speedup: {30*3/total_time:.1f}x (vs sequential)")

def check_active_workers():
    """Kiểm tra số workers đang hoạt động"""
    try:
        from tasks import app as celery_app
        inspect = celery_app.control.inspect()
        
        # Active workers
        active = inspect.active()
        registered = inspect.registered()
        stats = inspect.stats()
        
        print("👷 ACTIVE WORKERS:")
        if active:
            for worker_name, tasks in active.items():
                print(f"  🔥 {worker_name}: {len(tasks)} active tasks")
        
        print("\n📝 REGISTERED WORKERS:")
        if registered:
            for worker_name, tasks in registered.items():
                print(f"  📋 {worker_name}: {len(tasks)} registered tasks")
        
        print("\n📊 WORKER STATS:")
        if stats:
            for worker_name, stat in stats.items():
                pool_info = stat.get('pool', {})
                print(f"  📈 {worker_name}:")
                print(f"    - Processes: {pool_info.get('processes', 'N/A')}")
                print(f"    - Max concurrency: {pool_info.get('max-concurrency', 'N/A')}")
        
        total_workers = len(stats) if stats else 0
        print(f"\n🎯 TOTAL ACTIVE WORKERS: {total_workers}")
        
        return total_workers
        
    except Exception as e:
        print(f"❌ Error checking workers: {e}")
        return 0

if __name__ == '__main__':
    print("🔍 Checking current workers...")
    worker_count = check_active_workers()
    
    if worker_count == 0:
        print("\n⚠️ No workers found!")
        print("Start workers first:")
        print("  celery -A tasks worker --loglevel=info --pool=solo -n worker1@%h")
        exit(1)
    
    print(f"\n✅ Found {worker_count} workers")
    
    choice = input("\nRun scaling test? (y/n): ").lower()
    if choice == 'y':
        test_worker_scaling()
    else:
        print("Test cancelled.")