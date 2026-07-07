from django.contrib.auth.backends import ModelBackend
from .models import CustomUser  # Import your custom user model

class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using their email.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = CustomUser.objects.get(email=username)  # Use CustomUser model
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None
        return None
