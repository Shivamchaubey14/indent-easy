import calendar
from datetime import date
import re
from venv import logger
from django.utils.timezone import localtime
from django.db import models
from django.forms import ValidationError
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission, BaseUserManager
from django.utils.timezone import localtime, now
import pytz
from django.db import models 
from django.db.models import Max, Min, Sum, Count, Avg, Q 
from .choices import (
    EMPLOYEE_CODE_CHOICES,
    DEPARTMENT_CHOICES,
    LOCATION_CHOICES,
    UOM_CHOICES,
    STOCK_ITEM_CHOICES,
    STATUS_CHOICES,
) 

# A custom user manager to deal with emails as unique identifier for auth
class CustomUserManager(BaseUserManager):
    
    # Create a user with the given email and password
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    # Create a superuser with the given email and password
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

# Custom User model to use email as unique identifier for authentication
class CustomUser(AbstractUser):
    username = None  # Remove username field
    email = models.EmailField(unique=True)  # Email is the unique identifier
    location = models.CharField(max_length=255, verbose_name="Location")
    plant = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="SAP Plant Code"
    )
    is_hod = models.BooleanField(default=False, verbose_name="HOD Status")
    is_purchase = models.BooleanField(default=False, verbose_name="Purchase Team Status")
    is_finance = models.BooleanField(default=False, verbose_name="Finance Team Status")
    is_logistic = models.BooleanField(default=False, verbose_name="Logistics Team Status")
    employee_code = models.CharField(max_length=255, verbose_name="Employee Code")
    department = models.CharField(max_length=255, verbose_name="Department")
    address = models.TextField(null=True, blank=True)
    delivery_point_code = models.CharField(max_length=255, unique=True, null=True, blank=True)
    signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    mohar = models.ImageField(upload_to='mohars/', null=True, blank=True)
    objects = CustomUserManager()
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",
        blank=True,
        verbose_name="Groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",
        blank=True,
        verbose_name="User Permissions",
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    def __str__(self):
        return self.email

