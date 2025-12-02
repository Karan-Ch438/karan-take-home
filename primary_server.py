"""
Primary Server for Multi-Server Log Monitoring
This server can aggregate logs from multiple secondary servers
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="Primary Log Monitoring Server",
    description="Aggregates logs from multiple secondary servers",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecondaryServer(BaseModel):
    """Configuration for a secondary server"""
    name: str = Field(..., description="Server name/identifier")
    url: str = Field(..., description="Base URL of the secondary server")
    description: Optional[str] = Field(None, description="Server description")


class ServerRegistry(BaseModel):
    """Registry of secondary servers"""
    servers: List[SecondaryServer] = Field(default_factory=list)


class AggregatedLogEntry(BaseModel):
    """Log entry with server information"""
    server: str
    timestamp: Optional[str]
    content: str
    level: Optional[str]  # INFO, WARNING, ERROR, etc.


class AggregatedLogResponse(BaseModel):
    """Response for aggregated logs"""
    total_servers: int
    servers_queried: List[str]
    total_entries: int
    entries: List[Dict]


# In-memory registry of secondary servers
server_registry = ServerRegistry()


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Primary Log Monitoring Server",
        "version": "1.0.0",
        "endpoints": {
            "/servers": "Manage secondary servers",
            "/servers/register": "Register a new secondary server",
            "/servers/list": "List registered servers",
            "/aggregate/logs": "Fetch logs from multiple servers",
            "/aggregate/search": "Search logs across all servers",
            "/docs": "API documentation"
        }
    }


@app.post("/servers/register")
async def register_server(server: SecondaryServer):
    """Register a new secondary server"""
    # Check if server already exists
    for existing in server_registry.servers:
        if existing.name == server.name:
            raise HTTPException(status_code=400, detail=f"Server '{server.name}' already registered")

    # Validate server is reachable
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{server.url}/health", timeout=5) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail=f"Server health check failed: {response.status}")
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=400, detail=f"Cannot reach server: {str(e)}")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=400, detail="Server health check timed out")

    server_registry.servers.append(server)
    return {"message": f"Server '{server.name}' registered successfully", "total_servers": len(server_registry.servers)}


@app.delete("/servers/{server_name}")
async def unregister_server(server_name: str):
    """Remove a secondary server from the registry"""
    for i, server in enumerate(server_registry.servers):
        if server.name == server_name:
            server_registry.servers.pop(i)
            return {"message": f"Server '{server_name}' unregistered successfully"}

    raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")


@app.get("/servers/list")
async def list_servers():
    """List all registered secondary servers"""
    return {
        "total_servers": len(server_registry.servers),
        "servers": [
            {
                "name": s.name,
                "url": s.url,
                "description": s.description
            }
            for s in server_registry.servers
        ]
    }


@app.get("/servers/{server_name}/files")
async def list_server_files(server_name: str):
    """List available log files on a specific server"""
    server = None
    for s in server_registry.servers:
        if s.name == server_name:
            server = s
            break

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{server.url}/logs/list", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "server": server_name,
                        "files": data.get("files", [])
                    }
                else:
                    raise HTTPException(status_code=response.status, detail=f"Failed to fetch files from {server_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching files from {server_name}: {str(e)}")


async def fetch_logs_from_server(
    session: aiohttp.ClientSession,
    server: SecondaryServer,
    filename: str,
    entries: int,
    keyword: Optional[str]
) -> Dict:
    """Fetch logs from a single secondary server"""
    try:
        params = {
            "filename": filename,
            "entries": entries
        }
        if keyword:
            params["keyword"] = keyword

        async with session.get(
            f"{server.url}/logs",
            params=params,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    "server": server.name,
                    "status": "success",
                    "entries": data.get("entries", []),
                    "count": data.get("returned_lines", 0)
                }
            else:
                return {
                    "server": server.name,
                    "status": "error",
                    "error": f"HTTP {response.status}",
                    "entries": [],
                    "count": 0
                }
    except asyncio.TimeoutError:
        return {
            "server": server.name,
            "status": "timeout",
            "error": "Request timed out",
            "entries": [],
            "count": 0
        }
    except Exception as e:
        return {
            "server": server.name,
            "status": "error",
            "error": str(e),
            "entries": [],
            "count": 0
        }


@app.get("/aggregate/logs")
async def aggregate_logs(
    filename: str = Query(..., description="Log filename to fetch from all servers"),
    entries: int = Query(50, ge=1, le=1000, description="Number of entries per server"),
    keyword: Optional[str] = Query(None, description="Keyword to filter"),
    servers: Optional[str] = Query(None, description="Comma-separated list of server names to query")
):
    """
    Aggregate logs from multiple secondary servers

    - **filename**: Log file to fetch from each server
    - **entries**: Max entries to fetch from each server
    - **keyword**: Optional filter keyword
    - **servers**: Comma-separated list of specific servers to query (queries all if not specified)
    """

    if len(server_registry.servers) == 0:
        raise HTTPException(status_code=400, detail="No secondary servers registered")

    # Determine which servers to query
    servers_to_query = server_registry.servers
    if servers:
        server_names = [s.strip() for s in servers.split(",")]
        servers_to_query = [s for s in server_registry.servers if s.name in server_names]

        if not servers_to_query:
            raise HTTPException(status_code=404, detail=f"None of the specified servers found: {servers}")

    # Fetch logs from all servers in parallel
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_logs_from_server(session, server, filename, entries, keyword)
            for server in servers_to_query
        ]
        results = await asyncio.gather(*tasks)

    # Aggregate results
    all_entries = []
    servers_queried = []

    for result in results:
        servers_queried.append({
            "name": result["server"],
            "status": result["status"],
            "entries_returned": result["count"],
            "error": result.get("error")
        })

        for entry in result["entries"]:
            all_entries.append({
                "server": result["server"],
                "content": entry
            })

    # Sort entries by content (assuming timestamp is at the beginning)
    all_entries.sort(key=lambda x: x["content"], reverse=True)

    return {
        "total_servers": len(servers_to_query),
        "servers_queried": servers_queried,
        "total_entries": len(all_entries),
        "keyword": keyword,
        "entries": all_entries[:entries]  # Limit total entries
    }


@app.get("/aggregate/search")
async def search_logs(
    keyword: str = Query(..., description="Keyword to search for"),
    entries: int = Query(50, ge=1, le=1000, description="Max entries per server"),
    servers: Optional[str] = Query(None, description="Comma-separated list of server names")
):
    """
    Search for a keyword across all registered servers
    """

    if len(server_registry.servers) == 0:
        raise HTTPException(status_code=400, detail="No secondary servers registered")

    # Determine which servers to query
    servers_to_query = server_registry.servers
    if servers:
        server_names = [s.strip() for s in servers.split(",")]
        servers_to_query = [s for s in server_registry.servers if s.name in server_names]

    all_results = []

    async with aiohttp.ClientSession() as session:
        # First, get file lists from all servers
        file_tasks = []
        for server in servers_to_query:
            async def get_files(srv):
                try:
                    async with session.get(f"{srv.url}/logs/list", timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {"server": srv, "files": data.get("files", [])}
                        return {"server": srv, "files": []}
                except:
                    return {"server": srv, "files": []}

            file_tasks.append(get_files(server))

        file_results = await asyncio.gather(*file_tasks)

        # Now search in all files
        search_tasks = []
        for file_result in file_results:
            server = file_result["server"]
            for file_info in file_result["files"][:5]:  # Limit to first 5 files per server
                filename = file_info["filename"]
                search_tasks.append(
                    fetch_logs_from_server(session, server, filename, entries, keyword)
                )

        search_results = await asyncio.gather(*search_tasks)

    # Aggregate search results
    for result in search_results:
        if result["count"] > 0:
            for entry in result["entries"]:
                all_results.append({
                    "server": result["server"],
                    "content": entry,
                    "matches": entry.lower().count(keyword.lower())
                })

    # Sort by number of matches
    all_results.sort(key=lambda x: x["matches"], reverse=True)

    return {
        "keyword": keyword,
        "total_matches": len(all_results),
        "results": all_results[:entries]
    }


@app.get("/health")
async def health_check():
    """Health check for primary server"""
    # Also check health of secondary servers
    server_health = []

    async with aiohttp.ClientSession() as session:
        for server in server_registry.servers:
            try:
                async with session.get(f"{server.url}/health", timeout=5) as response:
                    server_health.append({
                        "name": server.name,
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "response_time": response.headers.get("X-Response-Time", "N/A")
                    })
            except:
                server_health.append({
                    "name": server.name,
                    "status": "unreachable",
                    "response_time": "N/A"
                })

    return {
        "status": "healthy",
        "service": "primary-log-monitor",
        "registered_servers": len(server_registry.servers),
        "server_health": server_health
    }


if __name__ == "__main__":
    print("Starting Primary Log Monitoring Server...")
    print("This server aggregates logs from multiple secondary servers")
    print("API documentation: http://localhost:8001/docs")

    uvicorn.run(
        "primary_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
