"""
CrownDesk V2 - Dental Coding Service
Per plan.txt Section 12: AI-Assisted Dental Coding

Handles:
- CDT code suggestions from clinical notes
- Code validation
- Human-in-the-loop approval workflow integration
"""

import time
from typing import Any, Dict, List, Optional

import asyncpg
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from ai_service.config import get_settings

# CDT Code categories
CDT_CATEGORIES = [
    "D0100-D0999",  # Diagnostic
    "D1000-D1999",  # Preventive
    "D2000-D2999",  # Restorative
    "D3000-D3999",  # Endodontics
    "D4000-D4999",  # Periodontics
    "D5000-D5899",  # Prosthodontics, removable
    "D5900-D5999",  # Maxillofacial Prosthetics
    "D6000-D6199",  # Implant Services
    "D6200-D6999",  # Prosthodontics, fixed
    "D7000-D7999",  # Oral & Maxillofacial Surgery
    "D8000-D8999",  # Orthodontics
    "D9000-D9999",  # Adjunctive General Services
]


class CDTSuggestion(BaseModel):
    """Individual CDT code suggestion"""
    code: str = Field(description="CDT code (e.g., D1110, D2750)")
    description: str = Field(description="Official CDT code description")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")
    reasoning: str = Field(description="Brief explanation for why this code applies")
    tooth_numbers: Optional[List[str]] = Field(default=None, description="Applicable tooth numbers if relevant")
    surfaces: Optional[List[str]] = Field(default=None, description="Tooth surfaces if relevant (M, O, D, B, L)")


class CodingSuggestionResponse(BaseModel):
    """Complete response from coding suggestion"""
    suggestions: List[CDTSuggestion] = Field(description="List of CDT code suggestions")
    warnings: List[str] = Field(default=[], description="Any warnings or concerns")
    notes: str = Field(default="", description="Additional notes for the coder")


class CodeValidationResponse(BaseModel):
    """Validation response for a proposed CDT code."""
    is_valid: bool = Field(description="Whether the code is supported by the notes")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")
    issues: List[str] = Field(default=[], description="Reasons the code may be invalid")
    alternative_codes: List[str] = Field(default=[], description="Suggested alternative CDT codes")


class CodingService:
    """AI-assisted dental coding service using LangChain."""

    def __init__(self):
        self.settings = get_settings()
        self.confidence_threshold = self.settings.coding_confidence_threshold
        self._pool: Optional[asyncpg.Pool] = None
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=0.2,  # Lower temperature for more consistent coding
            api_key=self.settings.openai_api_key
        )
        
        # Create structured prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert dental coder with deep knowledge of CDT (Current Dental Terminology) codes.
Your task is to analyze clinical notes and suggest appropriate CDT codes.

