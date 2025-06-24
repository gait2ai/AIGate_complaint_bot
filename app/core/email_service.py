"""
AI Gate for Artificial Intelligence Applications
Email Service Module for Institution Complaint Management Bot.

This module provides a dedicated, robust email service for sending critical
complaint notifications. It integrates with the application's configuration
system and provides asynchronous email sending capabilities.
"""

import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config.config_model import EmailConfigModel, ComplaintData


class EmailService:
    """
    A dedicated email service for handling complaint notifications.
    
    This service encapsulates all email sending logic and provides a clean
    interface for sending critical complaint notifications with proper error
    handling and asynchronous execution.
    """
    
    def __init__(self, email_config: EmailConfigModel):
        """
        Initialize the EmailService with configuration.
        
        Args:
            email_config: EmailConfigModel instance containing SMTP settings,
                         templates, and credentials loaded from environment.
        """
        self.config = email_config
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if not self.config.sender_email or not self.config.sender_password:
            self.logger.error("SMTP credentials not found in environment variables")
            raise ValueError("SMTP credentials (SMTP_EMAIL, SMTP_PASSWORD) must be set in environment")
        
        self.logger.info(f"EmailService initialized with SMTP server: {self.config.smtp_server}:{self.config.smtp_port}")
    
    async def send_critical_complaint_email(self, data: ComplaintData, notification_email: str) -> bool:
        """
        Send a critical complaint notification email.
        
        Args:
            data: ComplaintData object containing user and complaint information
            notification_email: Email address(es) to send the notification to
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            self.logger.info(f"Preparing to send critical complaint email for user: {data.name}")
            
            # Prepare email content
            subject = self._build_subject()
            body = self._build_email_body(data)
            
            # Create email message
            message = self._create_email_message(
                subject=subject,
                body=body,
                to_email=notification_email
            )
            
            # Send email asynchronously
            await asyncio.to_thread(self._send_sync, message, notification_email)
            
            self.logger.info(f"Critical complaint email sent successfully to: {notification_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send critical complaint email: {str(e)}", exc_info=True)
            return False
    
    def _build_subject(self) -> str:
        """
        Build the email subject line using the configured template.
        
        Returns:
            str: Formatted subject line
        """
        # Use the critical_subject template from configuration
        # Note: institution_name placeholder can be filled if needed
        return self.config.templates.critical_subject.format(
            institution_name="BCFHD"  # This could be made configurable
        )
    
    def _build_email_body(self, data: ComplaintData) -> str:
        """
        Build the email body with complaint details.
        
        Args:
            data: ComplaintData object containing complaint information
            
        Returns:
            str: Formatted email body
        """
        # Build a comprehensive email body with all relevant information
        body = "CRITICAL COMPLAINT RECEIVED\n"
        body += "=" * 50 + "\n\n"
        
        # User information
        body += f"User Name: {data.name if data.name else 'Not provided'}\n"
        body += f"Phone Number: {data.phone if data.phone else 'Not provided'}\n"
        
        # Add additional user details if available
        if hasattr(data, 'email') and data.email:
            body += f"Email: {data.email}\n"
        
        if hasattr(data, 'sex') and data.sex:
            body += f"Gender: {data.sex}\n"
            
        if hasattr(data, 'department') and data.department:
            body += f"Department: {data.department}\n"
            
        if hasattr(data, 'position') and data.position:
            body += f"Position: {data.position}\n"
            
        if hasattr(data, 'complaint_type') and data.complaint_type:
            body += f"Complaint Type: {data.complaint_type}\n"
            
        # Location information
        if hasattr(data, 'governorate') and data.governorate:
            body += f"Governorate: {data.governorate}\n"
            
        if hasattr(data, 'directorate') and data.directorate:
            body += f"Directorate: {data.directorate}\n"
            
        if hasattr(data, 'village') and data.village:
            body += f"Village: {data.village}\n"
        
        body += "\n" + "=" * 50 + "\n"
        body += "COMPLAINT DETAILS:\n"
        body += "=" * 50 + "\n\n"
        
        # Main complaint text
        body += f"{data.original_complaint_text if data.original_complaint_text else 'No complaint text provided'}\n\n"
        
        # Add metadata if available
        if hasattr(data, 'complaint_id') and data.complaint_id:
            body += f"Complaint ID: {data.complaint_id}\n"
            
        if hasattr(data, 'submission_time') and data.submission_time:
            body += f"Submission Time: {data.submission_time}\n"
            
        if hasattr(data, 'sensitivity_score') and data.sensitivity_score:
            body += f"Sensitivity Score: {data.sensitivity_score}\n"
        
        body += "\n" + "=" * 50 + "\n"
        body += "This complaint has been flagged as CRITICAL and requires immediate attention.\n"
        body += "Please review and take appropriate action as soon as possible.\n"
        
        return body
    
    def _create_email_message(self, subject: str, body: str, to_email: str) -> MIMEMultipart:
        """
        Create a properly formatted email message.
        
        Args:
            subject: Email subject
            body: Email body content
            to_email: Recipient email address(es)
            
        Returns:
            MIMEMultipart: Configured email message
        """
        message = MIMEMultipart()
        message['From'] = f"{self.config.templates.sender_name} <{self.config.sender_email}>"
        message['To'] = to_email
        message['Subject'] = subject
        
        # Attach the body to the email
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        return message
    
    def _send_sync(self, message: MIMEMultipart, to_email: str) -> None:
        """
        Synchronous email sending function to be run in a separate thread.
        
        Args:
            message: Email message to send
            to_email: Recipient email address(es)
            
        Raises:
            Exception: If email sending fails
        """
        server = None
        try:
            # Create SMTP connection
            if self.config.use_ssl:
                server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port)
            else:
                server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
                if self.config.use_tls:
                    server.starttls()
            
            # Set timeout
            server.timeout = self.config.behavior.timeout
            
            # Login with credentials
            server.login(self.config.sender_email, self.config.sender_password)
            
            # Send the email
            text = message.as_string()
            server.sendmail(self.config.sender_email, to_email.split(','), text)
            
            self.logger.debug(f"Email sent successfully via {self.config.smtp_server}")
            
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP authentication failed: {str(e)}")
            raise Exception(f"Email authentication failed: {str(e)}")
            
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.error(f"SMTP recipients refused: {str(e)}")
            raise Exception(f"Email recipients refused: {str(e)}")
            
        except smtplib.SMTPServerDisconnected as e:
            self.logger.error(f"SMTP server disconnected: {str(e)}")
            raise Exception(f"SMTP server disconnected: {str(e)}")
            
        except smtplib.SMTPException as e:
            self.logger.error(f"SMTP error occurred: {str(e)}")
            raise Exception(f"SMTP error: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Unexpected error during email sending: {str(e)}")
            raise Exception(f"Failed to send email: {str(e)}")
            
        finally:
            # Ensure connection is closed
            if server:
                try:
                    server.quit()
                except Exception as e:
                    self.logger.warning(f"Error closing SMTP connection: {str(e)}")
    
    async def send_test_email(self, test_email: str) -> bool:
        """
        Send a test email to verify email configuration.
        
        Args:
            test_email: Email address to send test email to
            
        Returns:
            bool: True if test email was sent successfully, False otherwise
        """
        try:
            # Create test complaint data
            from types import SimpleNamespace
            test_data = SimpleNamespace()
            test_data.name = "Test User"
            test_data.phone = "+9671234567"
            test_data.original_complaint_text = "This is a test email to verify email configuration."
            
            # Send test email
            success = await self.send_critical_complaint_email(test_data, test_email)
            
            if success:
                self.logger.info("Test email sent successfully")
            else:
                self.logger.error("Test email failed to send")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Test email failed: {str(e)}")
            return False
    
    def validate_configuration(self) -> bool:
        """
        Validate the email configuration.
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        try:
            # Check required fields
            if not self.config.smtp_server:
                self.logger.error("SMTP server not configured")
                return False
                
            if not self.config.sender_email:
                self.logger.error("Sender email not configured")
                return False
                
            if not self.config.sender_password:
                self.logger.error("Sender password not configured")
                return False
                
            if not self.config.templates.critical_subject:
                self.logger.error("Critical subject template not configured")
                return False
            
            # Validate port range
            if not (1 <= self.config.smtp_port <= 65535):
                self.logger.error(f"Invalid SMTP port: {self.config.smtp_port}")
                return False
            
            self.logger.info("Email configuration validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {str(e)}")
            return False
