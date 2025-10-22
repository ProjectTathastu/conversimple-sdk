"""Customer service agent definition for dispatcher-managed sessions."""

import asyncio
import aiofiles
import aiohttp
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from conversimple import ConversimpleAgent, tool, tool_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CustomerServiceAgent(ConversimpleAgent):
    """
    Advanced customer service agent with multiple business tools.
    
    Demonstrates:
    - Multiple sync and async tools
    - State management across tool calls  
    - External API integration
    - File operations
    - Error handling and recovery
    - Complex business logic
    """

    agent_id = "example-customer-service-agent"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Agent state management
        self.customer_sessions: Dict[str, Dict] = {}
        self.active_tickets: Dict[str, Dict] = {}
        
        # Mock customer database
        self.customer_db = {
            "cust_123": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1-555-0123", 
                "account_type": "premium",
                "balance": 1250.50,
                "recent_orders": ["ORD-001", "ORD-002"]
            },
            "cust_456": {
                "name": "Jane Smith",
                "email": "jane@example.com",
                "phone": "+1-555-0456",
                "account_type": "standard", 
                "balance": 45.75,
                "recent_orders": ["ORD-003"]
            }
        }

    @tool("Look up customer information by ID or email")
    def lookup_customer(self, identifier: str) -> Dict:
        """
        Look up customer information by customer ID or email.
        
        Args:
            identifier: Customer ID or email address
            
        Returns:
            Customer information dictionary
        """
        logger.info(f"Looking up customer: {identifier}")
        
        # Search by customer ID first
        if identifier in self.customer_db:
            customer = self.customer_db[identifier].copy()
            customer["customer_id"] = identifier
            return customer
            
        # Search by email
        for cust_id, customer in self.customer_db.items():
            if customer.get("email") == identifier:
                result = customer.copy()
                result["customer_id"] = cust_id
                return result
                
        return {"error": "Customer not found", "searched_for": identifier}

    @tool("Get customer account balance and recent transactions")
    def get_account_balance(self, customer_id: str) -> Dict:
        """
        Get customer account balance and recent transaction history.
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            Account balance and transaction information
        """
        logger.info(f"Getting account balance for: {customer_id}")
        
        customer = self.customer_db.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}
            
        # Simulate transaction history
        transactions = [
            {"date": "2025-01-20", "amount": -50.00, "description": "Online purchase"},
            {"date": "2025-01-18", "amount": 100.00, "description": "Account credit"},
            {"date": "2025-01-15", "amount": -25.50, "description": "Subscription fee"}
        ]
        
        return {
            "customer_id": customer_id,
            "current_balance": customer["balance"],
            "account_type": customer["account_type"],
            "recent_transactions": transactions
        }

    @tool_async("Create a support ticket for the customer")
    async def create_support_ticket(
        self, 
        customer_id: str, 
        issue_type: str, 
        description: str,
        priority: str = "normal"
    ) -> Dict:
        """
        Create a new support ticket for the customer.
        
        Args:
            customer_id: Customer identifier
            issue_type: Type of issue (billing, technical, general)
            description: Detailed description of the issue
            priority: Priority level (low, normal, high, urgent)
            
        Returns:
            Created ticket information
        """
        logger.info(f"Creating support ticket for customer: {customer_id}")
        
        # Simulate async ticket creation
        await asyncio.sleep(0.5)  # Simulate API delay
        
        ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        ticket = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "issue_type": issue_type,
            "description": description,
            "priority": priority,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "estimated_resolution": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        # Store in active tickets
        self.active_tickets[ticket_id] = ticket
        
        return {
            "success": True,
            "ticket": ticket,
            "message": f"Support ticket {ticket_id} created successfully"
        }

    @tool_async("Send email notification to customer")
    async def send_email_notification(
        self,
        customer_id: str,
        subject: str, 
        message: str,
        email_type: str = "general"
    ) -> Dict:
        """
        Send email notification to customer.
        
        Args:
            customer_id: Customer identifier
            subject: Email subject line
            message: Email message content
            email_type: Type of email (general, billing, technical)
            
        Returns:
            Email sending result
        """
        logger.info(f"Sending email to customer: {customer_id}")
        
        customer = self.customer_db.get(customer_id)
        if not customer:
            return {"success": False, "error": "Customer not found"}
            
        # Simulate async email sending
        await asyncio.sleep(0.3)
        
        email_id = f"EMAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # In production, this would integrate with actual email service
        email_result = {
            "success": True,
            "email_id": email_id,
            "recipient": customer["email"],
            "subject": subject,
            "sent_at": datetime.now().isoformat(),
            "delivery_status": "sent"
        }
        
        return email_result

    @tool("Process refund request for customer")  
    def process_refund(
        self,
        customer_id: str,
        order_id: str,
        amount: float,
        reason: str
    ) -> Dict:
        """
        Process refund request for a customer order.
        
        Args:
            customer_id: Customer identifier
            order_id: Order ID to refund
            amount: Refund amount
            reason: Reason for refund
            
        Returns:
            Refund processing result
        """
        logger.info(f"Processing refund for customer {customer_id}, order {order_id}")
        
        customer = self.customer_db.get(customer_id)
        if not customer:
            return {"success": False, "error": "Customer not found"}
            
        # Validate order belongs to customer
        if order_id not in customer["recent_orders"]:
            return {"success": False, "error": "Order not found for this customer"}
            
        # Process refund (simulate business logic)
        refund_id = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Update customer balance
        customer["balance"] += amount
        
        refund_result = {
            "success": True,
            "refund_id": refund_id,
            "customer_id": customer_id,
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "processed_at": datetime.now().isoformat(),
            "new_balance": customer["balance"],
            "estimated_arrival": "3-5 business days"
        }
        
        return refund_result

    @tool_async("Get real-time order status from external system")
    async def get_order_status(self, order_id: str) -> Dict:
        """
        Get real-time order status from external order management system.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Current order status and tracking information
        """
        logger.info(f"Fetching order status: {order_id}")
        
        # Simulate external API call
        await asyncio.sleep(0.4)
        
        # Mock order status data
        order_statuses = {
            "ORD-001": {
                "status": "delivered",
                "tracking_number": "1Z999AA1234567890",
                "estimated_delivery": "2025-01-25",
                "current_location": "Customer delivered"
            },
            "ORD-002": {
                "status": "in_transit", 
                "tracking_number": "1Z999AA1234567891",
                "estimated_delivery": "2025-01-28",
                "current_location": "Distribution center - Chicago, IL"
            },
            "ORD-003": {
                "status": "processing",
                "tracking_number": None,
                "estimated_delivery": "2025-01-30", 
                "current_location": "Fulfillment center"
            }
        }
        
        if order_id in order_statuses:
            return {
                "order_id": order_id,
                "found": True,
                **order_statuses[order_id]
            }
        else:
            return {
                "order_id": order_id,
                "found": False,
                "error": "Order not found in system"
            }

    @tool_async("Save conversation summary to customer file")
    async def save_conversation_summary(
        self,
        customer_id: str,
        summary: str,
        resolution: str = None
    ) -> Dict:
        """
        Save conversation summary to customer's file.
        
        Args:
            customer_id: Customer identifier
            summary: Conversation summary
            resolution: Resolution details if applicable
            
        Returns:
            File save result
        """
        logger.info(f"Saving conversation summary for customer: {customer_id}")
        
        # Create conversation record
        conversation_record = {
            "customer_id": customer_id,
            "timestamp": datetime.now().isoformat(),
            "agent": "customer_service",
            "summary": summary,
            "resolution": resolution,
            "conversation_id": self.conversation_id
        }
        
        # Save to file (simulate customer records system)
        filename = f"customer_records_{customer_id}_{datetime.now().strftime('%Y%m%d')}.json"
        
        try:
            async with aiofiles.open(filename, 'a') as f:
                await f.write(json.dumps(conversation_record) + '\n')
                
            return {
                "success": True,
                "filename": filename,
                "saved_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to save conversation summary: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # Event handlers
    def on_conversation_started(self, conversation_id: str) -> None:
        """Handle conversation started events."""
        logger.info(f"🎧 Customer service agent ready: {conversation_id}")
        print(f"Customer service agent is ready to help!")
        print("Available services: account lookup, billing, refunds, order tracking")

    def on_conversation_ended(self, conversation_id: str) -> None:
        """Handle conversation ended events."""
        logger.info(f"Customer service conversation ended: {conversation_id}")
        print("Thank you for contacting customer service. Have a great day!")

    def on_tool_called(self, tool_call) -> None:
        """Handle tool call events."""
        logger.info(f"🔧 Executing customer service tool: {tool_call.tool_name}")

    def on_error(self, error_type: str, error_message: str, details: Dict) -> None:
        """Handle error events including circuit breaker."""
        logger.error(f"❌ Customer service error ({error_type}): {error_message}")

        if error_type in ["AUTH_FAILED", "CUSTOMER_SUSPENDED"]:
            print(f"🚫 Service unavailable due to: {error_message}")
            print("📧 Please contact support for assistance")
        else:
            print(f"⚠️  Temporary issue: {error_message}")
            print("🔄 Service will reconnect automatically")

