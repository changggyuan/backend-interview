from __future__ import annotations

from collections import defaultdict
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, init_db
from app.models import AuthToken, BlackList, Comment, CommentLike, Post, PostLike, User
from app.schemas import (
    BlackListOut,
    CommentCreate,
    CommentTreeOut,
    Message,
    PostCreate,
    PostOut,
    ReplyCreate,
    TokenOut,
    TopCommentUpdate,
    UserCreate,
    UserLogin,
)
from app.security import create_token, hash_password, verify_password

app = FastAPI(title="Backend Interview API", version="0.1.0")
auth_scheme = HTTPBearer()
auth_scheme_optional = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)]
OptionalCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(auth_scheme_optional)]

POST_NOT_FOUND = "Post not found"
COMMENT_NOT_FOUND = "Comment not found"


@app.on_event("startup")
async def on_startup() -> None:
    """應用啟動時初始化資料表。"""

    await init_db()


async def get_current_user(
    credentials: Credentials,
    db: DbSession,
) -> User:
    """依據 Bearer Token 取得目前登入使用者。"""

    token = credentials.credentials
    token_row = await db.scalar(select(AuthToken).where(AuthToken.token == token))
    if token_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user_optional(
    credentials: OptionalCredentials,
    db: DbSession,
) -> User | None:
    """可選登入驗證；未帶 token 時回傳 None。"""

    if credentials is None:
        return None

    token = credentials.credentials
    token_row = await db.scalar(select(AuthToken).where(AuthToken.token == token))
    if token_row is None:
        return None

    return await db.get(User, token_row.user_id)


async def ensure_not_blocked(owner_id: int, actor_id: int, db: AsyncSession) -> None:
    """檢查 actor 是否被 owner 加入黑名單。"""

    blocked = await db.scalar(
        select(BlackList).where(
            BlackList.blocker_id == owner_id,
            BlackList.blocked_id == actor_id,
        )
    )
    if blocked is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are in this user's blacklist")


@app.post("/auth/register")
async def register(payload: UserCreate, db: DbSession) -> Message:
    """註冊新使用者帳號。"""

    existing = await db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    return Message(message="User registered")


@app.post("/auth/login")
async def login(payload: UserLogin, db: DbSession) -> TokenOut:
    """使用者登入並發放存取 Token。"""

    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_token()
    db.add(AuthToken(token=token, user_id=user.id))
    await db.commit()
    return TokenOut(access_token=token)


