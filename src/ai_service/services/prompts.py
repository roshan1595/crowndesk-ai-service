"""
CrownDesk V2 - Voice Agent Prompts System
AI-017: Dynamic prompts for AI receptionist

Provides context-aware prompts for different conversation scenarios.
Supports dynamic injection of practice info, patient context, and situational data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ConversationIntent(Enum):
    """Conversation intents for routing prompts."""
    GREETING = "greeting"
    APPOINTMENT_BOOKING = "appointment_booking"
    APPOINTMENT_RESCHEDULE = "appointment_reschedule"
    APPOINTMENT_CANCEL = "appointment_cancel"
    APPOINTMENT_INQUIRY = "appointment_inquiry"
    INSURANCE_INQUIRY = "insurance_inquiry"
    BILLING_INQUIRY = "billing_inquiry"
    EMERGENCY = "emergency"
    GENERAL_INQUIRY = "general_inquiry"
    HUMAN_HANDOFF = "human_handoff"
    CLOSING = "closing"


@dataclass
class PracticeInfo:
    """Practice information for prompt injection."""
    name: str
    phone: str
    address: str
    hours: Dict[str, str]
    website: Optional[str] = None
    specialties: List[str] = None
    providers: List[Dict[str, str]] = None
    
    def format_hours(self) -> str:
        """Format hours for voice readout."""
        if not self.hours:
            return "Please call for our current hours."
        
        lines = []
        for day, hours in self.hours.items():
            lines.append(f"{day}: {hours}")
        return ". ".join(lines)


@dataclass  
class PatientContext:
    """Patient context for personalized responses."""
    name: Optional[str] = None
    first_name: Optional[str] = None
    verified: bool = False
    has_upcoming_appointment: bool = False
    upcoming_appointment_date: Optional[str] = None
    upcoming_appointment_time: Optional[str] = None
    upcoming_appointment_provider: Optional[str] = None
    balance_due: Optional[float] = None
    insurance_on_file: bool = False
    last_visit: Optional[str] = None


class VoicePromptSystem:
    """
    Dynamic prompt system for voice AI receptionist.
    
    Features:
    - Context-aware prompt generation
    - Practice info injection
    - Patient personalization
    - Time-of-day awareness
    - Emergency routing
    """
    
    def __init__(self, practice_info: Optional[PracticeInfo] = None):
        self.practice_info = practice_info or self._default_practice_info()
        
    def _default_practice_info(self) -> PracticeInfo:
        """Default practice info - should be replaced with actual data."""
        return PracticeInfo(
            name="Your Dental Practice",
            phone="(555) 123-4567",
            address="123 Main Street, Suite 100",
            hours={
                "Monday-Thursday": "8 AM to 5 PM",
                "Friday": "8 AM to 2 PM",
                "Saturday-Sunday": "Closed"
            },
            specialties=["General Dentistry", "Cosmetic Dentistry", "Orthodontics"],
            providers=[
                {"name": "Dr. Smith", "title": "General Dentist"},
                {"name": "Dr. Johnson", "title": "Orthodontist"}
            ]
        )
    
    def get_system_prompt(
        self,
        patient_context: Optional[PatientContext] = None,
        current_intent: Optional[ConversationIntent] = None
    ) -> str:
        """
        Generate the main system prompt for the voice agent.
        
        This is the comprehensive prompt that guides the AI's behavior.
        """
        current_time = datetime.now()
        time_of_day = self._get_time_of_day(current_time)
        
        # Build provider list
        providers_text = ""
        if self.practice_info.providers:
            provider_names = [f"{p['name']} ({p['title']})" for p in self.practice_info.providers]
            providers_text = f"Our providers include: {', '.join(provider_names)}."
        
        # Build patient context section
        patient_section = ""
        if patient_context and patient_context.verified:
            patient_section = f"""
