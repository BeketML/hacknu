"""Routes for managing temporary context — organised into per-page sub-folders.

Each folder corresponds to a tldraw page identified by its page ID
(e.g. "page:abc123").  The frontend creates the folder on demand when the
user first opens a page.

Folder naming: tldraw IDs contain colons ("page:xyz") which are invalid on
some filesystems.  We sanitise by replacing ":" with "__".  The sanitised
name is used only for the on-disk folder; the API always accepts / returns
the original tldraw ID.
"""

from __future__ import annotations

import logging
import mimetypes
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context/temporary", tags=["temporary-context"])

ALLOWED_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".txt", ".md", ".pdf"}
)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

# Accept tldraw page IDs like "page:abc123" or legacy "board-N" names.
_VALID_ID_RE = re.compile(r"^[\w:.-]{1,128}$")


# ── helpers ───────────────────────────────────────────────────────────────────

def _temp_dir() -> Path:
    d = get_settings().temporary_context_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitise(board_id: str) -> str:
    """Convert a tldraw page ID to a safe folder name (replace ':' with '__')."""
    return board_id.replace(":", "__")


def _desanitise(folder_name: str) -> str:
    """Reverse _sanitise — convert a folder name back to a tldraw page ID."""
    return folder_name.replace("__", ":")


def _validate_id(board_id: str) -> None:
    if not _VALID_ID_RE.match(board_id) or ".." in board_id:
        raise HTTPException(status_code=400, detail="Invalid board_id")


def _board_dir(board_id: str, *, must_exist: bool = True) -> Path:
    """Return the on-disk folder path for a given page ID."""
    _validate_id(board_id)
    folder = _sanitise(board_id)
    p = (_temp_dir() / folder).resolve()
    try:
        p.relative_to(_temp_dir().resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid board_id")
    if must_exist and not p.is_dir():
        raise HTTPException(status_code=404, detail=f"Context folder for '{board_id}' not found")
    return p


def _safe_file(board_id: str, filename: str) -> Path:
    board = _board_dir(board_id)
    p = (board / filename).resolve()
    try:
        p.relative_to(board)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return p


def _file_info(p: Path) -> dict:
    stat = p.stat()
    mime, _ = mimetypes.guess_type(p.name)
    return {
        "name": p.name,
        "size": stat.st_size,
        "mime": mime or "application/octet-stream",
        "is_image": p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"},
        "modified": stat.st_mtime,
    }


def _board_info(p: Path) -> dict:
    files = [
        _file_info(f)
        for f in sorted(p.iterdir())
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    return {"board_id": _desanitise(p.name), "file_count": len(files)}


# ── board endpoints ───────────────────────────────────────────────────────────

@router.get("/boards")
def list_boards() -> JSONResponse:
    """List all context folders."""
    boards = sorted(
        [_board_info(p) for p in _temp_dir().iterdir() if p.is_dir()],
        key=lambda b: b["board_id"],
    )
    return JSONResponse({"boards": boards})


@router.post("/boards")
def create_board(board_id: str = Body(..., embed=True)) -> JSONResponse:
    """Ensure a context folder exists for the given page ID."""
    _validate_id(board_id)
    board_path = _board_dir(board_id, must_exist=False)
    existed = board_path.is_dir()
    board_path.mkdir(parents=True, exist_ok=True)
    logger.info("%s folder for board: %s", "Ensured" if existed else "Created", board_id)
    return JSONResponse({"board_id": board_id, "file_count": 0}, status_code=200 if existed else 201)


@router.delete("/boards/{board_id}")
def delete_board(board_id: str) -> JSONResponse:
    """Delete a board and all its files."""
    board = _board_dir(board_id)
    shutil.rmtree(board)
    logger.info("Deleted board: %s", board_id)
    return JSONResponse({"message": "deleted", "board_id": board_id})


# ── file endpoints ────────────────────────────────────────────────────────────

@router.get("/boards/{board_id}/files")
def list_files(board_id: str) -> JSONResponse:
    """List files inside a board."""
    board = _board_dir(board_id)
    files = [
        _file_info(p)
        for p in sorted(board.iterdir())
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    return JSONResponse({"files": files})


@router.post("/boards/{board_id}/files")
async def upload_file(board_id: str, file: UploadFile) -> JSONResponse:
    """Upload a file into a board."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"File type '{suffix}' not allowed")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    board = _board_dir(board_id)
    safe_name = Path(file.filename).name
    dest = board / safe_name
    dest.write_bytes(data)
    logger.info("Uploaded %s → %s (%d bytes)", safe_name, board_id, len(data))
    return JSONResponse({"message": "uploaded", "file": _file_info(dest)}, status_code=201)


@router.delete("/boards/{board_id}/files/{filename}")
def delete_file(board_id: str, filename: str) -> JSONResponse:
    """Delete a single file from a board."""
    p = _safe_file(board_id, filename)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    p.unlink()
    logger.info("Deleted %s from %s", filename, board_id)
    return JSONResponse({"message": "deleted", "name": filename})


@router.delete("/boards/{board_id}/files")
def clear_board_files(board_id: str) -> JSONResponse:
    """Delete all files in a board (keep the folder)."""
    board = _board_dir(board_id)
    deleted = []
    for p in board.iterdir():
        if p.is_file():
            p.unlink()
            deleted.append(p.name)
    logger.info("Cleared %s (%d files)", board_id, len(deleted))
    return JSONResponse({"message": "cleared", "deleted": deleted})


@router.get("/boards/{board_id}/files/{filename}")
def get_file(board_id: str, filename: str) -> FileResponse:
    """Serve a file from a board."""
    p = _safe_file(board_id, filename)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(p.name)
    return FileResponse(p, media_type=mime or "application/octet-stream", filename=p.name)
