import os
import logging
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

def get_streamable_http_mcp_client() -> MCPClient | None:
    """Return an optional MCP client when RAMS_MCP_ENDPOINT is explicitly configured."""
    endpoint = os.getenv("RAMS_MCP_ENDPOINT")
    if not endpoint:
        return None
    return MCPClient(lambda: streamablehttp_client(endpoint))
