import copy
import json
import os
import random
import time
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(os.getenv("ARTICLE_DATA_DIR", Path(__file__).resolve().parents[2]))
CONFIG_PATH = ROOT / "config.json"
ARTICLES_PATH = ROOT / "articles.json"
COOKIES_PATH = ROOT / "cookies_store.json"

app = FastAPI(title="Article Publisher API")
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class CookieInput(BaseModel):
    name: str = Field(min_length=1)
    cookie: str = Field(min_length=1)


class PublishRequest(BaseModel):
    indexes: list[int]
    cookie_name: str
    min_interval: float = Field(default=10, ge=0)
    max_interval: float = Field(default=15, ge=0)


class DataImport(BaseModel):
    articles: list[dict]
    cookies: list[CookieInput]


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def config() -> dict:
    value = read_json(CONFIG_PATH, {})
    value.pop("cookie", None)
    return value


def cookies() -> list[dict]:
    return read_json(COOKIES_PATH, [])


def cookie_for(name: str) -> str:
    for item in cookies():
        if item.get("name") == name:
            return item.get("cookie", "")
    raise HTTPException(status_code=404, detail="Cookie 账号不存在")


def image_objects(payload: Any) -> list[dict]:
    result = []
    if isinstance(payload, dict):
        url = payload.get("url") or payload.get("ResourceURL")
        preview = payload.get("preview_url") or payload.get("LiteResourceURL") or url
        if isinstance(url, str) and url.startswith("URLs://"):
            url = "https://" + url[7:]
        if isinstance(preview, str) and preview.startswith("URLs://"):
            preview = "https://" + preview[7:]
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            item = copy.deepcopy(payload)
            item.update({"url": url, "preview_url": preview, "id": payload.get("ResourceID", payload.get("id", ""))})
            item.setdefault("width", 280)
            item.setdefault("height", 210)
            result.append(item)
        for value in payload.values():
            result.extend(image_objects(value))
    elif isinstance(payload, list):
        for value in payload:
            result.extend(image_objects(value))
    unique = {}
    for item in result:
        key = item.get("id") or item["url"].split("?", 1)[0]
        unique.setdefault(key, item)
    return list(unique.values())


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {
        "name": "Article Publisher API",
        "ok": True,
        "message": "后端运行正常，请打开前端地址 http://127.0.0.1:5173",
        "docs": "/docs",
    }


@app.get("/api/articles")
def get_articles():
    return read_json(ARTICLES_PATH, [])


@app.put("/api/articles")
def put_articles(articles: list[dict]):
    write_json(ARTICLES_PATH, articles)
    return {"ok": True}


@app.get("/api/cookies")
def get_cookies():
    return [{"name": item.get("name", "")} for item in cookies()]


@app.post("/api/cookies")
def add_cookie(item: CookieInput):
    items = cookies()
    items = [old for old in items if old.get("name") != item.name]
    items.append(item.model_dump())
    write_json(COOKIES_PATH, items)
    return {"ok": True}


@app.put("/api/cookies/{name}")
def update_cookie(name: str, item: CookieInput):
    items = cookies()
    if not any(old.get("name") == name for old in items):
        raise HTTPException(status_code=404, detail="Cookie 账号不存在")
    updated = [{"name": item.name, "cookie": item.cookie} if old.get("name") == name else old for old in items]
    write_json(COOKIES_PATH, updated)
    return {"ok": True}


@app.delete("/api/cookies/{name}")
def delete_cookie(name: str):
    write_json(COOKIES_PATH, [item for item in cookies() if item.get("name") != name])
    return {"ok": True}


@app.post("/api/admin/import")
def import_data(data: DataImport, x_admin_token: str | None = Header(default=None)):
    expected_token = os.getenv("ADMIN_TOKEN", "")
    if not expected_token or x_admin_token != expected_token:
        raise HTTPException(status_code=401, detail="管理员令牌无效")
    write_json(ARTICLES_PATH, data.articles)
    write_json(COOKIES_PATH, [item.model_dump() for item in data.cookies])
    return {"ok": True, "articles": len(data.articles), "cookies": len(data.cookies)}


@app.get("/api/media")
def media(cookie_name: str, page: int = 1, page_size: int = 100):
    headers = config().get("headers", {}).copy()
    headers.update({"Cookie": cookie_for(cookie_name), "Referer": "https://www.autoengine.com/jdc/dealer/info/Article"})
    response = requests.get("https://www.autoengine.com/motor/dealer_admin/article/get_media_source_new", params={"resource_type": 3, "is_saved": 0, "page_index": page, "page_size": min(page_size, 100)}, headers=headers, timeout=30)
    response.raise_for_status()
    return {"images": image_objects(response.json())}


@app.post("/api/publish")
def publish(request: PublishRequest):
    if request.min_interval > request.max_interval:
        raise HTTPException(status_code=400, detail="最小间隔不能大于最大间隔")
    articles = read_json(ARTICLES_PATH, [])
    selected_cookie = cookie_for(request.cookie_name)
    results = []
    headers = config().get("headers", {}).copy()
    headers["Cookie"] = selected_cookie
    for position, index in enumerate(request.indexes):
        if index < 0 or index >= len(articles):
            results.append({"index": index, "success": False, "error": "稿件索引不存在"})
            continue
        result = {"index": index, "title": articles[index].get("title", ""), "success": False}
        for attempt in range(1, 4):
            try:
                response = requests.post(config()["base_url"], headers=headers, json=articles[index], timeout=30)
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                business_status = body.get("status")
                failed = response.status_code >= 400 or (isinstance(business_status, (int, float)) and business_status >= 400)
                result.update({"success": not failed, "status_code": response.status_code, "business_status": business_status, "response": body, "attempt": attempt})
                if not failed or attempt == 3:
                    break
            except requests.RequestException as error:
                result.update({"error": str(error), "attempt": attempt})
                if attempt == 3:
                    break
        results.append(result)
        if position < len(request.indexes) - 1:
            time.sleep(random.uniform(request.min_interval, request.max_interval))
    return {"results": results}
