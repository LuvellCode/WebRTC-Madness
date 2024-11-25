def test__mutables():
    from servers.includes.models import User
    def f1(user:User):
        user.name = "Hei there"

    u = User(None, 1212, "Not a Name")
    print(u.to_dict())

    f1(u)
    print(u.to_dict())

# test__mutables()

def test__inspecting():
    import inspect
    from servers.includes.models import User

    def dummy(user:User, somevar:str, othervar:bool):
        pass

    print(inspect.signature(dummy).parameters)

# test__inspecting()

def test__locals():
    test = "Ima test"
    hehe = "hehe?"

    for name, val in locals().items():
        print(f"{name}: {val}")

test__locals()