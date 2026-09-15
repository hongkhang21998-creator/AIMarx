"""Read-only, stdio MCP surface; cannot approve or access arbitrary paths."""
import os
from fastmcp import FastMCP
from .service import Service


def create_mcp(service):
    mcp = FastMCP("Trợ lý văn bản — read only")

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

    @mcp.tool
    def ask_aimarx(message: str, model_id: str | None = None) -> dict:
        """Ask an enabled local model. Cloud models require confirmation in the local UI."""
        return service.aimarx.ask(message, model_id)

    @mcp.tool
    def list_models() -> list[dict]:
        """List public model metadata; credentials are never returned."""
        return service.aimarx.list_models()

    @mcp.tool
    def get_usage(period: str = "7d") -> dict:
        """Return local token accounting for today, 7d, 30d, or all."""
        return service.aimarx.usage(period)

    return mcp


def main():
    create_mcp(Service(os.getenv("TLVB_DATA", "data"), required_mount=os.getenv("TLVB_REQUIRED_MOUNT"))).run(transport="stdio")


if __name__ == "__main__":
    main()
