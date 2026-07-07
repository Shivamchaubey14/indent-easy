from django.core.mail import EmailMessage
from django.conf import settings
import os
from .models import EmailSettings

def send_purchase_requisition_notification(po_number, party_name, recipient_emails, items, excel_attachment_path=None):
    try:
        email_settings = EmailSettings.objects.first()
        if not email_settings:
            raise Exception("Email settings not configured in the admin panel.")        
        cc_emails = [
            email.strip()
            for email in email_settings.cc_emails.split(",")
            if email.strip()
        ]
        table_rows = ""
        for index, item in enumerate(items, start=1):
            original_po_number = item['po_number']
            po_number_split = original_po_number.split(':')[0]  # Split and take the part before the colon
            print(f"Original PO Number: {original_po_number}, Split PO Number: {po_number_split}")
            
            # Use mapped product name if available, otherwise use original
            product_display_name = item.get('mapped_product_name', item['stock_item'])
            system_badge = item.get('mapped_system', '')
            
            # Add system badge note if available
            system_note = ""
            if system_badge and system_badge != 'INDENT_EASY':
                system_note = f"<br><small style='color: #666;'>({system_badge} Product)</small>"
            
            # Add original name note if mapped product is different
            original_note = ""
            if item.get('mapped_product_name') and item.get('mapped_system') != 'INDENT_EASY':
                original_note = f"<br><small style='color: #888;'>Original: {item['stock_item']}</small>"
            
            table_rows += f"""
            <tr>
                <td>{index}</td>
                <td>{po_number_split}</td>
                <td>{item['requisition_number']}</td>
                <td>
                    {product_display_name}
                    {system_note}
                    {original_note}
                </td>
                <td>{item['quantity']}</td>
                <td>{item['location']}</td>
                <td>{item['address']}</td>
                <td>{item['expected_delivery_date']}</td>
                <td>{item['remark']}</td>
            </tr>
            """
        
        # Create email body with attachment information
        attachment_note = ""
        attachment_status = False
        
        # Check if attachment path exists and is valid
        if excel_attachment_path and os.path.exists(excel_attachment_path):
            file_size = os.path.getsize(excel_attachment_path)
            print(f"Attachment file exists: {excel_attachment_path}, Size: {file_size} bytes")
            
            if file_size > 0:
                attachment_note = """
                <p><strong>Note:</strong> The delivery schedule Excel file is attached with this email.</p>
                """
                attachment_status = True
            else:
                print(f"Attachment file is empty: {excel_attachment_path}")
        else:
            print(f"Attachment file not found or invalid path: {excel_attachment_path}")
        
        subject = email_settings.subject
        from_email = email_settings.from_email
        body = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .product-name {{
                    font-weight: bold;
                }}
                .original-name {{
                    color: #666;
                    font-size: 0.9em;
                }}
                .system-badge {{
                    display: inline-block;
                    background-color: #ffc107;
                    color: #000;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 0.8em;
                    margin-left: 5px;
                }}
                .system-badge.sap {{
                    background-color: #17a2b8;
                    color: #fff;
                }}
            </style>
        </head>
        <body>
            <p>Dear <b>{party_name}</b>,</p>
            <p>Greetings from Shwetdhara!!</p>
            <p>You are requested to supply the items as per below details:</p>
            <table>
                <thead>
                    <tr>
                        <th>S.No</th>
                        <th>PO No.</th>
                        <th>Requisition No.</th>
                        <th>Item Name</th>
                        <th>Quantity</th>
                        <th>Location</th>
                        <th>Supply Address</th>
                        <th>Expected Delivery Date</th>
                        <th>Remarks</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            {attachment_note}
            <p>Regards,</p>
            <p>Shwetdhara MPO</p>
            <p><i>This is an automatically generated mail</i></p>
        </body>
        </html>
        """
        print(f"Email details - Subject: {subject}, From: {from_email}")  
        print(f"Attachment status: {'Attached' if attachment_status else 'Not attached'}")
        
        # Create email message
        email = EmailMessage(
            subject=subject,  # Subject
            body=body,  # Email body
            from_email=from_email,  # From email
            to=recipient_emails,  # To email (list of recipients)
            cc=cc_emails,  # CC emails
        )
        email.content_subtype = "html"  # Specify HTML content
        
        # Attach Excel file if available and valid
        if attachment_status:
            try:
                with open(excel_attachment_path, 'rb') as excel_file:
                    file_content = excel_file.read()
                    print(f"File content size: {len(file_content)} bytes")
                    
                    # Clean the PO number for filename
                    clean_po_number = po_number.replace('/', '_').replace(':', '_')
                    filename = f"Delivery_Schedule_{clean_po_number}.xlsx"
                    
                    email.attach(
                        filename=filename,
                        content=file_content,
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                print(f"Excel file attached successfully: {filename}")
            except Exception as e:
                print(f"Error attaching Excel file: {e}")
                attachment_status = False
                # Update body to remove attachment note
                body = body.replace(attachment_note, "<p><strong>Note:</strong> Delivery schedule attachment failed to include.</p>")
                email.body = body
        
        # Send the email
        email.send(fail_silently=False)
        print("Email sent successfully.")
        
        return attachment_status
        
    except Exception as e:
        print(f"Error sending email: {e}")
        raise e