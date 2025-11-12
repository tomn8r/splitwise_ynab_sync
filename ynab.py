# https://github.com/deanmcgregor/ynab-python
import requests
import os
from utils import setup_environment_vars

class YNABClient:
    BASE_URL = "https://api.youneedabudget.com/v1"

    def __init__(self, access_token):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method, endpoint, params=None, data=None):
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.request(method, url, headers=self.headers, params=params, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()

    def get_budgets(self):
        return self._make_request("GET", "budgets")
    
    def get_budget_id(self, budget_name):
        budgets = self.get_budgets()
        for budget in budgets['data']['budgets']:
            if budget['name'] == budget_name:
                return budget['id']
        return None

    def create_transaction(self, budget_id, transactions):
        endpoint = f"budgets/{budget_id}/transactions"
        data = {"transactions": transactions}
        return self._make_request("POST", endpoint, data=data)

    
    def get_accounts(self, budget_id):
        return self._make_request("GET", f"budgets/{budget_id}/accounts")
    
    def get_account_id(self, budget_id, account_name):
        accounts = self.get_accounts(budget_id)
        for account in accounts['data']['accounts']:
            if account['name'].strip() == account_name.strip():
                return account['id']
        return None
    
    def get_transactions(self, budget_id, since_date=None):
        """Get transactions for a budget, optionally filtered by date.
        
        Args:
            budget_id: The budget ID to get transactions from
            since_date: Optional date string in YYYY-MM-DD format to filter transactions
            
        Returns:
            List of transaction objects
        """
        endpoint = f"budgets/{budget_id}/transactions"
        params = {}
        if since_date:
            params['since_date'] = since_date
        
        response = self._make_request("GET", endpoint, params=params)
        return response['data']['transactions']
    
    def update_transaction(self, budget_id, transaction_id, transaction_data):
        """Update a transaction.
        
        Args:
            budget_id: The budget ID
            transaction_id: The transaction ID to update
            transaction_data: Dict with transaction fields to update (e.g., {'flag_color': 'red'})
            
        Returns:
            Response from YNAB API
        """
        endpoint = f"budgets/{budget_id}/transactions/{transaction_id}"
        data = {"transaction": transaction_data}
        return self._make_request("PUT", endpoint, data=data)


    



if __name__ == "__main__":
    # load environment variables from yaml file (locally)
    setup_environment_vars()

    # ynab creds
    ynab_budget_name = os.environ.get('ynab_budget_name')
    ynab_account_name = os.environ.get('ynab_account_name')
    personal_access_token = os.environ.get('ynab_personal_access_token')

    client = YNABClient(personal_access_token)

    budget_id = client.get_budget_id(ynab_budget_name)
    account_id = client.get_account_id(budget_id, ynab_account_name)

    # Create a transaction
    transactions = [
        {
            "account_id": account_id,
            "date": "2023-11-22",
            "amount": 5000,  # Example amount in milliunits
            "payee_name": "Grocery Store",
            "memo": "Weekly groceries",
            "cleared": "cleared",
            "approved": False
        }
        ,{
            "account_id": account_id,
            "date": "2023-11-23",
            "amount": 2000,  # Another example amount
            "payee_name": "Cafe",
            "memo": "Coffee break",
            "cleared": "cleared",
            "approved": False
        }
    ]

    # response = client.create_transaction(budget_id, transactions)
    # print("Transactions created on YNAB.")
