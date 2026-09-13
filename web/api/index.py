"""Vercel API: persistent uploaded recordings and share links."""
from pathlib import Path
from fastapi import FastAPI
from server.shared_uploads import create_upload_router
app = FastAPI(title="Tactile shared recordings")
app.include_router(create_upload_router(Path("/tmp/tactile-uploads")))
