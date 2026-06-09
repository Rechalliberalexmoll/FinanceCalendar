"""
Pydantic schemas for request / response validation.
"""
from datetime import date as DateType
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Category ──────────────────────────────────────────────
class CategoryOut(BaseModel):
    id: int
    name: str
    type: str


class CategoryCreate(BaseModel):
    name: str
    type: str = "expense"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None


# ── Project ───────────────────────────────────────────────
class ProjectOut(BaseModel):
    id: int
    name: str


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None


# ── Transaction ───────────────────────────────────────────
class TransactionCreate(BaseModel):
    date: DateType
    amount: float = Field(gt=0)
    type: str = "expense"
    category_id: Optional[int] = None
    project_id: Optional[int] = None
    note: Optional[str] = None


class TransactionUpdate(BaseModel):
    date: Optional[DateType] = None
    amount: Optional[float] = Field(default=None, gt=0)
    type: Optional[str] = None
    category_id: Optional[int] = None
    project_id: Optional[int] = None
    note: Optional[str] = None


class TransactionOut(BaseModel):
    id: int
    date: str
    amount: float
    type: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    note: Optional[str] = None
    created_at: str
    updated_at: str


# ── Reminder (还款日) ────────────────────────────────────
class ReminderCreate(BaseModel):
    name: str = Field(..., min_length=1)
    amount: Optional[float] = Field(None, ge=0)
    total_debt: Optional[float] = Field(None, ge=0)
    day_of_month: int = Field(..., ge=1, le=28)
    start_date: Optional[str] = Field(None, description="起始月份 YYYY-MM，不传则从现在开始")
    end_date: Optional[str] = Field(None, description="结束月份 YYYY-MM，不传则永久")
    note: Optional[str] = None
    color: str = "#ff3b30"


class ReminderUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    total_debt: Optional[float] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    note: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


class ReminderOut(BaseModel):
    id: int
    name: str
    amount: Optional[float] = None
    total_debt: Optional[float] = None
    day_of_month: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    note: Optional[str] = None
    color: str
    is_active: bool
    created_at: str


class ReminderDone(BaseModel):
    """Mark a reminder as done for a specific year-month."""
    year_month: str = Field(..., description="YYYY-MM 格式")


# ── Stats ─────────────────────────────────────────────────
class MonthlyStat(BaseModel):
    year: int
    month: int
    income: float = 0.0
    expense: float = 0.0
    net: float = 0.0


class CategoryStat(BaseModel):
    category_id: Optional[int] = None
    category_name: str
    type: str
    total: float = 0.0
    count: int = 0


class ProjectStat(BaseModel):
    project_id: Optional[int] = None
    project_name: str
    income: float = 0.0
    expense: float = 0.0
    net: float = 0.0
    count: int = 0


# ── Natural Language Parse ─────────────────────────
class ParseRequest(BaseModel):
    text: str = Field(..., min_length=1)
    model: Optional[str] = None


class ParseResult(BaseModel):
    amount: Optional[float] = None
    date: str
    type: str = "expense"
    category: str
    subcategory: Optional[str] = None
    project: Optional[str] = None
    note: Optional[str] = None
    needs_confirmation: bool = False
    missing_fields: List[str] = Field(default_factory=list)


class ParseConfirm(BaseModel):
    amount: float = Field(gt=0)
    date: str
    type: str = "expense"
    category_id: Optional[int] = None
    project_id: Optional[int] = None
    note: Optional[str] = None
