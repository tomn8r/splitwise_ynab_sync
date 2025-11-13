from splitwise import Splitwise
import os
import logging
from utils import setup_environment_vars

# https://github.com/namaggarwal/splitwise

logger = logging.getLogger(__name__)

class SW():
    def __init__(self, consumer_key, consumer_secret, api_key) -> None:
        # Initialize the Splitwise object with the API key
        try:
            self.sw = Splitwise(consumer_key, consumer_secret, api_key=api_key)
            logger.info("Splitwise client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Splitwise client: {e}")
            raise

        self.limit = 100
        
        try:
            current_user = self.sw.getCurrentUser()
            self.current_user = current_user.getFirstName()
            self.current_user_id = current_user.getId()
            logger.info(f"Current Splitwise user: {self.current_user} (ID: {self.current_user_id})")
        except Exception as e:
            logger.error(f"Failed to get current Splitwise user: {e}")
            raise

    def get_expenses(self, dated_before=None, dated_after=None):
        """Get expenses between two dates.
        
        Args:
            dated_before: End date (YYYY-MM-DD or date object)
            dated_after: Start date (YYYY-MM-DD or date object)
            
        Returns:
            List of expense dictionaries with owed amounts
        """
        try:
            logger.info(f"Fetching Splitwise expenses from {dated_after} to {dated_before}")
            expenses = self.sw.getExpenses(limit=self.limit, dated_before=dated_before, dated_after=dated_after)
            logger.info(f"Retrieved {len(expenses)} expense(s) from Splitwise")
        except Exception as e:
            logger.error(f"Failed to fetch Splitwise expenses: {e}")
            raise
        
        owed_expenses = []
        for expense in expenses:
            try:
                owed_expense = {}
                repayments = expense.getRepayments()
                
                for debt in repayments:
                    lender = debt.getFromUser()
                    borrower = debt.getToUser()
                    owed_expense['id'] = str(expense.getId())  # Add expense ID for tracking
                    owed_expense['description'] = expense.getDescription();
                    owed_expense['deleted_time'] = expense.getDeletedAt()
                    owed_expense['date'] = expense.getDate()
                    owed_expense['created_time'] = expense.getCreatedAt()
                    owed_expense['updated_time'] = expense.getUpdatedAt()
                    if lender == self.current_user_id:
                        owed_expense['amount'] = -float(debt.getAmount())
                        
                    elif borrower == self.current_user_id:
                        owed_expense['amount'] = float(debt.getAmount())
                    else:
                        owed_expense['amount'] = 0
                        
                    owed_expenses.append(owed_expense)
            except Exception as e:
                logger.error(f"Error processing expense {expense.getId()}: {e}")
                # Continue with next expense
                continue
                
        logger.info(f"Processed {len(owed_expenses)} owed expense(s)")
        return owed_expenses
    
    def get_groups(self):
        """Get all groups for the current user.
        
        Returns:
            List of group objects
        """
        try:
            logger.info("Fetching Splitwise groups")
            groups = self.sw.getGroups()
            logger.info(f"Retrieved {len(groups)} group(s)")
            return groups
        except Exception as e:
            logger.error(f"Failed to fetch Splitwise groups: {e}")
            raise
    
    def get_group_id_by_name(self, group_name):
        """Get group ID by group name.
        
        Args:
            group_name: Name of the group to find
            
        Returns:
            Group ID if found, None otherwise
        """
        try:
            groups = self.get_groups()
            for group in groups:
                if group.getName() == group_name:
                    logger.info(f"Found group '{group_name}' with ID: {group.getId()}")
                    return group.getId()
            logger.warning(f"Group '{group_name}' not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get group ID for '{group_name}': {e}")
            raise
    
    def create_expense(self, group_id, description, amount, date):
        """Create a new expense with 50/50 split in a group.
        
        Args:
            group_id: The Splitwise group ID
            description: Description of the expense
            amount: Amount in dollars (will be converted to absolute value)
            date: Date in YYYY-MM-DD format
            
        Returns:
            Created expense object
        """
        from splitwise import Expense
        
        try:
            expense = Expense()
            expense.setGroupId(group_id)
            expense.setDescription(description)
            # YNAB amounts are negative for expenses, make positive for Splitwise
            expense.setCost(str(abs(amount)))
            expense.setDate(date)
            expense.setSplitEqually()  # Split 50/50 among group members
            
            logger.info(f"Creating Splitwise expense: {description}, ${abs(amount):.2f}, {date}")
            # createExpense returns a tuple (expense, errors)
            created_expense, errors = self.sw.createExpense(expense)
            
            # Check for errors
            if errors:
                error_msg = f"Splitwise API returned errors: {errors}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            if not created_expense:
                error_msg = "Failed to create expense: No expense object returned"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"Successfully created expense with ID: {created_expense.getId()}")
            return created_expense
        except Exception as e:
            logger.error(f"Failed to create Splitwise expense: {e}")
            raise



if __name__ == "__main__":
    # load environment variables from yaml file (locally)
    setup_environment_vars()
    
    # splitwise creds
    consumer_key = os.environ.get('sw_consumer_key')
    consumer_secret = os.environ.get('sw_consumer_secret')
    api_key = os.environ.get('sw_api_key')

    a = SW(consumer_key, consumer_secret, api_key)
    # e = a.get_expenses(dated_after="2023-11-29", dated_before="2023-12-01")
