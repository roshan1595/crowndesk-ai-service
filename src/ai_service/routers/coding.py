"""
CrownDesk V2 - AI Dental Coding Router
Per plan.txt Section 12: AI-Assisted Dental Coding

Endpoints:
- POST /coding/suggest - Get CDT code suggestions from clinical notes
- POST /coding/validate - Validate a proposed CDT code
- GET /coding/codes - Search CDT code database
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_service.services.coding_service import CodingService, get_coding_service

router = APIRouter()


class CodingSuggestionRequest(BaseModel):
    """Request for CDT code suggestions."""

    tenant_id: str
    clinical_notes: str
    patient_id: Optional[str] = None
    appointment_id: Optional[str] = None


class CDTSuggestion(BaseModel):
    """A single CDT code suggestion."""

    code: str
    description: str
    confidence: float
    reasoning: str
    requires_approval: bool


class CodingSuggestionResponse(BaseModel):
    """Response with CDT code suggestions."""

    suggestions: List[CDTSuggestion]
    raw_notes: str
    processing_time_ms: int


class ValidateCodeRequest(BaseModel):
    """Request to validate a CDT code."""

    tenant_id: str
    code: str
    clinical_notes: str


class ValidateCodeResponse(BaseModel):
    """Response from code validation."""

    code: str
    is_valid: bool
    confidence: float
    issues: List[str]
    alternative_codes: List[str]


class CDTCodeInfo(BaseModel):
    """CDT code information."""

    code: str
    description: str
    category: str
    fee_range: Optional[str] = None


@router.post("/suggest", response_model=CodingSuggestionResponse)
async def suggest_codes(
    request: CodingSuggestionRequest,
    coding_service: CodingService = Depends(get_coding_service),
):
    """
    Get AI-powered CDT code suggestions from clinical notes.

    Per plan.txt Section 12:
    - Analyzes clinical notes using LLM
    - Returns CDT codes with confidence scores
    - Marks codes below threshold for human approval
    """
    try:
        result = await coding_service.suggest_codes(
            tenant_id=request.tenant_id,
            clinical_notes=request.clinical_notes,
            patient_id=request.patient_id,
            appointment_id=request.appointment_id,
        )
        return CodingSuggestionResponse(
            suggestions=[
                CDTSuggestion(
                    code=s["code"],
                    description=s["description"],
                    confidence=s["confidence"],
                    reasoning=s["reasoning"],
                    requires_approval=s["requires_approval"],
                )
                for s in result["suggestions"]
            ],
            raw_notes=request.clinical_notes,
            processing_time_ms=result["processing_time_ms"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=ValidateCodeResponse)
async def validate_code(
    request: ValidateCodeRequest,
    coding_service: CodingService = Depends(get_coding_service),
):
    """
    Validate a proposed CDT code against clinical notes.

    Checks if the code is appropriate for the documented procedures.
    """
    try:
        result = await coding_service.validate_code(
            tenant_id=request.tenant_id,
            code=request.code,
            clinical_notes=request.clinical_notes,
        )
        return ValidateCodeResponse(
            code=request.code,
            is_valid=result["is_valid"],
            confidence=result["confidence"],
            issues=result["issues"],
            alternative_codes=result["alternative_codes"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/codes", response_model=List[CDTCodeInfo])
async def search_codes(
    query: str,
    category: Optional[str] = None,
    limit: int = 20,
    coding_service: CodingService = Depends(get_coding_service),
):
    """Search CDT code database."""
    try:
        codes = await coding_service.search_codes(
            query=query,
            category=category,
            limit=limit,
        )
        return [
            CDTCodeInfo(
                code=c["code"],
                description=c["description"],
                category=c["category"],
                fee_range=c.get("fee_range"),
            )
            for c in codes
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
