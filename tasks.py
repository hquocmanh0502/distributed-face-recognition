from celery import Celery
from celery.result import AsyncResult
import cv2
import os
import time
from pathlib import Path
import socket
import face_recognition
import numpy as np
import logging
import sqlite3
from datetime import datetime

# ...existing code...

# Cấu hình logging chi tiết
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('face_recognition.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===========================
# CẤU HÌNH CELERY
# ===========================
app = Celery('tasks', broker='redis://localhost:6379/0')

app.conf.update(
    task_serializer='pickle',
    accept_content=['json', 'pickle'],
    result_serializer='pickle',
    timezone='UTC',
    enable_utc=True,
    worker_pool='solo',
    worker_concurrency=1,
    task_default_queue='celery',
    task_time_limit=300,
    task_soft_time_limit=240,
    result_expires=3600,
    task_track_started=True,
    task_send_sent_event=True,
    result_backend=None,  # Disable result backend để tránh lỗi serialization
)

# ===========================
# THƯ MỤC LƯU ẢNH
# ===========================
BASE_DIR = Path(__file__).parent.absolute()
RESULT_FOLDER = BASE_DIR / 'static' / 'results'
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
KNOWN_FACES_FOLDER = BASE_DIR / 'static' / 'known_faces'
DATABASE_FOLDER = BASE_DIR / 'database'

# Tạo tất cả thư mục cần thiết
for folder in [RESULT_FOLDER, UPLOAD_FOLDER, KNOWN_FACES_FOLDER, DATABASE_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"[FOLDER] Created/verified: {folder}")

# ===========================
# DATABASE SETUP
# ===========================
def init_database():
    """Khởi tạo database để lưu kết quả"""
    db_path = DATABASE_FOLDER / 'results.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            task_id TEXT,
            faces_detected INTEGER DEFAULT 0,
            recognized_faces TEXT,
            processing_time REAL,
            worker_name TEXT,
            result_path TEXT,
            status TEXT DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"[DATABASE] Initialized at {db_path}")

# Khởi tạo database
init_database()

def save_result_to_db(task_id, filename, faces_detected=0, recognized_faces="", 
                     processing_time=0, worker_name="", result_path="", 
                     status="success", error_message=""):
    """Lưu kết quả xử lý vào database"""
    try:
        db_path = DATABASE_FOLDER / 'results.db'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO processing_results 
            (task_id, filename, faces_detected, recognized_faces, processing_time, 
             worker_name, result_path, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, filename, faces_detected, recognized_faces, processing_time,
              worker_name, result_path, status, error_message))
        
        conn.commit()
        conn.close()
        logger.info(f"[DATABASE] Saved result for {filename}")
    except Exception as e:
        logger.error(f"[DATABASE] Error saving result: {e}")

# ===========================
# LOAD KNOWN FACES
# ===========================
def load_known_faces():
    """Load các khuôn mặt đã biết từ thư mục known_faces"""
    known_face_encodings = []
    known_face_names = []
    
    if KNOWN_FACES_FOLDER.exists():
        for image_file in KNOWN_FACES_FOLDER.glob("*.jpg"):
            try:
                name = image_file.stem.replace('_', ' ').title()
                image = face_recognition.load_image_file(str(image_file))
                encodings = face_recognition.face_encodings(image)
                
                if encodings:
                    known_face_encodings.append(encodings[0])
                    known_face_names.append(name)
                    logger.info(f"[SUCCESS] Đã load khuôn mặt: {name}")
                else:
                    logger.warning(f"[WARNING] Không tìm thấy khuôn mặt trong: {name}")
            except Exception as e:
                logger.error(f"[ERROR] Lỗi khi load {image_file.name}: {e}")
    
    logger.info(f"[STATS] Đã load {len(known_face_encodings)} khuôn mặt đã biết")
    return known_face_encodings, known_face_names

KNOWN_FACE_ENCODINGS, KNOWN_FACE_NAMES = load_known_faces()

