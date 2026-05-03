# ETL Pipeline REST API Backend

A modern, scalable REST API for automated ETL (Extract, Transform, Load) data processing built with FastAPI.

## 🎯 Features

- ✅ **File Upload & Processing** - Support for CSV, XLSX, XLS files
- 📊 **Automatic Relationship Detection** - Detect relationships between tables
- 🔄 **Async Processing** - Non-blocking background jobs
- 📁 **Data Export** - Save to CSV, database, or JSON
- 🛡️ **Error Handling** - Comprehensive validation and error responses
- 📚 **Auto Documentation** - Interactive Swagger UI & ReDoc
- 🐳 **Docker Support** - Easy deployment with Docker/Docker Compose
- 🔍 **Job Tracking** - Monitor processing status in real-time

## 📋 Project Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── config.py                  # Configuration & settings management
├── schemas.py                 # Pydantic models for validation
├── database.py                # SQLAlchemy models & database setup
├── processing.py              # Core ETL processing logic
├── routes_extraction.py        # API endpoints for file extraction
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose for local development
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- pip or conda
- Docker (optional)

### 2. Local Setup (Without Docker)

#### Clone the repository
```bash
cd backend
```

#### Create virtual environment
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

#### Install dependencies
```bash
pip install -r requirements.txt
```

#### Configure environment
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (optional - defaults work for local dev)
```

#### Run the server
```bash
uvicorn main:app --reload --port 8000
```

The API will be available at:
- 🌐 **API**: http://localhost:8000
- 📚 **Swagger Docs**: http://localhost:8000/docs
- 📖 **ReDoc**: http://localhost:8000/redoc
- ❤️ **Health Check**: http://localhost:8000/health

### 3. Setup with Docker

#### Build and run with Docker Compose
```bash
docker-compose up --build
```

#### Or build manually
```bash
docker build -t etl-api .
docker run -p 8000:8000 -v $(pwd)/uploads:/app/uploads etl-api
```

Access the same endpoints as above.

## 🔌 API Endpoints

### Core Endpoints

#### 1. **Health Check**
```
GET /health
```
Check if the API is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0"
}
```

#### 2. **API Information**
```
GET /api/v1/info
```
Get API configuration and supported features.

**Response:**
```json
{
  "name": "ETL Pipeline API",
  "version": "1.0.0",
  "supported_file_types": ["csv", "xlsx", "xls"],
  "max_upload_size_mb": 50,
  "max_workers": 4
}
```

### File Extraction Endpoints

#### 3. **Upload & Process Files**
```
POST /api/v1/extraction/upload-and-process
```

Upload files and start the extraction process.

**Parameters (Form Data):**
- `files` (required): One or more files (CSV, XLSX, XLS)
- `detect_relationships` (optional): Detect table relationships (default: true)
- `save_to_database` (optional): Save results to DB (default: true)
- `save_to_csv` (optional): Save results to CSV (default: true)

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/api/v1/extraction/upload-and-process" \
  -F "files=@data.csv" \
  -F "files=@data.xlsx" \
  -F "detect_relationships=true" \
  -F "save_to_csv=true"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Processing job created. Processing 2 file(s) (245.50KB)",
  "timestamp": "2024-01-15T10:30:00",
  "estimated_completion_time": 60
}
```

#### 4. **Check Job Status**
```
GET /api/v1/extraction/jobs/{job_id}/status
```

Check the progress of a processing job.

**Example:**
```bash
curl "http://localhost:8000/api/v1/extraction/jobs/550e8400-e29b-41d4-a716-446655440000/status"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 75,
  "message": "Job status: processing",
  "timestamp": "2024-01-15T10:30:30",
  "result": null
}
```

#### 5. **Get Job Results**
```
GET /api/v1/extraction/jobs/{job_id}/result
```

Get detailed results of a completed job.

**Example:**
```bash
curl "http://localhost:8000/api/v1/extraction/jobs/550e8400-e29b-41d4-a716-446655440000/result"
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "timestamp": "2024-01-15T10:31:00",
  "records_count": 1250,
  "file_path": "uploads/results/550e8400-e29b-41d4-a716-446655440000",
  "extracted_data": {
    "data.csv": [
      {"id": 1, "name": "John", "email": "john@example.com"},
      {"id": 2, "name": "Jane", "email": "jane@example.com"}
    ],
    "data.xlsx": {
      "Sheet1": [{"product": "A", "price": 100}],
      "Sheet2": [{"category": "Electronics"}]
    }
  },
  "detected_relationships": {
    "data.csv <-> data.xlsx/Sheet1": ["id", "product_id"]
  }
}
```

#### 6. **Download Results**
```
GET /api/v1/extraction/jobs/{job_id}/download
```

Download all results as a ZIP file.

**Example:**
```bash
curl -O "http://localhost:8000/api/v1/extraction/jobs/550e8400-e29b-41d4-a716-446655440000/download" \
  -H "Content-Disposition: attachment"
