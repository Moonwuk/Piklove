class LLMError(Exception):
    status_code = 503
    code = "AI_PROVIDER_UNAVAILABLE"


class LLMNotConfigured(LLMError):
    code = "AI_PROVIDER_NOT_CONFIGURED"


class LLMTimeout(LLMError):
    status_code = 504
    code = "AI_PROVIDER_TIMEOUT"


class LLMInvalidResponse(LLMError):
    status_code = 502
    code = "AI_PROVIDER_INVALID_RESPONSE"