@app.post("/posts")
async def create_post(
    payload: PostCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> PostOut:
    """建立一則新貼文。"""

    post = Post(owner_id=user.id, content=payload.content)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return PostOut.model_validate(post)


@app.get("/posts")
async def list_posts(
    user: Annotated[User | None, Depends(get_current_user_optional)],
    db: DbSession,
) -> list[PostOut]:
    """取得貼文列表；登入者不會看到封鎖自己的使用者貼文。"""

    stmt = select(Post).order_by(Post.created_at.desc())
    if user is not None:
        blocked_subq = select(BlackList.id).where(
            BlackList.blocker_id == Post.owner_id,
            BlackList.blocked_id == user.id,
        )
        stmt = stmt.where(~exists(blocked_subq))

    posts = (await db.scalars(stmt)).all()
    return [PostOut.model_validate(post) for post in posts]


@app.get("/posts/{post_id}")
async def get_post(
    post_id: int,
    user: Annotated[User | None, Depends(get_current_user_optional)],
    db: DbSession,
) -> PostOut:
    """取得單一貼文詳情。"""

    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    if user is not None:
        await ensure_not_blocked(post.owner_id, user.id, db)

    return PostOut.model_validate(post)


@app.post("/posts/{post_id}/likes")
async def like_post(
    post_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> Message:
    """對貼文按讚。"""

    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    await ensure_not_blocked(post.owner_id, user.id, db)

    existing_like = await db.scalar(
        select(PostLike).where(PostLike.user_id == user.id, PostLike.post_id == post_id)
    )
    if existing_like is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Post already liked")

    db.add(PostLike(user_id=user.id, post_id=post_id))
    await db.commit()
    return Message(message="Post liked")


@app.delete("/posts/{post_id}/likes")
async def unlike_post(
    post_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> Message:
    """取消貼文按讚。"""

    like = await db.scalar(select(PostLike).where(PostLike.user_id == user.id, PostLike.post_id == post_id))
    if like is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Like not found")

    await db.delete(like)
    await db.commit()
    return Message(message="Post unliked")


@app.post("/posts/{post_id}/comments")
async def comment_post(
    post_id: int,
    payload: CommentCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> CommentTreeOut:
    """在貼文新增留言，支援指定父留言形成巢狀。"""

    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    await ensure_not_blocked(post.owner_id, user.id, db)

    if payload.parent_comment_id is not None:
        parent = await db.get(Comment, payload.parent_comment_id)
        if parent is None or parent.post_id != post_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent comment")
        await ensure_not_blocked(parent.owner_id, user.id, db)

    comment = Comment(
        post_id=post_id,
        owner_id=user.id,
        content=payload.content,
        parent_comment_id=payload.parent_comment_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentTreeOut(
        id=comment.id,
        post_id=comment.post_id,
        owner_id=comment.owner_id,
        parent_comment_id=comment.parent_comment_id,
        content=comment.content,
        created_at=comment.created_at,
        like_count=0,
        replies=[],
    )


@app.post("/comments/{comment_id}/replies")
async def reply_comment(
    comment_id: int,
    payload: ReplyCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> CommentTreeOut:
    """回覆指定留言。"""

    parent = await db.get(Comment, comment_id)
    if parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=COMMENT_NOT_FOUND)

    post = await db.get(Post, parent.post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    await ensure_not_blocked(post.owner_id, user.id, db)
    await ensure_not_blocked(parent.owner_id, user.id, db)

    reply = Comment(
        post_id=parent.post_id,
        owner_id=user.id,
        parent_comment_id=parent.id,
        content=payload.content,
    )
    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    return CommentTreeOut(
        id=reply.id,
        post_id=reply.post_id,
        owner_id=reply.owner_id,
        parent_comment_id=reply.parent_comment_id,
        content=reply.content,
        created_at=reply.created_at,
        like_count=0,
        replies=[],
    )


@app.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: int,
    user: Annotated[User | None, Depends(get_current_user_optional)],
    db: DbSession,
) -> list[CommentTreeOut]:
    """取得貼文留言樹，回傳每則留言的回覆與按讚數。"""

    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    if user is not None:
        await ensure_not_blocked(post.owner_id, user.id, db)

    comments = (
        await db.scalars(select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc()))
    ).all()

    comment_ids = [comment.id for comment in comments]
    like_counts: dict[int, int] = defaultdict(int)
    if comment_ids:
        liked_comment_ids = (
            await db.scalars(
                select(CommentLike.comment_id).where(CommentLike.comment_id.in_(comment_ids))
            )
        ).all()
        for liked_comment_id in liked_comment_ids:
            like_counts[liked_comment_id] += 1

    nodes: dict[int, CommentTreeOut] = {}
    roots: list[CommentTreeOut] = []
    for comment in comments:
        nodes[comment.id] = CommentTreeOut(
            id=comment.id,
            post_id=comment.post_id,
            owner_id=comment.owner_id,
            parent_comment_id=comment.parent_comment_id,
            content=comment.content,
            created_at=comment.created_at,
            like_count=like_counts.get(comment.id, 0),
            replies=[],
        )

    for comment in comments:
        node = nodes[comment.id]
        if comment.parent_comment_id is None:
            roots.append(node)
            continue

        parent_node = nodes.get(comment.parent_comment_id)
        if parent_node is None:
            roots.append(node)
        else:
            parent_node.replies.append(node)

    return roots


@app.patch("/comments/{comment_id}")
async def update_comment(
    comment_id: int,
    payload: ReplyCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> CommentTreeOut:
    """修改留言內容（僅留言擁有者可修改）。"""

    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=COMMENT_NOT_FOUND)

    if comment.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can edit this comment")

    comment.content = payload.content
    await db.commit()
    await db.refresh(comment)

    return CommentTreeOut(
        id=comment.id,
        post_id=comment.post_id,
        owner_id=comment.owner_id,
        parent_comment_id=comment.parent_comment_id,
        content=comment.content,
        created_at=comment.created_at,
        like_count=0,
        replies=[],
    )


@app.post("/comments/{comment_id}/likes")
async def like_comment(
    comment_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> Message:
    """對留言按讚。"""

    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=COMMENT_NOT_FOUND)

    post = await db.get(Post, comment.post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    await ensure_not_blocked(post.owner_id, user.id, db)
    await ensure_not_blocked(comment.owner_id, user.id, db)

    existing_like = await db.scalar(
        select(CommentLike).where(CommentLike.user_id == user.id, CommentLike.comment_id == comment_id)
    )
    if existing_like is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Comment already liked")

    db.add(CommentLike(user_id=user.id, comment_id=comment_id))
    await db.commit()
    return Message(message="Comment liked")


@app.delete("/comments/{comment_id}/likes")
async def unlike_comment(
    comment_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> Message:
    """取消留言按讚。"""

    like = await db.scalar(
        select(CommentLike).where(CommentLike.user_id == user.id, CommentLike.comment_id == comment_id)
    )
    if like is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Like not found")

    await db.delete(like)
    await db.commit()
    return Message(message="Comment unliked")


@app.patch("/posts/{post_id}/top-comment")
async def set_top_comment(
    post_id: int,
    payload: TopCommentUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> PostOut:
    """設定貼文置頂留言（僅貼文擁有者可設定）。"""

    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=POST_NOT_FOUND)

    if post.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can set top comment")

    comment = await db.get(Comment, payload.comment_id)
    if comment is None or comment.post_id != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment does not belong to this post")

    post.top_comment_id = payload.comment_id
    await db.commit()
    await db.refresh(post)
    return PostOut.model_validate(post)


@app.post("/blacklist/{blocked_user_id}")
async def add_blacklist(
    blocked_user_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> BlackListOut:
    """將指定使用者加入我的黑名單。"""

    if blocked_user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot blacklist yourself")

    blocked_user = await db.get(User, blocked_user_id)
    if blocked_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await db.scalar(
        select(BlackList).where(BlackList.blocker_id == user.id, BlackList.blocked_id == blocked_user_id)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in blacklist")

    row = BlackList(blocker_id=user.id, blocked_id=blocked_user_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return BlackListOut.model_validate(row)


@app.delete("/blacklist/{blocked_user_id}")
async def remove_blacklist(
    blocked_user_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> Message:
    """從我的黑名單移除指定使用者。"""

    row = await db.scalar(
        select(BlackList).where(BlackList.blocker_id == user.id, BlackList.blocked_id == blocked_user_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blacklist entry not found")

    await db.delete(row)
    await db.commit()
    return Message(message="Removed from blacklist")


@app.get("/blacklist/me")
async def my_blacklist(
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> list[BlackListOut]:
    """查詢目前登入使用者的黑名單列表。"""

    rows = (await db.scalars(select(BlackList).where(BlackList.blocker_id == user.id))).all()
    return [BlackListOut.model_validate(row) for row in rows]
