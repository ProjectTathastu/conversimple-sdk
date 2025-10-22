"""Multi-step booking agent definition for dispatcher-managed sessions."""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

from conversimple import ConversimpleAgent, tool, tool_async

# Configure logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BookingStatus(Enum):
    """Booking status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingAgent(ConversimpleAgent):
    """
    Advanced booking agent with multi-step workflow management.
    
    Demonstrates:
    - Multi-turn conversation context
    - Complex state management across tool calls
    - Workflow orchestration
    - Validation and business rules
    - Transaction-like booking processes
    """

    agent_id = "example-booking-agent"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Booking state management
        self.active_bookings: Dict[str, Dict] = {}
        self.booking_sessions: Dict[str, Dict] = {}
        
        # Mock availability data
        self.availability = {
            "2025-01-29": {
                "09:00": {"available": True, "service": "consultation", "duration": 60},
                "10:00": {"available": True, "service": "consultation", "duration": 60},
                "11:00": {"available": False, "service": None, "duration": None},
                "14:00": {"available": True, "service": "full_service", "duration": 120},
                "16:00": {"available": True, "service": "consultation", "duration": 60}
            },
            "2025-01-30": {
                "09:00": {"available": True, "service": "consultation", "duration": 60},
                "10:00": {"available": True, "service": "full_service", "duration": 120},
                "13:00": {"available": True, "service": "consultation", "duration": 60},
                "15:00": {"available": True, "service": "full_service", "duration": 120},
                "17:00": {"available": True, "service": "consultation", "duration": 60}
            }
        }
        
        # Service catalog
        self.services = {
            "consultation": {
                "name": "Consultation",
                "duration": 60,
                "price": 150.00,
                "description": "Initial consultation and assessment"
            },
            "full_service": {
                "name": "Full Service Session", 
                "duration": 120,
                "price": 300.00,
                "description": "Complete service session with follow-up"
            }
        }

    @tool("Check availability for specific date and time")
    def check_availability(self, date: str, time: str = None) -> Dict:
        """
        Check availability for booking on a specific date and optionally time.
        
        Args:
            date: Date in YYYY-MM-DD format
            time: Optional time in HH:MM format
            
        Returns:
            Availability information
        """
        logger.info(f"Checking availability for {date} {time or 'all day'}")
        
        if date not in self.availability:
            return {
                "date": date,
                "available": False,
                "message": "No availability data for this date",
                "suggestions": list(self.availability.keys())
            }
        
        day_availability = self.availability[date]
        
        if time:
            # Check specific time
            if time in day_availability:
                slot = day_availability[time]
                return {
                    "date": date,
                    "time": time,
                    "available": slot["available"],
                    "service": slot["service"],
                    "duration": slot["duration"]
                }
            else:
                return {
                    "date": date,
                    "time": time,
                    "available": False,
                    "message": "Time slot not found",
                    "available_times": list(day_availability.keys())
                }
        else:
            # Return all availability for the day
            available_slots = []
            for slot_time, slot_info in day_availability.items():
                if slot_info["available"]:
                    available_slots.append({
                        "time": slot_time,
                        "service": slot_info["service"],
                        "duration": slot_info["duration"]
                    })
            
            return {
                "date": date,
                "available_slots": available_slots,
                "total_available": len(available_slots)
            }

    @tool("Get available services and pricing")
    def get_services(self) -> Dict:
        """
        Get list of available services with pricing and details.
        
        Returns:
            Service catalog information
        """
        logger.info("Retrieving service catalog")
        
        return {
            "services": self.services,
            "currency": "USD",
            "booking_policies": {
                "cancellation_window": "24 hours",
                "reschedule_window": "2 hours", 
                "deposit_required": False
            }
        }

    @tool_async("Create a new booking reservation")
    async def create_booking(
        self,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        date: str,
        time: str,
        service: str,
        special_requests: str = None
    ) -> Dict:
        """
        Create a new booking reservation.
        
        Args:
            customer_name: Customer full name
            customer_email: Customer email address
            customer_phone: Customer phone number
            date: Booking date (YYYY-MM-DD)
            time: Booking time (HH:MM)
            service: Service type key
            special_requests: Optional special requests
            
        Returns:
            Booking creation result
        """
        logger.info(f"Creating booking for {customer_name} on {date} at {time}")
        
        # Validate service
        if service not in self.services:
            return {
                "success": False,
                "error": "Invalid service type",
                "available_services": list(self.services.keys())
            }
        
        # Check availability
        availability = self.check_availability(date, time)
        if not availability.get("available", False):
            return {
                "success": False,
                "error": "Time slot not available",
                "availability": availability
            }
        
        # Simulate booking creation delay
        await asyncio.sleep(0.5)
        
        # Generate booking ID
        booking_id = f"BKG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create booking record
        booking = {
            "booking_id": booking_id,
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "phone": customer_phone
            },
            "appointment": {
                "date": date,
                "time": time,
                "service": service,
                "duration": self.services[service]["duration"],
                "price": self.services[service]["price"]
            },
            "special_requests": special_requests,
            "status": BookingStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "confirmation_code": f"CONF-{booking_id[-8:]}"
        }
        
        # Store booking
        self.active_bookings[booking_id] = booking
        
        # Mark time slot as unavailable
        if date in self.availability and time in self.availability[date]:
            self.availability[date][time]["available"] = False
            
        return {
            "success": True,
            "booking": booking,
            "message": f"Booking {booking_id} created successfully",
            "next_steps": "Please confirm this booking to finalize your reservation"
        }

    @tool_async("Confirm a pending booking")
    async def confirm_booking(self, booking_id: str) -> Dict:
        """
        Confirm a pending booking reservation.
        
        Args:
            booking_id: Booking identifier to confirm
            
        Returns:
            Confirmation result
        """
        logger.info(f"Confirming booking: {booking_id}")
        
        if booking_id not in self.active_bookings:
            return {
                "success": False,
                "error": "Booking not found",
                "booking_id": booking_id
            }
            
        booking = self.active_bookings[booking_id]
        
        if booking["status"] != BookingStatus.PENDING.value:
            return {
                "success": False,
                "error": f"Booking is already {booking['status']}",
                "current_status": booking["status"]
            }
        
        # Simulate confirmation processing
        await asyncio.sleep(0.3)
        
        # Update booking status
        booking["status"] = BookingStatus.CONFIRMED.value
        booking["confirmed_at"] = datetime.now().isoformat()
        
        # Generate calendar event details
        appointment_datetime = datetime.fromisoformat(f"{booking['appointment']['date']}T{booking['appointment']['time']}")
        
        confirmation_details = {
            "success": True,
            "booking_id": booking_id,
            "status": "confirmed",
            "confirmation_code": booking["confirmation_code"],
            "appointment_details": {
                "date": booking["appointment"]["date"],
                "time": booking["appointment"]["time"],
                "service": booking["appointment"]["service"],
                "duration": f"{booking['appointment']['duration']} minutes",
                "price": f"${booking['appointment']['price']:.2f}"
            },
            "customer": booking["customer"],
            "calendar_event": {
                "title": f"{self.services[booking['appointment']['service']]['name']} - {booking['customer']['name']}",
                "start_time": appointment_datetime.isoformat(),
                "end_time": (appointment_datetime + timedelta(minutes=booking['appointment']['duration'])).isoformat()
            }
        }
        
        return confirmation_details

    @tool("Cancel an existing booking")
    def cancel_booking(self, booking_id: str, reason: str = None) -> Dict:
        """
        Cancel an existing booking.
        
        Args:
            booking_id: Booking identifier to cancel
            reason: Optional cancellation reason
            
        Returns:
            Cancellation result
        """
        logger.info(f"Cancelling booking: {booking_id}")
        
        if booking_id not in self.active_bookings:
            return {
                "success": False,
                "error": "Booking not found"
            }
            
        booking = self.active_bookings[booking_id]
        
        if booking["status"] == BookingStatus.CANCELLED.value:
            return {
                "success": False,
                "error": "Booking is already cancelled"
            }
        
        # Check cancellation policy (24 hours)
        appointment_datetime = datetime.fromisoformat(f"{booking['appointment']['date']}T{booking['appointment']['time']}")
        hours_until_appointment = (appointment_datetime - datetime.now()).total_seconds() / 3600
        
        if hours_until_appointment < 24:
            return {
                "success": False,
                "error": "Cancellation not allowed within 24 hours of appointment",
                "hours_until_appointment": round(hours_until_appointment, 1),
                "policy": "24-hour cancellation policy"
            }
        
        # Cancel the booking
        booking["status"] = BookingStatus.CANCELLED.value
        booking["cancelled_at"] = datetime.now().isoformat()
        booking["cancellation_reason"] = reason
        
        # Free up the time slot
        date = booking["appointment"]["date"]
        time = booking["appointment"]["time"]
        if date in self.availability and time in self.availability[date]:
            self.availability[date][time]["available"] = True
            
        return {
            "success": True,
            "booking_id": booking_id,
            "status": "cancelled",
            "refund_eligible": True,
            "message": "Booking cancelled successfully"
        }

    @tool("Reschedule an existing booking")
    def reschedule_booking(
        self,
        booking_id: str,
        new_date: str,
        new_time: str
    ) -> Dict:
        """
        Reschedule an existing booking to a new date and time.
        
        Args:
            booking_id: Booking identifier to reschedule
            new_date: New date (YYYY-MM-DD)
            new_time: New time (HH:MM)
            
        Returns:
            Reschedule result
        """
        logger.info(f"Rescheduling booking {booking_id} to {new_date} {new_time}")
        
        if booking_id not in self.active_bookings:
            return {
                "success": False,
                "error": "Booking not found"
            }
            
        booking = self.active_bookings[booking_id]
        
        # Check availability for new slot
        availability = self.check_availability(new_date, new_time)
        if not availability.get("available", False):
            return {
                "success": False,
                "error": "New time slot not available",
                "availability": availability
            }
        
        # Free up old slot
        old_date = booking["appointment"]["date"]
        old_time = booking["appointment"]["time"]
        if old_date in self.availability and old_time in self.availability[old_date]:
            self.availability[old_date][old_time]["available"] = True
        
        # Book new slot
        if new_date in self.availability and new_time in self.availability[new_date]:
            self.availability[new_date][new_time]["available"] = False
        
        # Update booking
        booking["appointment"]["date"] = new_date
        booking["appointment"]["time"] = new_time
        booking["rescheduled_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "booking_id": booking_id,
            "old_appointment": {"date": old_date, "time": old_time},
            "new_appointment": {"date": new_date, "time": new_time},
            "message": "Booking rescheduled successfully"
        }

    @tool("Get booking details by ID or confirmation code")
    def get_booking(self, identifier: str) -> Dict:
        """
        Get booking details by booking ID or confirmation code.
        
        Args:
            identifier: Booking ID or confirmation code
            
        Returns:
            Booking details
        """
        logger.info(f"Retrieving booking: {identifier}")
        
        # Search by booking ID first
        if identifier in self.active_bookings:
            return {
                "found": True,
                "booking": self.active_bookings[identifier]
            }
        
        # Search by confirmation code
        for booking_id, booking in self.active_bookings.items():
            if booking["confirmation_code"] == identifier:
                return {
                    "found": True,
                    "booking": booking
                }
        
        return {
            "found": False,
            "error": "Booking not found",
            "searched_for": identifier
        }

    # Event handlers
    def on_conversation_started(self, conversation_id: str) -> None:
        """Handle conversation started events."""
        logger.info(f"📅 Booking agent ready: {conversation_id}")
        print("Booking agent is ready to help with appointments!")
        print("Available services: consultations, full service sessions")

    def on_conversation_ended(self, conversation_id: str) -> None:
        """Handle conversation ended events."""
        logger.info(f"Booking conversation ended: {conversation_id}")
        print("Thank you for using our booking service!")

    def on_tool_called(self, tool_call) -> None:
        """Handle tool call events."""
        logger.info(f"🔧 Executing booking tool: {tool_call.tool_name}")

    def on_error(self, error_type: str, error_message: str, details: Dict) -> None:
        """Handle error events including circuit breaker."""
        logger.error(f"❌ Booking agent error ({error_type}): {error_message}")

        if error_type in ["AUTH_FAILED", "CUSTOMER_SUSPENDED"]:
            print(f"🚫 Booking service unavailable: {error_message}")
            print("📧 Please contact support")
        else:
            print(f"⚠️  Temporary issue: {error_message}")
            print("🔄 Reconnecting automatically...")
