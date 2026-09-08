"""Read-only, stdio MCP surface; cannot approve or access arbitrary paths."""
import os
from fastmcp import FastMCP
from .service import Service


def create_mcp(service):
    mcp = FastMCP("Trợ lý văn bản — read only")

    @mcp.tool
    def list_documents() -> list[dict]:
        """List registered documents, at most 100."""
        return service.listing()[:100]

    @mcp.tool
    def read_document(document_id: str) -> dict:
        """Read source blocks and parser warnings for a registered document ID."""
        doc = service.get(document_id)
        return {k: doc[k] for k in ("id", "name", "blocks", "warnings", "state")}

    @mcp.tool
    def get_evidence(document_id: str, block_ids: list[str]) -> list[dict]:
        """Return at most 20 source blocks, constrained to one registered document."""
        if len(block_ids) > 20:
            raise ValueError("Tối đa 20 đoạn")
        blocks = {b["id"]: b for b in service.get(document_id)["blocks"]}
        if any(x not in blocks for x in block_ids):
            raise ValueError("Đoạn nguồn không tồn tại")
        return [blocks[x] for x in block_ids]

    return mcp


def main():
    create_mcp(Service(os.getenv("TLVB_DATA", "data"))).run(transport="stdio")
