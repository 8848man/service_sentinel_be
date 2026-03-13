from pydantic import BaseModel, Field

class DeviceTokenRegisterRequest(BaseModel):
    token: str = Field(..., min_length=10)
    platform: str = Field(..., examples=["android", "ios", "web"])