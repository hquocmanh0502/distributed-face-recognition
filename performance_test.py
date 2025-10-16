import time
import cv2
import os
import matplotlib.pyplot as plt
from tasks import detect_faces

UPLOAD_FOLDER = 'static/uploads'
files = [os.path.join(UPLOAD_FOLDER, f) for f in os.listdir(UPLOAD_FOLDER)]

def sequential_process():
    print("🚀 Bắt đầu xử lý tuần tự...")
    start = time.time()
    for f in files:
        detect_faces(f, os.path.basename(f))  # gọi trực tiếp, không dùng Celery
    end = time.time()
    return end - start

def distributed_process():
    print("🚀 Bắt đầu xử lý song song (Celery)...")
    start = time.time()
    tasks = []
    for f in files:
        t = detect_faces.delay(f, os.path.basename(f))
        tasks.append(t)

    # Đợi tất cả task hoàn thành
    for t in tasks:
        t.get()

    end = time.time()
    return end - start

if __name__ == "__main__":
    t_seq = sequential_process()
    t_dist = distributed_process()

    print(f"\n🧩 Tuần tự: {t_seq:.2f}s | Phân tán: {t_dist:.2f}s")

    plt.bar(["Sequential", "Distributed"], [t_seq, t_dist], color=["red", "green"])
    plt.ylabel("Thời gian (s)")
    plt.title("So sánh hiệu năng xử lý khuôn mặt")
    plt.show()