CURRENT PATIENT CONTEXT:
- Patient Name: {patient_context.name}
- Identity Verified: Yes
- Has Upcoming Appointment: {patient_context.has_upcoming_appointment}
{f"- Next Appointment: {patient_context.upcoming_appointment_date} at {patient_context.upcoming_appointment_time} with {patient_context.upcoming_appointment_provider}" if patient_context.has_upcoming_appointment else ""}
{f"- Balance Due: ${patient_context.balance_due:.2f}" if patient_context.balance_due else ""}
- Insurance on File: {"Yes" if patient_context.insurance_on_file else "No"}
"""

        system_prompt = f"""You are a friendly and professional AI receptionist for {self.practice_info.name}. 
Your role is to assist callers with scheduling appointments, answering questions about the practice, 
and providing helpful information while maintaining HIPAA compliance.

PRACTICE INFORMATION:
- Name: {self.practice_info.name}
- Phone: {self.practice_info.phone}
- Address: {self.practice_info.address}
- Hours: {self.practice_info.format_hours()}
{providers_text}

CURRENT TIME: {current_time.strftime("%A, %B %d, %Y at %I:%M %p")}
TIME OF DAY: {time_of_day}
{patient_section}

CORE RESPONSIBILITIES:
1. APPOINTMENT SCHEDULING
   - Help callers book, reschedule, or cancel appointments
   - Check provider availability before confirming
   - Collect necessary information (name, date of birth, contact info, reason for visit)
   - Confirm appointment details clearly

2. PATIENT INQUIRIES
   - Answer questions about office hours, location, and services
   - Provide general information about procedures (without medical advice)
   - Help with insurance and billing questions (general guidance only)
   - Transfer to appropriate staff for complex matters

3. IDENTITY VERIFICATION (REQUIRED FOR PHI)
   - Before discussing any personal health information, verify:
     a) Full name
     b) Date of birth
   - Do NOT disclose appointment details, balance, or medical info without verification

STRICT GUIDELINES - YOU MUST FOLLOW:
1. NEVER provide medical diagnoses or treatment recommendations
2. NEVER guarantee insurance coverage or specific costs
3. NEVER discuss other patients' information
4. ALWAYS verify identity before sharing PHI
5. For emergencies, direct to 911 or emergency services immediately
6. When uncertain, offer to transfer to a staff member

COMMUNICATION STYLE:
- Be warm, friendly, and professional
- Speak naturally as if having a phone conversation
- Keep responses concise (2-3 sentences for voice)
- Use the caller's name when verified
- Confirm important details by repeating them back
- End interactions positively

EMERGENCY KEYWORDS TO WATCH FOR:
- "emergency", "urgent", "severe pain", "can't breathe", "bleeding heavily"
- "swelling", "accident", "knocked out tooth", "broken jaw"
- If detected, immediately offer emergency guidance

AVAILABLE FUNCTIONS:
You can use these functions to help callers:
- book_appointment: Schedule a new appointment
- check_availability: Check available time slots
- reschedule_appointment: Change an existing appointment
- cancel_appointment: Cancel an appointment
- lookup_patient: Find patient information (requires verification)
- get_insurance_info: Get insurance details on file
- transfer_to_human: Connect to a staff member
- end_call: End the conversation politely

Remember: You are the first point of contact for the practice. Your goal is to provide 
excellent service while protecting patient privacy and ensuring appropriate care."""

        return system_prompt
    
    def get_greeting_message(
        self,
        patient_context: Optional[PatientContext] = None
    ) -> str:
        """Generate the initial greeting message."""
        current_time = datetime.now()
        time_of_day = self._get_time_of_day(current_time)
        
        greeting = self._time_greeting(time_of_day)
        
        if patient_context and patient_context.verified and patient_context.first_name:
            return f"{greeting}! Welcome back, {patient_context.first_name}. Thank you for calling {self.practice_info.name}. How can I help you today?"
        
        return f"{greeting}! Thank you for calling {self.practice_info.name}. My name is Ava, your virtual dental assistant. How may I help you today?"
    
    def get_intent_prompt(self, intent: ConversationIntent) -> str:
        """Get specialized prompt additions based on detected intent."""
        prompts = {
            ConversationIntent.APPOINTMENT_BOOKING: """
