import os
import logging
from datetime import datetime, timedelta, timezone

from sw import SW
from ynab import YNABClient
from utils import setup_environment_vars
from state_manager import StateManager

class ynab_splitwise_transfer():
    def __init__(self, sw_consumer_key, sw_consumer_secret,sw_api_key, 
                    ynab_personal_access_token, ynab_budget_name, ynab_account_name,
                    ynab_to_sw_flag_color=None, sw_group_name=None) -> None:
        self.sw = SW(sw_consumer_key, sw_consumer_secret, sw_api_key)
        self.ynab = YNABClient(ynab_personal_access_token)

        self.ynab_budget_id = self.ynab.get_budget_id(ynab_budget_name)
        self.ynab_account_id = self.ynab.get_account_id(self.ynab_budget_id, ynab_account_name)

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # Initialize state managers
        self.state_manager = StateManager()  # For SW to YNAB sync
        self.ynab_to_sw_state_manager = StateManager('ynab_to_sw_state.json')  # For YNAB to SW sync

        # timestamps
        now = datetime.now(timezone.utc)
        self.end_date = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        self.sw_start_date = self.state_manager.get_sync_start_date(self.end_date)
        
        # YNAB to SW configuration
        self.ynab_to_sw_flag_color = ynab_to_sw_flag_color
        self.sw_group_name = sw_group_name
        self.sw_group_id = None
        if sw_group_name:
            self.sw_group_id = self.sw.get_group_id_by_name(sw_group_name)
            if self.sw_group_id:
                self.logger.info(f"Found Splitwise group '{sw_group_name}' with ID: {self.sw_group_id}")
            else:
                self.logger.warning(f"Splitwise group '{sw_group_name}' not found!")

    def sw_to_ynab(self):
        self.logger.info("Moving transactions from Splitwise to YNAB...")
        self.logger.info(f"Getting all Splitwise expenses from {self.sw_start_date} to {self.end_date}")
        expenses = self.sw.get_expenses(dated_after=self.sw_start_date, dated_before=self.end_date)
        

        if expenses:
            # process
            ynab_transactions = []
            for expense in expenses:
                # don't import deleted expenses
                if expense['deleted_time']:
                    continue
                self.logger.info(expense)
                transaction = {
                                "account_id": self.ynab_account_id,
                                "date":expense['date'],
                                "amount":int(expense['amount']*1000),
                                "payee_name":expense['description'].strip(),
                                #"memo":" ".join([expense['description'].strip() ,"with", combine_names(expense['users'])]),
                                "cleared": "cleared"
                            }
                ynab_transactions.append(transaction)
            # export to ynab
            if ynab_transactions:
                self.logger.info(f"Writing {len(ynab_transactions)} record(s) to YNAB.")
                response = self.ynab.create_transaction(self.ynab_budget_id, ynab_transactions)
                # Save the successful sync date
                self.state_manager.save_last_sync_date(self.end_date)
                self.logger.info("Successfully synced transactions and saved state.")
            else:
                self.logger.info("No transactions to write to YNAB.")
                # Still update the state even if no transactions, to avoid re-checking same date range
                self.state_manager.save_last_sync_date(self.end_date)
        else:
            self.logger.info("No transactions to write to YNAB.")
            # Still update the state even if no transactions, to avoid re-checking same date range
            self.state_manager.save_last_sync_date(self.end_date)
    
    def ynab_to_sw(self):
        """Sync YNAB flagged transactions to Splitwise."""
        if not self.ynab_to_sw_flag_color:
            self.logger.info("YNAB to Splitwise sync not configured (no flag color specified).")
            return
        
        if not self.sw_group_id:
            self.logger.error(f"Cannot sync to Splitwise: group '{self.sw_group_name}' not found.")
            return
        
        self.logger.info("Moving flagged transactions from YNAB to Splitwise...")
        
        # Get start date for sync
        ynab_start_date = self.ynab_to_sw_state_manager.get_sync_start_date(self.end_date)
        self.logger.info(f"Getting YNAB transactions from {ynab_start_date.date()} to {self.end_date.date()}")
        
        try:
            # Get all transactions since last sync
            transactions = self.ynab.get_transactions(
                self.ynab_budget_id, 
                since_date=ynab_start_date.strftime('%Y-%m-%d')
            )
            
            # Get already synced transaction IDs
            synced_ids = self.ynab_to_sw_state_manager.get_synced_transaction_ids()
            
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
                return
            
            self.logger.info(f"Found {len(flagged_transactions)} {self.ynab_to_sw_flag_color}-flagged transactions to sync.")
            
            # Process each transaction
            successfully_synced = []
            for transaction in flagged_transactions:
                try:
                    # Get transaction details
                    txn_id = transaction['id']
                    payee_name = transaction.get('payee_name') or 'Expense'
                    amount = transaction['amount'] / 1000.0  # Convert from milliunits to dollars
                    date = transaction['date']
                    
                    self.logger.info(f"Syncing transaction: {payee_name} - ${abs(amount):.2f} on {date}")
                    
                    # Create expense in Splitwise
                    expense = self.sw.create_expense(
                        group_id=self.sw_group_id,
                        description=payee_name,
                        amount=amount,
                        date=date
                    )
                    
                    self.logger.info(f"Created Splitwise expense: {expense.getId()}")
                    
                    # Clear the flag in YNAB (set to null)
                    try:
                        self.ynab.update_transaction(
                            self.ynab_budget_id,
                            txn_id,
                            {'flag_color': None}
                        )
                        self.logger.info(f"Cleared flag for transaction {txn_id}")
                    except Exception as flag_error:
                        self.logger.warning(f"Failed to clear flag for transaction {txn_id}: {flag_error}")
                        # Continue anyway - the expense was created
                    
                    successfully_synced.append(txn_id)
                    
                except Exception as e:
                    self.logger.error(f"Failed to sync transaction {transaction.get('id', 'unknown')}: {e}")
                    # Continue with next transaction
                    continue
            
            # Update state with successfully synced transactions
            if successfully_synced:
                self.ynab_to_sw_state_manager.add_synced_transaction_ids(successfully_synced)
                self.logger.info(f"Successfully synced {len(successfully_synced)} transactions to Splitwise.")
            
            # Update last sync date
            self.ynab_to_sw_state_manager.save_last_sync_date(self.end_date)
            self.logger.info("YNAB to Splitwise sync completed.")
            
        except Exception as e:
            self.logger.error(f"Error during YNAB to Splitwise sync: {e}")
            raise


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

    a = ynab_splitwise_transfer(sw_consumer_key, sw_consumer_secret,
                                sw_api_key, ynab_personal_access_token,
                                ynab_budget_name, ynab_account_name,
                                ynab_to_sw_flag_color, sw_group_name)

    # splitwise to ynab
    a.sw_to_ynab()
    
    # ynab to splitwise
    a.ynab_to_sw()
