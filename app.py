from flask import Flask, render_template, request, send_from_directory, jsonify
from tasks import detect_faces
import os
import time
import glob
from datetime import datetime
from pathlib import Path
import logging
import sqlite3

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flask_app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Đường dẫn tuyệt đối
BASE_DIR = Path(__file__).parent.absolute()
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
RESULT_FOLDER = BASE_DIR / 'static' / 'results'
KNOWN_FACES_FOLDER = BASE_DIR / 'static' / 'known_faces'
DATABASE_FOLDER = BASE_DIR / 'database'

# Tạo thư mục
for folder in [UPLOAD_FOLDER, RESULT_FOLDER, KNOWN_FACES_FOLDER, DATABASE_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"[FOLDER] Ensured: {folder}")

@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(timestamp):
    """Convert timestamp to readable datetime"""
    try:
        return datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M')
    except:
        return 'N/A'

def get_results_from_db():
    """Lấy kết quả từ database thay vì scan file"""
    try:
        db_path = DATABASE_FOLDER / 'results.db'
        if not db_path.exists():
            return []
            
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT filename, faces_detected, recognized_faces, processing_time,
                   worker_name, result_path, status, created_at, error_message
            FROM processing_results 
            WHERE status = 'success'
            ORDER BY created_at DESC
        """)
        
        db_results = cursor.fetchall()
        conn.close()
        
        results = []
        for row in db_results:
            filename = row[0]
            result_path = RESULT_FOLDER / filename
            
            # Kiểm tra file có tồn tại không
            if result_path.exists():
                file_stat = result_path.stat()
                results.append({
                    'filename': filename,
                    'faces_detected': row[1],
                    'recognized_faces': row[2] or "",
                    'processing_time': row[3],
                    'worker_name': row[4],
                    'size': file_stat.st_size,
                    'modified': file_stat.st_mtime,
                    'status': row[6],
                    'created_at': row[7],
                    'path': str(result_path),
                    'url': f'/results/{filename}'
                })
        
        logger.info(f"[DATABASE] Found {len(results)} results in database")
        return results
        
    except Exception as e:
        logger.error(f"[DATABASE] Error getting results: {e}")
        return []

def get_results_from_files():
    """Backup method: Lấy kết quả từ file system"""
    result_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.JPG', '*.JPEG', '*.PNG', '*.GIF']:
        result_files.extend(list(RESULT_FOLDER.glob(ext)))
    
    results = []
    for file_path in result_files:
        try:
            filename = file_path.name
            file_size = file_path.stat().st_size
            mod_time = file_path.stat().st_mtime
            
            results.append({
                'filename': filename,
                'size': file_size,
                'modified': mod_time,
                'faces_detected': 'N/A',
                'recognized_faces': '',
                'processing_time': 'N/A',
                'worker_name': 'N/A',
                'status': 'unknown',
                'path': str(file_path),
                'url': f'/results/{filename}'
            })
            
        except Exception as e:
            logger.warning(f"[WARNING] Lỗi khi đọc file {file_path}: {e}")
    
    results.sort(key=lambda x: x['modified'], reverse=True)
    logger.info(f"[FILES] Found {len(results)} result files")
    return results

# ===========================
# MAIN ROUTES
# ===========================
@app.route('/results')
def results():
    """Hiển thị trang kết quả"""
    # Thử lấy từ database trước, nếu không được thì scan files
    results = get_results_from_db()
    if not results:
        results = get_results_from_files()
    
    # Tính thống kê
    total_size = sum(r.get('size', 0) for r in results)
    stats = {
        'total_files': len(results),
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'recent_files': len([r for r in results if (time.time() - r.get('modified', 0)) < 86400]),
        'large_files': len([r for r in results if r.get('size', 0) > 1024 * 1024])
    }
    
    logger.info(f"[RESULTS] Displaying {len(results)} results, {stats['total_size_mb']} MB")
    
    return render_template('results.html', results=results, stats=stats)

@app.route('/results/<filename>')
def result_image(filename):
    """Serve ảnh kết quả"""
    try:
        file_path = RESULT_FOLDER / filename
        
        if not file_path.exists():
            logger.error(f"[ERROR] File không tồn tại: {file_path}")
            return f"File not found: {filename}", 404
        
        if file_path.stat().st_size == 0:
            logger.error(f"[ERROR] File có size 0: {file_path}")
            return f"File is empty: {filename}", 404
            
        logger.info(f"[SERVE] Serving: {file_path} ({file_path.stat().st_size} bytes)")
        
        return send_from_directory(str(RESULT_FOLDER), filename)
        
    except Exception as e:
        logger.error(f"[ERROR] Lỗi serve file {filename}: {e}")
        return f"Error: {str(e)}", 500

@app.route('/api/status/<task_id>')
def task_status(task_id):
    """Check trạng thái task"""
    try:
        from celery.result import AsyncResult
        task = AsyncResult(task_id, app=detect_faces.app)
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Đang chờ xử lý...',
                'current': 0,
                'total': 100
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'status': task.info.get('status', 'Đang xử lý...'),
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 100),
                'filename': task.info.get('filename', '')
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'status': 'Hoàn thành!',
                'current': 100,
                'total': 100,
                'result': task.result
            }
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'status': 'Thất bại!',
                'error': str(task.info),
                'current': 0,
                'total': 100
            }
        else:
            response = {
                'state': task.state,
                'status': str(task.info),
                'current': 50,
                'total': 100
            }
            
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"[ERROR] Task status error {task_id}: {e}")
        return jsonify({
            'state': 'ERROR',
            'status': f'Lỗi: {str(e)}',
            'current': 0,
            'total': 100
        }), 500

@app.route('/dashboard')
def dashboard():
    """Dashboard với thống kê"""
    try:
        # Lấy stats từ database
        db_path = DATABASE_FOLDER / 'results.db'
        stats = {
            'total_images': 0,
            'total_faces': 0,
            'avg_processing_time': 0.0,
            'active_workers': 1
        }
        
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Đếm total images
            cursor.execute("SELECT COUNT(*) FROM processing_results WHERE status = 'success'")
            stats['total_images'] = cursor.fetchone()[0]
            
            # Tổng faces detected
            cursor.execute("SELECT SUM(faces_detected) FROM processing_results WHERE status = 'success'")
            result = cursor.fetchone()[0]
            stats['total_faces'] = result if result else 0
            
            # Avg processing time
            cursor.execute("SELECT AVG(processing_time) FROM processing_results WHERE status = 'success'")
            result = cursor.fetchone()[0]
            stats['avg_processing_time'] = round(result, 2) if result else 0.0
            
            conn.close()
        
        # Backup: get from files
        if stats['total_images'] == 0:
            result_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
                result_files.extend(list(RESULT_FOLDER.glob(ext)))
            stats['total_images'] = len(result_files)
        
        return render_template('dashboard.html', stats=stats)
        
    except Exception as e:
        logger.error(f"[ERROR] Dashboard error: {e}")
        stats = {
            'total_images': 0,
            'total_faces': 0,
            'avg_processing_time': 0.0,
            'active_workers': 0
        }
        return render_template('dashboard.html', stats=stats)

@app.route('/api/stats')
def api_stats():
    """API stats real-time"""
    try:
        db_path = DATABASE_FOLDER / 'results.db'
        stats = {}
        
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM processing_results WHERE status = 'success'")
            stats['total_images'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(faces_detected) FROM processing_results WHERE status = 'success'")
            result = cursor.fetchone()[0]
            stats['total_faces'] = result if result else 0
            
            cursor.execute("SELECT AVG(processing_time) FROM processing_results WHERE status = 'success'")
            result = cursor.fetchone()[0]
            stats['avg_processing_time'] = round(result, 2) if result else 0.0
            
            cursor.execute("SELECT COUNT(*) FROM processing_results")
            total_processed = cursor.fetchone()[0]
            
            stats['success_rate'] = round((stats['total_images'] / max(total_processed, 1)) * 100, 1)
            
            conn.close()
        else:
            stats = {
                'total_images': 0,
                'total_faces': 0,
                'avg_processing_time': 0.0,
                'success_rate': 0
            }
        
        # Get real worker count
        try:
            from tasks import app as celery_app
            inspect = celery_app.control.inspect()
            stats_workers = inspect.stats() or {}
            stats['active_workers'] = len(stats_workers)
        except:
            stats['active_workers'] = 1
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"[ERROR] API stats error: {e}")
        return jsonify({
            'total_images': 0,
            'total_faces': 0,
            'avg_processing_time': 0.0,
            'active_workers': 0,
            'success_rate': 0
        })

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Xóa tất cả kết quả"""
    try:
        deleted_files = 0
        
        # Xóa result files
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.JPG', '*.JPEG', '*.PNG', '*.GIF']:
            for file_path in RESULT_FOLDER.glob(ext):
                file_path.unlink()
                deleted_files += 1
        
        # Xóa upload files
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.JPG', '*.JPEG', '*.PNG', '*.GIF']:
            for file_path in UPLOAD_FOLDER.glob(ext):
                file_path.unlink()
                deleted_files += 1
        
        # Xóa database records
        db_path = DATABASE_FOLDER / 'results.db'
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM processing_results")
            conn.commit()
            conn.close()
        
        logger.info(f"[CLEAR] Đã xóa {deleted_files} files và database records")
        
        return jsonify({
            'success': True,
            'message': f'Đã xóa {deleted_files} files và tất cả records'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Clear error: {e}")
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500

@app.route('/known-faces')
def known_faces():
    """Trang quản lý known faces"""
    known_faces = []
    
    for image_file in KNOWN_FACES_FOLDER.glob("*.jpg"):
        try:
            name = image_file.stem.replace('_', ' ').title()
            known_faces.append({
                'name': name,
                'filename': image_file.name,
                'size': image_file.stat().st_size
            })
        except Exception as e:
            logger.warning(f"[WARNING] Lỗi đọc known face {image_file}: {e}")
    
    return render_template('known_faces.html', known_faces=known_faces)

@app.route('/add-known-face', methods=['POST'])
def add_known_face():
    """API thêm known face"""
    try:
        if 'image' not in request.files or 'name' not in request.form:
            return jsonify({'success': False, 'message': 'Thiếu ảnh hoặc tên'}), 400
        
        file = request.files['image']
        person_name = request.form['name'].strip()
        
        if not file.filename or not person_name:
            return jsonify({'success': False, 'message': 'Tên và ảnh không được để trống'}), 400
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Chỉ chấp nhận file ảnh'}), 400
        
        # Save temp file
        temp_filename = f"temp_{int(time.time())}_{file.filename}"
        temp_path = UPLOAD_FOLDER / temp_filename
        file.save(str(temp_path))
        
        logger.info(f"[SAVE] Saved temp file: {temp_path}")
        
        # Process with task
        from tasks import add_known_face as add_face_task
        result = add_face_task.delay(str(temp_path), person_name).get(timeout=30)
        
        # Clean up
        if temp_path.exists():
            temp_path.unlink()
        
        return jsonify(result)
        
    except Exception as e:
        if 'temp_path' in locals() and temp_path.exists():
            temp_path.unlink()
        
        logger.error(f"[ERROR] Add known face error: {e}")
        return jsonify({
            'success': False, 
            'message': f'Lỗi: {str(e)}'
        }), 500

@app.route('/known-faces/<filename>')
def known_face_image(filename):
    """Serve known face images"""
    return send_from_directory(str(KNOWN_FACES_FOLDER), filename)

@app.route('/api/delete-file', methods=['POST'])
def delete_file():
    """Xóa file cụ thể"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'success': False, 'message': 'Thiếu tên file'}), 400
        
        deleted_files = []
        
        # Delete từ results
        result_path = RESULT_FOLDER / filename
        if result_path.exists():
            result_path.unlink()
            deleted_files.append('result')
        
        # Delete từ uploads
        upload_path = UPLOAD_FOLDER / filename
        if upload_path.exists():
            upload_path.unlink()
            deleted_files.append('upload')
        
        # Delete từ database
        db_path = DATABASE_FOLDER / 'results.db'
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM processing_results WHERE filename = ?", (filename,))
            conn.commit()
            conn.close()
            deleted_files.append('database')
        
        if not deleted_files:
            return jsonify({'success': False, 'message': 'File không tồn tại'}), 404
        
        logger.info(f"[DELETE] Deleted {filename} from {', '.join(deleted_files)}")
        
        return jsonify({
            'success': True,
            'message': f'Đã xóa file khỏi {", ".join(deleted_files)}'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Delete file error: {e}")
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500

# ===========================
# DEBUG ROUTES
# ===========================
@app.route('/debug/files')
def debug_files():
    """Debug files"""
    upload_files = []
    result_files = []
    
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
        upload_files.extend(list(UPLOAD_FOLDER.glob(ext)))
        result_files.extend(list(RESULT_FOLDER.glob(ext)))
    
    return jsonify({
        'upload_folder': {
            'path': str(UPLOAD_FOLDER),
            'exists': UPLOAD_FOLDER.exists(),
            'files': [{'name': f.name, 'size': f.stat().st_size} for f in upload_files]
        },
        'result_folder': {
            'path': str(RESULT_FOLDER),
            'exists': RESULT_FOLDER.exists(),
            'files': [{'name': f.name, 'size': f.stat().st_size} for f in result_files]
        }
    })

@app.route('/debug/database')
def debug_database():
    """Debug database"""
    try:
        db_path = DATABASE_FOLDER / 'results.db'
        if not db_path.exists():
            return jsonify({'error': 'Database not found'})
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM processing_results ORDER BY created_at DESC LIMIT 10")
        recent_results = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM processing_results")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM processing_results WHERE status = 'success'")
        success_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'database_path': str(db_path),
            'total_records': total_count,
            'success_records': success_count,
            'recent_results': recent_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('images')
        
        if not files or not any(file.filename for file in files):
            return "[ERROR] Vui lòng chọn ít nhất một file!", 400
        
        task_ids = []
        processed_files = []
        failed_files = []

        for file in files:
            if file and file.filename and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                # Tạo filename unique và safe
                timestamp = int(time.time() * 1000)
                safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
                filename = f"{timestamp}_{safe_filename}"
                upload_path = UPLOAD_FOLDER / filename
                
                try:
                    file.save(str(upload_path))
                    
                    # Verify file
                    if not upload_path.exists() or upload_path.stat().st_size == 0:
                        raise Exception(f"File save failed: {upload_path}")
                    
                    logger.info(f"[SAVE] Saved: {upload_path} ({upload_path.stat().st_size} bytes)")
                    
                    # Send task
                    task = detect_faces.delay(str(upload_path), filename)
                    task_ids.append(task.id)
                    processed_files.append(filename)
                    
                    logger.info(f"[TASK] Sent task {task.id} for {filename}")
                    
                except Exception as e:
                    logger.error(f"[ERROR] File save error {file.filename}: {e}")
                    failed_files.append(file.filename)

        if not task_ids:
            return f"[ERROR] Không có file hợp lệ! Lỗi: {failed_files}", 400

        logger.info(f"[SUMMARY] {len(task_ids)} tasks sent, {len(failed_files)} failed")

        # Enhanced response for multiple files demo
        response_html = f"""
        <div style="padding: 20px; font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 30px;">
                <h2><i class="fas fa-rocket"></i> Hệ thống phân tán đang xử lý!</h2>
                <p style="font-size: 1.2rem; margin-bottom: 20px;">
                    <strong>{len(task_ids)} tasks</strong> đã được phân phối đến <strong>multiple workers</strong>
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px;">
                    <div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px;">
                        <i class="fas fa-images" style="font-size: 2rem; margin-bottom: 10px;"></i>
                        <div style="font-size: 1.5rem; font-weight: bold;">{len(processed_files)}</div>
                        <div>Files đang xử lý</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px;">
                        <i class="fas fa-server" style="font-size: 2rem; margin-bottom: 10px;"></i>
                        <div style="font-size: 1.5rem; font-weight: bold;">3+</div>
                        <div>Celery Workers</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px;">
                        <i class="fas fa-clock" style="font-size: 2rem; margin-bottom: 10px;"></i>
                        <div style="font-size: 1.5rem; font-weight: bold;">~{len(task_ids)*2}s</div>
                        <div>Thời gian ước tính</div>
                    </div>
                </div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 15px; margin-bottom: 20px;">
                <h3 style="color: #333; margin-bottom: 15px;"><i class="fas fa-list"></i> Danh sách Tasks:</h3>
                <div style="max-height: 300px; overflow-y: auto;">
                    {''.join([f'<div style="background: white; margin: 8px 0; padding: 12px; border-radius: 8px; border-left: 4px solid #007bff; display: flex; align-items: center; gap: 10px;"><i class="fas fa-cog fa-spin" style="color: #007bff;"></i> <strong>Task:</strong> {task_id[:8]}... <span style="margin-left: auto; color: #666;">File: {file}</span></div>' for task_id, file in zip(task_ids, processed_files)])}
                </div>
            </div>
            
            <div id="progress-container" style="margin: 20px 0;">
                <h4 style="color: #333;"><i class="fas fa-chart-line"></i> Theo dõi tiến trình real-time:</h4>
                <div id="progress-list"></div>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/results" style="background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; margin-right: 15px; display: inline-block;">
                    <i class="fas fa-images"></i> Xem kết quả
                </a>
                <a href="/dashboard" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; display: inline-block;">
                    <i class="fas fa-chart-bar"></i> Dashboard
                </a>
            </div>
            
            <div style="background: #e3f2fd; border: 1px solid #2196f3; border-radius: 10px; padding: 20px; margin-top: 20px;">
                <h5 style="color: #1976d2; margin-bottom: 10px;"><i class="fas fa-info-circle"></i> Demo Hệ thống Phân tán:</h5>
                <ul style="color: #1976d2; margin: 0; padding-left: 20px;">
                    <li>✅ Tasks được phân phối đồng đều cho các workers</li>
                    <li>✅ Xử lý song song giúp tăng tốc độ</li>
                    <li>✅ Redis queue quản lý tasks hiệu quả</li>
                    <li>✅ Tracking real-time qua API</li>
                </ul>
            </div>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/js/all.min.js"></script>
            <script>
                const taskIds = {task_ids};
                const progressContainer = document.getElementById('progress-list');
                let completedTasks = 0;
                
                function checkTaskStatus(taskId) {{
                    fetch(`/api/status/${{taskId}}`)
                        .then(response => response.json())
                        .then(data => {{
                            let progressDiv = document.getElementById(`progress-${{taskId}}`);
                            if (!progressDiv) {{
                                progressDiv = document.createElement('div');
                                progressDiv.id = `progress-${{taskId}}`;
                                progressDiv.style.cssText = 'margin: 10px 0; padding: 15px; border: 1px solid #ddd; border-radius: 12px; background: #f9f9f9;';
                                progressContainer.appendChild(progressDiv);
                            }}
                            
                            const current = data.current || 0;
                            const total = data.total || 100;
                            const percentage = Math.round((current / total) * 100);
                            
                            progressDiv.innerHTML = `
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                    <div style="display: flex; align-items: center; gap: 10px;">
                                        <i class="fas fa-server" style="color: #667eea;"></i>
                                        <strong>Worker processing: ${{taskId.substring(0, 8)}}...</strong>
                                    </div>
                                    <span style="font-size: 12px; color: #666; background: #e9ecef; padding: 4px 8px; border-radius: 12px;">${{data.filename || 'Processing...'}}</span>
                                </div>
                                <div style="margin-bottom: 10px;">
                                    <div style="background: #e0e0e0; border-radius: 15px; height: 24px; overflow: hidden;">
                                        <div style="background: linear-gradient(90deg, #667eea, #764ba2); height: 100%; width: ${{percentage}}%; transition: width 0.5s ease; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;">
                                            ${{percentage}}%
                                        </div>
                                    </div>
                                </div>
                                <div style="font-size: 13px; color: #555; display: flex; align-items: center; gap: 8px;">
                                    <i class="fas fa-${{data.state === 'SUCCESS' ? 'check' : data.state === 'FAILURE' ? 'times' : data.state === 'PROGRESS' ? 'cog fa-spin' : 'clock'}}"></i>
                                    ${{data.status}}
                                </div>
                            `;
                            
                            if (data.state === 'SUCCESS') {{
                                progressDiv.style.background = '#d4edda';
                                progressDiv.style.borderColor = '#c3e6cb';
                                progressDiv.innerHTML += '<div style="color: #155724; font-weight: bold; margin-top: 10px; text-align: center;"><i class="fas fa-check-circle"></i> HOÀN THÀNH!</div>';
                                completedTasks++;
                                
                                if (completedTasks === taskIds.length) {{
                                    setTimeout(() => {{
                                        window.location.href = '/results';
                                    }}, 3000);
                                }}
                            }} else if (data.state === 'FAILURE') {{
                                progressDiv.style.background = '#f8d7da';
                                progressDiv.style.borderColor = '#f5c6cb';
                                progressDiv.innerHTML += '<div style="color: #721c24; font-weight: bold; margin-top: 10px; text-align: center;"><i class="fas fa-exclamation-triangle"></i> LỖI!</div>';
                            }}
                        }})
                        .catch(error => {{
                            console.error('Error checking task:', error);
                        }});
                }}
                
                // Check mỗi 2 giây
                const interval = setInterval(() => {{
                    taskIds.forEach(checkTaskStatus);
                    
                    // Stop checking nếu tất cả đã xong
                    if (completedTasks === taskIds.length) {{
                        clearInterval(interval);
                    }}
                }}, 2000);
                
                // Check ngay lập tức
                taskIds.forEach(checkTaskStatus);
                
                // Auto refresh completed count
                setInterval(() => {{
                    document.title = `(${{completedTasks}}/${{taskIds.length}}) Face Recognition Processing`;
                }}, 1000);
            </script>
        </div>
        """
        
        return response_html

    return render_template('index.html')

@app.route('/api/dashboard-data')
def dashboard_data():
    """API cung cấp dữ liệu dashboard real-time"""
    try:
        from tasks import app as celery_app
        inspect = celery_app.control.inspect()
        
        # Worker information
        active = inspect.active() or {}
        stats = inspect.stats() or {}
        
        workers_info = []
        total_active_tasks = 0
        
        for worker_name in stats.keys():
            worker_tasks = active.get(worker_name, [])
            worker_stat = stats.get(worker_name, {})
            total_active_tasks += len(worker_tasks)
            
            workers_info.append({
                'name': worker_name.split('@')[0],
                'full_name': worker_name,
                'active_tasks': len(worker_tasks),
                'status': 'busy' if len(worker_tasks) > 0 else 'idle',
                'tasks': [
                    {
                        'name': task.get('name', 'Unknown').replace('tasks.', ''),
                        'id': task.get('id', 'No ID')[:8],
                        'args': str(task.get('args', ['Unknown']))[:50] + '...'
                    }
                    for task in worker_tasks[:3]
                ],
                'pool_processes': worker_stat.get('pool', {}).get('processes', 1),
                'total_completed': worker_stat.get('total', {}).get('tasks.detect_faces', 0)
            })
        
        # Database stats
        db_stats = get_database_stats()
        
        # Performance calculation
        processing_times = get_recent_processing_times()
        avg_time_per_image = sum(processing_times) / len(processing_times) if processing_times else 3.0
        
        # Estimated speedup calculation
        worker_count = len(workers_info)
        theoretical_speedup = min(worker_count, 4) if worker_count > 0 else 1  # Realistic cap
        estimated_sequential_time = avg_time_per_image * theoretical_speedup
        
        return jsonify({
            'workers': {
                'total': len(workers_info),
                'active': len([w for w in workers_info if w['status'] == 'busy']),
                'idle': len([w for w in workers_info if w['status'] == 'idle']),
                'details': workers_info
            },
            'tasks': {
                'active': total_active_tasks,
                'queue_length': get_queue_length(),
                'completed_today': db_stats.get('completed_today', 0)
            },
            'performance': {
                'avg_time_per_image': avg_time_per_image,
                'estimated_sequential_time': estimated_sequential_time,
                'speedup_factor': theoretical_speedup,
                'throughput_per_hour': int(3600 / avg_time_per_image * worker_count) if avg_time_per_image > 0 else 0
            },
            'database': db_stats,
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")
        return jsonify({'error': str(e)}), 500

def get_database_stats():
    """Lấy thống kê từ database"""
    try:
        db_path = DATABASE_FOLDER / 'results.db'
        if not db_path.exists():
            return {}
            
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Total stats
        cursor.execute("SELECT COUNT(*) FROM processing_results WHERE status = 'success'")
        total_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(faces_detected) FROM processing_results WHERE status = 'success'")
        total_faces = cursor.fetchone()[0] or 0
        
        # Today's stats
        cursor.execute("""
            SELECT COUNT(*) FROM processing_results 
            WHERE status = 'success' AND DATE(created_at) = DATE('now')
        """)
        completed_today = cursor.fetchone()[0]
        
        # Hourly stats for last 24 hours
        cursor.execute("""
            SELECT strftime('%H', created_at) as hour, COUNT(*) 
            FROM processing_results 
            WHERE status = 'success' AND datetime(created_at) >= datetime('now', '-24 hours')
            GROUP BY hour ORDER BY hour
        """)
        hourly_data = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total_images': total_images,
            'total_faces': total_faces,
            'completed_today': completed_today,
            'hourly_data': hourly_data
        }
    except Exception as e:
        logger.error(f"Database stats error: {e}")
        return {}

def get_recent_processing_times():
    """Lấy thời gian xử lý gần đây"""
    try:
        db_path = DATABASE_FOLDER / 'results.db'
        if not db_path.exists():
            return []
            
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT processing_time FROM processing_results 
            WHERE status = 'success' AND processing_time > 0
            ORDER BY created_at DESC LIMIT 50
        """)
        times = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return times
    except:
        return []

def get_queue_length():
    """Lấy số lượng tasks trong queue"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        return r.llen('celery')
    except:
        return 0

@app.route('/api/worker-count')
def worker_count():
    """API đơn giản để lấy số workers"""
    try:
        from tasks import app as celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats() or {}
        return jsonify({'count': len(stats)})
    except:
        return jsonify({'count': 1})  # Fallback

@app.route('/api/worker-info')
def worker_info():
    """API hiển thị thông tin workers thực tế"""
    try:
        from tasks import app as celery_app
        inspect = celery_app.control.inspect()
        
        active = inspect.active() or {}
        stats = inspect.stats() or {}
        
        workers = []
        for worker_name in stats.keys():
            worker_tasks = active.get(worker_name, [])
            worker_stat = stats.get(worker_name, {})
            
            workers.append({
                'name': worker_name,
                'short_name': worker_name.split('@')[0],  # worker1, worker2, etc.
                'active_tasks': len(worker_tasks),
                'status': 'busy' if len(worker_tasks) > 0 else 'idle',
                'tasks': [
                    {
                        'name': task.get('name', 'Unknown').replace('tasks.', ''),
                        'id': task.get('id', 'No ID')[:8] + '...',
                        'filename': str(task.get('args', ['Unknown']))[:30] + '...'
                    }
                    for task in worker_tasks[:5]  # Show max 5 tasks
                ],
                'pool_info': worker_stat.get('pool', {}),
                'total_completed': worker_stat.get('total', {}).get('tasks.detect_faces', 0)
            })
        
        # Sort workers by name for consistent order
        workers.sort(key=lambda x: x['name'])
        
        return jsonify({
            'total_workers': len(workers),
            'workers': workers,
            'total_active_tasks': sum(len(active.get(w, [])) for w in stats.keys()),
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Worker info error: {e}")
        return jsonify({
            'error': str(e),
            'total_workers': 0,
            'workers': [],
            'total_active_tasks': 0
        }), 500

if __name__ == '__main__':
    logger.info("[APP] Starting Flask app...")
    logger.info(f"[APP] Upload folder: {UPLOAD_FOLDER}")
    logger.info(f"[APP] Result folder: {RESULT_FOLDER}")
    app.run(debug=True, host='0.0.0.0', port=5000)