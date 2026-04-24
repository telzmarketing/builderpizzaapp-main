from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.paid_traffic import (
    AdIntegrationIn,
    AdIntegrationOut,
    CampaignLinkCreate,
    CampaignLinkOut,
    CampaignSettingsIn,
    CampaignSettingsOut,
    PaidTrafficDashboardOut,
    SyncResultOut,
    TrafficCampaignCreate,
    TrafficCampaignOut,
    TrafficCampaignUpdate,
    TrackingEventIn,
    TrackingEventOut,
)
from backend.services.paid_traffic_service import PaidTrafficService

router = APIRouter(tags=["paid-traffic"])


@router.post("/tracking/event", response_model=TrackingEventOut, status_code=201)
def record_tracking_event(body: TrackingEventIn, db: Session = Depends(get_db)):
    return PaidTrafficService(db).record_event(body)


admin_router = APIRouter(prefix="/paid-traffic", tags=["paid-traffic-admin"], dependencies=[Depends(get_current_admin)])


@admin_router.get("/dashboard", response_model=PaidTrafficDashboardOut)
def dashboard(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    return PaidTrafficService(db).dashboard(date_from=date_from, date_to=date_to)


@admin_router.get("/campaigns", response_model=list[TrafficCampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return PaidTrafficService(db).list_campaigns()


@admin_router.post("/campaigns", response_model=TrafficCampaignOut, status_code=201)
def create_campaign(body: TrafficCampaignCreate, db: Session = Depends(get_db)):
    return PaidTrafficService(db).create_campaign(body)


@admin_router.put("/campaigns/{campaign_id}", response_model=TrafficCampaignOut)
def update_campaign(campaign_id: str, body: TrafficCampaignUpdate, db: Session = Depends(get_db)):
    return PaidTrafficService(db).update_campaign(campaign_id, body)


@admin_router.delete("/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    PaidTrafficService(db).delete_campaign(campaign_id)


@admin_router.get("/links", response_model=list[CampaignLinkOut])
def list_links(campaign_id: Optional[str] = None, db: Session = Depends(get_db)):
    return PaidTrafficService(db).list_links(campaign_id=campaign_id)


@admin_router.post("/links", response_model=CampaignLinkOut, status_code=201)
def create_link(body: CampaignLinkCreate, db: Session = Depends(get_db)):
    return PaidTrafficService(db).create_link(body)


@admin_router.get("/integrations", response_model=list[AdIntegrationOut])
def list_integrations(db: Session = Depends(get_db)):
    return PaidTrafficService(db).list_integrations()


@admin_router.post("/integrations", response_model=AdIntegrationOut)
def upsert_integration(body: AdIntegrationIn, db: Session = Depends(get_db)):
    return PaidTrafficService(db).upsert_integration(body)


@admin_router.post("/integrations/{platform}/disconnect", response_model=AdIntegrationOut)
def disconnect_integration(platform: str, db: Session = Depends(get_db)):
    return PaidTrafficService(db).disconnect_integration(platform)


@admin_router.post("/integrations/{platform}/sync", response_model=SyncResultOut)
def sync_platform(platform: str, db: Session = Depends(get_db)):
    return PaidTrafficService(db).sync_platform(platform)


@admin_router.get("/settings", response_model=CampaignSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return PaidTrafficService(db).get_settings()


@admin_router.put("/settings", response_model=CampaignSettingsOut)
def update_settings(body: CampaignSettingsIn, db: Session = Depends(get_db)):
    return PaidTrafficService(db).update_settings(body)
