import json
import os
from locust import HttpUser, task, between, tag


class DjangoUser(HttpUser):
    """
    Locust user class to simulate load on:
    - Admin Dashboard (GET)
    - GRN Submission (POST with file + JSON)
    """

    wait_time = between(1, 5)
    host = "http://127.0.0.1:8000"

    def on_start(self):
        """
        Log in once per simulated user.
        """
        # First, check if we're already logged in by trying to access a protected page
        response = self.client.get("/", name="GET / (login check)")
        
        if response.status_code == 200:
            # Try to log in
            response = self.client.post(
                "/",
                name="POST / (login)",
                data={
                    "username": "admin",       # CHANGE if needed
                    "password": "admin123",    # CHANGE if needed
                },
                allow_redirects=True,
            )

            if response.status_code != 200:
                print(f"Login failed: {response.status_code}")
                print(f"Response: {response.text[:200]}")

    # -----------------------------
    # ADMIN DASHBOARD (SAFE)
    # -----------------------------
    @task(3)
    def admin_dashboard(self):
        response = self.client.get("/admin_dashboard/", name="GET /admin_dashboard")
        if response.status_code != 200:
            response.failure(f"Admin dashboard failed: {response.status_code}")

    # -----------------------------
    # SUBMIT GRN (HEAVY)
    # -----------------------------
    @tag('grn')
    @task(1)
    def submit_grn(self):
        """
        Submit a FULLY VALID GRN request.
        """
        test_file_path = "test.pdf"

        if not os.path.exists(test_file_path):
            # Create a dummy PDF file if it doesn't exist
            import io
            from reportlab.pdfgen import canvas
            
            packet = io.BytesIO()
            can = canvas.Canvas(packet)
            can.drawString(100, 100, "Test GRN PDF for Locust")
            can.save()
            
            # Save to file
            with open(test_file_path, "wb") as f:
                f.write(packet.getvalue())

        with open(test_file_path, "rb") as f:
            response = self.client.post(
                "/submit_grn/",
                name="POST /submit_grn",
                files={
                    "chalan_file": (
                        "test.pdf",
                        f,
                        "application/pdf",
                    )
                },
                data={
                    "po_number": "0000000000",
                    "chalan_number": "CH123",
                    "chalan_date": "2026-01-09",
                    "requisition_numbers": "1",  # Make sure this requisition exists!
                    "stock_items": json.dumps(
                        [
                            {
                                "stockItem": "Milk Powder",
                                "orderedQuantity": 10,
                                "receivedQuantity": 10,
                                "quantityRejected": 0,
                                "uom": "KG",
                                "remarks": "Locust test GRN",
                            }
                        ]
                    ),
                },
            )
            
            # Check response
            if response.status_code != 200:
                response.failure(f"GRN submission failed: {response.status_code}")
                print(f"Response: {response.text[:500]}")