# ===========================
# MAIN TASK - SỬA LỖI HOÀN TOÀN
# ===========================
@app.task(bind=True)
def detect_faces(self, image_path, filename):
    """
    Task xử lý khuôn mặt với nhận diện người - PHIÊN BẢN SỬA LỖI HOÀN CHỈNH
    """
    start_time = time.time()
    worker_name = socket.gethostname()
    recognized_names = []
    task_id = self.request.id
    
    logger.info(f"[START] [Task: {task_id}] [Worker: {worker_name}] Bắt đầu xử lý: {filename}")
    logger.info(f"[INPUT] Input path: {image_path}")
    logger.info(f"[RESULT] Result folder: {RESULT_FOLDER}")

    try:
        # Cập nhật trạng thái
        self.update_state(state='PROGRESS', meta={
            'status': 'Đang kiểm tra file...', 
            'current': 10, 
            'total': 100,
            'filename': filename
        })

        # 1. KIỂM TRA FILE INPUT
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File không tồn tại: {image_path}")

        file_size = os.path.getsize(image_path)
        if file_size == 0:
            raise ValueError(f"File rỗng: {image_path}")
            
        logger.info(f"[FILE] File size: {file_size} bytes")

        # 2. LOAD VÀ XỬ LÝ ẢNH
        self.update_state(state='PROGRESS', meta={
            'status': 'Đang load ảnh...', 
            'current': 20, 
            'total': 100,
            'filename': filename
        })
        
        # Load image với face_recognition
        try:
            image = face_recognition.load_image_file(image_path)
            height, width = image.shape[:2]
            logger.info(f"[SUCCESS] Đã load ảnh: {width}x{height}")
        except Exception as e:
            logger.error(f"[ERROR] Không thể load ảnh với face_recognition: {e}")
            # Fallback to OpenCV
            cv_image = cv2.imread(image_path)
            if cv_image is None:
                raise ValueError(f"Không thể đọc ảnh: {image_path}")
            image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            logger.info(f"[FALLBACK] Đã load ảnh bằng OpenCV")
        
        # 3. PHÁT HIỆN KHUÔN MẶT
        self.update_state(state='PROGRESS', meta={
            'status': 'Đang tìm khuôn mặt...', 
            'current': 40, 
            'total': 100,
            'filename': filename
        })
        
        face_locations = face_recognition.face_locations(image, model="hog")  # Dùng HOG cho tốc độ
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        logger.info(f"[FACES] Tìm thấy {len(face_locations)} khuôn mặt")
        
        # 4. NHẬN DIỆN KHUÔN MẶT
        self.update_state(state='PROGRESS', meta={
            'status': f'Đang nhận diện {len(face_locations)} khuôn mặt...', 
            'current': 60, 
            'total': 100,
            'filename': filename
        })
        
        # Chuyển sang format OpenCV để vẽ
        cv_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        for i, ((top, right, bottom, left), face_encoding) in enumerate(zip(face_locations, face_encodings)):
            name = "Unknown"
            confidence = 0
            
            # So sánh với known faces
            if len(KNOWN_FACE_ENCODINGS) > 0:
                matches = face_recognition.compare_faces(KNOWN_FACE_ENCODINGS, face_encoding, tolerance=0.6)
                
                if True in matches:
                    face_distances = face_recognition.face_distance(KNOWN_FACE_ENCODINGS, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    
                    if matches[best_match_index]:
                        name = KNOWN_FACE_NAMES[best_match_index]
                        confidence = round((1 - face_distances[best_match_index]) * 100, 1)
                        recognized_names.append(f"{name} ({confidence}%)")
                        logger.info(f"[RECOGNIZED] Nhận diện: {name} ({confidence}%)")
            
            # Vẽ khung và tên
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            thickness = 3
            
            # Vẽ khung
            cv2.rectangle(cv_image, (left, top), (right, bottom), color, thickness)
            
            # Vẽ label
            label = f"{name}" if name == "Unknown" else f"{name} ({confidence}%)"
            
            # Tính vị trí text
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            text_thickness = 2
            
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, text_thickness)
            
            # Vẽ background cho text
            text_y = bottom + text_height + 10
            if text_y > cv_image.shape[0]:  # Nếu vượt quá chiều cao
                text_y = top - 10
                text_bg_y1 = text_y - text_height - 5
                text_bg_y2 = text_y + 5
            else:
                text_bg_y1 = text_y - text_height - 5
                text_bg_y2 = text_y + 5
            
            cv2.rectangle(cv_image, (left, text_bg_y1), (left + text_width + 10, text_bg_y2), color, cv2.FILLED)
            cv2.putText(cv_image, label, (left + 5, text_y - 5), font, font_scale, (255, 255, 255), text_thickness)

        # 5. LƯU ẢNH KẾT QUẢ - PHƯƠNG PHÁP CHẮC CHẮN
        self.update_state(state='PROGRESS', meta={
            'status': 'Đang lưu kết quả...', 
            'current': 80, 
            'total': 100,
            'filename': filename
        })
        
        # Đảm bảo thư mục tồn tại và có quyền ghi
        RESULT_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # Tạo tên file kết quả an toàn
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        result_path = RESULT_FOLDER / safe_filename
        
        logger.info(f"[SAVE] Đang lưu kết quả: {result_path}")
        
        # Thử nhiều cách lưu file
        save_success = False
        
        # Cách 1: OpenCV với JPEG quality cao
        try:
            if str(result_path).lower().endswith(('.jpg', '.jpeg')):
                save_success = cv2.imwrite(str(result_path), cv_image, 
                                         [cv2.IMWRITE_JPEG_QUALITY, 95,
                                          cv2.IMWRITE_JPEG_OPTIMIZE, 1])
            elif str(result_path).lower().endswith('.png'):
                save_success = cv2.imwrite(str(result_path), cv_image,
                                         [cv2.IMWRITE_PNG_COMPRESSION, 6])
            else:
                save_success = cv2.imwrite(str(result_path), cv_image)
            
            if save_success and result_path.exists() and result_path.stat().st_size > 0:
                logger.info(f"[SAVE] Lưu thành công với OpenCV: {result_path.stat().st_size} bytes")
            else:
                raise Exception("OpenCV save failed or file is empty")
                
        except Exception as e:
            logger.warning(f"[SAVE] OpenCV thất bại: {e}")
            save_success = False
            
            # Cách 2: PIL fallback
            try:
                from PIL import Image
                rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_image)
                pil_image.save(str(result_path), quality=95, optimize=True)
                
                if result_path.exists() and result_path.stat().st_size > 0:
                    save_success = True
                    logger.info(f"[SAVE] Lưu thành công với PIL: {result_path.stat().st_size} bytes")
                else:
                    raise Exception("PIL save failed or file is empty")
                    
            except Exception as e2:
                logger.error(f"[SAVE] PIL cũng thất bại: {e2}")
        
        # Kiểm tra kết quả cuối cùng
        if not save_success or not result_path.exists():
            raise Exception(f"Không thể lưu file kết quả: {result_path}")
        
        final_file_size = result_path.stat().st_size
        if final_file_size == 0:
            raise Exception(f"File kết quả có size 0: {result_path}")
            
        # Đợi file system đồng bộ
        time.sleep(0.5)
        
        # 6. HOÀN THÀNH VÀ LƯU DATABASE
        processing_time = round(time.time() - start_time, 3)
        
        self.update_state(state='PROGRESS', meta={
            'status': 'Hoàn thành!', 
            'current': 100, 
            'total': 100,
            'filename': filename
        })
        
        # Lưu kết quả vào database
        save_result_to_db(
            task_id=task_id,
            filename=safe_filename,
            faces_detected=len(face_locations),
            recognized_faces=", ".join(recognized_names),
            processing_time=processing_time,
            worker_name=worker_name,
            result_path=str(result_path),
            status="success"
        )
        
        result_msg = (
            f"[SUCCESS] [Task: {task_id}] [Worker: {worker_name}] "
            f"Đã xử lý '{filename}' — {len(face_locations)} khuôn mặt, "
            f"{len(recognized_names)} nhận diện được, {processing_time}s"
        )
        logger.info(result_msg)

        return {
            "task_id": task_id,
            "filename": safe_filename,
            "original_filename": filename,
            "faces_detected": len(face_locations),
            "recognized_faces": recognized_names,
            "processing_time": processing_time,
            "worker": worker_name,
            "status": "success",
            "result_path": str(result_path),
            "relative_path": f"static/results/{safe_filename}",
            "file_size": final_file_size,
            "message": result_msg
        }

    except Exception as e:
        processing_time = round(time.time() - start_time, 3)
        error_msg = f"[ERROR] [Task: {task_id}] [Worker: {worker_name}] Lỗi khi xử lý '{filename}': {e}"
        logger.error(error_msg, exc_info=True)
        
        # Lưu lỗi vào database
        save_result_to_db(
            task_id=task_id,
            filename=filename,
            processing_time=processing_time,
            worker_name=worker_name,
            status="error",
            error_message=str(e)
        )
        
        self.update_state(state='FAILURE', meta={
            'error': str(e), 
            'filename': filename,
            'processing_time': processing_time
        })
        
        return {
            "task_id": task_id,
            "filename": filename,
            "error": str(e),
            "processing_time": processing_time,
            "worker": worker_name,
            "status": "error",
            "message": error_msg
        }


