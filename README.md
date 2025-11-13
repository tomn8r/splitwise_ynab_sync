# splitwise_ynab_sync

## What does it do?
The code automates bidirectional syncing between Splitwise and YNAB:
1. **Splitwise → YNAB**: Automatically imports transactions from Splitwise into your YNAB budget
2. **YNAB → Splitwise**: Flag transactions in YNAB (using a specific flag color) to automatically create 50/50 split expenses in a Splitwise group

By following instructions below, you can automate to run it daily using Github Actions.

### Key Features
- **Bidirectional sync**: Move transactions between Splitwise and YNAB in both directions
- **No missed transactions**: The app tracks the last successful sync date and syncs all transactions since then, ensuring no transactions are missed if a GitHub Action fails to run
- **Smart sync**: On first run or if state is lost, automatically syncs the last 7 days of transactions
- **Flag-based triggering**: Simply flag a transaction in YNAB to sync it to Splitwise
- **Timezone-aware**: Properly handles date comparisons across timezones (configurable, defaults to Sydney, Australia)
- **Optimized performance**: Uses dependency caching to reduce workflow run time
- **Concurrent run protection**: Prevents overlapping syncs to avoid duplicate transactions
- **Duplicate prevention**: Tracks synced transactions to avoid creating duplicates
- **Comprehensive logging**: Detailed logs for debugging and monitoring sync operations
- **Robust error handling**: Gracefully handles API failures with informative error messages