# Model for Product Mapping
class ProductMapping(models.Model):
    SYSTEM_CHOICES = [
        ('INDENT_EASY', 'Indent Easy'),
        ('SAP', 'SAP'),
        ('NDDB', 'NDDB'),
    ]
    
    system = models.CharField(max_length=20, choices=SYSTEM_CHOICES)
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    uom = models.CharField(max_length=50, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    material_type = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('system', 'product_name')
        verbose_name = "Product Mapping"
        verbose_name_plural = "Product Mappings"
        ordering = ['system', 'product_name']
    
    def __str__(self):
        return f"{self.get_system_display()}: {self.product_name}"

# Model for Product Mapping Group
class ProductMappingGroup(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Group name for related products across systems")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Product Mapping Group"
        verbose_name_plural = "Product Mapping Groups"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_mapped_products(self):
        """Get all products mapped in this group"""
        return {
            'indent_easy': self.mappings.filter(product_mapping__system='INDENT_EASY').first(),
            'sap': self.mappings.filter(product_mapping__system='SAP').first(),
            'nddb': self.mappings.filter(product_mapping__system='NDDB').first(),
        }

# Model for Product Mapping Relation
class ProductMappingRelation(models.Model):
    group = models.ForeignKey(ProductMappingGroup, on_delete=models.CASCADE, related_name='mappings')
    product_mapping = models.ForeignKey(ProductMapping, on_delete=models.CASCADE, related_name='groups')
    is_primary = models.BooleanField(default=False, help_text="Mark as primary product for this group")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('group', 'product_mapping')
        verbose_name = "Product Mapping Relation"
        verbose_name_plural = "Product Mapping Relations"
        ordering = ['group', '-is_primary', 'product_mapping__system']
    
    def __str__(self):
        return f"{self.group.name} - {self.product_mapping.product_name}"

# Model for Inventory History
class InventoryHistory(models.Model):
    ACTION_CHOICES = [
        ('GRN', 'Goods Received'),
        ('SALE', 'Sale'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('ADJUSTMENT', 'Stock Adjustment'),
        ('RETURN', 'Return'),
        ('DAMAGE', 'Damage/Loss'),
        ('EXPIRED', 'Expired'),
        ('DAMAGED', 'Damaged'),
        ('DISPOSED', 'Disposed'),
    ]
    
    inventory = models.ForeignKey('Inventory', on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity_change = models.IntegerField()  # Positive for additions, negative for deductions
    previous_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    reference_number = models.CharField(max_length=100, blank=True, null=True)  # GRN, STN, Sale ID, etc.
    notes = models.TextField(blank=True, null=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='inventory_actions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Inventory Histories"
    
    def __str__(self):
        return f"{self.action} - {self.inventory.product.name} ({self.quantity_change:+d})"
    
    def save(self, *args, **kwargs):
        # Calculate new quantity based on change
        if not self.new_quantity:
            self.new_quantity = self.previous_quantity + self.quantity_change
        super().save(*args, **kwargs)
    
# Model for Inventory
class Inventory(models.Model):
    """Represents the inventory of a specific MCC/BMC user."""
    mcc_bmc_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inventories"
    )
    product = models.ForeignKey(
        'Product', on_delete=models.CASCADE, related_name="inventories"
    )
    # Good / usable stock — the balance that STN/GRN/sales already operate on.
    quantity = models.PositiveIntegerField(default=0)
    # Condition buckets that are still physically ON HAND (held, not usable).
    expired_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    # Cumulative quantity SCRAPPED / disposed (burned, dumped). This is gone —
    # it is NOT on hand; it is kept only as an audit counter.
    scrap_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("mcc_bmc_user", "product")

    # Source buckets that stock can be marked-bad from or disposed from.
    CONDITION_FIELDS = {
        "GOOD": "quantity",
        "EXPIRED": "expired_quantity",
        "DAMAGED": "damaged_quantity",
    }

    @property
    def total_quantity(self):
        """On-hand count = usable + expired + damaged (scrap is disposed/gone)."""
        return self.quantity + self.expired_quantity + self.damaged_quantity

    def __str__(self):
        return f"Inventory for {self.mcc_bmc_user.location}: {self.product.name} ({self.quantity} units)"
    
    def clean(self):
        """Add custom validation for quantity if needed."""
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative unless for return or stock deduction purposes.")
    
    def update_quantity(self, new_quantity, action, reference_number='', notes='', user=None):
        """Update quantity and create history record"""
        if user is None:
            user = self.mcc_bmc_user
            
        previous_quantity = self.quantity
        quantity_change = new_quantity - previous_quantity
        
        # Update inventory
        self.quantity = new_quantity
        self.save()
        
        # Create history record
        InventoryHistory.objects.create(
            inventory=self,
            action=action,
            quantity_change=quantity_change,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            reference_number=reference_number,
            notes=notes,
            performed_by=user
        )
    
    def add_quantity(self, quantity_to_add, action, reference_number='', notes='', user=None):
        """Add quantity to inventory"""
        new_quantity = self.quantity + quantity_to_add
        self.update_quantity(new_quantity, action, reference_number, notes, user)
    
    def deduct_quantity(self, quantity_to_deduct, action, reference_number='', notes='', user=None):
        """Deduct quantity from inventory"""
        new_quantity = self.quantity - quantity_to_deduct
        if new_quantity < 0:
            raise ValidationError("Insufficient stock available.")
        self.update_quantity(new_quantity, action, reference_number, notes, user)


class InventoryAdjustment(models.Model):
    """
    Audit trail for stock-condition changes a location user makes on their OWN
    inventory:
      - MARK_EXPIRED / MARK_DAMAGED: move usable (Good) stock into the matching
        on-hand condition bucket (one-way).
      - DISPOSE: scrap/destroy stock (burned, dumped). The quantity leaves
        inventory entirely and a proof photo is mandatory.
    """
    ACTION_CHOICES = [
        ('MARK_EXPIRED', 'Mark Expired'),
        ('MARK_DAMAGED', 'Mark Damaged'),
        ('DISPOSE', 'Dispose / Scrap'),
    ]
    SOURCE_CHOICES = [
        ('GOOD', 'Good'),
        ('EXPIRED', 'Expired'),
        ('DAMAGED', 'Damaged'),
    ]

    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name='adjustments'
    )
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='inventory_adjustments'
    )
    location = models.CharField(max_length=255, blank=True, default='')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    # Which bucket the quantity was taken from (relevant for DISPOSE).
    source_condition = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='GOOD')
    quantity = models.PositiveIntegerField()
    # Mandatory for DISPOSE — photo of the destroyed/burned goods.
    proof = models.ImageField(upload_to='inventory_disposal_proofs/', null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} x{self.quantity} of {self.product} by {self.performed_by}"


# Model for GRN
class DoGRN(models.Model):
    grn_number = models.CharField(max_length=50, blank=True, null=True)
    requisition_number = models.CharField(max_length=50, blank=True, null=True)
    po_number = models.CharField(max_length=50)
    date_of_receipt = models.DateField(default=timezone.now)
    time_of_receipt = models.TimeField()
    location = models.CharField(max_length=255)
    chaalan_number = models.CharField(max_length=255, blank=True, null=True)
    chaalan_file = models.FileField(upload_to='chaalan/', blank=True, null=True)
    invoice_file = models.FileField(upload_to='invoice/', blank=True, null=True)
    employee_name = models.CharField(max_length=255)
    employee_code = models.CharField(max_length=255)
    uom = models.CharField(max_length=50)
    stock_item = models.CharField(max_length=255)
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField()
    quantity_rejected = models.PositiveIntegerField(default=0)
    remarks = models.TextField(blank=True, null=True)
    approval_file = models.FileField(upload_to='approval/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"GRN {self.grn_number} for PO: {self.po_number}, Product: {self.stock_item}"

class DoGRNAgainstSTN(models.Model):
    # General GRN Details
    stn_number = models.CharField(max_length=50)
    grn_number = models.CharField(max_length=50, blank=True, null=True)
    stn_date = models.DateField(default=timezone.now)
    stn_file = models.FileField(upload_to='stn_files/', blank=True, null=True)
    eway_bill_file = models.FileField(upload_to='eway_bill_files/', blank=True, null=True)
    employee_name = models.CharField(max_length=255)
    employee_code = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    department = models.CharField(max_length=255, blank=True, null=True)

    # Stock Item Details
    stock_item = models.CharField(max_length=255)
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField()
    quantity_rejected = models.PositiveIntegerField(default=0)
    rejected_file = models.FileField(upload_to='rejected_files/', blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.grn_number:
            with transaction.atomic():
                # Check if a GRN already exists for the same STN number
                last_grn = DoGRNAgainstSTN.objects.filter(stn_number=self.stn_number).order_by('-id').first()
                if last_grn and last_grn.grn_number:
                    # Use the existing GRN number for the same STN
                    self.grn_number = last_grn.grn_number
                else:
                    # Generate a new GRN number
                    self.grn_number = f"GRN-{self.stn_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"STN {self.stn_number} - {self.stock_item} (GRN: {self.grn_number})"

# Model for Advance Sale 
class AdvanceSale(models.Model):
    bmc_or_mcc = models.CharField(max_length=50, blank=True, null=True)
    mpp_with_code = models.CharField(max_length=50, blank=True, null=True)
    uom = models.CharField(max_length=50, blank=True, null=True)
    stock_item = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField(blank=True, null=True)
    dispatched_at = models.DateTimeField(auto_now_add=True)
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='advance_sales')
    pod_uploaded = models.BooleanField(default=False)  # New field to track POD status
    pod_uploaded_at = models.DateTimeField(null=True, blank=True)  # When POD was uploaded
    pod_file = models.FileField(max_length=500, upload_to='advance_sale_pods/', null=True, blank=True)  # To store POD file
    unique_code = models.CharField(max_length=50, null=True)  # Unique code for each advance sale
    pdf_file = models.FileField(upload_to='advance_sale_pdfs/', null=True, blank=True)
    pdf_generated = models.BooleanField(default=False)
    cycle = models.ForeignKey(
        'Cycle', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='advance_sales',
        verbose_name="Sales Cycle"
    )
    
    # Add sale date
    sale_date = models.DateField(default=timezone.now, verbose_name="Sale Date")
    
    # Add template reference
    template_entry = models.ForeignKey(
        'SaleTemplateEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advance_sales',
        verbose_name="Sale Template Entry"
    )
    
    def __str__(self):
        cycle_info = f" - {self.cycle.name}" if self.cycle else ""
        return f"AdvanceSale {self.unique_code}{cycle_info} - {self.stock_item}"

class BMCOrMCC(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # SAP Plant Code
    plant = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="SAP Plant Code"
    )

    def __str__(self):
        return self.name

class MPPWithCode(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('DEACTIVE', 'DeActive'),
    ]
    
    # Add this new field for unique identification
    mpp_transaction_code = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True,
        verbose_name="MPP Transaction Code"
    )
    
    bmc_or_mcc = models.ForeignKey(BMCOrMCC, on_delete=models.CASCADE, related_name="mpps")
    name_with_code = models.CharField(max_length=100)
    sahayak_mobile_number = models.CharField(max_length=15, blank=True, null=True)
    cycle = models.CharField(max_length=10, choices=[("1-10", "Cycle 1-10"), ("11-20", "Cycle 11-20"), ("21-31", "Cycle 21-31")], blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        # Remove the old unique constraint and add new one with transaction code
        unique_together = ('bmc_or_mcc', 'name_with_code', 'mpp_transaction_code')
        verbose_name = "MPP With Code"
        verbose_name_plural = "MPPs With Codes"

    def __str__(self):
        return f"{self.name_with_code} ({self.bmc_or_mcc.name}) - {self.mpp_transaction_code or 'No Code'}"

# Model for Email Settings
class EmailSettings(models.Model):
    subject = models.CharField(max_length=255, default="Purchase Requisition Notification")
    from_email = models.EmailField(default="shivamc36@gmail.com")
    cc_emails = models.TextField(blank=True, help_text="Place the person's email to put in cc using comma")
    
    def __str__(self):
        return "Email Settings"

# Model for Employee
class Employee(models.Model):
    employee_code = models.CharField(max_length=100, unique=True)
    employee_name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.employee_name

# Model for HOD Approval
class HODApproval(models.Model):
    """Tracks approval status by HOD for a Purchase Requisition."""
    requisition = models.ForeignKey('PurchaseRequisition', on_delete=models.CASCADE)
    status = models.CharField(
        max_length=250,
        choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("APPROVED FOR TRANSFER", "Approved for Transfer")],
        default="PENDING",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hod_approvals"
    )
    approval_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if not self.approval_date:
            return f"Approval for {self.requisition.requisition_number} - {self.status}"
        
        if timezone.is_naive(self.approval_date):
            approval_date = timezone.make_aware(self.approval_date)
        else:
            approval_date = self.approval_date
            
        local_approval_date = localtime(approval_date)
        formatted_date = local_approval_date.strftime("%Y-%m-%d")
        formatted_time = local_approval_date.strftime("%H:%M")
        return (
            f"Approval for {self.requisition.requisition_number} by "
            f"{self.approved_by.first_name.upper()} {self.approved_by.last_name.upper()} "
            f"on Date {formatted_date} at {formatted_time}"
        )

    def save(self, *args, **kwargs):
        if self.status in ["APPROVED", "REJECTED"] and not self.approval_date:
            self.approval_date = timezone.now()
        super().save(*args, **kwargs)

# Model for Message
class MessageQueue(models.Model):
    """Persistent database-backed message queue for guaranteed delivery"""
    MESSAGE_TYPES = [
        ('SMS', 'SMS'),
        ('WHATSAPP', 'WhatsApp'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('RETRY', 'Retry'),
    ]
    
    # Message metadata
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    advance_sale = models.ForeignKey(
        'AdvanceSale', 
        on_delete=models.CASCADE, 
        related_name='messages',
        null=True,
        blank=True
    )
    unique_code = models.CharField(max_length=50, db_index=True)
    mpp_name = models.CharField(max_length=255)
    
    # Recipient info
    mobile_number = models.CharField(max_length=15)
    
    # Message content
    message = models.TextField()
    cycle_info = models.CharField(max_length=100, blank=True, null=True)
    
    # Processing metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    last_error = models.TextField(blank=True, null=True)
    error_count = models.IntegerField(default=0)
    
    # Ordering and correlation
    sequence_number = models.BigIntegerField(default=0)  # For sequential processing
    correlation_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['sequence_number', 'created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['unique_code', 'message_type']),
        ]
        verbose_name = "Message Queue"
        verbose_name_plural = "Message Queue"
    
    def __str__(self):
        return f"{self.message_type} to {self.mobile_number} - {self.status}"
    
    def mark_processing(self):
        """Mark message as being processed"""
        self.status = 'PROCESSING'
        self.processing_started_at = timezone.now()
        self.save(update_fields=['status', 'processing_started_at'])
    
    def mark_sent(self):
        """Mark message as sent successfully"""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'sent_at', 'completed_at'])
    
    def mark_failed(self, error_message=None):
        """Mark message as failed"""
        self.status = 'FAILED'
        self.completed_at = timezone.now()
        if error_message:
            self.last_error = error_message
        self.save(update_fields=['status', 'completed_at', 'last_error'])
    
    def mark_for_retry(self, error_message=None):
        """Mark message for retry"""
        self.retry_count += 1
        self.status = 'RETRY'
        if error_message:
            self.last_error = error_message
        self.save(update_fields=['status', 'retry_count', 'last_error'])
    
    @classmethod
    def get_next_message(cls):
        """Get next pending message in sequence"""
        with transaction.atomic():
            # Select for update to lock the row
            message = cls.objects.select_for_update().filter(
                status__in=['PENDING', 'RETRY'],
                retry_count__lt=models.F('max_retries')
            ).order_by('sequence_number', 'created_at').first()
            
            if message:
                message.mark_processing()
                return message
            return None
    @classmethod
    def create_queued_messages(cls, advance_sale, messages_data):
        """Create SMS and WhatsApp messages in the queue with proper sequencing"""
        # Get the next sequence number
        last_message = cls.objects.order_by('-sequence_number').first()
        sequence_number = (last_message.sequence_number + 1) if last_message else 1
        
        messages = []
        
        # Process SMS messages
        for sms in messages_data.get("sms", []):
            message = cls(
                message_type='SMS',
                advance_sale=advance_sale,
                unique_code=advance_sale.unique_code,
                mobile_number=sms["mobile_number"],
                message=sms["message"],
                mpp_name=sms["mpp_name"],
                cycle_info=sms["cycle_info"],
                status='PENDING',
                sequence_number=sequence_number
            )
            messages.append(message)
            sequence_number += 1
        
        # Process WhatsApp messages
        for wa in messages_data.get("whatsapp", []):
            message = cls(
                message_type='WHATSAPP',
                advance_sale=advance_sale,
                unique_code=advance_sale.unique_code,
                mobile_number=wa["mobile_number"],
                message=wa["message"],
                mpp_name=wa["mpp_name"],
                cycle_info=wa["cycle_info"],
                status='PENDING',
                sequence_number=sequence_number
            )
            messages.append(message)
            sequence_number += 1
        
        # Bulk create all messages
        cls.objects.bulk_create(messages)
        return messages
