from beanie import PydanticObjectId


class GoogleFileException(Exception):  # noqa: N818
    pass


class UserBannedException(GoogleFileException):
    def __init__(self, user_id: PydanticObjectId):
        self.user_id = user_id
        super().__init__(f"User {user_id} is banned from the file")


class InvalidGmailException(GoogleFileException):
    def __init__(self, gmail: str):
        self.gmail = gmail
        super().__init__(f"Gmail {gmail} does not exist or is not associated with a Google account")


class UnknownErrorException(GoogleFileException):
    def __init__(self):
        super().__init__("Unknown error")


class FileNotFoundException(GoogleFileException):
    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"File with slug {slug} not found")


class GmailAlreadyUsedException(GoogleFileException):
    def __init__(self, gmail: str):
        self.gmail = gmail
        super().__init__(f"Gmail {gmail} is already used by another user")
