def mutable_testing():
    from servers.includes.models import User
    def f1(user:User):
        user.name = "Hei there"

    u = User(None, 1212, "Not a Name")
    print(u.to_dict())

    f1(u)
    print(u.to_dict())

mutable_testing()