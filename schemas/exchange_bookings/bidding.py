from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import List, Optional, Literal
from datetime import date, datetime

class LegBidCreate(BaseModel):
    tender_id: int
    slots_per_interval: int
    main_bid_amount: Optional[float] = None
    secondary_bid_amount: Optional[float] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_bids(self):
        if self.main_bid_amount is None and self.secondary_bid_amount is None:
            raise ValueError("At least one of main_bid_amount or secondary_bid_amount must be provided.")
        if self.main_bid_amount is not None and self.secondary_bid_amount is None:
            raise ValueError("A main_bid_amount cannot be submitted without a secondary_bid_amount.")
        return self

class TenderBidCreate(BaseModel):
    bids: List[LegBidCreate]

class ShipmentLegBid(BaseModel):
    auction_id: int
    main_rate: Optional[float] = None
    secondary_rate: Optional[float] = None
    number_of_loads: int
    lead_time: str
    bid_notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_bids(self):
        if self.main_rate is None and self.secondary_rate is None:
            raise ValueError(
                "At least one of main_rate or secondary_rate must be provided."
            )
        if self.main_rate is not None and self.secondary_rate is None:
            raise ValueError(
                "A main_rate cannot be submitted without a secondary_rate."
            )
        if self.number_of_loads <= 0:
            raise ValueError(
                "number_of_loads must be greater than zero."
            )
        if self.main_rate is not None and self.main_rate < 0:
            raise ValueError(
                "main_rate cannot be negative."
            )
        if self.secondary_rate is not None and self.secondary_rate < 0:
            raise ValueError(
                "secondary_rate cannot be negative."
            )
        return self


class Create_Shipment_Bid(BaseModel):
    bids: List[ShipmentLegBid]