```

#### 7. **Cancel Job**
```
GET /api/v1/extraction/jobs/{job_id}/cancel
```

Cancel a processing job.

**Example:**
```bash
curl "http://localhost:8000/api/v1/extraction/jobs/550e8400-e29b-41d4-a716-446655440000/cancel"
```

## 📝 Frontend Integration Example

### JavaScript/React Example

```javascript
// Upload and start processing
async function uploadFiles(files) {
  const formData = new FormData();
  
  // Add files
  files.forEach(file => {
    formData.append('files', file);
  });
  
  // Add options
  formData.append('detect_relationships', true);
  formData.append('save_to_csv', true);
  
  // Upload
  const response = await fetch('http://localhost:8000/api/v1/extraction/upload-and-process', {
    method: 'POST',
    body: formData
  });
  
  const data = await response.json();
  return data.job_id;
}

// Poll for job status
async function checkJobStatus(jobId) {
  const response = await fetch(
    `http://localhost:8000/api/v1/extraction/jobs/${jobId}/status`
  );
  return response.json();
}

// Get results when done
async function getResults(jobId) {
  const response = await fetch(
    `http://localhost:8000/api/v1/extraction/jobs/${jobId}/result`
  );
  return response.json();
}

// Download results
function downloadResults(jobId) {
  window.open(
    `http://localhost:8000/api/v1/extraction/jobs/${jobId}/download`
  );
}

// Usage
async function processData() {
  const files = document.getElementById('fileInput').files;
  const jobId = await uploadFiles(files);
  console.log('Job started:', jobId);
  
  // Poll status every 2 seconds
  const interval = setInterval(async () => {
    const status = await checkJobStatus(jobId);
    console.log('Progress:', status.progress, '%');
    
    if (status.status === 'completed') {
      clearInterval(interval);
      const results = await getResults(jobId);
      console.log('Results:', results);
    }
  }, 2000);
}
```

### Python Example

```python
import requests
import time

API_URL = "http://localhost:8000/api/v1"

def upload_and_process(file_paths):
    """Upload files and start processing."""
    files = []
    for path in file_paths:
        files.append(('files', open(path, 'rb')))
    
    data = {
        'detect_relationships': True,
        'save_to_csv': True,
    }
    
    response = requests.post(
        f"{API_URL}/extraction/upload-and-process",
        files=files,
        data=data
    )
    
    return response.json()['job_id']

def check_status(job_id):
    """Check job status."""
    response = requests.get(
        f"{API_URL}/extraction/jobs/{job_id}/status"
    )
    return response.json()

def get_results(job_id):
    """Get job results."""
    response = requests.get(
        f"{API_URL}/extraction/jobs/{job_id}/result"
    )
    return response.json()

# Usage
job_id = upload_and_process(['data.csv', 'data.xlsx'])
print(f"Job started: {job_id}")

# Wait for completion
while True:
    status = check_status(job_id)
    print(f"Status: {status['status']} ({status['progress']}%)")
    
    if status['status'] == 'completed':
        results = get_results(job_id)
        print("Results:", results)
        break
    
    time.sleep(2)
