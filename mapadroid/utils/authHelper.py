import base64
import re
from typing import Dict, Optional

from aiocache import cached

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import AuthLevel, SettingsAuth


def check_auth(logger, auth_header: Optional[str], auths: Dict[str, SettingsAuth]):
    if not auth_header or not auths:
        return False
    username: Optional[str] = None
    try:
        auth_code = re.match(r'^Basic (\S+)$', auth_header)
        decoded = base64.b64decode(auth_code.group(1)).decode('utf-8')
        (username, password) = decoded.split(":", 1)
        if auths[username].password != password:
            logger.warning("Auth attempt from {} failed", auth_header)
        else:
            return True
    except AttributeError:
        logger.warning("Auth without Basic auth, aborting.")
    except KeyError:
        logger.warning('Auth attempt from non-configured user {}', username)
    except TypeError:
        logger.warning('Unable to decode header {}', auth_header)
    except ValueError:
        logger.warning('Unable to determine auth parameters from {}', auth_header)
    except Exception as e:
        logger.error("Auth attempt failed: {}", e)
    return False


@cached(ttl=300)
async def get_auths_for_levl(db_wrapper: DbWrapper, auth_level: AuthLevel) -> Dict[str, SettingsAuth]:
    """
    Cached for 5 minutes
    Args:
        auth_level:
        db_wrapper:

    Returns: Dict mapping username to the auth entry

    """
    async with db_wrapper as session, session:
        return await SettingsAuthHelper.get_auths_for_auth_level(
            session, db_wrapper.get_instance_id(), auth_level)