# Add this to your models.py after existing MessageQueue model

class EnhancedMessageQueue(models.Model):
    """Enhanced database-backed message queue for crash-safe sequential processing"""
    MESSAGE_TYPES = [
        ('SMS', 'SMS'),
        ('WHATSAPP', 'WhatsApp'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('RETRY', 'Retry'),
    ]
    
    # Message metadata
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    advance_sale = models.ForeignKey(
        'AdvanceSale', 
        on_delete=models.CASCADE, 
        related_name='enhanced_messages',
        null=True,
        blank=True
    )
    unique_code = models.CharField(max_length=50, db_index=True)
    mpp_name = models.CharField(max_length=255)
    
    # Recipient info
    mobile_number = models.CharField(max_length=15)
    
    # Message content
    message = models.TextField()
    cycle_info = models.CharField(max_length=100, blank=True, null=True)
    
    # Processing metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    last_error = models.TextField(blank=True, null=True)
    error_count = models.IntegerField(default=0)
    
    # Ordering and correlation
    sequence_number = models.BigIntegerField(default=0, db_index=True)  # For sequential processing
    correlation_id = models.CharField(max_length=100, blank=True, null=True)
    
    # WhatsApp session management
    whatsapp_session_id = models.CharField(max_length=100, blank=True, null=True)
    whatsapp_window_active = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['sequence_number', 'created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['unique_code', 'message_type']),
            models.Index(fields=['sequence_number', 'status']),
        ]
        verbose_name = "Enhanced Message Queue"
        verbose_name_plural = "Enhanced Message Queue"
    
    def __str__(self):
        return f"{self.message_type} to {self.mobile_number} - {self.status}"
    
    def mark_processing(self):
        """Mark message as being processed"""
        self.status = 'PROCESSING'
        self.processing_started_at = timezone.now()
        self.retry_count += 1
        self.save(update_fields=['status', 'processing_started_at', 'retry_count'])
    
    def mark_sent(self):
        """Mark message as sent successfully"""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'sent_at', 'completed_at'])
    
    def mark_failed(self, error_message=None):
        """Mark message as failed"""
        self.status = 'FAILED'
        self.completed_at = timezone.now()
        if error_message:
            self.last_error = error_message[:500]  # Limit error message length
        self.save(update_fields=['status', 'completed_at', 'last_error'])
    
    def mark_for_retry(self, error_message=None):
        """Mark message for retry"""
        self.status = 'RETRY'
        if error_message:
            self.last_error = error_message[:500]
        self.save(update_fields=['status', 'last_error'])
    
    @classmethod
    def get_next_sequence_number(cls):
        """Get next sequence number for ordering"""
        last = cls.objects.order_by('-sequence_number').first()
        return (last.sequence_number + 1) if last else 1
    
    @classmethod
    def get_next_message(cls):
        """Get next pending message in sequence with locking"""
        with transaction.atomic():
            # Select for update to lock the row
            message = cls.objects.select_for_update(
                skip_locked=True
            ).filter(
                status__in=['PENDING', 'RETRY'],
                retry_count__lt=models.F('max_retries')
            ).order_by('sequence_number', 'created_at').first()
            
            if message:
                message.mark_processing()
                return message
            return None

class MessageDeliveryLog(models.Model):
    """Detailed audit log for each message delivery attempt"""
    message_queue = models.ForeignKey(MessageQueue, on_delete=models.CASCADE, related_name='delivery_logs')
    attempt_number = models.IntegerField()
    status = models.CharField(max_length=20)
    sent_via = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(max_length=255, null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Attempt {self.attempt_number} - {self.status}"
        
# Model for MCC or BMC User
class MCCBMCUser(models.Model):
    """Represents MCC/BMC users at different locations."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    location = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.user.first_name} ({self.location})"

# Model for Product
class ProductVendor(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='product_vendors')
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='product_vendors')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'vendor')

    def __str__(self):
        return f"{self.product.name} - {self.vendor.name}"

# Model for Product
class Product(models.Model):
    
    CATEGORY_CHOICES = [
        ('CONSUMABLE', 'Consumable'),
        ('ASSET', 'Asset'),
        ('TRADING', 'Trading'),
        ('SERVICE', 'Service'),
        ('RAW_MATERIAL', 'Raw Material'),
        ('FINISHED_GOOD', 'Finished Good'),
        ('SPARE_PART', 'Spare Part'),
        ('OTHER', 'Other'),
    ]
     
    product_code = models.CharField(max_length=255, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, unique=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    uom = models.CharField(max_length=50, choices=UOM_CHOICES, blank=True, null=True)
    material_type = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES, 
        null=True, 
        blank=True,
        help_text="Product category (Consumable, Asset, Trading, etc.)"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    vendors = models.ManyToManyField('Vendor', through='ProductVendor', related_name='products')
    hod = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='hod_products',
        limit_choices_to={'is_hod': True},
        verbose_name="Assigned HOD",
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'size'], name='unique_product_name_size')
        ]

    def __str__(self):
        return f"{self.name} - {self.size}"

class PurchaseRequisition(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True
    )
    requisition_number = models.CharField(max_length=10, editable=False, default="")
    date_of_request = models.DateField(auto_now_add=True)
    time_of_request = models.TimeField(auto_now_add=True)
    department = models.CharField(
        max_length=100, choices=DEPARTMENT_CHOICES, blank=True, null=True
    )
    employee_name = models.CharField(max_length=245, default="EMPLOYEE")
    employee_code = models.CharField(max_length=50, choices=EMPLOYEE_CODE_CHOICES)
    location = models.CharField(
        max_length=100, choices=LOCATION_CHOICES, default="LOCATION NOT PROVIDED"
    )
    uom = models.CharField(max_length=20, choices=UOM_CHOICES)
    stock_item = models.CharField(max_length=255)
    quantity = models.IntegerField()
    expected_delivery_date = models.DateField(default=timezone.now, null=True, blank=True)
    remark = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=250, choices=STATUS_CHOICES, default="INDENT RAISED"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    po_number = models.CharField(max_length=200, null=True, blank=True)
    grn_done = models.BooleanField(default=False)
    send_grn_mail = models.BooleanField(default=False)
    grn_cancelled = models.BooleanField(default=False)
    grn_cancelled_at = models.DateTimeField(null=True, blank=True)
    grn_cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="cancelled_grns"
    )

    def __str__(self):
        return f"{self.requisition_number} - {self.employee_name}"

    def save(self, *args, **kwargs):
        """Override the save method to handle unique requisition number, inventory update, and assign the current user to created_by."""
        if not self.requisition_number:
            last_requisition = (
                PurchaseRequisition.objects.filter(requisition_number__startswith="REQ")
                .order_by("-id")
                .first()
            )
            last_number = (
                int(last_requisition.requisition_number[3:]) if last_requisition else 0
            )
            self.requisition_number = f"REQ{last_number + 1:04d}"
        if not self.created_by and "user" in kwargs:
            self.created_by = kwargs.get("user")
        super().save(*args, **kwargs)

    def propagate_quantity_change(self, new_quantity):
        """
        Call this after updating self.quantity to cascade the change
        to all linked models. Returns a summary dict of what was updated.
        """
        updated = {}

        # Update LogisticDepartment records
        logistic_count = LogisticDepartment.objects.filter(
            requisition=self
        ).update(quantity=new_quantity)
        updated['logistic_department'] = logistic_count

        # Update DoGRN records (quantity_ordered only — received/rejected stay intact)
        grn_count = DoGRN.objects.filter(
            requisition_number=self.requisition_number
        ).update(quantity_ordered=new_quantity)
        updated['do_grn'] = grn_count

        return updated
        
class PurchaseDepartment(models.Model):
    """Represents the purchase department's process for a Purchase Requisition."""
    requisition = models.ForeignKey(PurchaseRequisition, on_delete=models.CASCADE)
    po_number = models.CharField(max_length=255, null=True, blank=True, unique=True)
    po_generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_dept"
    )
    po_generation_date = models.DateTimeField(null=True, blank=True)
    party_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    remarks_of = models.CharField(max_length=254, null=True, blank=True)
    mail_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"PO for {self.requisition.requisition_number} - {self.po_number}"
    