```

## 🔧 Configuration

Edit `.env` file to customize:

```bash
# Application
DEBUG=True
HOST=0.0.0.0
PORT=8000

# File uploads
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=50

# Database
DATABASE_URL=sqlite:///./etl_pipeline.db

# Processing
MAX_WORKERS=4
PROCESSING_TIMEOUT=3600

# Security
SECRET_KEY=your-secret-key-here
```

## 🚀 Deployment

### Option 1: Render.com

1. **Push to GitHub**
```bash
git push origin main
```

2. **Connect to Render**
   - Go to [render.com](https://render.com)
   - New → Web Service
   - Connect your repository
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Set environment variables** in Render dashboard

### Option 2: Railway.app

1. **Connect GitHub repo**
2. **Set environment variables**
3. **Railway automatically detects and deploys**

### Option 3: Docker + AWS EC2

```bash
# Build image
docker build -t etl-api:latest .

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URL
docker tag etl-api:latest YOUR_ECR_URL/etl-api:latest
docker push YOUR_ECR_URL/etl-api:latest

# Run on EC2
docker run -p 80:8000 YOUR_ECR_URL/etl-api:latest
```

### Option 4: Traditional VPS (nginx + Gunicorn)

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app

# Configure nginx as reverse proxy
```

## 🧪 Testing the API

### Using Swagger UI
Open http://localhost:8000/docs and try the endpoints directly.

### Using curl

```bash
# Upload files
curl -X POST "http://localhost:8000/api/v1/extraction/upload-and-process" \
  -F "files=@test.csv"

# Check status
curl "http://localhost:8000/api/v1/extraction/jobs/JOB_ID/status"

# Get results
curl "http://localhost:8000/api/v1/extraction/jobs/JOB_ID/result"
```

### Using Postman

1. Import the API collection from Swagger: http://localhost:8000/openapi.json
2. Create POST request to upload-and-process
3. Add files in form-data
4. Send and copy job_id
5. Create GET request to check status

## 📊 Database Schema

The application uses SQLAlchemy ORM with three main tables:

### processing_jobs
Stores information about each processing job.

### uploaded_files
Tracks uploaded files and their association with jobs.

### extraction_results
Stores extracted data and detected relationships.

## 🐛 Troubleshooting

### Issue: "File not found" error
**Solution:** Ensure the upload directory exists and has write permissions.
```bash
mkdir -p uploads
chmod 755 uploads
```

### Issue: Database locked
**Solution:** If using SQLite, close other connections:
```bash
rm etl_pipeline.db
```

### Issue: Port already in use
**Solution:** Change the port in config:
```bash
# In .env or command line
uvicorn main:app --port 8001
```

### Issue: Slow processing
**Solution:** Increase max workers in .env:
```bash
MAX_WORKERS=8
```

## 📚 API Documentation

- **Swagger UI**: `/docs` - Interactive API documentation
- **ReDoc**: `/redoc` - Alternative documentation format
- **OpenAPI Schema**: `/openapi.json` - Machine-readable spec

## 🔐 Security

### Production Checklist

- [ ] Change `SECRET_KEY` in .env
- [ ] Set `DEBUG=False`
- [ ] Use HTTPS (enable in reverse proxy)
- [ ] Add authentication middleware
- [ ] Use PostgreSQL instead of SQLite
- [ ] Add rate limiting
- [ ] Enable CORS only for your frontend domain
- [ ] Add request logging and monitoring
- [ ] Use environment-specific database URLs

## 📦 Dependencies

- **fastapi** - Web framework
- **uvicorn** - ASGI server
- **pydantic** - Data validation
- **sqlalchemy** - ORM
- **pandas** - Data processing
- **python-multipart** - File upload handling

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## 📄 License

This project is part of the ETL-AI-Agent system.

## 🆘 Support

For issues and questions:
- Check the troubleshooting section above
- Review API documentation at `/docs`
- Check application logs

## 📞 Contact

For more information about the ETL-AI-Agent project, visit the main repository.

---

**Happy Data Processing!** 🚀📊
