# Log Monitoring Service 🖥️

A high-performance REST API service for monitoring and fetching logs from Unix-based servers without direct login. Features efficient handling of large log files (>1GB) and a beautiful web UI.

## 🚀 Quick Start

**Starting from scratch?** See [**QUICK_START.md**](additional_documentation/QUICK_START.md) for complete setup and testing guide

## ✨ Features

- **REST API** for fetching log entries from `/var/log` directory
- **Efficient Large File Handling**: Optimized for files up to 3.5GB using memory-mapped files
- **Reverse Chronological Order**: Returns newest log entries first
- **Flexible Querying**:
  - Specify any file within `/var/log` including nested directories
  - Fetch last N entries
  - Filter by keywords (case-insensitive)
- **Web UI**: Beautiful, modern interface for interacting with the API
- **Primary-Secondary Architecture**: Aggregate logs from multiple servers (optional)
- **Comprehensive Test Suite**: Full test coverage with performance tests

## 🚀 Quick Start

### Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Service

1. **Start the main log monitoring server:**

```bash
python app.py
```

The server will start on `http://localhost:8000`

2. **Access the Web UI:**
   Open your browser and navigate to `http://localhost:8000/ui`

3. **API Documentation:**

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Running Tests

```bash
pytest test_api.py -v
```

## 📡 API Endpoints

### Core Endpoints

#### `GET /logs`

Fetch log entries from a specified file.

**Query Parameters:**

- `filename` (required): Path to log file relative to `/var/log` (e.g., `log1.txt`, `apache/log3.txt`)
- `entries` (optional, default=100): Number of latest entries to return (1-10000)
- `keyword` (optional): Filter entries containing this keyword

**Example:**

```bash
curl "http://localhost:8000/logs?filename=apache/log3.txt&entries=50&keyword=ERROR"
```

#### `GET /logs/list`

List available log files in `/var/log` or a subdirectory.

**Query Parameters:**

- `directory` (optional): Subdirectory within `/var/log`

**Example:**

```bash
curl "http://localhost:8000/logs/list?directory=apache"
```

#### `GET /logs/stream`

Stream log entries for very large files (returns JSON stream).

**Query Parameters:**
Same as `/logs` endpoint

### Additional Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `GET /ui` - Web interface

## 🎨 Web UI Features

The web UI provides:

- **File Browser**: Browse and select log files from available files
- **Live Preview**: View log entries with syntax highlighting
- **Filtering**: Search for specific keywords in logs
- **Statistics**: View metrics about returned logs
- **Responsive Design**: Works on desktop and mobile devices

### Using the Web UI

1. Open `http://localhost:8000/ui` in your browser
2. Click "Refresh File List" to load available log files
3. Select a file from the list or enter a path manually
4. Set the number of entries to fetch
5. (Optional) Add a keyword filter
6. Click "Fetch Logs" to view the entries

## 🔄 Primary-Secondary Server Architecture (Challenge)

For distributed log monitoring across multiple servers:

### Starting a Primary Server

```bash
python primary_server.py
```

The primary server runs on `http://localhost:8001`

### Registering Secondary Servers

```bash
# Register a secondary server
curl -X POST "http://localhost:8001/servers/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server1",
    "url": "http://localhost:8000",
    "description": "Main application server"
  }'
```

### Aggregating Logs from Multiple Servers

```bash
# Fetch logs from all registered servers
curl "http://localhost:8001/aggregate/logs?filename=log1.txt&entries=50"

# Search across all servers
curl "http://localhost:8001/aggregate/search?keyword=ERROR&entries=100"
```

## 🏗️ Project Structure

```
/Users/karanchatha/Desktop/fun-things/
├── var/
│   └── log/                 # Log files directory
│       ├── apache/
│       │   └── log3.txt     # Apache logs
│       ├── log1.txt         # System logs
│       └── log2.txt         # Application logs
├── ui/
│   └── index.html           # Web UI
├── app.py                   # Main FastAPI application
├── primary_server.py        # Primary server for aggregation
├── test_api.py             # Test suite
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 Configuration

### Environment Variables (Optional)

You can configure the following environment variables:

```bash
export LOG_BASE_DIR="/var/log"  # Base directory for logs
export MAX_FILE_SIZE="4294967296"  # Max file size in bytes (4GB)
export API_PORT="8000"  # API server port
```

## 🧪 Performance Considerations

### Large File Handling

The service uses several techniques for efficient large file processing:

1. **Memory-Mapped Files**: For files > 80KB, uses mmap for efficient random access
2. **Reverse Reading**: Reads from the end of file to quickly get latest entries
3. **Chunked Processing**: Processes files in 8KB chunks to minimize memory usage
4. **Streaming API**: Optional streaming endpoint for very large result sets

### Performance Benchmarks

- **1GB File**: < 500ms to fetch last 100 entries
- **3.5GB File**: < 2s to fetch last 100 entries
- **Keyword Search (1GB)**: < 3s for full file search

## 🔒 Security Features

- **Path Traversal Prevention**: Validates file paths to prevent directory traversal attacks
- **File Size Limits**: Enforces maximum file size (4GB default)
- **Input Validation**: Strict parameter validation using Pydantic
- **CORS Configuration**: Configurable CORS for secure cross-origin requests

## 📚 API Examples

### Python Client Example

```python
import requests

# Fetch logs
response = requests.get(
    "http://localhost:8000/logs",
    params={
        "filename": "apache/log3.txt",
        "entries": 100,
        "keyword": "ERROR"
    }
)

data = response.json()
print(f"Found {data['returned_lines']} entries")
for entry in data['entries']:
    print(entry)
```

### JavaScript Client Example

```javascript
async function fetchLogs() {
  const response = await fetch(
    "http://localhost:8000/logs?" +
      new URLSearchParams({
        filename: "log1.txt",
        entries: 50,
        keyword: "WARNING",
      })
  );

  const data = await response.json();
  console.log(`Found ${data.returned_lines} entries`);
  data.entries.forEach((entry) => console.log(entry));
}
```

## 🎯 Future Enhancements

- [ ] Real-time log streaming using WebSockets
- [ ] Log analysis and pattern detection
- [ ] Export logs to various formats (CSV, JSON, PDF)
- [ ] Authentication and authorization
- [ ] Log rotation handling
- [ ] Metrics and monitoring dashboard
- [ ] Docker containerization
- [ ] Kubernetes deployment manifests

## 📚 Additional Documentation

- [**QUICK_START.md**](QUICK_START.md) - Step-by-step setup and testing from scratch:
  - Environment setup with virtual environment
  - Creating test data
  - Running unit tests
  - Testing API endpoints
  - Using the web UI
  - Troubleshooting common issues
- [**TECHNICAL_README.md**](TECHNICAL_README.md) - Comprehensive technical documentation covering:
  - Detailed architecture diagrams
  - Performance optimization strategies
  - Security considerations
  - Design decision rationales
  - Benchmarks and metrics
  - Trade-offs and limitations
- [**ARCHITECTURE_DECISIONS.md**](ARCHITECTURE_DECISIONS.md) - Architecture Decision Records (ADRs):
  - Key design decisions with rationale
  - Trade-offs and alternatives considered
  - Performance benchmarks for each decision
  - Review schedule for decisions
