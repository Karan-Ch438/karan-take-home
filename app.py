"""
Log Monitoring Service API
A REST API for fetching and monitoring log files from /var/log directory
"""

import os
import mmap
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="Log Monitoring Service",
    description="REST API for fetching and monitoring Unix server logs",
    version="1.0.0"
)

# Add CORS middleware for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_LOG_DIR = Path("./var/log")  # Using relative path for development
CHUNK_SIZE = 8192  # 8KB chunks for reading
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB max file size


class LogResponse(BaseModel):
    """Response model for log entries"""
    filename: str
    total_lines: int
    returned_lines: int
    filtered: bool
    entries: List[str]


def read_last_n_lines_efficient(filepath: Path, n: int = 100, keyword: Optional[str] = None) -> List[str]:
    """
    Efficiently read the last n lines from a file, even for very large files.
    Uses memory-mapped files and reads from the end for optimal performance.

    Args:
        filepath: Path to the log file
        n: Number of lines to read
        keyword: Optional keyword to filter lines

    Returns:
        List of log lines (newest first)
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Log file not found: {filepath}")

    file_size = filepath.stat().st_size

    if file_size == 0:
        return []

    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE} bytes)")

    lines = []

    # For small files, just read normally
    if file_size < CHUNK_SIZE * 10:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            if keyword:
                all_lines = [line for line in all_lines if keyword.lower() in line.lower()]
            return all_lines[-n:][::-1]  # Return last n lines, reversed

    # For large files, use memory-mapped file for efficiency
    with open(filepath, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
            # Start from the end of the file
            position = file_size
            buffer = b''
            lines_found = 0

            while position > 0 and lines_found < n * 2:  # Read extra lines for filtering
                # Determine chunk size
                chunk_size = min(CHUNK_SIZE, position)
                position -= chunk_size

                # Read chunk
                mmapped_file.seek(position)
                chunk = mmapped_file.read(chunk_size)

                # Prepend to buffer
                buffer = chunk + buffer

                # Find lines in buffer
                while b'\n' in buffer:
                    line_end = buffer.rfind(b'\n')
                    if line_end != -1:
                        line = buffer[line_end + 1:]
                        buffer = buffer[:line_end]

                        if line:
                            try:
                                decoded_line = line.decode('utf-8', errors='ignore').strip()
                                if decoded_line:
                                    if keyword is None or keyword.lower() in decoded_line.lower():
                                        lines.append(decoded_line)
                                        lines_found += 1
                                        if lines_found >= n:
                                            return lines
                            except Exception:
                                pass  # Skip lines that can't be decoded

            # Handle remaining buffer
            if buffer and lines_found < n:
                try:
                    decoded_line = buffer.decode('utf-8', errors='ignore').strip()
                    if decoded_line:
                        if keyword is None or keyword.lower() in decoded_line.lower():
                            lines.append(decoded_line)
                except Exception:
                    pass

    return lines[:n]


def read_last_n_lines_streaming(filepath: Path, n: int = 100, keyword: Optional[str] = None):
    """
    Generator version for streaming large results
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Log file not found: {filepath}")

    file_size = filepath.stat().st_size
    if file_size == 0:
        return

    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE} bytes)")

    lines_yielded = 0

    with open(filepath, 'rb') as f:
        # Seek to end of file
        f.seek(0, 2)
        position = f.tell()
        buffer = []

        while position > 0 and lines_yielded < n:
            # Read in chunks from the end
            chunk_size = min(CHUNK_SIZE, position)
            position -= chunk_size
            f.seek(position)
            chunk = f.read(chunk_size)

            # Process chunk line by line
            lines = chunk.split(b'\n')

            if buffer:
                lines[-1] += buffer.pop(0)

            buffer = lines[::-1] + buffer

            while len(buffer) > 1 and lines_yielded < n:
                line = buffer.pop(0)
                if line:
                    try:
                        decoded = line.decode('utf-8', errors='ignore').strip()
                        if decoded and (keyword is None or keyword.lower() in decoded.lower()):
                            yield decoded
                            lines_yielded += 1
                    except:
                        pass


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Log Monitoring Service",
        "version": "1.0.0",
        "endpoints": {
            "/logs": "Fetch log entries",
            "/logs/list": "List available log files",
            "/docs": "API documentation (Swagger UI)",
            "/redoc": "API documentation (ReDoc)"
        }
    }


