from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str


class TaskOut(BaseModel):
    id: int
    title: str
    created_at: str


class TaskDeleted(BaseModel):
    id: int
    deleted: bool
