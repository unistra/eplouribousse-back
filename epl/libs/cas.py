def create_user(args) -> None:
    """
    user_attributes is a dict of the form:
    {
        "username": "username",
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
    }
    """
    user_model, attributes = args
    user = user_model.objects.create_user(username=attributes["username"], email=attributes["mail"][0])
    return user