@app.task(bind=True)
def add_known_face(self, image_path, person_name):
    """Task thêm khuôn mặt mới vào database"""
    try:
        logger.info(f"[ADD] Thêm known face: {person_name} từ {image_path}")
        
        self.update_state(state='PROGRESS', meta={'status': 'Đang xử lý ảnh...', 'current': 30, 'total': 100})
        
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        
        if not encodings:
            raise Exception("Không tìm thấy khuôn mặt trong ảnh")
        
        self.update_state(state='PROGRESS', meta={'status': 'Đang lưu ảnh...', 'current': 70, 'total': 100})
        
        filename = f"{person_name.lower().replace(' ', '_')}.jpg"
        known_face_path = KNOWN_FACES_FOLDER / filename
        
        import shutil
        shutil.copy2(image_path, known_face_path)
        
        # Reload known faces
        global KNOWN_FACE_ENCODINGS, KNOWN_FACE_NAMES
        KNOWN_FACE_ENCODINGS, KNOWN_FACE_NAMES = load_known_faces()
        
        logger.info(f"[SUCCESS] Đã thêm khuôn mặt: {person_name} -> {known_face_path}")
        
        return {
            "success": True, 
            "message": f"Đã thêm khuôn mặt của {person_name}",
            "filename": filename
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Lỗi khi thêm known face: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {"success": False, "message": f"Lỗi: {str(e)}"}


@app.task(bind=True)
def test_task(self):
    """Task test đơn giản"""
    import time
    
    self.update_state(state='PROGRESS', meta={'status': 'Bắt đầu test...', 'current': 0, 'total': 100})
    time.sleep(1)
    
    self.update_state(state='PROGRESS', meta={'status': 'Đang xử lý...', 'current': 50, 'total': 100})
    time.sleep(1)
    
    self.update_state(state='PROGRESS', meta={'status': 'Hoàn thành!', 'current': 100, 'total': 100})
    
    return {
        "message": "Task test hoàn thành!",
        "status": "success",
        "timestamp": time.time()
    }


if __name__ == '__main__':
    print("[TEST] Testing face loading...")
    encodings, names = load_known_faces()
    print(f"[STATS] Loaded {len(encodings)} known faces: {names}")
    
    print(f"[TEST] Testing folder permissions...")
    for folder_name, folder_path in [
        ("RESULT", RESULT_FOLDER),
        ("UPLOAD", UPLOAD_FOLDER), 
        ("KNOWN_FACES", KNOWN_FACES_FOLDER)
    ]:
        print(f"  {folder_name}: {folder_path}")
        print(f"    Exists: {folder_path.exists()}")
        print(f"    Writable: {os.access(folder_path, os.W_OK)}")