class LogisticDepartment(models.Model):
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True
    )
    requisition = models.ForeignKey(
        'PurchaseRequisition', on_delete=models.CASCADE, related_name='logistics', null=True, blank=True
    )
    to_location = models.CharField(max_length=100)
    from_location = models.CharField(max_length=100)
    stock_item = models.CharField(max_length=255)
    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    stn_number = models.CharField(max_length=30, null=True)
    mail_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"STN: {self.stn_number} - {self.stock_item} transfer from {self.from_location} to {self.to_location}"

# Transfering the Product between BMC or MCC user.
class Transfer(models.Model):
    """Represents inventory transfer between MCC/BMC users."""
    from_user = models.ForeignKey(
        MCCBMCUser, on_delete=models.CASCADE, related_name="transfers_out"
    )
    to_user = models.ForeignKey(
        MCCBMCUser, on_delete=models.CASCADE, related_name="transfers_in"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="transfers"
    )
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")],
        default="PENDING",
    )
    
    def __str__(self):
        return f"Transfer-{self.id}: {self.from_user.location} -> {self.to_user.location}"


class StockTransferNote(models.Model):
    """
    A Stock Transfer Note (STN) raised by a location user to move material to
    another location. This is the header record; line items are stored in
    StockTransferNoteItem. Generating an STN produces a PDF and saves this
    record so it can be listed and re-downloaded later (no inventory change).
    """
    stn_number = models.CharField(max_length=20, unique=True, editable=False, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="stock_transfer_notes",
    )
    from_location = models.CharField(max_length=255)
    from_address = models.TextField(blank=True, null=True)
    to_location = models.CharField(max_length=255)
    to_address = models.TextField(blank=True, null=True)
    transporter_name = models.CharField(max_length=255, blank=True, null=True)
    vehicle_number = models.CharField(max_length=50, blank=True, null=True)
    driver_name = models.CharField(max_length=255, blank=True, null=True)
    driver_contact = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Final posting: generating an STN only creates the draft document. The
    # creator must "Final Post" it to actually commit the dispatch — that is
    # when the items are deducted from their inventory.
    is_posted = models.BooleanField(default=False)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posted_stns",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    # Receiving side: the destination acknowledges receipt, which adds the
    # items to their inventory.
    is_received = models.BooleanField(default=False)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_stns",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    # GRN-against-STN: assigned when the destination receives the STN. Holds
    # the GRN number, the receipt document (always uploaded on receipt), and an
    # optional proof-of-receipt document (required only when received short).
    grn_number = models.CharField(max_length=30, blank=True, default="")
    receipt = models.FileField(upload_to="stn_grn_receipts/", null=True, blank=True)
    proof = models.FileField(upload_to="stn_grn_proofs/", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stn_number}: {self.from_location} -> {self.to_location}"

    def save(self, *args, **kwargs):
        """Assign a sequential STN-NNNNNN number on first save."""
        if not self.stn_number:
            last = (
                StockTransferNote.objects.filter(stn_number__startswith="STN-")
                .order_by("-id")
                .first()
            )
            last_num = (
                int(last.stn_number.split("-")[-1]) if last and last.stn_number else 0
            )
            self.stn_number = f"STN-{last_num + 1:06d}"
        super().save(*args, **kwargs)


class StockTransferNoteItem(models.Model):
    """A single line item (stock item + quantity) on a Stock Transfer Note."""
    stn = models.ForeignKey(
        StockTransferNote, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        'Product', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stn_items",
    )
    stock_item = models.CharField(max_length=255)
    uom = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.PositiveIntegerField()  # transferred (dispatched) quantity
    received_quantity = models.PositiveIntegerField(null=True, blank=True)
    # Expired / damaged units the receiver rejected at GRN time. These are
    # returned (redispatched) to the sender's inventory instead of the receiver's.
    rejected_quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.stock_item} x{self.quantity} ({self.stn.stn_number})"

    @property
    def shortfall(self):
        """Transferred minus received (None until received)."""
        if self.received_quantity is None:
            return None
        return self.quantity - self.received_quantity


# Model for Vendor
class Vendor(models.Model):
    name = models.CharField(max_length=255, unique=True)
    email = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.name
    
# Model for Dispatch Notification 
class DispatchNotification(models.Model):
    logistic_department = models.ForeignKey(LogisticDepartment, on_delete=models.CASCADE)
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dispatch_notifications')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_notifications')
    is_dispatched = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Notification for {self.logistic_department.stock_item} from {self.from_user.location} to {self.to_user.location}"

# Model for Dispatch Log
class DispatchLog(models.Model):
    logistic_department = models.ForeignKey(LogisticDepartment, on_delete=models.CASCADE)
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    dispatched_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Dispatched {self.quantity} of {self.logistic_department.stock_item} by {self.dispatched_by.email} on {self.dispatched_at}"
    
class SMSQueue(models.Model):
    mobile_number = models.CharField(max_length=15)
    unique_code = models.CharField(max_length=50)
    mpp_name = models.CharField(max_length=255)
    cycle_info = models.CharField(max_length=100, blank=True, null=True)  # ADD THIS FIELD
    retry_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed')
    ], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"SMS to {self.mobile_number} - {self.status}"

    class Meta:
        ordering = ['created_at']
        
# ===========================
# NEW CYCLE MANAGEMENT MODELS
# ===========================

class MonthlyCycle(models.Model):
    """Main container for monthly cycles"""
    month = models.CharField(max_length=20)  # January, February, etc.
    year = models.PositiveIntegerField()
    name = models.CharField(max_length=100)  # e.g., "January 2024 Cycles"
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('month', 'year')
        verbose_name = "Monthly Cycle"
        verbose_name_plural = "Monthly Cycles"
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.month} {self.year}"
    
    @property
    def cycle_count(self):
        return self.cycles.count()
    
    @property
    def total_days(self):
        return sum(cycle.duration_days for cycle in self.cycles.all())
    
    def get_month_display(self):
        """Get display name for the month"""
        return f"{self.month} {self.year}"

class Cycle(models.Model):
    """Individual cycles within a month"""
    monthly_cycle = models.ForeignKey(MonthlyCycle, on_delete=models.CASCADE, related_name='cycles')
    name = models.CharField(max_length=50)  # e.g., "Cycle 1", "Cycle 2", "Special Cycle"
    sap_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="SAP Cycle Number")  # Add this field
    cycle_number = models.PositiveIntegerField()  # 1, 2, 3, 4, etc.
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('monthly_cycle', 'cycle_number')
        ordering = ['cycle_number']
    
    def __str__(self):
        return f"{self.monthly_cycle.month} {self.monthly_cycle.year} - {self.name}"
    
    def clean(self):
        if self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")
        
        # Check if cycle is within the month
        month_start = date(self.monthly_cycle.year, self.get_month_number(), 1)
        _, last_day = calendar.monthrange(self.monthly_cycle.year, self.get_month_number())
        month_end = date(self.monthly_cycle.year, self.get_month_number(), last_day)
        
        if self.start_date < month_start or self.end_date > month_end:
            raise ValidationError("Cycle dates must be within the month")
        
        # Check for overlapping cycles
        overlapping = Cycle.objects.filter(
            monthly_cycle=self.monthly_cycle,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(id=self.id)
        
        if overlapping.exists():
            raise ValidationError("This cycle overlaps with existing cycles in the same month")
    
    def get_month_number(self):
        """Convert month name to number"""
        month_names = ["January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
        try:
            return month_names.index(self.monthly_cycle.month) + 1
        except ValueError:
            return 1  # Default to January if month name not found
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
    
    @property
    def date_range_display(self):
        return f"{self.start_date.strftime('%d')} to {self.end_date.strftime('%d')}"
    
    @property
    def month_display(self):
        """Get month display for admin"""
        return self.monthly_cycle.get_month_display()

# ===========================
# UPDATED SALE TEMPLATE MODELS
# ===========================
        
class SaleTemplateConfig(models.Model):
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='sale_templates')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Sale Template Configuration"
        verbose_name_plural = "Sale Template Configurations"
    
    def __str__(self):
        return f"{self.cycle.monthly_cycle.month} - {self.cycle.name}"
    
    @property
    def month(self):
        """Backward compatibility - returns month from cycle"""
        return self.cycle.monthly_cycle.month
    
    @property
    def cycle_name(self):
        """Backward compatibility - returns cycle name"""
        return self.cycle.name

class SaleTemplateEntry(models.Model):
    config = models.ForeignKey(SaleTemplateConfig, on_delete=models.CASCADE)
    location = models.CharField(max_length=255)
    mpp = models.CharField(max_length=255)
    product_name = models.CharField(max_length=255)
    advance_sale_quantity = models.PositiveIntegerField(default=0)
    filled_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ('OK', 'OK - Perfect Match'),
        ('OVER_SOLD', 'Over Sold'),
        ('UNDER_SOLD', 'Under Sold'),
        ('NOT_SOLD', 'Not Sold')
    ], default='NOT_SOLD')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('config', 'location', 'mpp', 'product_name')
    
    def calculate_status(self):
        if self.filled_quantity == self.advance_sale_quantity:
            return 'OK'
        elif self.filled_quantity > self.advance_sale_quantity:
            return 'OVER_SOLD'
        elif self.filled_quantity < self.advance_sale_quantity and self.filled_quantity > 0:
            return 'UNDER_SOLD'
        else:
            return 'NOT_SOLD'
    
    def save(self, *args, **kwargs):
        self.status = self.calculate_status()
        super().save(*args, **kwargs)

