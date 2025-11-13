import os
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sw import SW
from ynab import YNABClient
from utils import setup_environment_vars
from state_manager import StateManager

class ynab_splitwise_transfer():
    def __init__(self, sw_consumer_key, sw_consumer_secret,sw_api_key, 
                    ynab_personal_access_token, ynab_budget_name, ynab_account_name,
                    ynab_to_sw_flag_color=None, sw_group_name=None, user_timezone='Australia/Sydney') -> None:
        # Set up logging first
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Set user timezone (default to Sydney, Australia)
        self.user_timezone = ZoneInfo(user_timezone)
        self.logger.info(f"Using timezone: {user_timezone}")
        
        try:
            self.sw = SW(sw_consumer_key, sw_consumer_secret, sw_api_key)
            self.logger.info("Successfully initialized Splitwise client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Splitwise client: {e}")
            raise
        
        try:
            self.ynab = YNABClient(ynab_personal_access_token)
            self.logger.info("Successfully initialized YNAB client")
        except Exception as e:
            self.logger.error(f"Failed to initialize YNAB client: {e}")
            raise

        try:
            self.ynab_budget_id = self.ynab.get_budget_id(ynab_budget_name)
            if not self.ynab_budget_id:
                raise ValueError(f"Budget '{ynab_budget_name}' not found")
            self.logger.info(f"Found YNAB budget '{ynab_budget_name}' with ID: {self.ynab_budget_id}")
        except Exception as e:
            self.logger.error(f"Failed to get YNAB budget ID: {e}")
            raise
            
        try:
            self.ynab_account_id = self.ynab.get_account_id(self.ynab_budget_id, ynab_account_name)
            if not self.ynab_account_id:
                raise ValueError(f"Account '{ynab_account_name}' not found in budget '{ynab_budget_name}'")
            self.logger.info(f"Found YNAB account '{ynab_account_name}' with ID: {self.ynab_account_id}")
        except Exception as e:
            self.logger.error(f"Failed to get YNAB account ID: {e}")
            raise

        # Initialize state managers
        self.state_manager = StateManager(user_timezone=user_timezone)  # For SW to YNAB sync
        self.ynab_to_sw_state_manager = StateManager('ynab_to_sw_state.json', user_timezone=user_timezone)  # For YNAB to SW sync

        # timestamps - use current time in user's timezone
        self.end_date = datetime.now(self.user_timezone)
        self.logger.info(f"Current time in {user_timezone}: {self.end_date}")
        self.sw_start_date = self.state_manager.get_sync_start_date(self.end_date)
        self.logger.info(f"Syncing from {self.sw_start_date} to {self.end_date}")
        
        # YNAB to SW configuration
        self.ynab_to_sw_flag_color = ynab_to_sw_flag_color
        self.sw_group_name = sw_group_name
        self.sw_group_id = None
        if sw_group_name:
            try:
                self.sw_group_id = self.sw.get_group_id_by_name(sw_group_name)
                if self.sw_group_id:
                    self.logger.info(f"Found Splitwise group '{sw_group_name}' with ID: {self.sw_group_id}")
                else:
                    self.logger.warning(f"Splitwise group '{sw_group_name}' not found!")
            except Exception as e:
                self.logger.error(f"Failed to get Splitwise group ID: {e}")
                # Don't raise here, as YNAB->SW sync is optional

    def sw_to_ynab(self):
        """Sync transactions from Splitwise to YNAB."""
        self.logger.info("=" * 60)
        self.logger.info("Starting Splitwise → YNAB sync")
        self.logger.info("=" * 60)
        self.logger.info(f"Sync window: {self.sw_start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} to {self.end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        try:
            # Use updated_after to fetch expenses that were created or modified since last sync.
            # This ensures we catch expenses created from YNAB→Splitwise sync, even if their
            # original date is older than our sync window.
            # For example: A YNAB transaction dated 3 days ago is flagged today. When we create
            # it in Splitwise, it gets date=3 days ago. Using updated_after catches it because
            # it was just created/updated today.
            # Duplicates are prevented by tracking synced expense IDs in state_manager.
            updated_after_str = self.sw_start_date.isoformat()
            
            self.logger.info(f"Fetching Splitwise expenses updated after {updated_after_str}")
            expenses = self.sw.get_expenses(updated_after=updated_after_str)
            self.logger.info(f"Retrieved {len(expenses) if expenses else 0} expense(s) from Splitwise")
        except Exception as e:
            self.logger.error(f"Failed to fetch Splitwise expenses: {e}")
            raise

        if expenses:
            # Get already synced expense IDs to prevent duplicates
            synced_expense_ids = self.state_manager.get_synced_expense_ids()
            self.logger.info(f"Already synced expense IDs count: {len(synced_expense_ids)}")
            
            # process
            ynab_transactions = []
            newly_synced_expense_ids = []
            for expense in expenses:
                # don't import deleted expenses
                if expense['deleted_time']:
                    self.logger.debug(f"Skipping deleted expense {expense.get('id')}")
                    continue
                
                # Skip already synced expenses to prevent duplicates
                expense_id = expense.get('id')
                if expense_id in synced_expense_ids:
                    self.logger.debug(f"Skipping already synced expense {expense_id}")
                    continue
                
                self.logger.info(f"Processing new expense: ID={expense_id}, Date={expense['date']}, Amount=${expense['amount']:.2f}, Description={expense['description']}")
                transaction = {
                                "account_id": self.ynab_account_id,
                                "date":expense['date'],
                                "amount":int(expense['amount']*1000),
                                "payee_name":expense['description'].strip(),
                                #"memo":" ".join([expense['description'].strip() ,"with", combine_names(expense['users'])]),
                                "cleared": "cleared"
                            }
                ynab_transactions.append(transaction)
                newly_synced_expense_ids.append(expense_id)
            
            # export to ynab
            if ynab_transactions:
                self.logger.info(f"Creating {len(ynab_transactions)} transaction(s) in YNAB...")
                try:
                    response = self.ynab.create_transaction(self.ynab_budget_id, ynab_transactions)
                    self.logger.info(f"Successfully created transactions in YNAB")
                    
                    # Track synced expense IDs to prevent duplicates
                    if newly_synced_expense_ids:
                        self.state_manager.add_synced_expense_ids(newly_synced_expense_ids)
                        self.logger.info(f"Tracked {len(newly_synced_expense_ids)} new expense IDs")
                    
                    # Save the successful sync date
                    self.state_manager.save_last_sync_date(self.end_date)
                    self.logger.info("Successfully synced transactions and saved state.")
                except Exception as e:
                    self.logger.error(f"Failed to create transactions in YNAB: {e}")
                    raise
            else:
                self.logger.info("No new transactions to write to YNAB.")
                # Still update the state even if no transactions, to avoid re-checking same date range
                self.state_manager.save_last_sync_date(self.end_date)
        else:
            self.logger.info("No transactions to write to YNAB.")
            # Still update the state even if no transactions, to avoid re-checking same date range
            self.state_manager.save_last_sync_date(self.end_date)
        
        self.logger.info("Splitwise → YNAB sync completed")
        self.logger.info("=" * 60)
    
    def ynab_to_sw(self):
        """Sync YNAB flagged transactions to Splitwise."""
        self.logger.info("=" * 60)
        self.logger.info("Starting YNAB → Splitwise sync")
        self.logger.info("=" * 60)
        
        if not self.ynab_to_sw_flag_color:
            self.logger.info("YNAB to Splitwise sync not configured (no flag color specified).")
            self.logger.info("=" * 60)
            return
        
        if not self.sw_group_id:
            self.logger.error(f"Cannot sync to Splitwise: group '{self.sw_group_name}' not found.")
            self.logger.info("=" * 60)
            return
        
        self.logger.info(f"Configuration: Flag color={self.ynab_to_sw_flag_color}, Splitwise group={self.sw_group_name}")
        
        # Get start date for sync
        ynab_start_date = self.ynab_to_sw_state_manager.get_sync_start_date(self.end_date)
        self.logger.info(f"Sync window: {ynab_start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} to {self.end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        try:
            # Get all transactions since last sync
            # YNAB API expects date in YYYY-MM-DD format
            since_date_str = ynab_start_date.strftime('%Y-%m-%d')
            self.logger.info(f"Fetching YNAB transactions since {since_date_str}")
            
            transactions = self.ynab.get_transactions(
                self.ynab_budget_id, 
                since_date=since_date_str
            )
            
            self.logger.info(f"Retrieved {len(transactions)} transaction(s) from YNAB")
            
            # Get already synced transaction IDs
            synced_ids = self.ynab_to_sw_state_manager.get_synced_transaction_ids()
            self.logger.info(f"Already synced transaction IDs count: {len(synced_ids)}")
            
            # Filter for flagged transactions that haven't been synced
            flagged_transactions = [
                t for t in transactions 
                if t.get('flag_color') == self.ynab_to_sw_flag_color 
                and t['id'] not in synced_ids
                and not t.get('deleted')  # Skip deleted transactions
            ]
            
            if not flagged_transactions:
                self.logger.info(f"No new {self.ynab_to_sw_flag_color}-flagged transactions to sync.")
                # Still update the state to avoid re-checking
                self.ynab_to_sw_state_manager.save_last_sync_date(self.end_date)
                self.logger.info("=" * 60)
                return
            
            self.logger.info(f"Found {len(flagged_transactions)} {self.ynab_to_sw_flag_color}-flagged transaction(s) to sync.")
            
            # Process each transaction
            successfully_synced = []
            failed_count = 0
            for transaction in flagged_transactions:
                try:
                    # Get transaction details
                    txn_id = transaction['id']
                    payee_name = transaction.get('payee_name') or 'Expense'
                    amount = transaction['amount'] / 1000.0  # Convert from milliunits to dollars
                    date = transaction['date']
                    
                    self.logger.info(f"Processing transaction: ID={txn_id}, Payee={payee_name}, Amount=${abs(amount):.2f}, Date={date}")
                    
                    # Create expense in Splitwise
                    self.logger.info(f"Creating Splitwise expense...")
                    expense = self.sw.create_expense(
                        group_id=self.sw_group_id,
                        description=payee_name,
                        amount=amount,
                        date=date
                    )
                    
                    expense_id = expense.getId()
                    self.logger.info(f"Successfully created Splitwise expense with ID: {expense_id}")
                    
                    # Clear the flag in YNAB (set to null)
                    try:
                        self.logger.info(f"Clearing {self.ynab_to_sw_flag_color} flag for YNAB transaction {txn_id}")
                        self.ynab.update_transaction(
                            self.ynab_budget_id,
                            txn_id,
                            {'flag_color': None}
                        )
                        self.logger.info(f"Successfully cleared flag for transaction {txn_id}")
                    except Exception as flag_error:
                        self.logger.warning(f"Failed to clear flag for transaction {txn_id}: {flag_error}")
                        self.logger.warning("The expense was created in Splitwise, but you'll need to manually clear the flag in YNAB")
                        # Continue anyway - the expense was created
                    
                    successfully_synced.append(txn_id)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"Failed to sync transaction {transaction.get('id', 'unknown')}: {e}")
                    self.logger.error(f"Transaction details: {transaction}")
                    # Continue with next transaction
                    continue
            
            # Update state with successfully synced transactions
            if successfully_synced:
                self.ynab_to_sw_state_manager.add_synced_transaction_ids(successfully_synced)
                self.logger.info(f"Successfully synced {len(successfully_synced)} transaction(s) to Splitwise.")
            
            if failed_count > 0:
                self.logger.warning(f"Failed to sync {failed_count} transaction(s). Check logs above for details.")
            
            # Update last sync date
            self.ynab_to_sw_state_manager.save_last_sync_date(self.end_date)
            self.logger.info("YNAB → Splitwise sync completed.")
            
        except Exception as e:
            self.logger.error(f"Error during YNAB to Splitwise sync: {e}")
            self.logger.error("Full error details:", exc_info=True)
            raise
        
        self.logger.info("=" * 60)


if __name__=="__main__":
    # load environment variables from yaml file (locally)
    setup_environment_vars()

    # splitwise creds
    sw_consumer_key = os.environ.get('sw_consumer_key')
    sw_consumer_secret = os.environ.get('sw_consumer_secret')
    sw_api_key = os.environ.get('sw_api_key')

    # ynab creds
    ynab_budget_name = os.environ.get('ynab_budget_name')
    ynab_account_name = os.environ.get('ynab_account_name')
    ynab_personal_access_token = os.environ.get('ynab_personal_access_token')
    
    # ynab to splitwise config
    ynab_to_sw_flag_color = os.environ.get('ynab_to_sw_flag_color', 'blue')  # Default to 'blue'
    sw_group_name = os.environ.get('sw_group_name', 'Kate & Tom')  # Default to 'Kate & Tom'
    
    # timezone config (default to Sydney, Australia)
    user_timezone = os.environ.get('user_timezone', 'Australia/Sydney')

    try:
        a = ynab_splitwise_transfer(sw_consumer_key, sw_consumer_secret,
                                    sw_api_key, ynab_personal_access_token,
                                    ynab_budget_name, ynab_account_name,
                                    ynab_to_sw_flag_color, sw_group_name,
                                    user_timezone)

        # ynab to splitwise (run first to create expenses in SW)
        a.ynab_to_sw()
        
        # splitwise to ynab (run second to pull back the split amounts)
        a.sw_to_ynab()
        
        logging.info("All syncs completed successfully!")
    except Exception as e:
        logging.error(f"Sync failed with error: {e}")
        logging.error("Full error details:", exc_info=True)
        raise