Guidelines:
1. Only suggest codes that are clearly supported by the clinical notes
2. Assign confidence scores honestly - high (0.9+) for clear matches, lower for ambiguous cases
3. Include tooth numbers when the procedure is tooth-specific
4. Include surfaces (M=Mesial, O=Occlusal, D=Distal, B=Buccal, L=Lingual) when relevant
5. Flag any concerns about code combinations or missing information
6. Consider common bundling rules (e.g., don't suggest prophylaxis with scaling on same day)

CDT Code Categories:
- D0100-D0999: Diagnostic (exams, x-rays)
- D1000-D1999: Preventive (prophylaxis, sealants, fluoride)
- D2000-D2999: Restorative (fillings, crowns)
- D3000-D3999: Endodontics (root canals)
- D4000-D4999: Periodontics (deep cleaning, gum treatment)
- D7000-D7999: Oral Surgery (extractions)

Return your response as valid JSON matching this structure:
{{
    "suggestions": [
        {{
            "code": "D1110",
            "description": "Prophylaxis - adult",
            "confidence": 0.95,
            "reasoning": "Notes indicate routine cleaning performed",
            "tooth_numbers": null,
            "surfaces": null
        }}
    ],
    "warnings": ["List any concerns"],
    "notes": "Additional context"
}}"""),
            ("human", """Clinical Notes:
{clinical_notes}

Patient Age: {patient_age}
Previous Visit Notes: {previous_notes}

Analyze these notes and suggest appropriate CDT codes.""")
        ])
        
        # JSON parser for structured output
        self.parser = JsonOutputParser(pydantic_object=CodingSuggestionResponse)
        self.chain = self.prompt | self.llm | self.parser

        self.validation_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a dental coding compliance reviewer.
Evaluate whether a proposed CDT code is supported by the clinical notes.

Return your response as valid JSON with this structure:
{
  "is_valid": true,
  "confidence": 0.0,
  "issues": ["..."] ,
  "alternative_codes": ["D1110"]
}
""",
            ),
            (
                "human",
                """Clinical Notes:
{clinical_notes}

Proposed Code: {code}
Assess validity and suggest alternatives if needed.""",
            ),
        ])
        self.validation_parser = JsonOutputParser(pydantic_object=CodeValidationResponse)
        self.validation_chain = self.validation_prompt | self.llm | self.validation_parser

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.settings.database_url,
                min_size=1,
                max_size=5,
            )
        return self._pool

    async def _lookup_codes(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        if not codes:
            return {}
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT code, description, category, default_fee
                FROM procedure_codes
                WHERE is_active = true AND code = ANY($1::text[])
                """,
                codes,
            )
        return {
            row["code"]: {
                "description": row["description"],
                "category": row["category"],
                "default_fee": float(row["default_fee"]),
            }
            for row in rows
        }

    async def suggest_codes(
        self,
        tenant_id: str,
        clinical_notes: str,
        patient_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        patient_age: int = 35,
        previous_notes: str = "No previous notes available"
    ) -> Dict[str, Any]:
        """
        Generate CDT code suggestions from clinical notes.

        Uses LLM to analyze notes and suggest appropriate codes
        with confidence scoring.
        """
        start_time = time.time()

        result: CodingSuggestionResponse = await self.chain.ainvoke(
            {
                "clinical_notes": clinical_notes,
                "patient_age": patient_age,
                "previous_notes": previous_notes,
            }
        )

        suggestions = [s.model_dump() for s in result.suggestions]

        # Enrich descriptions from procedure code database
        code_lookup = await self._lookup_codes([s["code"] for s in suggestions])
        for s in suggestions:
            if s["code"] in code_lookup:
                s["description"] = code_lookup[s["code"]]["description"]
            s["requires_approval"] = s["confidence"] < self.confidence_threshold

        processing_time = int((time.time() - start_time) * 1000)

        return {
            "suggestions": suggestions,
            "warnings": result.warnings,
            "notes": result.notes,
            "processing_time_ms": processing_time,
        }

    async def validate_code(
        self,
        tenant_id: str,
        code: str,
        clinical_notes: str,
    ) -> Dict[str, Any]:
        """
        Validate if a CDT code is appropriate for the clinical notes.
        """
        validation: CodeValidationResponse = await self.validation_chain.ainvoke(
            {
                "clinical_notes": clinical_notes,
                "code": code,
            }
        )

        # Ensure the code exists in the procedure code table
        code_lookup = await self._lookup_codes([code])
        issues = list(validation.issues)
        if code not in code_lookup:
            issues.append("Code not found in active CDT catalog")

        return {
            "is_valid": validation.is_valid and code in code_lookup,
            "confidence": validation.confidence,
            "issues": issues,
            "alternative_codes": validation.alternative_codes,
        }

    async def search_codes(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search CDT code database.
        """
        pool = await self._get_pool()
        search_term = f"%{query}%"
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT code, description, category, default_fee
                FROM procedure_codes
                WHERE is_active = true
                  AND (tenant_id = $3 OR tenant_id IS NULL)
                  AND (code ILIKE $1 OR description ILIKE $1)
                  AND ($2::text IS NULL OR category::text = $2)
                ORDER BY code ASC
                LIMIT $4
                """,
                search_term,
                category,
                tenant_id,
                limit,
            )

        return [
            {
                "code": row["code"],
                "description": row["description"],
                "category": row["category"],
                "fee_range": f"${float(row['default_fee']):.0f}",
            }
            for row in rows
        ]


def get_coding_service() -> CodingService:
    """Dependency injection for coding service."""
    return CodingService()
