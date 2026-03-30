from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_FK_USERS = "users.id"
_FK_POSTS = "posts.id"
_FK_COMMENTS = "comments.id"
_NOW = text("CURRENT_TIMESTAMP")


class User(Base):
    """平台使用者帳號資料。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class AuthToken(Base):
    """登入後發放並綁定使用者的存取 Token。"""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Post(Base):
    """使用者發佈的貼文。"""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text())
    top_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey(_FK_COMMENTS, ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW, index=True)


class Comment(Base):
    """貼文留言，支援巢狀回覆。"""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey(_FK_POSTS, ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    parent_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey(_FK_COMMENTS, ondelete="CASCADE"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW, index=True)


class PostLike(Base):
    """使用者與貼文的按讚關聯。"""

    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_post_like"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey(_FK_POSTS, ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class CommentLike(Base):
    """使用者與留言的按讚關聯。"""

    __tablename__ = "comment_likes"
    __table_args__ = (UniqueConstraint("user_id", "comment_id", name="uq_comment_like"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey(_FK_COMMENTS, ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class BlackList(Base):
    """黑名單關聯：封鎖者可限制被封鎖者的可見與互動。"""

    __tablename__ = "blacklists"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id", name="uq_blacklist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    blocker_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey(_FK_USERS, ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