class SaleUploadHistory(models.Model):
    config = models.ForeignKey(SaleTemplateConfig, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_records = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.file_name} - {self.uploaded_at}"
    
# WhatsAppLog model
class WhatsAppLog(models.Model):
    # Add these fields if not present
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent to WhatsApp server'),
        ('DELIVERED', 'Delivered to phone'),
        ('READ', 'Read by user'),
        ('FAILED', 'Failed'),
        ('NOT_REGISTERED', 'Not on WhatsApp'),  # ADD THIS
        ('RECEIVED', 'Received from user'),     # ADD THIS
        ('DELETED', 'Deleted'),                 # ADD THIS
    ]
    
    SENT_VIA_CHOICES = [
        ('WEB_WHATSAPP', 'Web WhatsApp'),
        ('PYWHATKIT', 'PyWhatKit'),
        ('API', 'API'),
        ('META_API', 'Meta Business API'),
        ('USER', 'User'),  # ADD THIS
    ]
    
    mobile_number = models.CharField(max_length=15)
    message = models.TextField()
    unique_code = models.CharField(max_length=50, blank=True, null=True)
    mpp_name = models.CharField(max_length=255, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sent_via = models.CharField(max_length=20, choices=SENT_VIA_CHOICES, default='META_API')
    
    # Template tracking
    template_name = models.CharField(max_length=100, blank=True, null=True)
    template_message_id = models.CharField(max_length=100, blank=True, null=True)  # CRITICAL: Store message ID
    template_variables = models.JSONField(default=dict, blank=True, null=True)
    api_response = models.JSONField(default=dict, blank=True, null=True)
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_count = models.IntegerField(default=0)
    last_read_at = models.DateTimeField(null=True, blank=True)
    not_registered = models.BooleanField(default=False, help_text="Number not registered on WhatsApp")
    
    # Add this field to track terminal status
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When message reached terminal state")
     # ADD THESE FIELDS:
    purpose = models.CharField(
        max_length=50,
        choices=[
            ('ADVANCE_SALE', 'Advance Sale'),
            ('GENERAL', 'General Message'),
            ('AUTO_CREATED', 'Auto-Created from Webhook'),
        ],
        default='GENERAL',
        help_text="Purpose of this WhatsApp message"
    )
    
    advance_sale = models.ForeignKey(
        'AdvanceSale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_logs'
    )
    
    def save(self, *args, **kwargs):
        """
        Auto-extract message_id from api_response if not set
        """
        # Only try to extract if template_message_id is empty/null
        if not self.template_message_id and self.api_response:
            extracted_id = self.extract_message_id(self.api_response)
            if extracted_id:
                self.template_message_id = extracted_id
        
        super().save(*args, **kwargs)
        
    def is_terminal_status(self):
        """Check if status is terminal (no further updates allowed)"""
        terminal_statuses = ['FAILED', 'NOT_REGISTERED', 'READ']
        return self.status in terminal_statuses
    
    def can_update_to_status(self, new_status):
        """
        Check if message can be updated to new status
        """
        # If already in terminal status, no updates allowed
        if self.is_terminal_status():
            logger.warning(f"Message {self.id} in terminal status {self.status}, cannot update to {new_status}")
            return False
        
        # Status order
        status_order = {
            'PENDING': 1,
            'SENT': 2,
            'DELIVERED': 3,
            'READ': 4,
            'FAILED': -1,
            'NOT_REGISTERED': -1,
        }
        
        # FAILED/NOT_REGISTERED can always be set from any non-terminal state
        if new_status in ['FAILED', 'NOT_REGISTERED']:
            return True
        
        # Check normal progression
        current_order = status_order.get(self.status, 0)
        new_order = status_order.get(new_status, 0)
        
        return new_order > current_order
        
    def can_update_status(self, new_status):
        """
        Validate status progression - prevent regression
        """
        status_order = {
            'CREATED': 0,
            'PENDING': 1,
            'SENT': 2,
            'DELIVERED': 3,
            'READ': 4,
            'FAILED': -1,
            'NOT_REGISTERED': -1,
        }
        
        current_order = status_order.get(self.status, -2)
        new_order = status_order.get(new_status, -2)
        
        # Allow FAILED/NOT_REGISTERED to be updated to any status
        if self.status in ['FAILED', 'NOT_REGISTERED']:
            return True
            
        # Don't allow regression (except from FAILED)
        return new_order > current_order
        
    def mark_as_read(self, read_time=None):
        """Mark message as read with timestamp"""
        if not read_time:
            read_time = timezone.now()
        
        self.status = 'READ'
        self.read_at = read_time
        self.last_read_at = read_time
        self.is_read = True
        self.read_count += 1
        self.save(update_fields=[
            'status', 'read_at', 'last_read_at', 'is_read', 'read_count'
        ])
        
        logger.info(f"📖 Message marked as read: {self.mobile_number} at {read_time}")
        return True
        
    def can_be_marked_read(self):
        """Check if message is eligible to be marked as read"""
        # Must be delivered first
        if self.status not in ['DELIVERED', 'SENT']:
            return False
        
        # Not already read
        if self.is_read:
            return False
            
        # Has template message ID (needed for webhook matching)
        if not self.template_message_id:
            return False
            
        return True
    
    @property
    def time_to_read(self):
        """Calculate time between sent and read"""
        if self.sent_at and self.read_at:
            return (self.read_at - self.sent_at).total_seconds()
        return None
    
    @classmethod
    def create_with_extracted_id(cls, **kwargs):
        """
        Create WhatsAppLog and auto-extract message ID from api_response
        Use this instead of objects.create() to prevent the issue
        """
        api_response = kwargs.get('api_response')
        
        # If template_message_id is not provided, try to extract it
        if 'template_message_id' not in kwargs and api_response:
            kwargs['template_message_id'] = cls.extract_message_id(api_response)
        
        # Ensure sent_at is set for SENT messages
        if kwargs.get('status') == 'SENT' and 'sent_at' not in kwargs:
            kwargs['sent_at'] = timezone.now()
        
        return cls.objects.create(**kwargs)
    
    @staticmethod
    def extract_message_id(api_response):
        """
        Extract WhatsApp message ID from API response
        Returns: message_id or None
        """
        if not api_response:
            return None
        
        try:
            # Case 1: api_response is a dict
            if isinstance(api_response, dict):
                # Check for messages array
                if 'messages' in api_response:
                    messages = api_response['messages']
                    if messages and isinstance(messages, list) and len(messages) > 0:
                        first_msg = messages[0]
                        if isinstance(first_msg, dict) and 'id' in first_msg:
                            return first_msg['id']
                
                # Check for direct message_id
                for key in ['message_id', 'id', 'wamid', 'messageId']:
                    if key in api_response:
                        return api_response[key]
            
            # Case 2: api_response is a string (JSON)
            elif isinstance(api_response, str):
                import json
                data = json.loads(api_response)
                return WhatsAppLog.extract_message_id(data)
        
        except Exception as e:
            # Silent fail - just return None
            pass
        
        return None

    def __str__(self):
        return f"WhatsApp to {self.mobile_number} - {self.status}"
    

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mobile_number', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['template_message_id']),  # IMPORTANT for webhook lookup
            models.Index(fields=['unique_code']),
        ]
        

class UploadBatch(models.Model):
    """Tracks upload batches for idempotency and auditing"""
    batch_id = models.CharField(max_length=100, unique=True, db_index=True)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processing_started_at = models.DateTimeField(null=True)
    processing_completed_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=50, choices=[
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success')
    ], default='PENDING')
    total_rows = models.PositiveIntegerField(default=0)
    rows_processed = models.PositiveIntegerField(default=0)
    rows_succeeded = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    error_summary = models.JSONField(null=True, blank=True)
    metrics = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Upload Batch"
        verbose_name_plural = "Upload Batches"
    
    def __str__(self):
        return f"{self.batch_id} - {self.file_name}"

class ProcessingErrorLog(models.Model):
    """Logs processing errors for auditing and analysis"""
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name='errors')
    row_index = models.PositiveIntegerField()
    field = models.CharField(max_length=100, null=True, blank=True)
    value = models.TextField(null=True, blank=True)
    rule = models.CharField(max_length=100)
    error_message = models.TextField()
    suggestion = models.TextField(null=True, blank=True)
    is_critical = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['batch', 'row_index']
        indexes = [
            models.Index(fields=['batch', 'row_index']),
            models.Index(fields=['rule']),
        ]
    
    def __str__(self):
        return f"Error in batch {self.batch.batch_id}, row {self.row_index}: {self.rule}"
    
    
