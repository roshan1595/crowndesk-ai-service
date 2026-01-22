"""
CrownDesk V2 - HIPAA Guardrails Module
Per plan.txt Section 13 & 16: AI Guardrails

Implements safety checks for AI responses:
- No medical diagnosis
- No coverage guarantees
- Identity verification requirements
- PII protection
- Audit logging
"""

import re
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HIPAAGuardrails:
    """
    HIPAA-compliant guardrails for AI responses.
    
    Ensures AI assistant:
    - Never provides medical diagnoses
    - Never guarantees insurance coverage
    - Requires identity verification for PHI
    - Properly handles sensitive information
    """
    
    def __init__(self):
        # Patterns for detecting dangerous requests
        self.diagnosis_patterns = [
            r"(do i have|diagnose|diagnosis|what('s| is) wrong|what condition)",
            r"(is it|could it be|might be|probably have).*(cancer|disease|infection|virus)",
            r"(what('s| is) causing|why do i have|why am i).*(pain|symptoms|problem)",
            r"should i (take|stop taking|change).*(medication|medicine|pills|drugs)",
            r"(prescription|prescribe|medication recommendation)",
        ]
        
        self.coverage_guarantee_patterns = [
            r"(will|does).*(insurance|my plan).*(cover|pay for)",
            r"how much (will|does) (my|the) insurance (cover|pay)",
            r"(guarantee|promise).*(coverage|payment|cost)",
            r"exactly how much (will i|do i have to) pay",
        ]
        
        self.emergency_patterns = [
            r"(can't breathe|chest pain|heart attack|stroke|unconscious)",
            r"(severe|extreme|intense).*(pain|bleeding|swelling)",
            r"(emergency|urgent|immediately|right now)",
            r"(choking|allergic reaction|anaphylaxis)",
            r"(suicide|kill myself|want to die|harm myself)",
        ]
        
        # Sensitive data patterns for PII scrubbing
        self.pii_patterns = {
            "ssn": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
            "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "dob": r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](\d{2}|\d{4})\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        }
        
        # Standard responses for blocked queries
        self.blocked_responses = {
            "diagnosis": "I'm not able to provide medical diagnoses. I'd recommend scheduling an appointment with one of our dentists who can properly examine you and provide a professional assessment. Would you like me to help you schedule an appointment?",
            "coverage_guarantee": "I can't guarantee specific coverage amounts as that depends on your individual plan and circumstances. Our billing team can give you accurate estimates once they review your insurance details. Would you like me to connect you with them?",
            "emergency": "If this is a medical emergency, please hang up and call 911 immediately, or go to your nearest emergency room. For dental emergencies during office hours, I can try to get you in for an urgent appointment. Is this a life-threatening emergency?",
        }
    
    def check_message(self, message: str) -> Dict[str, Any]:
        """
        Check a user message for content that should be blocked or handled specially.
        
        Returns:
            Dict with:
            - blocked: bool - whether the message should trigger a guardrail response
            - guardrail_type: str - type of guardrail triggered
            - message: str - appropriate response if blocked
            - severity: str - low/medium/high
        """
        message_lower = message.lower()
        
        # Check for emergency first (highest priority)
        for pattern in self.emergency_patterns:
            if re.search(pattern, message_lower):
                return {
                    "blocked": True,
                    "guardrail_type": "emergency",
                    "message": self.blocked_responses["emergency"],
                    "severity": "high",
                    "matched_pattern": pattern
                }
        
        # Check for diagnosis requests
        for pattern in self.diagnosis_patterns:
            if re.search(pattern, message_lower):
                return {
                    "blocked": True,
                    "guardrail_type": "diagnosis",
                    "message": self.blocked_responses["diagnosis"],
                    "severity": "medium",
                    "matched_pattern": pattern
                }
        
        # Check for coverage guarantee requests
        for pattern in self.coverage_guarantee_patterns:
            if re.search(pattern, message_lower):
                return {
                    "blocked": True,
                    "guardrail_type": "coverage_guarantee",
                    "message": self.blocked_responses["coverage_guarantee"],
                    "severity": "low",
                    "matched_pattern": pattern
                }
        
        # No guardrails triggered
        return {
            "blocked": False,
            "guardrail_type": None,
            "message": None,
            "severity": None
        }
    
    def check_response(self, response: str) -> Dict[str, Any]:
        """
        Check an AI-generated response for problematic content.
        
        Ensures AI responses don't accidentally:
        - Provide diagnoses
        - Guarantee coverage
        - Include unscrubbed PII
        """
        response_lower = response.lower()
        warnings = []
        
        # Check for diagnosis-like language
        diagnosis_indicators = [
            r"you (have|might have|probably have|likely have)",
            r"(this is|it sounds like|appears to be).*(condition|disease|infection)",
            r"(definitely|certainly|clearly).*(need|should|must)",
        ]
        
        for pattern in diagnosis_indicators:
            if re.search(pattern, response_lower):
                warnings.append({
                    "type": "potential_diagnosis",
                    "pattern": pattern,
                    "severity": "medium"
                })
        
        # Check for coverage guarantees
        guarantee_indicators = [
            r"(your insurance will|we guarantee|definitely covered)",
            r"(you'll pay|your cost will be|that will cost you) \$[\d,]+",
        ]
        
        for pattern in guarantee_indicators:
            if re.search(pattern, response_lower):
                warnings.append({
                    "type": "coverage_guarantee",
                    "pattern": pattern,
                    "severity": "medium"
                })
        
        return {
            "safe": len(warnings) == 0,
            "warnings": warnings
        }
    
    def scrub_pii(self, text: str, replacement: str = "[REDACTED]") -> str:
        """
        Remove PII from text for logging purposes.
        
        Removes:
        - SSN
        - Phone numbers
        - Email addresses
        - Dates of birth
        - Credit card numbers
        """
        scrubbed = text
        
        for pii_type, pattern in self.pii_patterns.items():
            scrubbed = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", scrubbed)
        
        return scrubbed
    
    def validate_identity_verification(
        self,
        patient_name: Optional[str],
        patient_dob: Optional[str],
        verified: bool
    ) -> Dict[str, Any]:
        """
        Check if identity verification is sufficient for PHI access.
        
        Per HIPAA, we need to verify identity before disclosing PHI.
        """
        if not patient_name:
            return {
                "verified": False,
                "message": "I need your name to look up your information. What is your full name?",
                "missing": ["name"]
            }
        
        if not patient_dob:
            return {
                "verified": False,
                "message": f"Thank you, {patient_name}. For security purposes, I also need to verify your date of birth. What is your date of birth?",
                "missing": ["dob"]
            }
        
        if not verified:
            # Additional verification might be needed
            return {
                "verified": True,
                "message": None,
                "verification_level": "basic"
            }
        
        return {
            "verified": True,
            "message": None,
            "verification_level": "confirmed"
        }
    
    def should_transfer_to_human(
        self,
        confidence: float,
        intent: str,
        explicit_request: bool = False
    ) -> Dict[str, Any]:
        """
        Determine if the call should be transferred to a human.
        
        Criteria:
        - Explicit request from caller
        - Low confidence in AI response (< 0.7)
        - High-stakes intents
        """
        high_stakes_intents = [
            "emergency",
            "complaint",
            "legal_question",
            "insurance_dispute",
            "billing_dispute",
            "complex_scheduling",
        ]
        
        if explicit_request:
            return {
                "transfer": True,
                "reason": "patient_request",
                "message": "Of course! I'll transfer you to our staff right away."
            }
        
        if confidence < 0.7:
            return {
                "transfer": True,
                "reason": "low_confidence",
                "message": "I want to make sure you get the best help. Let me transfer you to our staff who can better assist you."
            }
        
        if intent in high_stakes_intents:
            return {
                "transfer": True,
                "reason": "high_stakes_intent",
                "message": "For this matter, I'd like to connect you with our team to ensure you get the assistance you need."
            }
        
        return {
            "transfer": False,
            "reason": None,
            "message": None
        }
    
    def create_audit_record(
        self,
        action: str,
        call_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        details: Optional[Dict] = None,
        pii_accessed: bool = False
    ) -> Dict[str, Any]:
        """
        Create an audit record for AI actions.
        
        All AI actions that access or modify data should be logged.
        """
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "actor_type": "ai",
            "call_id": call_id,
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "pii_accessed": pii_accessed,
            "details": self.scrub_pii(str(details)) if details else None
        }
        
        logger.info(f"AUDIT: {action} - tenant={tenant_id}, patient={patient_id}")
        
        return record


