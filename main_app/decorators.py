from django.shortcuts import render
from django.urls import resolve

def restrict_hod_access(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Get the current URL name
        current_url = resolve(request.path_info).url_name

        # Check if the user is HOD
        if hasattr(request.user, "is_hod") and request.user.is_hod:
            # List of allowed paths for HOD
            allowed_urls = [
                "login",
                "logout",
                "hod_requisitions",
                "approve_requisition",
                "reject_requisition",
            ]
            if current_url not in allowed_urls:
                return render(request, "403.html", status=403)

        # Check if the user is Purchase
        elif hasattr(request.user, "is_purchase") and request.user.is_purchase:
            # List of allowed paths for Purchase users
            allowed_urls = [
                "login",
                "logout",
                "view_purchase_requisitions",
            ]
            if current_url not in allowed_urls:
                return render(request, "403.html", status=403)

        # Check if the user is Finance
        elif hasattr(request.user, "is_finance") and request.user.is_finance:
            # List of allowed paths for Finance users
            allowed_urls = [
                "login",
                "logout",
                "finance_dashboard",
            ]
            if current_url not in allowed_urls:
                return render(request, "403.html", status=403)

        # Check if the user is Logistic
        elif hasattr(request.user, "is_logistic") and request.user.is_logistic:
            # List of allowed paths for Logistic users
            allowed_urls = [
                "login",
                "logout",
                "logistic_dashboard",
            ]
            if current_url not in allowed_urls:
                return render(request, "403.html", status=403)

        # If the user is neither HOD, Purchase, Finance, nor Logistic, allow unrestricted access
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def restrict_user_access(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Get the current URL name
        current_url = resolve(request.path_info).url_name

        # Check if the user is HOD
        if hasattr(request.user, "is_hod") and request.user.is_hod:
            return render(request, "403.html", status=403)

        # Check if the user is Purchase
        elif hasattr(request.user, "is_purchase") and request.user.is_purchase:
            return render(request, "403.html", status=403)

        # Check if the user is Logistic
        elif hasattr(request.user, "is_logistic") and request.user.is_logistic:
            # List of allowed paths for Logistic users
            allowed_urls = [
                "login",
                "logout",
                "logistic_dashboard",
            ]
            if current_url not in allowed_urls:
                return render(request, "403.html", status=403)

        # Check if the user is a normal user (not Finance)
        elif not hasattr(request.user, "is_finance") or not request.user.is_finance:
            return render(request, "403.html", status=403)

        # If the user is Finance, allow access
        return view_func(request, *args, **kwargs)

    return _wrapped_view