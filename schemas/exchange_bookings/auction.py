from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

class Accept_Bid(BaseModel):
    bid_id: int

class Exchange_Id(BaseModel):
    id: int

# Bid Schemas
class Exchange_FTL_Shipment_Bid_Create(BaseModel):
    exchange_id: int
    type: str
    bid_amount: int
    bid_notes: Optional [str] = None

class Exchange_POWER_Shipment_Bid_Create(BaseModel):
    exchange_id: int
    type: str
    bid_amount: int
    bid_notes: Optional [str] = None


class Exchange_FTL_Exchange_Loadboard_BidResponse(BaseModel):
    id: int
    exchange_id: int
    carrier_id: int
    carrier_name: str
    user_id: Optional[int]
    bid_amount: int
    bid_notes: Optional[str]
    status: str
    submitted_at: datetime

    class Config:
        orm_mode = True

class Exchange_Power_Exchange_Loadboard_BidResponse(BaseModel):
    id: int
    exchange_id: int
    carrier_id: int
    carrier_name: str
    user_id: Optional[int]
    bid_amount: int
    bid_notes: Optional[str]
    status: str
    submitted_at: datetime

    class Config:
        orm_mode = True

class FTL_Exchange_ShipperSide_BidResponse(BaseModel):
    id: int
    exchange_id: int
    carrier_id: int
    baked_bid_amount: int
    bid_notes: Optional[str]
    status: str
    submitted_at: datetime

    class Config:
        orm_mode = True

class POWER_Exchange_ShipperSide_BidResponse(BaseModel):
    id: int
    exchange_id: int
    carrier_id: int
    baked_bid_amount: int
    bid_notes: Optional[str]
    status: str
    submitted_at: datetime

    class Config:
        orm_mode = True

class Exchange_FTL_Lane_Bid_Create(BaseModel):
    exchange_id: int
    type: str
    per_shipment_bid_amount: int
    bid_notes: Optional [str] = None

class Exchange_FTL_Lane_ShipperSide_BidResponse(BaseModel):
    id: int
    exchange_id: int
    carrier_id: int
    baked_per_shipment_bid_amount: int
    baked_contract_bid_amount: int
    bid_notes: Optional[str]
    status: str
    submitted_at: datetime

    class Config:
        orm_mode = True