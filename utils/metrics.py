import time
from .face_detection import detect_faces

def measure_sequential_time(filepath):
    """Đo thời gian xử lý tuần tự cho một ảnh"""
    start_time = time.time()
    detect_faces(filepath)
    return time.time() - start_time