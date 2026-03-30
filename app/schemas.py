from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Message(BaseModel):
    """通用訊息回應格式。"""

    message: str


class UserCreate(BaseModel):
    """使用者註冊請求資料。"""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class UserLogin(BaseModel):
    """使用者登入請求資料。"""

    username: str
    password: str


class TokenOut(BaseModel):
    """登入成功後回傳的 Token 資料。"""

    access_token: str
    token_type: str = "bearer"


class PostCreate(BaseModel):
    """建立貼文請求資料。"""

    content: str = Field(min_length=1, max_length=5000)


class PostOut(BaseModel):
    """貼文回應資料。"""

    id: int
    owner_id: int
    content: str
    top_comment_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    """建立留言請求資料，可指定父留言形成巢狀結構。"""

    content: str = Field(min_length=1, max_length=5000)
    parent_comment_id: int | None = None


class ReplyCreate(BaseModel):
    """回覆留言請求資料。"""

    content: str = Field(min_length=1, max_length=5000)


class CommentTreeOut(BaseModel):
    """留言樹狀回應資料，包含子回覆。"""

    id: int
    post_id: int
    owner_id: int
    parent_comment_id: int | None
    content: str
    created_at: datetime
    like_count: int = 0
    replies: list["CommentTreeOut"] = []


class TopCommentUpdate(BaseModel):
    """設定置頂留言請求資料。"""

    comment_id: int


class BlackListOut(BaseModel):
    """黑名單關聯回應資料。"""

    blocker_id: int
    blocked_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
