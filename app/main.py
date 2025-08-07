from typing import Union

from fastapi import FastAPI

app = FastAPI(
    title="LinkyBoard AI API",
    description="링키보드 AI 서비스의 공식 문서",
    version="0.1.0",
    contact={"name": "Wonjun", "url": "https://github.com/wonjun0120"}
)

@app.get("/")
def read_root():
    return {"Hello": "World"}
