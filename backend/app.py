"""
车齿刀设计工具 — FastAPI 后端入口
Hello World 验证：提供 /api/hello 端点验证前后端通信
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="PowerSkivingTool API", version="0.1.0")

# CORS 配置——允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/hello")
async def hello() -> dict:
    """Hello World 端点——返回框架验证信息"""
    return {
        "message": "Hello from PowerSkivingTool Backend!",
        "status": "ok",
        "framework": "FastAPI",
        "version": "0.1.0",
        "python_version": "3.13+",
        "timestamp": "2026-08-05",
    }


@app.get("/api/health")
async def health() -> dict:
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5199, log_level="info")
