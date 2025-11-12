from splitwise import Splitwise
import os
from utils import setup_environment_vars

# https://github.com/namaggarwal/splitwise

class SW():
    def __init__(self, consumer_key, consumer_secret, api_key) -> None:
        # Initialize the Splitwise object with the API key
        self.sw = Splitwise(consumer_key, consumer_secret, api_key=api_key)

        self.limit = 100
        self.current_user = self.sw.getCurrentUser().getFirstName()
        self.current_user_id = self.sw.getCurrentUser().getId()

    def get_expenses(self, dated_before=None, dated_after=None):
        # get all expenses between 2 dates
        expenses = self.sw.getExpenses(limit=self.limit, dated_before=dated_before, dated_after=dated_after)
        owed_expenses = []
        for expense in expenses:
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
                
        return owed_expenses
    
    def get_groups(self):
        """Get all groups for the current user.
        
        Returns:
            List of group objects
        """
        return self.sw.getGroups()
    
    def get_group_id_by_name(self, group_name):
        """Get group ID by group name.
        
        Args:
            group_name: Name of the group to find
            
        Returns:
            Group ID if found, None otherwise
        """
        groups = self.get_groups()
        for group in groups:
            if group.getName() == group_name:
                return group.getId()
        return None
    
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
        
        expense = Expense()
        expense.setGroupId(group_id)
        expense.setDescription(description)
        # YNAB amounts are negative for expenses, make positive for Splitwise
        expense.setCost(str(abs(amount)))
        expense.setDate(date)
        expense.setSplitEqually()  # Split 50/50 among group members
        
        return self.sw.createExpense(expense)



if __name__ == "__main__":
    # load environment variables from yaml file (locally)
    setup_environment_vars()
    
    # splitwise creds
    consumer_key = os.environ.get('sw_consumer_key')
    consumer_secret = os.environ.get('sw_consumer_secret')
    api_key = os.environ.get('sw_api_key')

    a = SW(consumer_key, consumer_secret, api_key)
    # e = a.get_expenses(dated_after="2023-11-29", dated_before="2023-12-01")
