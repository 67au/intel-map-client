class Error(RuntimeError):
    pass


class ResultError(Error):
    pass


class RequestError(Error):
    pass


class IncompleteError(ResultError):
    pass


class ParserError(Error):
    pass


class LoginError(Error):
    pass