The caller wants to book an appointment. Guide them through:
1. Ask what type of appointment they need (cleaning, checkup, specific concern)
2. Ask for their preferred date and time
3. Use check_availability to find open slots
4. Once a time is selected, collect/verify their information
5. Use book_appointment to schedule
6. Confirm all details before ending""",

            ConversationIntent.APPOINTMENT_RESCHEDULE: """
The caller wants to reschedule. Steps:
1. Verify their identity (name and DOB)
2. Look up their current appointment
3. Ask for their new preferred date/time
4. Check availability
5. Use reschedule_appointment
6. Confirm the change""",

            ConversationIntent.APPOINTMENT_CANCEL: """
The caller wants to cancel. Steps:
1. Verify their identity
2. Confirm which appointment they want to cancel
3. Ask if they'd like to reschedule instead
4. If they confirm cancellation, use cancel_appointment
5. Let them know they can call back anytime to reschedule""",

            ConversationIntent.INSURANCE_INQUIRY: """
The caller has insurance questions. Remember:
- You can tell them what insurance info we have on file (after verification)
- You CANNOT guarantee coverage amounts
- You CANNOT confirm what procedures are covered
- For specific coverage questions, offer to transfer to billing staff
- You can help them update their insurance information""",

            ConversationIntent.BILLING_INQUIRY: """
The caller has billing questions. Remember:
- After verification, you can tell them their current balance
- You CANNOT negotiate payment amounts
- You CANNOT waive fees
- For payment plans or disputes, transfer to billing staff
- You can confirm if a payment was received (general terms only)""",

            ConversationIntent.EMERGENCY: """
