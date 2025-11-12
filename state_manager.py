import os
import json
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

class StateManager:
    """Manages persistent state for tracking last successful sync date."""
    
    STATE_FILE = 'sync_state.json'
    DEFAULT_LOOKBACK_DAYS = 7
    
    def __init__(self, state_file=None):
        """Initialize the state manager.
        
        Args:
            state_file: Path to the state file. If None, uses STATE_FILE constant.
        """
        self.state_file = state_file or self.STATE_FILE
        
    def get_last_sync_date(self):
        """Get the last successful sync date.
        
        Returns:
            datetime: The last successful sync date, or None if no state exists.
        """
        if not os.path.exists(self.state_file):
            logger.info(f"State file {self.state_file} does not exist. No previous sync date found.")
            return None
            
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                last_sync = state.get('last_sync_date')
                if last_sync:
                    # Parse ISO format date string
                    return datetime.fromisoformat(last_sync)
                return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Error reading state file: {e}. Will treat as no previous sync.")
            return None
    
    def save_last_sync_date(self, sync_date):
        """Save the last successful sync date.
        
        Args:
            sync_date: datetime object representing the sync date.
        """
        state = {
            'last_sync_date': sync_date.isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
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
            end_date: The end date for the sync. If None, uses current date.
            
        Returns:
            datetime: The start date for syncing.
        """
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        
        last_sync = self.get_last_sync_date()
        
        if last_sync:
            logger.info(f"Found previous sync date: {last_sync.isoformat()}")
            # Start from the last sync time to catch any transactions added after the last sync
            # Duplicates will be prevented by tracking synced transaction/expense IDs
            start_date = last_sync
        else:
            logger.info(f"No previous sync found. Using default lookback of {self.DEFAULT_LOOKBACK_DAYS} days.")
            start_date = end_date - timedelta(days=self.DEFAULT_LOOKBACK_DAYS)
        
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
            state['updated_at'] = datetime.now(timezone.utc).isoformat()
            
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
            state['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Save state
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Added {len(expense_ids)} expense IDs to synced set")
        except Exception as e:
            logger.error(f"Error saving synced expense IDs: {e}")
            raise
