import os
import logging
from datetime import datetime, timedelta, timezone

from sw import SW
from ynab import YNABClient
from utils import setup_environment_vars

class ynab_splitwise_transfer():
    def __init__(self, sw_consumer_key, sw_consumer_secret,sw_api_key, 
                    ynab_personal_access_token, ynab_budget_name, ynab_account_name) -> None:
        self.sw = SW(sw_consumer_key, sw_consumer_secret, sw_api_key)
        self.ynab = YNABClient(ynab_personal_access_token)

        self.ynab_budget_id = self.ynab.get_budget_id(ynab_budget_name)
        self.ynab_account_id = self.ynab.get_account_id(self.ynab_budget_id, ynab_account_name)

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # timestamps
        now = datetime.now(timezone.utc)
        self.end_date = datetime(now.year, now.month, now.day)
        self.sw_start_date = self.end_date - timedelta(days=1)

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
            else:
                self.logger.info("No transactions to write to YNAB.")
        else:
            self.logger.info("No transactions to write to YNAB.")



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

    a = ynab_splitwise_transfer(sw_consumer_key, sw_consumer_secret,
                                sw_api_key, ynab_personal_access_token,
                                ynab_budget_name, ynab_account_name)

    # splitwise to ynab
    a.sw_to_ynab()
