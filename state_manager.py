import os
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

class StateManager:
    """Manages persistent state for tracking last successful sync date."""
    
    STATE_FILE = 'sync_state.json'
    DEFAULT_LOOKBACK_DAYS = 7
    
    def __init__(self, state_file=None, user_timezone='Australia/Sydney'):
        """Initialize the state manager.
        
        Args:
            state_file: Path to the state file. If None, uses STATE_FILE constant.
            user_timezone: Timezone string (e.g., 'Australia/Sydney'). Default is 'Australia/Sydney'.
        """
        self.state_file = state_file or self.STATE_FILE
        self.user_timezone = ZoneInfo(user_timezone)
        logger.info(f"StateManager initialized with timezone: {user_timezone}")
        
    def get_last_sync_date(self):
        """Get the last successful sync date.
        
        Returns:
            datetime: The last successful sync date in user's timezone, or None if no state exists.
        """
        if not os.path.exists(self.state_file):
            logger.info(f"State file {self.state_file} does not exist. No previous sync date found.")
            return None
            
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                last_sync = state.get('last_sync_date')
                if last_sync:
                    # Parse ISO format date string and convert to user's timezone
                    dt = datetime.fromisoformat(last_sync)
                    # If the datetime is naive, assume it's in user's timezone
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=self.user_timezone)
                    else:
                        # Convert to user's timezone
                        dt = dt.astimezone(self.user_timezone)
                    logger.info(f"Loaded last sync date: {dt}")
                    return dt
                return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Error reading state file: {e}. Will treat as no previous sync.")
            return None
    
    def save_last_sync_date(self, sync_date):
        """Save the last successful sync date.
        
        Args:
            sync_date: datetime object representing the sync date (should be timezone-aware).
        """
        # Ensure sync_date is timezone-aware
        if sync_date.tzinfo is None:
            sync_date = sync_date.replace(tzinfo=self.user_timezone)
        
        # Load existing state to preserve other fields
        state = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
            except (json.JSONDecodeError, ValueError):
                # File exists but is empty or invalid - start fresh
                state = {}
        
        state['last_sync_date'] = sync_date.isoformat()
        state['updated_at'] = datetime.now(self.user_timezone).isoformat()
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved last sync date: {sync_date.isoformat()}")
        except Exception as e:
            logger.error(f"Error saving state file: {e}")
            raise
    
    def get_sync_start_date(self, end_date=None):
        """Get the start date for syncing transactions.
        
        If a previous sync date exists, returns that date.
        Otherwise, returns a date DEFAULT_LOOKBACK_DAYS ago.
        
        Args:
            end_date: The end date for the sync (should be timezone-aware). If None, uses current date in user's timezone.
            
        Returns:
            datetime: The start date for syncing in user's timezone.
        """
        if end_date is None:
            end_date = datetime.now(self.user_timezone)
        
        # Ensure end_date is timezone-aware in user's timezone
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=self.user_timezone)
        else:
            end_date = end_date.astimezone(self.user_timezone)
        
        last_sync = self.get_last_sync_date()
        
        if last_sync:
            logger.info(f"Found previous sync date: {last_sync.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            # Start from the last sync time to catch any transactions added after the last sync
            # Duplicates will be prevented by tracking synced transaction/expense IDs
            start_date = last_sync
        else:
            logger.info(f"No previous sync found. Using default lookback of {self.DEFAULT_LOOKBACK_DAYS} days.")
            start_date = end_date - timedelta(days=self.DEFAULT_LOOKBACK_DAYS)
        
        logger.info(f"Sync start date: {start_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        return start_date
    
    def get_synced_transaction_ids(self):
        """Get the set of transaction IDs that have been synced.
        
        Returns:
            set: Set of synced transaction IDs.
        """
        if not os.path.exists(self.state_file):
            return set()
            
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                return set(state.get('synced_transaction_ids', []))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Error reading synced transaction IDs: {e}")
            return set()
    
    def add_synced_transaction_ids(self, transaction_ids):
        """Add transaction IDs to the synced set.
        
        Args:
            transaction_ids: List or set of transaction IDs to mark as synced.
        """
        try:
            # Load existing state
            state = {}
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, 'r') as f:
                        state = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    # File exists but is empty or invalid - start fresh
                    state = {}
            
            # Update synced IDs
            synced_ids = set(state.get('synced_transaction_ids', []))
            synced_ids.update(transaction_ids)
            state['synced_transaction_ids'] = list(synced_ids)
            state['updated_at'] = datetime.now(self.user_timezone).isoformat()
            
            # Save state
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Added {len(transaction_ids)} transaction IDs to synced set")
        except Exception as e:
            logger.error(f"Error saving synced transaction IDs: {e}")
            raise
    
    def get_synced_expense_ids(self):
        """Get the set of Splitwise expense IDs that have been synced.
        
        Returns:
            set: Set of synced Splitwise expense IDs (as strings).
        """
        if not os.path.exists(self.state_file):
            return set()
            
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                return set(state.get('synced_expense_ids', []))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Error reading synced expense IDs: {e}")
            return set()
    
    def add_synced_expense_ids(self, expense_ids):
        """Add Splitwise expense IDs to the synced set.
        
        Args:
            expense_ids: List or set of Splitwise expense IDs to mark as synced.
        """
        try:
            # Load existing state
            state = {}
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, 'r') as f:
                        state = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    # File exists but is empty or invalid - start fresh
                    state = {}
            
            # Update synced expense IDs
            synced_ids = set(state.get('synced_expense_ids', []))
            synced_ids.update(str(id) for id in expense_ids)
            state['synced_expense_ids'] = list(synced_ids)
            state['updated_at'] = datetime.now(self.user_timezone).isoformat()
            
            # Save state
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Added {len(expense_ids)} expense IDs to synced set")
        except Exception as e:
            logger.error(f"Error saving synced expense IDs: {e}")
            raise
