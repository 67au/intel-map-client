class Error(Exception):
    pass


class ResponseError(Error):
    """
    Bad Response
    """
    pass


class RequestError(Error):
    """
    Bad Request
    """
    pass


class CookiesError(Error):
    pass