from enum import Enum

class ProcessingStatus(Enum):
    """Upload processing status"""
    PENDING = "PENDING"          # Upload received, not yet started
    PROCESSING = "PROCESSING"    # Currently being processed
    COMPLETED = "COMPLETED"      # Successfully completed with all rows processed
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"  # Some rows succeeded, some failed
    FAILED = "FAILED"            # Complete failure
    CANCELLED = "CANCELLED"      # Manually cancelled by user or system
    
class ProductMappingUpload(models.Model):
    """Audit trail for upload operations"""
    upload_id = models.CharField(max_length=100, unique=True, db_index=True)
    user_id = models.IntegerField(null=True, blank=True)
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    status = models.CharField(max_length=50, choices=[(s.value, s.name) for s in ProcessingStatus])
    progress = models.FloatField(default=0.0)
    metrics = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_mapping_uploads'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.upload_id} - {self.status}"

class ReconciliationAuditLog(models.Model):
    """Detailed audit log for reconciliation operations"""
    upload = models.ForeignKey(ProductMappingUpload, on_delete=models.CASCADE, related_name='audit_logs')
    row_index = models.IntegerField()
    action_type = models.CharField(max_length=50)  # CREATE, UPDATE, MERGE, SKIP, REJECT
    entity_type = models.CharField(max_length=50)  # GROUP, MAPPING, RELATION
    entity_id = models.IntegerField(null=True, blank=True)
    entity_identifier = models.CharField(max_length=500)
    changes = models.JSONField(default=dict, blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reconciliation_audit_logs'
        indexes = [
            models.Index(fields=['upload', 'row_index']),
            models.Index(fields=['action_type', 'timestamp']),
        ]    
        
# =========== SAP PO INTEGRATION MODELS ==============

class SAPPOExcelUpload(models.Model):
    """Tracks SAP Excel uploads for audit trail"""
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    upload_date = models.DateTimeField(auto_now_add=True)
    total_rows = models.PositiveIntegerField(default=0)
    rows_processed = models.PositiveIntegerField(default=0)
    rows_succeeded = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ], default='PENDING')
    
    class Meta:
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.filename} - {self.upload_date.strftime('%Y-%m-%d %H:%M')}"


class SAPMaterialPOMapping(models.Model):
    """Maps materials to their SAP PO numbers, linked to ProductMappingGroup"""
    upload = models.ForeignKey(SAPPOExcelUpload, on_delete=models.CASCADE, related_name='po_mappings')
    product_group = models.ForeignKey(
        ProductMappingGroup, 
        on_delete=models.CASCADE, 
        related_name='sap_po_mappings',
        null=True,  # Can be null if no mapping found
        blank=True
    )
    sap_material_code = models.CharField(max_length=100)  # SAP material code
    sap_material_name = models.CharField(max_length=500)  # SAP short text
    po_number = models.CharField(max_length=50, db_index=True)
    order_quantity = models.DecimalField(max_digits=15, decimal_places=2)
    plant = models.CharField(max_length=100, blank=True, null=True)
    storage_location = models.CharField(max_length=100, blank=True, null=True)
    document_date = models.DateField()
    vendor_info = models.CharField(max_length=500, blank=True, null=True)  # Read-only vendor metadata
    
    # Usage tracking
    is_used = models.BooleanField(default=False)
    used_in_requisition = models.ForeignKey(
        PurchaseRequisition, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='used_sap_pos'
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('po_number', 'sap_material_code')  # Prevent duplicate PO-material combos
        indexes = [
            models.Index(fields=['po_number', 'is_used']),
            models.Index(fields=['product_group', 'is_used']),
        ]
        ordering = ['-document_date']
    
    def __str__(self):
        return f"{self.po_number} - {self.sap_material_name}"
    
    def mark_as_used(self, requisition, user):
        """Mark this PO as used for a requisition"""
        self.is_used = True
        self.used_in_requisition = requisition
        self.used_by = user
        self.used_at = timezone.now()
        self.save()
        
    @property
    def display_text(self):
        """Display text for dropdown"""
        vendor = f" ({self.vendor_info})" if self.vendor_info else ""
        return f"{self.po_number} - Qty: {self.order_quantity}{vendor}"
    
    
# ===========================
# POST RECONCILIATION MODELS - UPDATED WITH CUMULATIVE LEDGER SYSTEM
# ===========================

class ReconciliationSheet(models.Model):
    """Stores uploaded reconciliation data from Finance"""
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('PROCESSING', 'Processing'),
        ('DISTRIBUTED', 'Distributed to Locations'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed'),
    ]
    
    # Upload details
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reconciliation_sheets')
    file_name = models.CharField(max_length=255)
    upload_date = models.DateTimeField(auto_now_add=True)
    
    # Cycle information - MANDATORY for your flow
    monthly_cycle = models.ForeignKey('MonthlyCycle', on_delete=models.CASCADE, related_name='reconciliation_sheets')
    cycle = models.ForeignKey('Cycle', on_delete=models.CASCADE, related_name='reconciliation_sheets')
    
    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Summary statistics
    total_records = models.PositiveIntegerField(default=0)
    over_recorded_count = models.PositiveIntegerField(default=0)
    under_recorded_count = models.PositiveIntegerField(default=0)
    perfect_match_count = models.PositiveIntegerField(default=0)
    not_recorded_count = models.PositiveIntegerField(default=0)  # Added for NOT RECORDED status
    
    # File reference
    excel_file = models.FileField(upload_to='reconciliation_sheets/%Y/%m/', null=True, blank=True)
    
    class Meta:
        ordering = ['-upload_date']
        verbose_name = "Reconciliation Sheet"
        verbose_name_plural = "Reconciliation Sheets"
    
    def __str__(self):
        return f"{self.file_name} - {self.monthly_cycle} {self.cycle}"


class ReconciliationRecord(models.Model):
    """Individual records from reconciliation sheet - MATCHING YOUR EXCEL FORMAT"""
    STATUS_CHOICES = [
        ('OVER_RECORDED', 'OVER RECORDED'),
        ('UNDER_RECORDED', 'UNDER RECORDED'),
        ('PERFECT_MATCH', 'PERFECT MATCH'),
        ('NOT_RECORDED', 'NOT RECORDED'),  # Added for NOT RECORDED status
    ]
    
    # Parent reference
    reconciliation_sheet = models.ForeignKey(ReconciliationSheet, on_delete=models.CASCADE, related_name='records')
    
    # Location and MPP details - FROM YOUR EXCEL COLUMNS
    location = models.CharField(max_length=255)  # Location column
    mpp_code = models.CharField(max_length=50)   # MPP Code column
    mpp_name = models.CharField(max_length=255)  # MPP Name column
    mpp = models.ForeignKey('MPPWithCode', on_delete=models.SET_NULL, null=True, blank=True, 
                           related_name='reconciliation_records')
    
    # Product details - FROM YOUR EXCEL COLUMNS
    product_name = models.CharField(max_length=255)  # Product column
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='reconciliation_records')
    
    # Quantity data - FROM YOUR EXCEL COLUMNS
    advance_sale_qty = models.IntegerField(default=0)  # Advance Sale Qty column
    sap_entry_qty = models.IntegerField()              # SAP Entry Qty column
    quantity_difference = models.IntegerField(default=0)  # Calculated field
    
    # Reconciliation results - FROM YOUR EXCEL COLUMNS
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)  # Status column
    match_quality = models.CharField(max_length=100)  # Match Quality column
    
    # Action required - FROM YOUR EXCEL COLUMNS
    to_be_sent_to_mpp = models.IntegerField(default=0)  # Make sure this matches
    to_be_deducted = models.IntegerField(default=0)     # To be deducted column
    
    # Service flag - IMPORTANT FOR YOUR BUSINESS RULE
    is_service = models.BooleanField(default=False)  # To identify services like "Ai Services"
    
    # Processing flags
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Location user acknowledgment
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                       null=True, blank=True, related_name='acknowledged_reconciliations')
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['location', 'mpp_code', 'product_name']
        unique_together = ['reconciliation_sheet', 'location', 'mpp_code', 'product_name']
    
    def __str__(self):
        return f"{self.location} - {self.mpp_name} - {self.product_name}: {self.status}"
    
    def save(self, *args, **kwargs):
        # Calculate difference (should match Excel calculation)
        self.quantity_difference = self.sap_entry_qty - self.advance_sale_qty
        
        # Check if product is a service (for your business rule)
        service_keywords = ['service', 'services', 'ai service', 'consulting', 'training']
        self.is_service = any(keyword in self.product_name.lower() for keyword in service_keywords)
        
        super().save(*args, **kwargs)


