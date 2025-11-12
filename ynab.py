# https://github.com/deanmcgregor/ynab-python
import requests
import os
import logging
from utils import setup_environment_vars

logger = logging.getLogger(__name__)

class YNABClient:
    BASE_URL = "https://api.youneedabudget.com/v1"

    def __init__(self, access_token):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        logger.info("YNAB client initialized")

    def _make_request(self, method, endpoint, params=None, data=None):
        """Make a request to the YNAB API with error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            
        Returns:
            Response JSON
            
        Raises:
            Exception: If the request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            logger.debug(f"Making {method} request to {endpoint}")
            response = requests.request(method, url, headers=self.headers, params=params, json=data, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            logger.debug(f"Request successful: {method} {endpoint}")
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {method} {url}")
            raise Exception(f"YNAB API request timed out: {method} {endpoint}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            raise Exception(f"YNAB API error {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise Exception(f"YNAB API request failed: {e}")

    def get_budgets(self):
        """Get all budgets for the user."""
        try:
            return self._make_request("GET", "budgets")
        except Exception as e:
            logger.error(f"Failed to get budgets: {e}")
            raise
    
    def get_budget_id(self, budget_name):
        """Get budget ID by name.
        
        Args:
            budget_name: Name of the budget
            
        Returns:
            Budget ID or None if not found
        """
        try:
            budgets = self.get_budgets()
            for budget in budgets['data']['budgets']:
                if budget['name'] == budget_name:
                    logger.info(f"Found budget '{budget_name}' with ID: {budget['id']}")
                    return budget['id']
            logger.warning(f"Budget '{budget_name}' not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get budget ID for '{budget_name}': {e}")
            raise

    def create_transaction(self, budget_id, transactions):
        """Create one or more transactions.
        
        Args:
            budget_id: Budget ID
            transactions: List of transaction objects
            
        Returns:
            API response
        """
        try:
            endpoint = f"budgets/{budget_id}/transactions"
            data = {"transactions": transactions}
            logger.info(f"Creating {len(transactions)} transaction(s) in budget {budget_id}")
            return self._make_request("POST", endpoint, data=data)
        except Exception as e:
            logger.error(f"Failed to create transactions: {e}")
            raise

    
    def get_accounts(self, budget_id):
        """Get all accounts for a budget.
        
        Args:
            budget_id: Budget ID
            
        Returns:
            API response with accounts
        """
        try:
            return self._make_request("GET", f"budgets/{budget_id}/accounts")
        except Exception as e:
            logger.error(f"Failed to get accounts for budget {budget_id}: {e}")
            raise
    
    def get_account_id(self, budget_id, account_name):
        """Get account ID by name.
        
        Args:
            budget_id: Budget ID
            account_name: Name of the account
            
        Returns:
            Account ID or None if not found
        """
        try:
            accounts = self.get_accounts(budget_id)
            for account in accounts['data']['accounts']:
                if account['name'].strip() == account_name.strip():
                    logger.info(f"Found account '{account_name}' with ID: {account['id']}")
                    return account['id']
            logger.warning(f"Account '{account_name}' not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get account ID for '{account_name}': {e}")
            raise
    
    def get_transactions(self, budget_id, since_date=None):
        """Get transactions for a budget, optionally filtered by date.
        
        Args:
            budget_id: The budget ID to get transactions from
            since_date: Optional date string in YYYY-MM-DD format to filter transactions
            
        Returns:
            List of transaction objects
        """
        try:
            endpoint = f"budgets/{budget_id}/transactions"
            params = {}
            if since_date:
                params['since_date'] = since_date
                logger.info(f"Fetching transactions since {since_date}")
            
            response = self._make_request("GET", endpoint, params=params)
            transactions = response['data']['transactions']
            logger.info(f"Retrieved {len(transactions)} transaction(s)")
            return transactions
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise
    
    def update_transaction(self, budget_id, transaction_id, transaction_data):
        """Update a transaction.
        
        Args:
            budget_id: The budget ID
            transaction_id: The transaction ID to update
            transaction_data: Dict with transaction fields to update (e.g., {'flag_color': 'red'})
            
        Returns:
            Response from YNAB API
        """
        try:
            endpoint = f"budgets/{budget_id}/transactions/{transaction_id}"
            data = {"transaction": transaction_data}
            logger.debug(f"Updating transaction {transaction_id}")
            return self._make_request("PUT", endpoint, data=data)
        except Exception as e:
            logger.error(f"Failed to update transaction {transaction_id}: {e}")
            raise


    



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
