"""
사용자 토큰 쿼터 관리 API 스키마
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class TokenQuotaResponse(BaseModel):
    """토큰 쿼터 정보 응답"""
    user_id: int
    plan_month: date
    allocated_quota: int = Field(..., description="할당된 총 토큰 수")
    used_tokens: int = Field(..., description="사용된 토큰 수")
    remaining_tokens: int = Field(..., description="남은 토큰 수")
    total_purchased: int = Field(..., description="구매한 토큰 수")
    usage_percentage: float = Field(..., description="사용률 (0.0-1.0)")
    is_quota_exceeded: bool = Field(..., description="쿼터 초과 여부")
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class TokenPurchaseRequest(BaseModel):
    """토큰 구매 요청"""
    token_amount: int = Field(..., gt=0, description="구매할 토큰 수")
    purchase_type: str = Field("purchase", description="구매 유형: purchase, bonus, refund")
    payment_method: Optional[str] = Field(None, description="결제 수단")
    payment_amount: Optional[float] = Field(None, gt=0, description="결제 금액")
    currency: str = Field("KRW", description="통화")
    transaction_id: Optional[str] = Field(None, description="거래 ID")
    plan_month: Optional[date] = Field(None, description="적용할 월 (기본: 현재 월)")

    @validator('purchase_type')
    def validate_purchase_type(cls, v):
        allowed_types = ['purchase', 'bonus', 'refund']
        if v not in allowed_types:
            raise ValueError(f'구매 유형은 {allowed_types} 중 하나여야 합니다')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        allowed_currencies = ['KRW', 'USD', 'EUR']
        if v not in allowed_currencies:
            raise ValueError(f'통화는 {allowed_currencies} 중 하나여야 합니다')
        return v


class TokenPurchaseResponse(BaseModel):
    """토큰 구매 응답"""
    id: int
    user_id: int
    plan_month: date
    token_amount: int
    purchase_type: str
    payment_method: Optional[str]
    payment_amount: Optional[float]
    currency: str
    status: str
    transaction_id: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        orm_mode = True


class TokenUsageHistoryResponse(BaseModel):
    """토큰 사용 이력 응답"""
    id: int
    user_id: int
    plan_month: date
    token_amount: int
    purchase_type: str
    payment_method: Optional[str]
    payment_amount: Optional[float]
    currency: str
    status: str
    transaction_id: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        orm_mode = True


class QuotaCheckResponse(BaseModel):
    """쿼터 확인 응답"""
    user_id: int
    required_tokens: int
    available: bool
    remaining_tokens: int
    total_quota: int


class TokenConsumptionRequest(BaseModel):
    """토큰 소비 요청 (내부 API용)"""
    user_id: int
    token_amount: int = Field(..., gt=0)
    plan_month: Optional[date] = None
    description: Optional[str] = Field(None, description="사용 목적 설명")


class TokenConsumptionResponse(BaseModel):
    """토큰 소비 응답"""
    user_id: int
    consumed_tokens: int
    remaining_tokens: int
    total_quota: int
    success: bool
    message: str


class MonthlyQuotaSummary(BaseModel):
    """월별 쿼터 요약"""
    plan_month: date
    allocated_quota: int
    used_tokens: int
    remaining_tokens: int
    total_purchased: int
    usage_percentage: float
    purchase_count: int
    total_spent: Optional[float] = None


class UserQuotaStats(BaseModel):
    """사용자 쿼터 통계"""
    user_id: int
    current_month: MonthlyQuotaSummary
    last_month: Optional[MonthlyQuotaSummary]
    total_lifetime_tokens: int
    total_lifetime_spent: Optional[float] = None
    average_monthly_usage: float
    months_active: int