class MPPProductLedger(models.Model):
    """CUMULATIVE LEDGER SYSTEM - Tracks opening/closing balances per MPP per Product per Cycle"""
    mpp = models.ForeignKey('MPPWithCode', on_delete=models.CASCADE, related_name='product_ledgers')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='mpp_ledgers')
    cycle = models.ForeignKey('Cycle', on_delete=models.CASCADE, related_name='mpp_ledgers')
    
    # Opening balance from previous cycle
    opening_balance = models.IntegerField(default=0)  # Can be positive (to send) or negative (to deduct)
    
    # Current cycle transactions
    current_advance_sale = models.IntegerField(default=0)  # Advance sale in current cycle
    current_sap_entry = models.IntegerField(default=0)     # SAP entry in current cycle
    current_difference = models.IntegerField(default=0)    # current_sap_entry - current_advance_sale
    
    # Closing balance (calculated)
    closing_balance = models.IntegerField(default=0)       # opening_balance + current_difference
    
    # Reconciliation status
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    
    # Link to reconciliation record
    reconciliation_record = models.ForeignKey(
        ReconciliationRecord, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ledger_entries'
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['mpp', 'product', 'cycle']
        ordering = ['cycle', 'mpp', 'product']
        verbose_name = "MPP Product Ledger"
        verbose_name_plural = "MPP Product Ledgers"
    
    def __str__(self):
        return f"{self.cycle} - {self.mpp.name_with_code} - {self.product.name}"
    
    def save(self, *args, **kwargs):
        # FIXED: Calculate current difference correctly
        # SAP Entry - Advance Sale = What we actually deducted vs what we sent
        self.current_difference = self.current_sap_entry - self.current_advance_sale
        
        # FIXED: Calculate closing balance correctly
        # Opening + (Advance - SAP) = What MPP owes us minus what we've deducted
        # OR more clearly: Opening + Advance - SAP
        self.closing_balance = (self.opening_balance + self.current_sap_entry - self.current_advance_sale)

        
        super().save(*args, **kwargs)
    
    def get_balance_status(self):
        """Get human-readable balance status"""
        if self.closing_balance > 0:
            return f"To be sent to MPP: {self.closing_balance}"
        elif self.closing_balance < 0:
            return f"To be deducted from MPP: {abs(self.closing_balance)}"
        else:
            return "Perfectly reconciled"
    
    def get_previous_cycle_ledger(self):
        """Get ledger entry from previous cycle"""
        if not self.cycle:
            return None
        
        # Find previous cycle in same monthly cycle
        previous_cycle = Cycle.objects.filter(
            monthly_cycle=self.cycle.monthly_cycle,
            cycle_number=self.cycle.cycle_number - 1
        ).first()
        
        if previous_cycle:
            return MPPProductLedger.objects.filter(
                mpp=self.mpp,
                product=self.product,
                cycle=previous_cycle
            ).first()
        
        return None
    
    def create_next_cycle_ledger(self):
        """Create ledger entry for next cycle with opening balance - FIXED for cross-month continuity"""
        if not self.cycle:
            return None
        
        # Try to find next cycle in same monthly cycle first
        next_cycle = Cycle.objects.filter(
            monthly_cycle=self.cycle.monthly_cycle,
            cycle_number=self.cycle.cycle_number + 1
        ).first()
        
        # If no next cycle in same month, check if this is the last cycle of the month
        if not next_cycle:
            print(f"   No next cycle in same month for {self.cycle.name}")
            
            # Check if this is the last cycle of the month
            last_cycle_in_month = Cycle.objects.filter(
                monthly_cycle=self.cycle.monthly_cycle
            ).order_by('-cycle_number').first()
            
            if last_cycle_in_month and last_cycle_in_month.id == self.cycle.id:
                print(f"   This is the last cycle of the month. Looking for next month's Cycle 1...")
                
                # Find the next month
                month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December']
                
                current_month_index = month_order.index(self.cycle.monthly_cycle.month)
                next_month_name = month_order[(current_month_index + 1) % 12]
                
                # Adjust year if going from December to January
                next_year = self.cycle.monthly_cycle.year
                if self.cycle.monthly_cycle.month == 'December':
                    next_year += 1
                
                print(f"   Looking for next month: {next_month_name} {next_year}")
                
                # Find the monthly cycle for next month
                next_monthly_cycle = MonthlyCycle.objects.filter(
                    month=next_month_name,
                    year=next_year
                ).first()
                
                if next_monthly_cycle:
                    print(f"   Found next monthly cycle: {next_monthly_cycle.month} {next_monthly_cycle.year}")
                    
                    # Find Cycle 1 of the next month
                    next_cycle = Cycle.objects.filter(
                        monthly_cycle=next_monthly_cycle,
                        cycle_number=1
                    ).first()
                    
                    if next_cycle:
                        print(f"   Found next month's Cycle 1: {next_cycle.name}")
                    else:
                        print(f"   No Cycle 1 found in next month")
                        return None
                else:
                    print(f"   No monthly cycle found for next month")
                    return None
        
        if not next_cycle:
            print(f"   No next cycle found for {self.cycle.name}")
            return None
        
        # Create or update next cycle ledger with opening balance = current closing balance
        next_ledger, created = MPPProductLedger.objects.update_or_create(
            mpp=self.mpp,
            product=self.product,
            cycle=next_cycle,
            defaults={
                'opening_balance': self.closing_balance,
                'current_advance_sale': 0,  # Reset for next cycle
                'current_sap_entry': 0,     # Reset for next cycle
                'current_difference': 0,     # Reset for next cycle
                'closing_balance': self.closing_balance  # Initially same as opening
            }
        )
        
        if created:
            print(f"   ✅ Created new ledger for next cycle: {next_cycle.name}")
        else:
            print(f"   🔄 Updated existing ledger for next cycle: {next_cycle.name}")
        
        return next_ledger


class CycleProductSummary(models.Model):
    """Summary of product totals per cycle"""
    cycle = models.ForeignKey('Cycle', on_delete=models.CASCADE, related_name='product_summaries')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='cycle_summaries')
    
    # Totals across all MPPs
    total_advance_sale = models.IntegerField(default=0)
    total_sap_entry = models.IntegerField(default=0)
    total_difference = models.IntegerField(default=0)
    total_to_send = models.IntegerField(default=0)     # Positive differences
    total_to_deduct = models.IntegerField(default=0)   # Negative differences
    
    # Statistics
    mpp_count = models.IntegerField(default=0)         # Number of MPPs with this product
    reconciled_count = models.IntegerField(default=0)  # Number of MPPs reconciled
    
    class Meta:
        unique_together = ['cycle', 'product']
        ordering = ['cycle', 'product']
    
    def __str__(self):
        return f"{self.cycle} - {self.product.name}"


class CycleLedger(models.Model):
    """Tracks opening and closing balances per product per cycle - CRITICAL FOR YOUR FLOW"""
    cycle = models.ForeignKey('Cycle', on_delete=models.CASCADE, related_name='ledger_entries')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='cycle_ledger')
    
    # Balance tracking
    opening_balance = models.IntegerField(default=0)  # From previous cycle
    advance_sale_qty = models.IntegerField(default=0)  # Total advance sale this cycle
    sap_entry_qty = models.IntegerField(default=0)    # Total SAP entry this cycle
    closing_balance = models.IntegerField(default=0)  # Calculated: opening + (advance - sap)
    
    # Status
    is_reconciled = models.BooleanField(default=False)
    reconciliation_date = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['cycle', 'product']
        ordering = ['cycle', 'product']
        verbose_name = "Cycle Ledger"
        verbose_name_plural = "Cycle Ledgers"
    
    def __str__(self):
        return f"{self.cycle} - {self.product.name}: Opening={self.opening_balance}, Closing={self.closing_balance}"
    
    def save(self, *args, **kwargs):
        # CORRECTED: pending = opening + sap - advance
        self.closing_balance = (
            self.opening_balance
            + self.sap_entry_qty
            - self.advance_sale_qty
        )
        super().save(*args, **kwargs)


    
    def get_balance_status(self):
        """Get human-readable balance status"""
        if self.closing_balance > 0:
            return f"To be sent: {self.closing_balance}"
        elif self.closing_balance < 0:
            return f"To be deducted: {abs(self.closing_balance)}"
        else:
            return "Perfectly reconciled"


