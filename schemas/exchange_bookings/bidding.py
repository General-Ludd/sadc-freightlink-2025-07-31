from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import List, Optional, Literal
from datetime import date, datetime

class LegBidCreate(BaseModel):
    tender_id: int
    slots_per_interval: int
    main_bid_amount: Optional[float] = None
    secondary_bid_amount: Optional[float] = None

    @model_validator(mode="after")
    def validate_bids(self):
        if self.main_bid_amount is None and self.secondary_bid_amount is None:
            raise ValueError("At least one of main_bid_amount or secondary_bid_amount must be provided.")
        if self.main_bid_amount is not None and self.secondary_bid_amount is None:
            raise ValueError("A main_bid_amount cannot be submitted without a secondary_bid_amount.")
        return self

class TenderBidCreate(BaseModel):
    bids: List[LegBidCreate]