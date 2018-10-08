from matthuisman.language import BaseLanguage

class Language(BaseLanguage):
    LOGIN            = 30000
    HIDE_CHANNEL     = 30001
    LOGOUT           = 30002
    SETTINGS         = 30003
    ASK_USERNAME     = 30004
    ASK_PASSWORD     = 30005
    LOGIN_ERROR      = 30006
    LOGOUT_YES_NO    = 30007
    NO_CHANNEL       = 30008
    NO_STREAM        = 30009
    ADOBE_ERROR      = 30010
    TOKEN_ERROR      = 30011
    LIVE_TV          = 30012
    RESET_HIDDEN     = 30013
    RESET_HIDDEN_OK  = 30014

_ = Language()