## What change do you need in your YNAB workflow to implement this?
You would need to create a new account named 'Splitwise' in your YNAB accounts(mentioned below in Setup #1).
That is the only necessity for this repo.

That said, I would to mention my workflow:
- In addition to a 'Splitwise' account, I also create a 'Splitwise' category. I place this in a 'Don't count' group as it helps in the reports.
- Expenses paid by me: I split the expense between a category corrsponding to the expense and the 'Splitwise' category.
- Expenses paid by others: I add my share as an expense under 'Splitwise' account and the corresponding category.

## Which transactions are synced?
- **Splitwise → YNAB**: Imports all transactions for which you owe money
- **YNAB → Splitwise**: Syncs transactions you flag with the configured flag color (default: blue)

## Is it free?
Yes. Since you will be deploying your own Github Actions to deploy, you will be using just around 15 minutes from the [free 2000 minutes per month](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions#included-storage-and-minutes).

## Setup
This repo enables bidirectional syncing between Splitwise and YNAB.

1. Go to your YNAB budget ([YNAB](https://app.youneedabudget.com/)) and create a new account named `Splitwise`. This is where the imported transactions will flow into.
2. Collect Credentials from YNAB and Splitwise:

    a. YNAB:
     - Go to [YNAB Developer Settings](https://app.ynab.com/settings/developer)
     - Create a new `Personal Access Token`.
     - You will see the token at the top of page, save that in a safe place as you won't be able to access it again.
    
    b. Splitwise:
    - Go to [Splitwise Apps](https://secure.splitwise.com/apps)
    - Click on `Register your application`
    - Fill `application name` (YNAB_Splitwise_sync), `description` and `Homepage URL` (http://api-example.splitwise.com/) and click on `Register and API key`
    - Copy `Consumer Key`, `Consumer Secret` and `API keys`.
3. Fork this repo. (by clicking on the 'Fork' option on the top of this page.)
4. Add the Credentials on Github Actions:
    - Go to the `Settings` tab, then `Secrets and variables` > `Actions`
    - Under `Secrets` tab, using `New repository secret`, you need to add 4 Name-Secret pairs:
        - Name: `YNAB_PERSONAL_ACCESS_TOKEN`, Secret: `Personal Access Token` from 2a.
        - Name: `SW_API_KEY`, Secret: `API keys` from 2b.
        - Name: `SW_CONSUMER_KEY`, Secret: `Consumer Key` from 2b.
        - Name: `SW_CONSUMER_SECRET`, Secret: `Consumer Secret` from 2b.
    - Similarly, Under `Variables` tab, using `New repository variable`, add:
        - Name: `YNAB_BUDGET_NAME`, Value: your YNAB budget name (check your YNAB app or website, if you don't know, fill 'My Budget')
        - Name: `YNAB_ACCOUNT_NAME`, Value: 'Splitwise' (created in step 1).
        - Name: `YNAB_TO_SW_FLAG_COLOR`, Value: 'blue' (or any other flag color you prefer: red, orange, yellow, green, purple)
        - Name: `SW_GROUP_NAME`, Value: name of your Splitwise group (e.g., 'Kate & Tom')
        - Name: `USER_TIMEZONE`, Value: your timezone (e.g., 'Australia/Sydney', 'America/New_York', 'Europe/London'). If not specified, defaults to 'Australia/Sydney'.


The Github Actions now triggers this code repo at `12:13 UTC` everyday and syncs transactions bidirectionally between Splitwise and YNAB.

If you would like to change the schedule time, change the cron expression in [python-app.yaml](.github/workflows/python-app.yml) file.

### How it works

#### Splitwise → YNAB
The application maintains a persistent state file that tracks the last successful sync date. On each run:
1. It retrieves the last sync date from the cache
2. Syncs all transactions from the last sync date to today
3. Updates the state with the current date after a successful sync

This means if a GitHub Action fails to run for any reason (GitHub outage, workflow disabled, etc.), the next successful run will catch up and sync all missed transactions automatically.

#### YNAB → Splitwise
To sync a transaction from YNAB to Splitwise:
1. In YNAB, flag any transaction with the configured flag color (default: blue)
2. The next sync run will automatically:
   - Find all flagged transactions that haven't been synced yet
   - Create corresponding 50/50 split expenses in your configured Splitwise group
   - Clear the flag in YNAB after successful sync
   - Track the transaction ID to prevent duplicate syncs

The app maintains a separate state file for YNAB→Splitwise syncing to track which transactions have been synced and prevent duplicates.


## Troubleshooting

### Timezone Issues
If you notice that transactions are missing or syncing at unexpected times:
1. Check that the `USER_TIMEZONE` variable is set correctly in your GitHub repository settings
2. Use a valid timezone string from the [IANA timezone database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., 'Australia/Sydney', 'America/New_York', 'Europe/London')
3. Review the GitHub Actions logs to see what timezone is being used - it's logged at the start of each sync

### Sync Errors
If the sync fails:
1. Check the GitHub Actions logs for detailed error messages
2. Verify all credentials are correct in your repository secrets
3. Ensure your YNAB budget and account names match exactly (including spaces and capitalization)
4. Verify your Splitwise group name is correct
5. Check that you have active internet connectivity to both YNAB and Splitwise APIs

### YNAB to Splitwise Flag-Based Sync
If flagged transactions aren't syncing to Splitwise:
1. Verify the `YNAB_TO_SW_FLAG_COLOR` variable is set correctly (must be one of: red, orange, yellow, green, blue, purple)
2. Check that the `SW_GROUP_NAME` variable matches your Splitwise group name exactly
3. Review the logs to see if the flagged transactions are being detected
4. Ensure the transactions are not deleted in YNAB

## Bugfixes
1. Apr 6, 2024: fixed the `UnboundLocalError: local variable 'paid' referenced before assignment` error.
2. Nov 12, 2024: Added timezone support, comprehensive error handling, and enhanced logging to fix date mismatch issues and improve debugging capabilities.
3. Nov 13, 2024: Fixed blue flagged transactions not syncing back their "share" from Splitwise to YNAB by using `updated_after` parameter to catch newly created expenses regardless of their original date.

### How to keep your repo updated to this repo?
1. On your forked repo, you would see something like `This branch is X commits behind amit-hm/splitwise_yanb_sync:main`.
2. Click on `Sync fork`.
3. Click on `Update branch`.

   This should update your forked repo to this repo and hence bring in those new bugfixes or features.

# NOTE
Github Actions, unfortunately, deactivates after 60 days of inactivity. So, you might have to manually enable the workflow again every 60 days.


Contact me at devsama42@gmail.com
