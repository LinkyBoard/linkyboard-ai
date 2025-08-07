from typing import Union

from fastapi import FastAPI
from app.collect.v1.clipper.router import router as clipper_router

app = FastAPI(
    title="LinkyBoard AI API",
    description="링키보드 AI 서비스의 공식 문서",
    version="0.1.0",
    contact={"name": "Wonjun", "url": "https://github.com/wonjun0120"}
)

# Clipper
app.include_router(clipper_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}
