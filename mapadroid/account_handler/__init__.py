from mapadroid.account_handler.AbstractAccountHandler import \
    AbstractAccountHandler
from mapadroid.account_handler.AccountHandler import AccountHandler
from mapadroid.db.DbWrapper import DbWrapper


async def setup_account_handler(db_wrapper: DbWrapper) -> AbstractAccountHandler:
    """
    Utility method to be extended/overwritten for any other account handling options (e.g., external provider)
    Args:
        db_wrapper:

    Returns:

    """
    return AccountHandler(db_wrapper)
