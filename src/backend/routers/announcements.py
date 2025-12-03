"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[str] = None
    expiration_date: str
    created_by: str


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None


@router.get("/active")
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all active announcements (within date range)"""
    current_time = datetime.utcnow().isoformat()
    
    # Query for announcements that:
    # 1. Haven't expired yet
    # 2. Either have no start_date, or the start_date has passed
    query = {
        "expiration_date": {"$gte": current_time},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": current_time}}
        ]
    }
    
    announcements = list(announcements_collection.find(query))
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.get("")
def get_all_announcements(username: str) -> List[Dict[str, Any]]:
    """Get all announcements (for management) - requires authentication"""
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    announcements = list(announcements_collection.find().sort("created_at", -1))
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.post("")
def create_announcement(announcement: AnnouncementCreate) -> Dict[str, Any]:
    """Create a new announcement - requires authentication"""
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": announcement.created_by})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Validate expiration date is required
    if not announcement.expiration_date:
        raise HTTPException(status_code=400, detail="Expiration date is required")
    
    # Validate dates are in ISO format and expiration is in the future
    try:
        expiration = datetime.fromisoformat(announcement.expiration_date.replace('Z', '+00:00'))
        if expiration < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Expiration date must be in the future")
        
        if announcement.start_date:
            start = datetime.fromisoformat(announcement.start_date.replace('Z', '+00:00'))
            if start >= expiration:
                raise HTTPException(status_code=400, detail="Start date must be before expiration date")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Create announcement document
    announcement_doc = {
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date,
        "created_by": announcement.created_by,
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = announcements_collection.insert_one(announcement_doc)
    announcement_doc["_id"] = str(result.inserted_id)
    
    return announcement_doc


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    announcement: AnnouncementUpdate,
    username: str
) -> Dict[str, Any]:
    """Update an announcement - requires authentication"""
    from bson import ObjectId
    
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Build update document
    update_doc = {}
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date
    if announcement.expiration_date is not None:
        update_doc["expiration_date"] = announcement.expiration_date
    
    if not update_doc:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Validate dates if provided
    try:
        if announcement.expiration_date:
            expiration = datetime.fromisoformat(announcement.expiration_date.replace('Z', '+00:00'))
            if expiration < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Expiration date must be in the future")
        
        if announcement.start_date and announcement.expiration_date:
            start = datetime.fromisoformat(announcement.start_date.replace('Z', '+00:00'))
            expiration = datetime.fromisoformat(announcement.expiration_date.replace('Z', '+00:00'))
            if start >= expiration:
                raise HTTPException(status_code=400, detail="Start date must be before expiration date")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    try:
        result = announcements_collection.find_one_and_update(
            {"_id": ObjectId(announcement_id)},
            {"$set": update_doc},
            return_document=True
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if not result:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    result["_id"] = str(result["_id"])
    return result


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, username: str) -> Dict[str, str]:
    """Delete an announcement - requires authentication"""
    from bson import ObjectId
    
    # Verify user is authenticated
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        result = announcements_collection.delete_one({"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
