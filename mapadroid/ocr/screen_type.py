from enum import Enum


class ScreenType(Enum):
    UNDEFINED = -1
    BIRTHDATE = 1  # birthday selection screen, set by PogoWindows.__screendetection_get_type_internal
    RETURNING = 2  # returning player screen
    LOGINSELECT = 3  # login selection regarding OAUTH
    PTC = 4  # PTC login
    FAILURE = 5  # Unable to authenticate. Please try again. One green button: OK
    RETRY = 6  # Failed to log in. Green button on top: RETRY - no background button below: TRY A DIFFERENT ACCOUNT
    WRONG = 7  # incorrect credentials?
    GAMEDATA = 8  # game data could not be fetched from server
    GGL = 10  # Google account picker
    PERMISSION = 11  # permission grant overlay (Android)
    MARKETING = 12  # marketing notification request (pogo)
    CONSENT = 13  # consent activity
    SN = 14  # OS not compatible message (pogo)
    UPDATE = 15  # Force update modal (pogo)
    STRIKE = 16  # Strike / red warning modal (pogo)
    SUSPENDED = 17  # account suspended modal / temporarily banned (pogo)
    TERMINATED = 18  # account terminated modal (pogo)
    QUEST = 20  # research menu / quest listing (pogo)
    GPS = 21  # GPS signal not found error message (pogo)
    CREDENTIALS = 22  # new GrantCredentials dialog
    NOGGL = 23  # loginselect, but without the google button (probably failed to set a correct birthdate)
    NOTRESPONDING = 24  # system popup about an app not responding, blocking most actions
    POGO = 99  # uhm, whatever... At least pogo is topmost, no idea where we are yet tho (in the process of switching)
    ERROR = 100  # some issue occurred while handling screentypes or not able to determine screen
    BLACK = 110  # screen is black, likely loading up game
    CLOSE = 500  # pogo is not topmost app (whatever app is topmost, it's not pogo)
    DISABLED = 999  # screendetection disabled