@app.get("/logs", response_model=LogResponse)
async def get_logs(
    filename: str = Query(..., description="Path to log file relative to /var/log (e.g., 'log1.txt' or 'apache/log3.txt')"),
    entries: int = Query(100, ge=1, le=10000, description="Number of latest entries to return"),
    keyword: Optional[str] = Query(None, description="Keyword to filter log entries")
):
    """
    Fetch log entries from a specified file.

    - **filename**: Path to the log file relative to /var/log
    - **entries**: Number of latest entries to return (1-10000, default: 100)
    - **keyword**: Optional keyword to filter entries (case-insensitive)

    Returns the newest entries first.
    """

    # Sanitize filename to prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Construct full path
    log_path = BASE_LOG_DIR / filename

    # Check if file exists
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Log file not found: {filename}")

    if not log_path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {filename}")

    try:
        # Read log entries efficiently
        log_entries = read_last_n_lines_efficient(log_path, entries, keyword)

        return LogResponse(
            filename=filename,
            total_lines=-1,  # Not counting all lines for performance
            returned_lines=len(log_entries),
            filtered=keyword is not None,
            entries=log_entries
        )

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")


@app.get("/logs/list")
async def list_logs(directory: Optional[str] = Query(None, description="Subdirectory within /var/log")):
    """
    List available log files in /var/log or a subdirectory.

    - **directory**: Optional subdirectory path (e.g., 'apache')
    """

    # Determine base directory
    if directory:
        if ".." in directory or directory.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid directory")
        search_dir = BASE_LOG_DIR / directory
    else:
        search_dir = BASE_LOG_DIR

    if not search_dir.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory or 'var/log'}")

    # Find all log files recursively
    log_files = []
    for path in search_dir.rglob("*"):
        if path.is_file():
            # Get relative path from BASE_LOG_DIR
            relative_path = path.relative_to(BASE_LOG_DIR)
            file_size = path.stat().st_size
            log_files.append({
                "filename": str(relative_path),
                "size_bytes": file_size,
                "size_readable": format_bytes(file_size)
            })

    return {
        "directory": directory or "var/log",
        "total_files": len(log_files),
        "files": sorted(log_files, key=lambda x: x["filename"])
    }


@app.get("/logs/stream")
async def stream_logs(
    filename: str = Query(..., description="Path to log file relative to /var/log"),
    entries: int = Query(100, ge=1, le=10000, description="Number of latest entries to return"),
    keyword: Optional[str] = Query(None, description="Keyword to filter log entries")
):
    """
    Stream log entries for very large files.
    Returns a JSON stream of log entries.
    """

    # Sanitize filename
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    log_path = BASE_LOG_DIR / filename

    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Log file not found: {filename}")

    try:
        from fastapi.responses import StreamingResponse
        import json

        def generate():
            yield '{"entries": ['
            first = True
            for line in read_last_n_lines_streaming(log_path, entries, keyword):
                if not first:
                    yield ','
                yield json.dumps(line)
                first = False
            yield ']}'

        return StreamingResponse(generate(), media_type="application/json")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error streaming log file: {str(e)}")


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string"""
    value = float(bytes_value)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if value < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TB"


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "log-monitoring"}


# Serve UI
@app.get("/ui")
async def serve_ui():
    """Serve the web UI"""
    ui_path = Path("./ui/index.html")
    if ui_path.exists():
        return FileResponse(ui_path)
    else:
        raise HTTPException(status_code=404, detail="UI file not found")


if __name__ == "__main__":
    # Run the server
    print("Starting Log Monitoring Service...")
    print(f"Base log directory: {BASE_LOG_DIR.absolute()}")
    print("API documentation available at: http://localhost:8000/docs")
    print("Interactive UI available at: http://localhost:8000/ui (if implemented)")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
