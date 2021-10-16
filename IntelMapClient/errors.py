class Error(Exception):
    pass


class ResultError(Error):
    pass


class RequestError(Error):
    """
    Bad Request
    """
    pass


class ParserError(Error):
    pass


class LoginError(Error):
    pass
