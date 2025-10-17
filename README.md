# 🎭 Distributed Face Recognition System

Hệ thống nhận diện khuôn mặt phân tán sử dụng **Flask**, **Celery**, **Redis** và **OpenCV** với khả năng xử lý song song nhiều ảnh thông qua multiple workers.

## 🚀 Features

### ⚡ Xử lý phân tán
- **Multiple Celery Workers** - Xử lý song song nhiều ảnh cùng lúc
- **Redis Queue Management** - Phân phối tasks hiệu quả
- **Real-time monitoring** - Theo dõi workers và progress trực tiếp
- **Auto-scaling** - Tự động detect số workers đang hoạt động

### 🎯 Face Recognition  
- **Face Detection** - Phát hiện khuôn mặt trong ảnh bằng OpenCV
- **Face Recognition** - Nhận diện người đã biết
- **Known Faces Management** - Quản lý database khuôn mặt đã học
- **Multiple formats** - Hỗ trợ JPG, PNG, GIF

### 📊 Dashboard & Monitoring
- **Live Dashboard** - Thống kê real-time
- **Worker Status** - Monitor workers đang hoạt động
- **Processing History** - Lịch sử xử lý chi tiết
- **Performance Metrics** - Số liệu hiệu suất

### 🎮 Demo Interface
- **Drag & Drop Upload** - Kéo thả nhiều ảnh
- **Batch Processing** - Demo buttons (5, 10, 20 ảnh)
- **Real-time Progress** - Thanh tiến trình chi tiết
- **Worker Visualization** - Hiển thị phân phối công việc

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Flask Web     │    │   Redis Queue   │    │ Multiple Workers│
│     Server      │───▶│    Manager      │───▶│  (Celery)       │
│                 │    │                 │    │                 │
│ • Upload UI     │    │ • Task Queue    │    │ • Face Detection│
│ • Dashboard     │    │ • Results Store │    │ • Recognition   │
│ • API Routes    │    │ • Worker Coord  │    │ • File Processing│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File System   │    │   SQLite DB     │    │   Known Faces   │
│                 │    │                 │    │                 │
│ • static/uploads│    │ • Process logs  │    │ • Face encodings│
│ • static/results│    │ • Worker stats  │    │ • Names mapping │
│ • static/known  │    │ • Error tracking│    │ • Training data │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📦 Installation

### 1. Clone Repository
```bash
git clone https://github.com/hquocmanh0502/distributed-face-recognition.git
cd distributed-face-recognition
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Redis Server
#### Windows:
1. Download Redis từ [Microsoft Archive](https://github.com/microsoftarchive/redis/releases)
2. Extract và chạy `redis-server.exe`

#### Linux/Mac:
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis
```

### 4. Setup Known Faces (Optional)
Thêm ảnh các khuôn mặt đã biết vào thư mục `static/known_faces/`:
```
static/known_faces/
├── john_doe.jpg
├── jane_smith.jpg
└── bob_wilson.jpg
```

## 🚀 Quick Start

### Method 1: Auto Start (Windows)
```bash
# Chạy tất cả services
./start_system.bat
```

### Method 2: Manual Start
#### Terminal 1 - Redis Server
```bash
redis-server
```

#### Terminal 2 - Worker 1
```bash
celery -A tasks worker --loglevel=info --pool=solo -n worker1@%h
```

#### Terminal 3 - Worker 2  
```bash
celery -A tasks worker --loglevel=info --pool=solo -n worker2@%h
```

#### Terminal 4 - Worker 3
```bash
celery -A tasks worker --loglevel=info --pool=solo -n worker3@%h
```

#### Terminal 5 - Flask App
```bash
python app.py
```

### 📱 Access Application
- **Main App:** http://localhost:5000
- **Dashboard:** http://localhost:5000/dashboard  
- **Results:** http://localhost:5000/results
- **Known Faces:** http://localhost:5000/known-faces

## 🔧 Configuration

### Celery Settings (`tasks.py`)
```python
app.conf.update(
    task_serializer='pickle',
    accept_content=['json', 'pickle'],
    result_serializer='pickle',
    task_default_queue='celery',
    task_time_limit=300,
    worker_concurrency=1,
)
```

### Flask Settings (`app.py`)
```python
UPLOAD_FOLDER = 'static/uploads'
RESULT_FOLDER = 'static/results' 
KNOWN_FACES_FOLDER = 'static/known_faces'
DATABASE_FOLDER = 'database'
```

## 📊 Performance Testing

### Test với nhiều workers:
```bash
# Kiểm tra workers hiện tại
python check_workers.py

# Demo performance với 30 ảnh
python worker_demo.py

# Monitor real-time
python check_workers.py monitor
```

