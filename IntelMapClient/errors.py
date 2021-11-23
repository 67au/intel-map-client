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


class ParserError(Error):
    pass


class CommTabError(Error):
    pass


class CookieError(Error):
    pass
