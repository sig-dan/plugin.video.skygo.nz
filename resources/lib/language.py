from matthuisman.language import BaseLanguage

class Language(BaseLanguage):
    HIDE_CHANNEL     = 30000
    ASK_USERNAME     = 30001
    ASK_PASSWORD     = 30002
    NO_CHANNEL       = 30003
    NO_STREAM        = 30004
    ADOBE_ERROR      = 30005
    TOKEN_ERROR      = 30006
    LIVE_TV          = 30007
    RESET_HIDDEN     = 30008
    RESET_HIDDEN_OK  = 30009

_ = Language()