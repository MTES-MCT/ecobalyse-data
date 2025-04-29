from app.lib.schema import CamelizedBaseStruct


class AccountLogin(CamelizedBaseStruct):
    username: str
    password: str


class DjangoUser(CamelizedBaseStruct):
    email: str
    first_name: str
    last_name: str
    staff: bool
    terms_of_use: bool
    token: str
