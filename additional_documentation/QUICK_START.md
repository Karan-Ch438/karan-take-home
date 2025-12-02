# 🚀 Quick Start Guide - Setup & Testing From Scratch

## Prerequisites

- **Python**: 3.8+ (check: `python3 --version`)
- **OS**: Unix-based (macOS, Linux, WSL)

## 📦 Step 1: Environment Setup

```bash
# 1. Clone/Download repository
git clone <repo-url> && cd fun-things

# 2. Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## 🗂️ Step 2: Create Test Data

```bash
# Create directory structure
mkdir -p var/log/apache

# Create sample log files
echo '2024-01-15 10:23:45 INFO Application started
2024-01-15 10:23:46 ERROR Database connection failed
2024-01-15 10:23:47 WARNING Memory usage high: 85%
2024-01-15 10:23:48 INFO Retry successful
2024-01-15 10:23:49 DEBUG Cache initialized' > var/log/log1.txt

echo '2024-01-15 11:00:00 INFO User login: user123
2024-01-15 11:00:15 ERROR Timeout: API request failed
2024-01-15 11:00:30 WARNING Certificate expires soon
2024-01-15 11:00:45 INFO Backup completed
2024-01-15 11:01:00 DEBUG Session cleaned' > var/log/log2.txt

echo '192.168.1.1 - - [15/Jan/2024:10:00:00] "GET /api/data" 200
192.168.1.2 - - [15/Jan/2024:10:00:01] "POST /login" 401
[error] File not found: /favicon.ico
192.168.1.3 - - [15/Jan/2024:10:00:02] "GET /health" 200
[error] Access denied: insufficient privileges' > var/log/apache/log3.txt
```

## 🧪 Step 3: Run Tests

```bash
# Run all unit tests
pytest test_api.py -v

# Expected output: "====== 20 passed in X.XXs ======"

# Run specific test categories
pytest test_api.py -k "test_get_logs"     # Log fetching tests
pytest test_api.py -k "TestPerformance"   # Performance tests
```

## 🚀 Step 4: Start & Test Server

### Start Server

```bash
# Terminal 1: Start server
python app.py
# Should see: "Uvicorn running on http://0.0.0.0:8000"
```

### Test API Endpoints

```bash
# Terminal 2: Test endpoints

# 1. Check server is running
curl http://localhost:8000/
# Expected: {"message":"Log Monitoring Service API","version":"1.0.0"}

# 2. List log files
curl http://localhost:8000/logs/list
# Expected: JSON array of files with sizes

# 3. Get last 5 log entries
curl "http://localhost:8000/logs?filename=log1.txt&entries=5"

# 4. Search for ERROR messages
curl "http://localhost:8000/logs?filename=log2.txt&keyword=ERROR"

# 5. Get nested directory logs
curl "http://localhost:8000/logs?filename=apache/log3.txt&entries=10"
```

## 🌐 Step 5: Test Web UI

1. Open browser: `http://localhost:8000/ui`
2. Click **"Scan File System"** → Should list all files
3. Click any log file → Should populate filename field
4. Set **Entry Limit**: 5
5. Add **Search Pattern**: ERROR
6. Click **"Execute Query"** → Should show filtered results

## 🔧 Optional: Test Distributed Architecture

```bash
# Start multiple instances
python app.py                    # Port 8000 (Terminal 1)
uvicorn app:app --port 8002      # Port 8002 (Terminal 2)
python primary_server.py         # Port 8001 (Terminal 3)

# Register servers with primary
curl -X POST http://localhost:8001/servers/register \
  -H "Content-Type: application/json" \
  -d '{"name":"server1","url":"http://localhost:8000"}'

# Aggregate logs from all servers
curl "http://localhost:8001/aggregate/logs?filename=log1.txt&entries=20"
```

## 🐛 Troubleshooting

| Issue                  | Solution                                          |
| ---------------------- | ------------------------------------------------- |
| `ModuleNotFoundError`  | Activate venv: `source venv/bin/activate`         |
| `Permission denied`    | Make executable: `chmod +x venv/bin/activate`     |
| `Port already in use`  | Kill process: `lsof -i:8000` then `kill -9 <PID>` |
| `Pydantic build error` | Update: `pip install pydantic==2.10.6`            |
| Tests fail             | Check: `ls var/log/` (files exist?)               |

## ✅ Verification Checklist

- [ ] Virtual environment activated (see `(venv)` in prompt)
- [ ] All dependencies installed (`pip list | grep fastapi`)
- [ ] Test files exist (`ls -la var/log/`)
- [ ] Unit tests pass (`pytest test_api.py`)
- [ ] Server starts (`python app.py`)
- [ ] API responds (`curl http://localhost:8000/`)
- [ ] UI loads (`http://localhost:8000/ui`)

## 📊 Performance Test (Optional)

```bash
# Create 100MB test file
for i in {1..1000000}; do
  echo "2024-01-15 10:00:00 INFO Test message $i" >> var/log/big.txt
done

# Test performance
time curl "http://localhost:8000/logs?filename=big.txt&entries=100"
# Should complete in < 1 second

# Load test (requires Apache Bench)
ab -n 100 -c 10 "http://localhost:8000/logs?filename=log1.txt&entries=10"
```

## 🎯 Success Criteria

You're ready when:

1. ✅ All tests pass (20/20)
2. ✅ Server responds to API calls
3. ✅ UI displays and filters logs
4. ✅ Can handle 100MB+ files efficiently

## 📚 Next Steps

- API Documentation: `http://localhost:8000/docs`
- Modify UI: Edit `ui/index.html`
- Add features: See `README.md`
- Deploy: Dockerize and ship!
