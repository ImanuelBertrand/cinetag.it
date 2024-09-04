class TMDbAPIError(Exception):
    """
    Custom exception for TMDb API errors.
    """

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class UserFeedbackError(Exception):
    """
    Custom exception for user feedback errors.
    """

    def __init__(self, message):
        super().__init__(message)
