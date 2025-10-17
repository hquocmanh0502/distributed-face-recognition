import cv2
import os
import face_recognition
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def detect_faces(filepath, known_face_encodings=None, known_face_names=None):
    """
    Phát hiện và nhận diện khuôn mặt - PHIÊN BẢN CẢI THIỆN
    
    Args:
        filepath: Đường dẫn tới file ảnh
        known_face_encodings: List encoding của khuôn mặt đã biết
        known_face_names: List tên tương ứng
    
    Returns:
        dict: Kết quả xử lý
    """
    try:
        # Load ảnh
        image = face_recognition.load_image_file(filepath)
        logger.info(f"[DETECTION] Loaded image: {image.shape}")
        
        # Tìm khuôn mặt với model HOG (nhanh hơn)
        face_locations = face_recognition.face_locations(image, model="hog")
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        logger.info(f"[DETECTION] Found {len(face_locations)} faces")
        
        # Convert sang OpenCV format để vẽ
        cv_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        recognized_faces = []
        
        # Xử lý từng khuôn mặt
        for i, ((top, right, bottom, left), face_encoding) in enumerate(zip(face_locations, face_encodings)):
            name = "Unknown"
            confidence = 0
            
            # Nhận diện nếu có known faces
            if known_face_encodings and len(known_face_encodings) > 0:
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
                
                if True in matches:
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    
                    if matches[best_match_index]:
                        name = known_face_names[best_match_index]
                        confidence = round((1 - face_distances[best_match_index]) * 100, 1)
                        recognized_faces.append(f"{name} ({confidence}%)")
                        logger.info(f"[RECOGNIZED] {name} with {confidence}% confidence")
            
            # Vẽ khung và label
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            thickness = 3
            
            # Vẽ khung
            cv2.rectangle(cv_image, (left, top), (right, bottom), color, thickness)
            
            # Vẽ label
            label = f"{name}" if name == "Unknown" else f"{name} ({confidence}%)"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            text_thickness = 2
            
            # Tính kích thước text
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, text_thickness)
            
            # Vị trí text
            text_y = bottom + text_height + 10
            if text_y > cv_image.shape[0]:
                text_y = top - 10
            
            # Vẽ background cho text
            cv2.rectangle(cv_image, (left, text_y - text_height - 5), 
                         (left + text_width + 10, text_y + 5), color, cv2.FILLED)
            
            # Vẽ text
            cv2.putText(cv_image, label, (left + 5, text_y - 5), 
                       font, font_scale, (255, 255, 255), text_thickness)
        
        # Lưu ảnh kết quả
        output_path = os.path.join('static/results', os.path.basename(filepath))
        
        # Đảm bảo thư mục tồn tại
        os.makedirs('static/results', exist_ok=True)
        
        # Lưu với quality cao
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            cv2.imwrite(output_path, cv_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            cv2.imwrite(output_path, cv_image)
        
        logger.info(f"[SUCCESS] Saved result to: {output_path}")
        
        return {
            "success": True,
            "faces_detected": len(face_locations),
            "recognized_faces": recognized_faces,
            "output_path": output_path,
            "message": f"Detected {len(face_locations)} faces, recognized {len(recognized_faces)}"
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Detection failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "faces_detected": 0,
            "recognized_faces": [],
            "output_path": None
        }

def detect_faces_simple(filepath):
    """Version đơn giản chỉ dùng OpenCV Haar Cascade"""
    try:
        # Load ảnh
        image = cv2.imread(filepath)
        if image is None:
            raise ValueError(f"Cannot load image: {filepath}")
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Load cascade classifier
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Phát hiện khuôn mặt
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        logger.info(f"[SIMPLE] Found {len(faces)} faces")
        
        # Vẽ khung
        for (x, y, w, h) in faces:
            cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(image, "Face", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Lưu kết quả
        output_path = os.path.join('static/results', os.path.basename(filepath))
        os.makedirs('static/results', exist_ok=True)
        cv2.imwrite(output_path, image)
        
        return output_path
        
    except Exception as e:
        logger.error(f"[ERROR] Simple detection failed: {e}")
        return None