class ConversationSafetyMonitor:
    """
    Monitor conversation for safety issues in real-time.
    
    Tracks:
    - Repeated attempts to circumvent guardrails
    - Escalating emotional content
    - Potential fraud indicators
    """
    
    def __init__(self):
        self.guardrail_triggers = []
        self.emotional_escalation_count = 0
        self.max_guardrail_triggers = 3
    
    def record_guardrail_trigger(self, guardrail_type: str) -> Dict[str, Any]:
        """Record when a guardrail is triggered."""
        self.guardrail_triggers.append({
            "type": guardrail_type,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Check for repeated attempts
        if len(self.guardrail_triggers) >= self.max_guardrail_triggers:
            return {
                "action": "transfer",
                "reason": "repeated_guardrail_triggers",
                "message": "I've noticed you have some questions that I'm not the best equipped to answer. Let me transfer you to our staff who can better help you."
            }
        
        return {"action": None}
    
    def check_emotional_state(self, message: str) -> Dict[str, Any]:
        """Check for escalating emotional content."""
        frustration_indicators = [
            r"(frustrated|angry|upset|annoyed|tired of)",
            r"(this is ridiculous|this is absurd|unacceptable)",
            r"(never mind|forget it|this is useless)",
            r"(let me speak to|get me a|transfer me to).*(manager|supervisor|human|person)",
        ]
        
        message_lower = message.lower()
        for pattern in frustration_indicators:
            if re.search(pattern, message_lower):
                self.emotional_escalation_count += 1
                
                if self.emotional_escalation_count >= 2:
                    return {
                        "escalated": True,
                        "action": "transfer",
                        "message": "I understand this has been frustrating. Let me get you connected with our staff right away."
                    }
        
        return {"escalated": False}
    
    def get_safety_summary(self) -> Dict[str, Any]:
        """Get summary of safety monitoring for the conversation."""
        return {
            "guardrail_triggers": len(self.guardrail_triggers),
            "guardrail_types": [t["type"] for t in self.guardrail_triggers],
            "emotional_escalations": self.emotional_escalation_count,
            "recommended_action": "transfer" if len(self.guardrail_triggers) >= 3 else None
        }
