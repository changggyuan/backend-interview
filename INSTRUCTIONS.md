# Backend Interview API

使用 Python 3.12 + FastAPI + async SQLAlchemy (SQLite) 實作簡易社群平台後端。

## 專案目標

此專案實作以下核心需求：

- 使用者系統：註冊、登入
- 發文功能：登入後可建立貼文，所有使用者可瀏覽（黑名單限制除外）
- 互動功能：貼文按讚、留言、巢狀留言、留言按讚
- 置頂留言：貼文擁有者可設定置頂留言
- 黑名單：被封鎖者無法看到封鎖者貼文，也無法對封鎖者的貼文或留言互動

## 技術棧

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x Async
- SQLite (aiosqlite)

## 專案結構

- app/main.py：API 路由與主要業務邏輯
- app/models.py：資料表模型
- app/schemas.py：請求/回應資料結構
- app/database.py：資料庫連線與初始化
- app/security.py：密碼雜湊與 Token 工具

## 快速開始

### 1) 安裝依賴

使用 Poetry：

poetry install

或使用現有 venv：

.venv\Scripts\python.exe -m pip install fastapi uvicorn sqlalchemy aiosqlite

### 2) 啟動 Server

使用 Poetry：

poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

使用 venv Python：

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

### 3) API 文件

- Swagger UI：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc

## 驗證流程（建議）

1. 先註冊
2. 再登入取得 access_token
3. 在 Swagger 右上角 Authorize 貼上 token 值（只貼 token，不需加 Bearer）
4. 測試發文、留言、按讚、黑名單

## 授權說明

需要登入的 API 需帶 Header：

Authorization: Bearer <access_token>

注意：

- /auth/login 本身不需要 token
- 目前 token 無過期時間（資料庫有記錄即有效）

## API 清單

### Auth

- POST /auth/register
- POST /auth/login

### Posts

- POST /posts
- GET /posts
- GET /posts/{post_id}
- POST /posts/{post_id}/likes
- DELETE /posts/{post_id}/likes
- PATCH /posts/{post_id}/top-comment

### Comments

- POST /posts/{post_id}/comments
- POST /comments/{comment_id}/replies
- GET /posts/{post_id}/comments
- PATCH /comments/{comment_id}
- POST /comments/{comment_id}/likes
- DELETE /comments/{comment_id}/likes

### Blacklist

- POST /blacklist/{blocked_user_id}
- DELETE /blacklist/{blocked_user_id}
- GET /blacklist/me

## 重要行為規則

- 第一次留言時，parent_comment_id 可省略或填 null
- 回覆留言時，parent_comment_id 必須是同一篇貼文中的留言 id
- 只有貼文擁有者可設定 top comment
- 只有留言擁有者可編輯自己的留言
- 不能把自己加入黑名單

## 資料庫

- 使用 SQLite，檔案位於專案根目錄 app.db
- 關閉/重啟 server 不會清空資料
- 若手動刪除 app.db，資料會重建且原資料遺失

## 已知限制

- token 為資料庫儲存型簡易 token，尚未實作過期與 refresh
- 未導入 migration 工具（如 Alembic）