EMERGENCY DETECTED. Immediately:
1. Ask if they need to call 911 (life-threatening situations)
2. For dental emergencies during office hours, try to get them an urgent appointment
3. For after-hours dental emergencies, provide the emergency contact number
4. Stay calm and reassuring
5. If it's a medical emergency (not dental), direct to 911 or ER""",

            ConversationIntent.HUMAN_HANDOFF: """
The caller wants to speak with a human. 
1. Acknowledge their request politely
2. Let them know you'll transfer them
3. Use transfer_to_human function
4. If no one is available, take a message or offer a callback""",

            ConversationIntent.CLOSING: """
Ending the conversation:
1. Summarize any actions taken (appointments booked, etc.)
2. Ask if there's anything else they need
3. Thank them for calling
4. Remind them of any upcoming appointments
5. Use end_call function"""
        }
        
        return prompts.get(intent, "")
    
    def get_verification_prompt(self, step: str = "name") -> str:
        """Get prompt for identity verification steps."""
        prompts = {
            "name": "To access your account information, I'll need to verify your identity. May I have your full name as it appears in our records?",
            "dob": "Thank you. And for verification, could you please provide your date of birth?",
            "confirm": "Thank you for verifying. I can now access your information.",
            "failed": "I apologize, but I wasn't able to verify your identity with that information. Would you like to try again, or would you prefer I transfer you to our front desk staff?"
        }
        return prompts.get(step, prompts["name"])
    
    def get_hold_message(self) -> str:
        """Message when placing caller on brief hold."""
        return "Let me check on that for you. This will just take a moment."
    
    def get_no_availability_message(self, date: str) -> str:
        """Message when requested time slot is not available."""
        return f"I apologize, but we don't have any availability on {date}. Would you like me to check some alternative dates, or would you prefer the next available appointment?"
    
    def get_appointment_confirmation(
        self,
        date: str,
        time: str,
        provider: str,
        appointment_type: str
    ) -> str:
        """Generate appointment confirmation message."""
        return f"I've booked your {appointment_type} appointment with {provider} on {date} at {time}. You should receive a confirmation text and email shortly. Is there anything else I can help you with?"
    
    def get_transfer_message(self, department: str = "staff") -> str:
        """Message when transferring to human."""
        messages = {
            "staff": "I'll transfer you to one of our team members now. Please hold for just a moment.",
            "billing": "I'll connect you with our billing department. One moment please.",
            "clinical": "Let me transfer you to our clinical team. Please hold.",
            "manager": "I'll connect you with a manager. Please hold while I transfer your call."
        }
        return messages.get(department, messages["staff"])
    
    def get_after_hours_message(self) -> str:
        """Message for calls outside office hours."""
        return f"""Thank you for calling {self.practice_info.name}. 
Our office is currently closed. Our regular hours are {self.practice_info.format_hours()}.

If this is a dental emergency, please call our emergency line or go to your nearest emergency room.
Otherwise, I'd be happy to help you schedule an appointment for when we're open.
Would you like to book an appointment?"""
    
    def get_emergency_response(self, severity: str = "dental") -> str:
        """Get appropriate emergency response."""
        if severity == "medical":
            return "This sounds like a medical emergency. Please hang up and call 911 immediately, or have someone take you to the nearest emergency room right away."
        
        return f"""I understand this is urgent. For dental emergencies, here's what I can do:
If we're currently open, let me see if we can get you in for an emergency appointment today.
If this is after hours, our emergency line is {self.practice_info.phone}.

Can you tell me briefly what's happening so I can help you appropriately?"""
    
    def get_closing_message(
        self,
        patient_name: Optional[str] = None,
        appointment_booked: bool = False
    ) -> str:
        """Generate closing message."""
        name_part = f", {patient_name}" if patient_name else ""
        
        if appointment_booked:
            return f"You're all set{name_part}! We look forward to seeing you. If you have any questions before your appointment, don't hesitate to call. Have a great day!"
        
        return f"Thank you for calling {self.practice_info.name}{name_part}. Have a wonderful day, and we hope to see you soon!"
    
    def _get_time_of_day(self, dt: datetime) -> str:
        """Determine time of day for contextual greetings."""
        hour = dt.hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        else:
            return "evening"
    
    def _time_greeting(self, time_of_day: str) -> str:
        """Get appropriate greeting for time of day."""
        greetings = {
            "morning": "Good morning",
            "afternoon": "Good afternoon",
            "evening": "Good evening"
        }
        return greetings.get(time_of_day, "Hello")


class PromptTemplateManager:
    """
    Manages prompt templates for different tenants/practices.
    
    Allows customization of prompts per practice while maintaining
    compliance with HIPAA and safety guidelines.
    """
    
    def __init__(self):
        self.templates: Dict[str, VoicePromptSystem] = {}
        self.default_system = VoicePromptSystem()
    
    def register_practice(
        self,
        tenant_id: str,
        practice_info: PracticeInfo
    ) -> None:
        """Register a practice with custom prompts."""
        self.templates[tenant_id] = VoicePromptSystem(practice_info)
    
    def get_system(self, tenant_id: Optional[str] = None) -> VoicePromptSystem:
        """Get the prompt system for a tenant."""
        if tenant_id and tenant_id in self.templates:
            return self.templates[tenant_id]
        return self.default_system
    
    def get_system_prompt(
        self,
        tenant_id: Optional[str] = None,
        patient_context: Optional[PatientContext] = None,
        current_intent: Optional[ConversationIntent] = None
    ) -> str:
        """Get full system prompt for a tenant."""
        system = self.get_system(tenant_id)
        base_prompt = system.get_system_prompt(patient_context, current_intent)
        
        if current_intent:
            intent_addition = system.get_intent_prompt(current_intent)
            if intent_addition:
                base_prompt += f"\n\nCURRENT CONVERSATION FOCUS:\n{intent_addition}"
        
        return base_prompt


# Singleton instance for global access
prompt_manager = PromptTemplateManager()