class GeneralSale(models.Model):
    """Records for products to be sent to MPP after reconciliation - EXCLUDES SERVICES"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Distribution'),
        ('DISPATCHED', 'Dispatched to MPP'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Source reference
    reconciliation_record = models.ForeignKey(ReconciliationRecord, on_delete=models.CASCADE, 
                                             related_name='general_sales', null=True, blank=True)
    
    # Sale details
    location = models.CharField(max_length=255)
    mpp = models.ForeignKey('MPPWithCode', on_delete=models.CASCADE, related_name='general_sales')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='general_sales')
    quantity = models.PositiveIntegerField()
    
    # Cycle information
    cycle = models.ForeignKey('Cycle', on_delete=models.CASCADE, related_name='general_sales')
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Document generation
    pdf_file = models.FileField(upload_to='general_sale_pdfs/%Y/%m/', null=True, blank=True)
    
    # Notification tracking
    whatsapp_sent = models.BooleanField(default=False)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "General Sale"
        verbose_name_plural = "General Sales"
    
    def __str__(self):
        return f"General Sale: {self.mpp.name_with_code} - {self.product.name}: {self.quantity}"
    
    @property
    def requires_whatsapp(self):
        """Check if WhatsApp notification is required"""
        return self.status == 'PENDING' and not self.whatsapp_sent


class ReconciliationNotification(models.Model):
    """Tracks notifications sent to location users"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('VIEWED', 'Viewed'),
        ('ACKNOWLEDGED', 'Acknowledged'),
    ]
    
    reconciliation_sheet = models.ForeignKey(ReconciliationSheet, on_delete=models.CASCADE, 
                                            related_name='notifications')
    location_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                     related_name='reconciliation_notifications')
    location = models.CharField(max_length=255)
    
    # Notification details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Content
    message = models.TextField()
    pdf_file = models.FileField(upload_to='reconciliation_notifications/%Y/%m/', null=True, blank=True)
    
    # Response
    user_comments = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['reconciliation_sheet', 'location_user']
    
    def __str__(self):
        return f"Notification to {self.location_user.email} for {self.reconciliation_sheet}"
    
    def mark_viewed(self):
        """Mark notification as viewed by location user"""
        self.status = 'VIEWED'
        self.viewed_at = timezone.now()
        self.save()
    
    def mark_acknowledged(self, comments=''):
        """Mark notification as acknowledged by location user"""
        self.status = 'ACKNOWLEDGED'
        self.acknowledged_at = timezone.now()
        self.user_comments = comments


class IdempotencyRecord(models.Model):
    """
    Stores the outcome of a POST request keyed by a client-supplied idempotency key
    (sent as the ``X-Idempotency-Key`` header). Used by IdempotencyMiddleware so that
    a retried request (e.g. after a network error) never creates a second record:
    the first attempt's response is replayed instead.

    Lifecycle:
        PROCESSING -> COMPLETED  (view returned a success response, which is stored)
        PROCESSING -> FAILED     (view raised / returned an error; a later retry may re-run)
    """
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    key = models.CharField(max_length=255, unique=True, db_index=True)
    method = models.CharField(max_length=10, default='POST')
    path = models.CharField(max_length=500, blank=True, default='')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='idempotency_records',
    )
    # sha256 of the request body (JSON requests only) so we can detect a key being
    # reused with a *different* payload and reject it instead of replaying wrongly.
    request_fingerprint = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)

    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default='')
    # True when response_body holds base64-encoded bytes (binary responses such as a
    # generated PDF); decoded back to bytes on replay so the download is byte-identical.
    response_is_base64 = models.BooleanField(default=False)
    response_content_type = models.CharField(max_length=150, blank=True, default='application/json')
    response_location = models.CharField(max_length=1000, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"IdempotencyRecord {self.key} [{self.status}]"


# ======================================================================================================================
# SALE & STOCK REPORT (monthly-cycle stock statement)
# ======================================================================================================================
# A per-cycle stock statement per MCC/BMC x Product:
#   Closing = Opening + Received + StockTransfer(net) - MPP Sale - Damage - Expire
# Received / Stock Transfer are pulled from InventoryHistory for the cycle date range;
# MPP Sale is aggregated from an uploaded SAP sale export; Damage / Expire are filled by
# the admin (download -> fill -> re-upload); Opening carries forward from the previous
# cycle's finalized Closing (or a current-inventory snapshot for the very first cycle).

class StockStatement(models.Model):
    STATUS_DRAFT = 'DRAFT'
    STATUS_SALE_UPLOADED = 'SALE_UPLOADED'
    STATUS_FINALIZED = 'FINALIZED'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SALE_UPLOADED, 'Sale Uploaded'),
        (STATUS_FINALIZED, 'Finalized'),
    ]

    cycle = models.OneToOneField('Cycle', on_delete=models.CASCADE, related_name='stock_statement')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    sale_file = models.FileField(upload_to='stock_reports/sale_uploads/', null=True, blank=True, max_length=500)
    sale_file_name = models.CharField(max_length=255, blank=True, default='')
    sale_rows_total = models.PositiveIntegerField(default=0)
    sale_rows_matched = models.PositiveIntegerField(default=0)
    sale_rows_unmatched = models.PositiveIntegerField(default=0)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_statements',
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    sale_uploaded_at = models.DateTimeField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    # Set when an admin uploads a corrected report workbook. While True, the statement is
    # NOT auto-refreshed from inventory (so the manual corrections stick) until the admin
    # explicitly clicks Generate / Refresh again.
    is_manual_override = models.BooleanField(default=False)
    override_uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"StockStatement {self.cycle.name} [{self.status}]"


class StockStatementEntry(models.Model):
    statement = models.ForeignKey(StockStatement, on_delete=models.CASCADE, related_name='entries')
    bmc_or_mcc = models.ForeignKey('BMCOrMCC', on_delete=models.CASCADE, related_name='stock_statement_entries')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='stock_statement_entries')

    opening_balance = models.IntegerField(default=0)
    received = models.IntegerField(default=0)         # GRN from NDS / other company / party (action=GRN)
    received_mcc = models.IntegerField(default=0)     # incoming STN transfer from another MCC/BMC (TRANSFER_IN)
    stock_transfer = models.IntegerField(default=0)   # outgoing STN transfers to other MCC/BMC (TRANSFER_OUT, negative)
    mpp_sale = models.IntegerField(default=0)
    damage = models.IntegerField(default=0)
    expire = models.IntegerField(default=0)
    closing_balance = models.IntegerField(default=0)
    remark = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('statement', 'bmc_or_mcc', 'product')
        indexes = [
            models.Index(fields=['statement', 'bmc_or_mcc']),
        ]

    def compute_closing(self):
        return (
            (self.opening_balance or 0)
            + (self.received or 0)
            + (self.received_mcc or 0)
            + (self.stock_transfer or 0)
            - (self.mpp_sale or 0)
            - (self.damage or 0)
            - (self.expire or 0)
        )

    def save(self, *args, **kwargs):
        self.closing_balance = self.compute_closing()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bmc_or_mcc.name} / {self.product.name} = {self.closing_balance}"


class StockReportProduct(models.Model):
    """
    Admin-added extension of the fixed Sale & Stock Report product list (REPORT_ORDER in
    stock_report.py). Each row inserts one extra product into the report at `position`
    (a 0-based index within the combined order). If `locations` is empty the product shows
    for every MCC/BMC; otherwise only for the selected locations.
    """
    product = models.OneToOneField('Product', on_delete=models.CASCADE, related_name='report_extra')
    display_name = models.CharField(max_length=255, blank=True, default='')
    position = models.PositiveIntegerField(default=0)
    locations = models.ManyToManyField('BMCOrMCC', blank=True, related_name='extra_report_products')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return f"{self.display_name or self.product.name} @ {self.position}"


class MPPSaleAggregate(models.Model):
    """
    Per-MPP x product aggregation of the uploaded SAP sale export (the drill-down that
    sums up into StockStatementEntry.mpp_sale). Rows that could not be mapped to an
    internal Product / BMC-MCC are stored with matched=False for troubleshooting.
    """
    statement = models.ForeignKey(StockStatement, on_delete=models.CASCADE, related_name='mpp_sales')
    bmc_or_mcc = models.ForeignKey('BMCOrMCC', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='mpp_sale_aggregates')
    mpp = models.ForeignKey('MPPWithCode', on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='mpp_sale_aggregates')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='mpp_sale_aggregates')

    sap_plant = models.CharField(max_length=50, blank=True, default='')
    sap_mcc_name = models.CharField(max_length=150, blank=True, default='')
    sap_mpp_code = models.CharField(max_length=50, blank=True, default='')
    sap_mpp_name = models.CharField(max_length=150, blank=True, default='')
    sap_material_code = models.CharField(max_length=50, blank=True, default='')
    sap_material_desc = models.CharField(max_length=255, blank=True, default='')

    quantity = models.IntegerField(default=0)
    net_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    matched = models.BooleanField(default=False)

    class Meta:
        unique_together = ('statement', 'sap_mpp_code', 'sap_material_code')
        indexes = [
            models.Index(fields=['statement', 'matched']),
        ]

    def __str__(self):
        return f"{self.sap_mpp_name}/{self.sap_material_desc} = {self.quantity}"


class StockStatementLocationState(models.Model):
    """Per-location Damage/Expire editing gate within a statement (i.e. per cycle + location).

    The admin 'opens' a location so that location's user can fill Damage / Expire; while
    'closed' (the default) the location user sees those columns read-only. Admins can edit
    regardless. Kept as a separate row per (statement, location) so it survives statement
    re-generation (which rebuilds the entry rows).
    """
    statement = models.ForeignKey(StockStatement, on_delete=models.CASCADE, related_name='location_states')
    bmc_or_mcc = models.ForeignKey('BMCOrMCC', on_delete=models.CASCADE, related_name='stock_statement_location_states')
    damage_expire_open = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('statement', 'bmc_or_mcc')

    def __str__(self):
        return f"{self.bmc_or_mcc.name} [{'OPEN' if self.damage_expire_open else 'LOCKED'}]"