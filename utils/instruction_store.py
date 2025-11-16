#!/usr/bin/env python3
"""Instruction store with proper state management (no globals)"""

import logging
import threading
from typing import Optional, Dict
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Context state keys
STATE_INSTRUCTION_STEP = "instruction_step"
STATE_INSTRUCTION_DATA = "instruction_data"


class InstructionManager:
    """Manage instruction/wizard state without global variables"""
    
    # Valid instruction types
    INSTRUCTION_TYPES = ["ban_user", "unban_user", "send_alert", "create_backup"]
    
    def __init__(self):
        self._lock = threading.RLock()  # Thread-safe access

    def start_instruction(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        instruction_type: str,
        initial_data: dict = None
    ) -> bool:
        """
        Start an instruction/wizard
        
        Args:
            context: Telegram context
            instruction_type: Type of instruction
            initial_data: Initial data for instruction
        
        Returns:
            True if started successfully
        """
        try:
            if instruction_type not in self.INSTRUCTION_TYPES:
                logger.error(f"Invalid instruction type: {instruction_type}")
                return False
            
            if not context.user_data:
                context.user_data = {}
            
            with self._lock:
                context.user_data[STATE_INSTRUCTION_STEP] = 0
                context.user_data[STATE_INSTRUCTION_DATA] = {
                    "type": instruction_type,
                    "data": initial_data or {},
                    "started_at": self._get_timestamp()
                }
            
            logger.info(f"Started instruction: {instruction_type}")
            return True
        
        except Exception as e:
            logger.error(f"Error starting instruction: {e}")
            return False

    def get_instruction(self, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
        """
        Get current instruction
        
        Returns:
            Instruction data or None
        """
        if not context.user_data:
            return None
        
        with self._lock:
            instruction = context.user_data.get(STATE_INSTRUCTION_DATA)
            if instruction:
                return instruction.copy()
            return None

    def get_instruction_step(self, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Get current instruction step"""
        if not context.user_data:
            return 0
        
        with self._lock:
            return context.user_data.get(STATE_INSTRUCTION_STEP, 0)

    def set_instruction_step(self, context: ContextTypes.DEFAULT_TYPE, step: int) -> bool:
        """
        Set instruction step
        
        Args:
            context: Telegram context
            step: Step number
        
        Returns:
            True if successful
        """
        try:
            if step < 0:
                logger.warning(f"Invalid step: {step}, using 0")
                step = 0
            
            if not context.user_data:
                context.user_data = {}
            
            with self._lock:
                context.user_data[STATE_INSTRUCTION_STEP] = step
            
            logger.debug(f"Set instruction step: {step}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting instruction step: {e}")
            return False

    def update_instruction_data(self, context: ContextTypes.DEFAULT_TYPE, updates: dict) -> bool:
        """
        Update instruction data
        
        Args:
            context: Telegram context
            updates: Dictionary with updates
        
        Returns:
            True if successful
        """
        try:
            if not isinstance(updates, dict):
                logger.error("Updates must be dict")
                return False
            
            if not context.user_data:
                context.user_data = {}
            
            with self._lock:
                instruction = context.user_data.get(STATE_INSTRUCTION_DATA)
                if not instruction:
                    logger.warning("No active instruction")
                    return False
                
                instruction["data"].update(updates)
                logger.debug(f"Updated instruction data: {list(updates.keys())}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error updating instruction data: {e}")
            return False

    def get_instruction_data(self, context: ContextTypes.DEFAULT_TYPE, key: str, default=None):
        """
        Get specific instruction data field
        
        Args:
            context: Telegram context
            key: Field key
            default: Default value if not found
        
        Returns:
            Field value or default
        """
        if not context.user_data:
            return default
        
        with self._lock:
            instruction = context.user_data.get(STATE_INSTRUCTION_DATA)
            if not instruction:
                return default
            
            return instruction.get("data", {}).get(key, default)

    def cancel_instruction(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Cancel current instruction
        
        Returns:
            True if cancelled successfully
        """
        try:
            if not context.user_data:
                return False
            
            with self._lock:
                if STATE_INSTRUCTION_STEP in context.user_data:
                    del context.user_data[STATE_INSTRUCTION_STEP]
                if STATE_INSTRUCTION_DATA in context.user_data:
                    del context.user_data[STATE_INSTRUCTION_DATA]
            
            logger.info("Cancelled instruction")
            return True
        
        except Exception as e:
            logger.error(f"Error cancelling instruction: {e}")
            return False

    def is_active(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if instruction is active"""
        if not context.user_data:
            return False
        
        with self._lock:
            return STATE_INSTRUCTION_DATA in context.user_data

    def get_status(self, context: ContextTypes.DEFAULT_TYPE) -> dict:
        """Get instruction status"""
        if not context.user_data:
            return {"active": False}
        
        with self._lock:
            instruction = context.user_data.get(STATE_INSTRUCTION_DATA)
            if not instruction:
                return {"active": False}
            
            return {
                "active": True,
                "type": instruction.get("type"),
                "step": context.user_data.get(STATE_INSTRUCTION_STEP, 0),
                "started_at": instruction.get("started_at"),
                "data_keys": list(instruction.get("data", {}).keys())
            }
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp"""
        from datetime import datetime
        from config import TIMEZONE
        return datetime.now(TIMEZONE).isoformat()


class BanInstructionHelper:
    """Helper for ban user instruction"""
    
    STEP_ASK_USER_ID = 0
    STEP_ASK_REASON = 1
    STEP_CONFIRM = 2
    STEP_DONE = 3
    
    @staticmethod
    def validate_user_id(user_id_str: str) -> bool:
        """Validate user ID"""
        try:
            user_id = int(user_id_str)
            return user_id > 0
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_reason(reason: str) -> bool:
        """Validate ban reason"""
        if not reason or not isinstance(reason, str):
            return False
        reason = reason.strip()
        return 3 <= len(reason) <= 500


class UnbanInstructionHelper:
    """Helper for unban user instruction"""
    
    STEP_ASK_USER_ID = 0
    STEP_CONFIRM = 1
    STEP_DONE = 2
    
    @staticmethod
    def validate_user_id(user_id_str: str) -> bool:
        """Validate user ID"""
        try:
            user_id = int(user_id_str)
            return user_id > 0
        except (ValueError, TypeError):
            return False


class BackupInstructionHelper:
    """Helper for backup instruction"""
    
    STEP_CONFIRM = 0
    STEP_RUNNING = 1
    STEP_DONE = 2
    
    @staticmethod
    def validate_backup_type(backup_type: str) -> bool:
        """Validate backup type"""
        valid_types = ["full", "files"]
        return backup_type in valid_types


# Global instance (singleton)
instruction_manager = InstructionManager()