### Expected Performance:
| Workers | 30 Images | Processing Time | Speedup |
|---------|-----------|----------------|---------|
| 1       | Sequential| ~90s           | 1.0x    |
| 2       | Parallel  | ~45s           | 2.0x    |
| 3       | Parallel  | ~30s           | 3.0x    |
| 4       | Parallel  | ~25s           | 3.6x    |

## 🎮 Usage Examples

### 1. Batch Upload
1. Truy cập http://localhost:5000
2. Kéo thả nhiều ảnh hoặc click "Demo 20 ảnh"
3. Xem workers xử lý real-time
4. Kiểm tra kết quả tại `/results`

### 2. Add Known Face
```bash
curl -X POST http://localhost:5000/add-known-face \
  -F "image=@person.jpg" \
  -F "name=John Doe"
```

### 3. API Monitoring
```bash
# Worker information
curl http://localhost:5000/api/worker-info

# System stats  
curl http://localhost:5000/api/stats

# Task status
curl http://localhost:5000/api/status/TASK_ID
```

## 📁 Project Structure

```
distributed-face-recognition/
├── 📄 app.py                 # Flask web application
├── 📄 tasks.py               # Celery worker tasks
├── 📄 requirements.txt       # Python dependencies
├── 📄 README.md             # This file
├── 📄 start_system.bat      # Auto-start script
├── 📄 check_workers.py      # Worker monitoring
├── 📄 worker_demo.py        # Performance testing
├── 📄 clear_redis.py        # Redis cleanup
├── 📁 templates/            # HTML templates
│   ├── index.html           # Main upload page
│   ├── dashboard.html       # Statistics dashboard  
│   ├── results.html         # Results gallery
│   └── known_faces.html     # Known faces management
├── 📁 static/               # Static files
│   ├── uploads/             # Uploaded images
│   ├── results/             # Processed results
│   └── known_faces/         # Known faces database
├── 📁 database/             # SQLite database
│   └── results.db           # Processing logs
└── 📁 utils/                # Utility modules
    ├── __init__.py
    ├── face_detection.py    # Core detection logic
    ├── metrics.py           # Performance metrics
    └── visualization.py     # Result visualization
```

## 🐛 Troubleshooting

### Redis Connection Issues
```bash
# Check Redis status
redis-cli ping
# Should return: PONG

# Clear stuck tasks
python clear_redis.py
```

### Worker Not Starting
```bash
# Kill existing processes
taskkill /f /im celery.exe

# Check Python imports
python -c "from tasks import detect_faces; print('OK')"

# Restart with debug
celery -A tasks worker --loglevel=debug
```

### File Permission Errors
```bash
# Windows - Run as Administrator
# Linux/Mac - Check folder permissions
chmod 755 static/
chmod 777 static/uploads static/results
```

### Memory Issues
```bash
# Reduce image size or worker concurrency
# Monitor with:
python check_workers.py monitor
```

## 📈 Monitoring & Debugging

### Debug Commands
```bash
# System health check
python check_system.py

# Worker detailed info
python check_workers.py

# Performance test
python worker_demo.py

# Clear all data
python clear_redis.py
```

### Log Files
- **Flask logs:** `flask_app.log`
- **Celery logs:** `face_recognition.log` 
- **Worker output:** Terminal windows

### Debug URLs
- http://localhost:5000/debug/files
- http://localhost:5000/debug/database
- http://localhost:5000/api/worker-info

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)  
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Quoc Manh Ho**
- GitHub: [@hquocmanh0502](https://github.com/hquocmanh0502)
- Project: [distributed-face-recognition](https://github.com/hquocmanh0502/distributed-face-recognition)

## 🙏 Acknowledgments

- **OpenCV** - Computer vision library
- **Face Recognition** - Face recognition library by Adam Geitgey
- **Flask** - Web framework
- **Celery** - Distributed task queue
- **Redis** - In-memory data store

## 📚 Technical Details

### Dependencies
- `Flask==3.0.3` - Web framework
- `Celery==5.3.4` - Task queue
- `redis==5.0.1` - Redis client
- `opencv-python==4.11.0.86` - Computer vision
- `face_recognition==1.3.0` - Face recognition
- `dlib==19.24.99` - Machine learning
- `pillow==10.1.0` - Image processing
- `numpy==1.24.3` - Numerical computing

### System Requirements
- **Python:** 3.8+
- **RAM:** 4GB+ (recommended 8GB)
- **Storage:** 2GB+ free space
- **OS:** Windows 10+, Ubuntu 18+, macOS 10.14+

### Performance Notes
- **Face detection:** ~2-5 seconds per image
- **Memory usage:** ~200-500MB per worker
- **Scaling:** Linear performance increase with workers
- **Bottleneck:** CPU-bound operations (face encoding)

---

🎉 **Happy Face Recognition!** 🎉
