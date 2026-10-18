class QIException(Exception):
    def __init__(self, title, code, http_status, description, translation) -> None:
        self.title = title
        self.code = code
        self.http_status = http_status
        self.description = description
        self.translation = translation
