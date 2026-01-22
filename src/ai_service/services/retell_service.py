"""
CrownDesk V2 - Retell AI Service
Per plan.txt Section 13: AI Receptionist

Service layer for Retell AI integration including:
- Agent management via Retell API
- Backend API calls for appointment operations
- Call record storage
- Webhook processing
"""

import httpx
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg

from ai_service.config import Settings

logger = logging.getLogger(__name__)


class RetellService:
    """
    Service for Retell AI integration.
    
    Handles:
    - Creating and managing Retell AI agents
    - Calling CrownDesk backend APIs for patient/appointment data
    - Storing call records and transcripts
    - Processing post-call webhooks
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.retell_api_key = getattr(settings, 'retell_api_key', '')
        self.retell_base_url = "https://api.retellai.com"
        self.backend_url = getattr(settings, 'backend_url', 'http://localhost:3001')
        self._pool: Optional[asyncpg.Pool] = None
        
        # WebSocket URL for our custom LLM endpoint
        self.llm_websocket_url = getattr(
            settings, 
            'retell_llm_websocket_url',
            'wss://ai.crowndesk.app/ws/retell'
        )

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.settings.database_url,
                min_size=1,
                max_size=5,
            )
        return self._pool

    def _parse_date(self, value: str) -> datetime:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError("Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY.")

    def _normalize_name(self, name: str) -> Dict[str, str]:
        cleaned = re.sub(r"\s+", " ", name.strip())
        parts = cleaned.split(" ")
        if len(parts) == 1:
            return {"first": parts[0], "last": ""}
        return {"first": parts[0], "last": parts[-1]}
    
    # =========================================================================
    # Retell Agent Management
    # =========================================================================
    
    async def create_agent(
        self,
        tenant_id: str,
        agent_name: str,
        voice_id: Optional[str] = None,
        language: str = "en-US",
        transfer_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new Retell AI agent for a tenant.
        
        Uses Custom LLM integration pointing to our WebSocket server.
        """
        if not self.retell_api_key:
            raise ValueError("Retell API key not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.retell_base_url}/create-agent",
                headers={
                    "Authorization": f"Bearer {self.retell_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "agent_name": agent_name,
                    "response_engine": {
                        "type": "retell-llm",
                        "llm_websocket_url": f"{self.llm_websocket_url}?tenant_id={tenant_id}"
                    },
                    "voice_id": voice_id or "eleven_labs_rachel",
                    "language": language,
                    "vocab_specialization": "medical",  # Healthcare-specific transcription
                    "enable_backchannel": True,
                    "ambient_sound": None,
                    "responsiveness": 0.7,
                    "interruption_sensitivity": 0.6,
                    "reminder_trigger_ms": 8000,
                    "reminder_max_count": 2,
                    "end_call_after_silence_ms": 30000,
                    "max_call_duration_ms": 1800000,  # 30 minutes
                    "normalize_for_speech": True,
                    "opt_out_sensitive_data_storage": False,  # We handle HIPAA via BAA
                }
            )
            
            if response.status_code != 201:
                logger.error(f"Failed to create agent: {response.text}")
                raise Exception(f"Failed to create Retell agent: {response.text}")
            
            agent_data = response.json()
            
            # Store agent config in our database (to be implemented)
            # await self._store_agent_config(tenant_id, agent_data)
            
            return {
                "agent_id": agent_data["agent_id"],
                "agent_name": agent_name,
                "llm_websocket_url": f"{self.llm_websocket_url}?tenant_id={tenant_id}",
                "voice_id": agent_data.get("voice_id"),
                "language": language
            }
    
    async def get_agents(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all agents for a tenant."""
        if not self.retell_api_key:
            raise ValueError("Retell API key not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.retell_base_url}/list-agents",
                headers={
                    "Authorization": f"Bearer {self.retell_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.error(f"Failed to list agents: {response.text}")
                raise Exception(f"Failed to list Retell agents: {response.text}")

            data = response.json()
            agents = data.get("agents", data if isinstance(data, list) else [])
            return [
                {
                    "agent_id": agent.get("agent_id"),
                    "agent_name": agent.get("agent_name"),
                    "status": agent.get("status", "active"),
                    "language": agent.get("language", "en-US"),
                }
                for agent in agents
            ]
    
    # =========================================================================
    # Appointment Operations (calls backend API)
    # =========================================================================
    
    async def book_appointment(
        self,
        tenant_id: str,
        patient_name: str,
        patient_dob: Optional[str],
        appointment_type: str,
        preferred_date: str,
        preferred_time: Optional[str],
        notes: Optional[str]
    ) -> Dict[str, Any]:
        """
        Book an appointment through the approval system.
        
        Creates an approval request rather than directly booking.
        """
        try:
            # First, try to find the patient
            patient = await self._find_patient(tenant_id, patient_name, patient_dob)
            
            if not patient:
                return {
                    "success": False,
                    "message": f"I couldn't find a patient named {patient_name} in our system. Would you like me to help you register as a new patient, or should I transfer you to our staff?"
                }
            
            # Check availability for the requested date/time
            availability = await self.check_availability(
                tenant_id=tenant_id,
                date=preferred_date,
                appointment_type=appointment_type
            )
            
            if not availability.get("slots"):
                return {
                    "success": False,
                    "message": f"Unfortunately, we don't have any openings on {preferred_date}. The next available dates are: {', '.join(availability.get('next_available', ['Please call back']))}. Would you like to book one of those instead?"
                }
            
            # Find best matching slot
            selected_slot = availability["slots"][0]  # Default to first available
            if preferred_time:
                for slot in availability["slots"]:
                    if preferred_time.lower() in slot.get("time", "").lower():
                        selected_slot = slot
                        break
            
            start_time = self._combine_date_time(preferred_date, selected_slot.get("time"))
            duration = selected_slot.get("duration", 30)
            end_time = start_time + timedelta(minutes=duration)

            provider = await self._get_default_provider(tenant_id)
            if not provider:
                return {
                    "success": False,
                    "message": "I couldn't find a provider available for scheduling."
                }

            appointment_id = str(uuid4())
            await self._create_appointment_approval(
                tenant_id=tenant_id,
                appointment_id=appointment_id,
                patient_id=patient["id"],
                provider_id=provider["id"],
                provider_name=provider["name"],
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                appointment_type=appointment_type or "treatment",
                status="scheduled",
                notes=notes,
                action="create",
            )

            return {
                "success": True,
                "message": f"I've submitted a scheduling request for {patient_name} on {preferred_date} at {selected_slot.get('time')}. Our team will confirm shortly.",
                "appointment": {
                    "date": preferred_date,
                    "time": selected_slot.get("time"),
                    "type": appointment_type,
                    "patient_name": patient_name,
                    "confirmation_pending": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return {
                "success": False,
                "message": "I apologize, I'm having trouble accessing our scheduling system. Would you like me to transfer you to our staff?"
            }
    
    async def check_availability(
        self,
        tenant_id: str,
        date: str,
        appointment_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check available appointment slots."""
        try:
            date_obj = self._parse_date(date)
            provider = await self._get_default_provider(tenant_id)

            if not provider:
                return {
                    "date": date,
                    "slots": [],
                    "message": "No providers are configured for scheduling right now."
                }

            working_hours = self._get_working_hours(provider.get("working_hours"), date_obj)
            if not working_hours:
                return {
                    "date": date,
                    "slots": [],
                    "message": "Provider availability is not configured for that date."
                }

            duration = 30
            slots = await self._calculate_slots(
                tenant_id=tenant_id,
                provider_id=provider["id"],
                date_obj=date_obj,
                start_time=working_hours["start"],
                end_time=working_hours["end"],
                duration_minutes=duration,
            )

            return {
                "date": date,
                "provider": provider["name"],
                "slots": slots,
                "next_available": []
            }

        except Exception as e:
            logger.warning(f"Error checking availability: {e}")
            return {
                "date": date,
                "slots": [],
                "message": "I couldn't access live availability right now."
            }
    
    async def reschedule_appointment(
        self,
        tenant_id: str,
        patient_name: str,
        patient_dob: str,
        current_date: Optional[str],
        new_date: str,
        new_time: Optional[str]
    ) -> Dict[str, Any]:
        """Reschedule an existing appointment."""
        try:
            # Verify patient
            patient = await self._find_patient(tenant_id, patient_name, patient_dob)
            if not patient:
                return {
                    "success": False,
                    "message": "I couldn't verify your patient information. Could you please confirm your date of birth?"
                }
            
            appointment = await self._find_appointment_by_date(
                tenant_id=tenant_id,
                patient_id=patient["id"],
                date=current_date,
            )

            if not appointment:
                return {
                    "success": False,
                    "message": "I couldn't find the appointment you're trying to reschedule."
                }

            availability = await self.check_availability(tenant_id, new_date)
            slots = availability.get("slots", [])
            if not slots:
                return {
                    "success": False,
                    "message": f"Unfortunately, {new_date} is fully booked. Would you like to try a different date?"
                }

            selected_slot = slots[0]
            if new_time:
                selected_slot = self._match_slot(slots, new_time)

            start_time = self._combine_date_time(new_date, selected_slot.get("time"))
            end_time = start_time + timedelta(minutes=appointment["duration"])

            await self._create_appointment_approval(
                tenant_id=tenant_id,
                appointment_id=appointment["id"],
                patient_id=patient["id"],
                provider_id=appointment.get("provider_id"),
                provider_name=appointment.get("provider") or "",
                start_time=start_time,
                end_time=end_time,
                duration=appointment["duration"],
                appointment_type=appointment.get("appointment_type") or "treatment",
                status=appointment.get("status") or "scheduled",
                notes=appointment.get("notes"),
                action="reschedule",
            )

            return {
                "success": True,
                "message": f"I've submitted a reschedule request for {new_date} at {selected_slot.get('time')}. Our team will confirm shortly."
            }
            
        except Exception as e:
            logger.error(f"Error rescheduling: {e}")
            return {
                "success": False,
                "message": "I'm having trouble with our scheduling system. Let me transfer you to our staff."
            }
    
    async def cancel_appointment(
        self,
        tenant_id: str,
        patient_name: str,
        patient_dob: str,
        appointment_date: Optional[str],
        reason: Optional[str]
    ) -> Dict[str, Any]:
        """Cancel an existing appointment."""
        try:
            patient = await self._find_patient(tenant_id, patient_name, patient_dob)
            if not patient:
                return {
                    "success": False,
                    "message": "I couldn't verify your information. Could you please confirm your date of birth?"
                }
            
            appointment = await self._find_appointment_by_date(
                tenant_id=tenant_id,
                patient_id=patient["id"],
                date=appointment_date,
            )

            if not appointment:
                return {
                    "success": False,
                    "message": "I couldn't find the appointment you're trying to cancel."
                }

            await self._create_appointment_approval(
                tenant_id=tenant_id,
                appointment_id=appointment["id"],
                patient_id=patient["id"],
                provider_id=appointment.get("provider_id"),
                provider_name=appointment.get("provider") or "",
                start_time=appointment["start_time"],
                end_time=appointment["end_time"],
                duration=appointment["duration"],
                appointment_type=appointment.get("appointment_type") or "treatment",
                status="cancelled",
                notes=appointment.get("notes"),
                action="cancel",
                metadata={"reason": reason},
            )

            return {
                "success": True,
                "message": "I've submitted a cancellation request. Our team will confirm shortly."
            }
            
        except Exception as e:
            logger.error(f"Error cancelling: {e}")
            return {
                "success": False,
                "message": "I'm having trouble processing that. Let me transfer you to our staff."
            }
    
    # =========================================================================
    # Patient Operations
    # =========================================================================
    
    async def lookup_patient(
        self,
        tenant_id: str,
        patient_name: str,
        patient_dob: str
    ) -> Dict[str, Any]:
        """Look up patient information."""
        patient = await self._find_patient(tenant_id, patient_name, patient_dob)
        
        if patient:
            return {
                "found": True,
                "patient_id": patient.get("id"),
                "message": f"I found your record, {patient_name}. How can I help you today?"
            }
        else:
            return {
                "found": False,
                "message": f"I couldn't find a record for {patient_name} with that date of birth. Would you like to register as a new patient, or should I transfer you to our staff to help locate your record?"
            }
    
    # =========================================================================
    # NEW PATIENT REGISTRATION (Hybrid Voice + Web)
    # =========================================================================
    
    async def collect_new_patient_info(
        self,
        tenant_id: str,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        phone: str,
        reason_for_visit: Optional[str] = None,
        call_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Collect basic info from new patient via voice and create registration token.
        
        This is the first step in hybrid voice + web registration.
        Collects: name, DOB, phone, reason for visit via voice call.
        Then sends SMS with link to complete full registration online.
        """
        try:
            # Validate DOB format
            try:
                dob_parsed = self._parse_date(date_of_birth)
            except ValueError:
                return {
                    "success": False,
                    "message": "I'm having trouble with that date of birth. Could you please say it again, like 'January 15th, 1985'?"
                }
            
            # Check if patient already exists
            existing = await self._find_patient(
                tenant_id=tenant_id,
                patient_name=f"{first_name} {last_name}",
                patient_dob=date_of_birth
            )
            
            if existing:
                return {
                    "success": False,
                    "already_exists": True,
                    "message": f"It looks like {first_name} is already in our system. Would you like to schedule an appointment instead, or should I transfer you to our staff to help with your account?"
                }
            
            # Call backend to create registration token
            async with httpx.AsyncClient() as client:
                # Use internal service-to-service auth or API key
                headers = {
                    "Content-Type": "application/json",
                    "X-Service-Key": getattr(self.settings, 'service_api_key', ''),
                    # For development, we'll also support Clerk token
                    "Authorization": f"Bearer {getattr(self.settings, 'clerk_api_key', '')}"
                }
                
                response = await client.post(
                    f"{self.backend_url}/api/register/voice-intake",
                    headers=headers,
                    json={
                        "phone": phone,
                        "firstName": first_name,
                        "lastName": last_name,
                        "dateOfBirth": dob_parsed.strftime("%Y-%m-%d"),
                        "reasonForVisit": reason_for_visit,
                        "callId": call_id,
                        "agentId": agent_id
                    },
                    timeout=30.0
                )
                
                if response.status_code != 201:
                    logger.error(f"Failed to create registration: {response.text}")
                    return {
                        "success": False,
                        "message": "I'm having trouble with our registration system. Would you like me to transfer you to our staff?"
                    }
                
                result = response.json()
                
                # Trigger SMS send
                sms_response = await client.post(
                    f"{self.backend_url}/api/register/send-sms",
                    headers=headers,
                    json={
                        "registrationTokenId": result.get("registrationTokenId"),
                        "registrationUrl": result.get("registrationUrl")
                    },
                    timeout=30.0
                )
                
                if sms_response.status_code != 200:
                    logger.warning(f"Failed to send registration SMS: {sms_response.text}")
                    # Continue anyway, we can tell user we'll send it
            
            return {
                "success": True,
                "registration_token_id": result.get("registrationTokenId"),
                "message": f"Perfect, {first_name}! I've collected your basic information. "
                           f"I'm sending a text message to {phone} with a secure link to complete your registration. "
                           f"The link will let you fill in your address, medical history, and insurance info at your convenience. "
                           f"It expires in 24 hours. Would you like to schedule a tentative appointment now, "
                           f"or would you prefer to complete registration first and then call back?"
            }
            
        except Exception as e:
            logger.error(f"Error in new patient registration: {e}")
            return {
                "success": False,
                "message": "I apologize, I'm having trouble with our registration system. Let me transfer you to our staff."
            }
    
    async def check_registration_status(
        self,
        tenant_id: str,
        phone: str
    ) -> Dict[str, Any]:
        """
        Check if a patient has a pending registration.
        Used by AI to check if returning caller has incomplete registration.
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Content-Type": "application/json",
                    "X-Service-Key": getattr(self.settings, 'service_api_key', ''),
                    "Authorization": f"Bearer {getattr(self.settings, 'clerk_api_key', '')}"
                }
                
                # Normalize phone to E.164
                cleaned_phone = "".join(filter(str.isdigit, phone))
                if len(cleaned_phone) == 10:
                    cleaned_phone = f"+1{cleaned_phone}"
                elif not cleaned_phone.startswith("+"):
                    cleaned_phone = f"+{cleaned_phone}"
                
                response = await client.get(
                    f"{self.backend_url}/api/register/status/{cleaned_phone}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return {"has_pending_registration": False}
                
                data = response.json()
                
                if data.get("hasActiveRegistration"):
                    stage = data.get("stage", "")
                    
                    if stage in ["voice_intake", "sms_sent"]:
                        return {
                            "has_pending_registration": True,
                            "stage": stage,
                            "message": "I see we sent you a registration link earlier. Did you get a chance to complete it? I can resend the link if you'd like."
                        }
                    elif stage in ["form_started", "form_incomplete"]:
                        return {
                            "has_pending_registration": True,
                            "stage": stage,
                            "message": "I can see you started your registration. Would you like me to resend the link so you can finish it?"
                        }
                    else:
                        return {
                            "has_pending_registration": True,
                            "stage": stage,
                            "message": "Your registration is being processed. Our team will contact you shortly."
                        }
                
                return {"has_pending_registration": False}
                
        except Exception as e:
            logger.warning(f"Error checking registration status: {e}")
            return {"has_pending_registration": False}
    
    async def resend_registration_link(
        self,
        tenant_id: str,
        phone: str
    ) -> Dict[str, Any]:
        """Resend registration SMS to a patient with pending registration."""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Content-Type": "application/json",
                    "X-Service-Key": getattr(self.settings, 'service_api_key', ''),
                    "Authorization": f"Bearer {getattr(self.settings, 'clerk_api_key', '')}"
                }
                
                # Normalize phone
                cleaned_phone = "".join(filter(str.isdigit, phone))
                if len(cleaned_phone) == 10:
                    cleaned_phone = f"+1{cleaned_phone}"
                elif not cleaned_phone.startswith("+"):
                    cleaned_phone = f"+{cleaned_phone}"
                
                response = await client.post(
                    f"{self.backend_url}/api/register/resend-sms/{cleaned_phone}",
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "I've resent the registration link to your phone. You should receive it in a moment."
                    }
                else:
                    return {
                        "success": False,
                        "message": "I couldn't resend the link. Would you like to start a new registration?"
                    }
                    
        except Exception as e:
            logger.error(f"Error resending registration link: {e}")
            return {
                "success": False,
                "message": "I'm having trouble with our system. Let me transfer you to our staff."
            }
    
    async def get_insurance_info(
        self,
        tenant_id: str,
        patient_name: str,
        patient_dob: str,
        procedure_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get insurance information for a patient."""
        try:
            patient = await self._find_patient(tenant_id, patient_name, patient_dob)
            if not patient:
                return {
                    "has_insurance": None,
                    "message": "I couldn't verify your insurance without confirming your patient record."
                }

            pool = await self._get_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(1)
                    FROM insurance_policies
                    WHERE tenant_id = $1 AND patient_id = $2
                    """,
                    tenant_id,
                    patient["id"],
                )

            has_insurance = count > 0
            message = (
                "I can see insurance on file. For coverage details and estimates, "
                "our billing team can provide exact information. Would you like me to transfer you?"
                if has_insurance
                else "I don't see active insurance on file. Our billing team can help update this if needed."
            )

            return {
                "has_insurance": has_insurance,
                "message": message,
            }
            
        except Exception as e:
            logger.error(f"Error getting insurance info: {e}")
            return {
                "has_insurance": None,
                "message": "I'm having trouble accessing insurance information. Let me transfer you to our billing team."
            }
    
    async def _find_patient(
        self,
        tenant_id: str,
        patient_name: str,
        patient_dob: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Find a patient by name and DOB."""
        try:
            name_parts = self._normalize_name(patient_name)
            dob_value = self._parse_date(patient_dob).date() if patient_dob else None

            pool = await self._get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, first_name, last_name, dob
                    FROM patients
                    WHERE tenant_id = $1
                      AND ($2::date IS NULL OR dob = $2::date)
                      AND (
                        (first_name ILIKE $3 AND last_name ILIKE $4)
                        OR (first_name ILIKE $3 AND $4 = '')
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    tenant_id,
                    dob_value,
                    f"%{name_parts['first']}%",
                    f"%{name_parts['last']}%",
                )

            if row:
                return {
                    "id": row["id"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "dob": row["dob"].isoformat() if row["dob"] else None,
                }

            return None

        except Exception as e:
            logger.warning(f"Error finding patient: {e}")
            return None

    async def _get_default_provider(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, first_name, last_name, working_hours
                FROM providers
                WHERE tenant_id = $1 AND is_active = true
                ORDER BY created_at ASC
                LIMIT 1
                """,
                tenant_id,
            )

        if not row:
            return None

        return {
            "id": row["id"],
            "name": f"{row['first_name']} {row['last_name']}".strip(),
            "working_hours": row["working_hours"],
        }

    def _get_working_hours(self, working_hours: Optional[Dict[str, Any]], date_obj: datetime) -> Optional[Dict[str, datetime]]:
        if not working_hours or not isinstance(working_hours, dict):
            return None

        day_key = date_obj.strftime("%A").lower()
        entry = working_hours.get(day_key)
        if not entry:
            return None

        start_value = entry.get("start") or entry.get("startTime")
        end_value = entry.get("end") or entry.get("endTime")
        if not start_value or not end_value:
            return None

        start_time = self._combine_date_time(date_obj.strftime("%Y-%m-%d"), start_value)
        end_time = self._combine_date_time(date_obj.strftime("%Y-%m-%d"), end_value)

        return {"start": start_time, "end": end_time}

    def _combine_date_time(self, date_str: str, time_str: Optional[str]) -> datetime:
        date_obj = self._parse_date(date_str)
        if not time_str:
            return date_obj

        time_clean = time_str.strip().lower()
        if time_clean in {"morning", "am"}:
            return date_obj.replace(hour=9, minute=0)
        if time_clean in {"afternoon", "pm"}:
            return date_obj.replace(hour=13, minute=0)

        for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
            try:
                parsed_time = datetime.strptime(time_str, fmt)
                return date_obj.replace(hour=parsed_time.hour, minute=parsed_time.minute)
            except ValueError:
                continue
        return date_obj

    def _match_slot(self, slots: List[Dict[str, Any]], preferred_time: str) -> Dict[str, Any]:
        for slot in slots:
            if preferred_time.lower() in str(slot.get("time", "")).lower():
                return slot
        return slots[0]

    async def _calculate_slots(
        self,
        tenant_id: str,
        provider_id: str,
        date_obj: datetime,
        start_time: datetime,
        end_time: datetime,
        duration_minutes: int,
    ) -> List[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            appointments = await conn.fetch(
                """
                SELECT start_time, end_time
                FROM appointments
                WHERE tenant_id = $1
                  AND provider_id = $2
                  AND status NOT IN ('cancelled', 'no_show')
                  AND start_time::date = $3::date
                ORDER BY start_time ASC
                """,
                tenant_id,
                provider_id,
                date_obj.date(),
            )

        slots: List[Dict[str, Any]] = []
        slot_start = start_time

        while slot_start + timedelta(minutes=duration_minutes) <= end_time:
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            conflict = False
            for appt in appointments:
                if slot_start < appt["end_time"] and slot_end > appt["start_time"]:
                    conflict = True
                    break
            if not conflict:
                slots.append({
                    "time": slot_start.strftime("%I:%M %p").lstrip("0"),
                    "available": True,
                    "duration": duration_minutes,
                })
            slot_start += timedelta(minutes=15)

        return slots

    async def _find_appointment_by_date(
        self,
        tenant_id: str,
        patient_id: str,
        date: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        pool = await self._get_pool()
        date_obj = self._parse_date(date) if date else datetime.utcnow()
        day_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, provider_id, provider, start_time, end_time, duration, appointment_type, status, notes
                FROM appointments
                WHERE tenant_id = $1
                  AND patient_id = $2
                  AND start_time >= $3
                  AND start_time < $4
                  AND status NOT IN ('cancelled', 'no_show')
                ORDER BY start_time DESC
                LIMIT 1
                """,
                tenant_id,
                patient_id,
                day_start,
                day_end,
            )

        if not row:
            return None

        return {
            "id": row["id"],
            "provider_id": row["provider_id"],
            "provider": row["provider"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "duration": row["duration"],
            "appointment_type": row["appointment_type"],
            "status": row["status"],
            "notes": row["notes"],
        }

    async def _create_appointment_approval(
        self,
        tenant_id: str,
        appointment_id: str,
        patient_id: str,
        provider_id: Optional[str],
        provider_name: str,
        start_time: datetime,
        end_time: datetime,
        duration: int,
        appointment_type: str,
        status: str,
        notes: Optional[str],
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        pool = await self._get_pool()
        approval_id = str(uuid4())
        after_state = {
            "id": appointment_id,
            "tenantId": tenant_id,
            "patientId": patient_id,
            "providerId": provider_id,
            "provider": provider_name,
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
            "duration": duration,
            "appointmentType": appointment_type,
            "status": status,
            "notes": notes,
        }
        if metadata:
            after_state["metadata"] = metadata

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO approvals (
                    id,
                    tenant_id,
                    entity_type,
                    entity_id,
                    before_state,
                    after_state,
                    ai_rationale,
                    status,
                    created_at,
                    updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
                """,
                approval_id,
                tenant_id,
                "appointment",
                appointment_id,
                {},
                after_state,
                f"AI receptionist requested {action}",
                "pending",
                datetime.utcnow(),
            )
    
    # =========================================================================
    # Call Recording & Storage
    # =========================================================================
    
    async def ensure_call_record(
        self,
        tenant_id: str,
        retell_call_id: str,
        call_details: Dict[str, Any],
    ) -> Optional[str]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM call_records
                WHERE tenant_id = $1 AND retell_call_id = $2
                """,
                tenant_id,
                retell_call_id,
            )

            if row:
                return row["id"]

            phone_number = call_details.get("from_number") or call_details.get("phone_number")
            direction = call_details.get("direction") or "inbound"
            start_time = call_details.get("start_timestamp")

            start_dt = (
                datetime.fromtimestamp(start_time / 1000.0)
                if isinstance(start_time, (int, float))
                else datetime.utcnow()
            )

            call_id = str(uuid4())
            await conn.execute(
                """
                INSERT INTO call_records (
                    id, tenant_id, retell_call_id, phone_number, direction, start_time,
                    status, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
                """,
                call_id,
                tenant_id,
                retell_call_id,
                phone_number,
                direction,
                start_dt,
                "in_progress",
                datetime.utcnow(),
            )

            return call_id

    async def store_transcript(
        self,
        call_id: str,
        transcript: List[Dict[str, Any]],
        start_sequence: int = 0,
    ) -> int:
        if not transcript:
            return start_sequence

        pool = await self._get_pool()
        sequence = start_sequence
        async with pool.acquire() as conn:
            for utterance in transcript[start_sequence:]:
                role = utterance.get("role")
                content = utterance.get("content")
                if not content:
                    sequence += 1
                    continue

                await conn.execute(
                    """
                    INSERT INTO call_transcripts (call_id, sequence, role, content, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                    """,
                    call_id,
                    sequence,
                    role,
                    content,
                    datetime.utcnow(),
                )
                sequence += 1

        return sequence

    async def log_tool_call(
        self,
        call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO call_tool_invocations (
                    id, call_id, tool_name, arguments, result, success,
                    error_message, invoked_at, completed_at, duration_ms, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                str(uuid4()),
                call_id,
                tool_name,
                arguments,
                result,
                success,
                error_message,
                datetime.utcnow(),
                datetime.utcnow(),
                None,
                datetime.utcnow(),
            )

    async def finalize_call(
        self,
        tenant_id: str,
        retell_call_id: str,
        call_details: Dict[str, Any],
    ) -> None:
        pool = await self._get_pool()
        end_time = call_details.get("end_timestamp")
        end_dt = (
            datetime.fromtimestamp(end_time / 1000.0)
            if isinstance(end_time, (int, float))
            else datetime.utcnow()
        )
        duration_ms = call_details.get("call_analysis", {}).get("call_duration_ms")
        disconnect_reason = call_details.get("disconnection_reason")

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE call_records
                SET end_time = $1,
                    duration_secs = $2,
                    status = $3,
                    disconnect_reason = $4,
                    updated_at = $5
                WHERE tenant_id = $6 AND retell_call_id = $7
                """,
                end_dt,
                int(duration_ms / 1000) if duration_ms else None,
                "completed",
                disconnect_reason,
                datetime.utcnow(),
                tenant_id,
                retell_call_id,
            )

    async def store_call_record(self, call_data: Dict[str, Any]) -> None:
        """Store call record and transcript after call ends."""
        call_id = call_data.get("call_id")

        if not call_id:
            logger.warning("Call record missing call_id")
            return

        tenant_id = call_data.get("tenant_id")
        if not tenant_id:
            logger.warning("Call record missing tenant_id")
            return

        await self.ensure_call_record(
            tenant_id=tenant_id,
            retell_call_id=call_id,
            call_details=call_data,
        )

        await self.finalize_call(
            tenant_id=tenant_id,
            retell_call_id=call_id,
            call_details=call_data,
        )
    
    async def process_call_analysis(self, call_data: Dict[str, Any]) -> None:
        """Process post-call analysis from Retell."""
        call_id = call_data.get("call_id")
        analysis = call_data.get("call_analysis", {})
        
        try:
            summary = analysis.get("call_summary")
            sentiment = analysis.get("user_sentiment")
            successful = analysis.get("call_successful")

            logger.info(f"Call analysis: {call_id}, sentiment: {sentiment}, successful: {successful}")

            tenant_id = call_data.get("tenant_id")
            if not tenant_id or not call_id:
                return

            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE call_records
                    SET summary = $1,
                        sentiment = $2,
                        outcome = $3,
                        updated_at = $4
                    WHERE tenant_id = $5 AND retell_call_id = $6
                    """,
                    summary,
                    sentiment,
                    "completed" if successful else "follow_up_required",
                    datetime.utcnow(),
                    tenant_id,
                    call_id,
                )
            
        except Exception as e:
            logger.error(f"Error processing call analysis: {e}")
