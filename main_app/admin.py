from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.db import connection
from django.contrib import messages
from django.template import loader
from django.http import HttpResponse, JsonResponse
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q, Sum, F, Prefetch
from .forms import SQLFileUploadForm
from .models import *
from django.contrib.auth.admin import UserAdmin
import os
from .views import edit_choices, download_backup, inventory_by_location
from django.conf import settings

# Custom Admin Site
class CustomAdminSite(admin.AdminSite):
    site_header = "Shwetdhara Web App Admin"
    site_title = "Shwetdhara Admin Portal"
    index_title = "Welcome to Shwetdhara Admin Dashboard"
    index_template = "admin/index.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-sql/', self.admin_view(self.upload_sql), name='upload-sql'),
            path('list-media-files/', self.admin_view(list_media_files), name='list-media-files'),
            path('edit-choices/', self.admin_view(edit_choices), name='edit-choices'),
            path('download-backup/', self.admin_view(download_backup), name='download-backup'),
            path('inventory_by_location/', self.admin_view(inventory_by_location), name='inventory_by_location'),
            path('product-mapping-overview/', self.admin_view(self.product_mapping_overview), name='product-mapping-overview'),
            path('quick-mapping-setup/', self.admin_view(self.quick_mapping_setup), name='quick-mapping-setup'),
            path('cycle-management/', self.admin_view(self.cycle_management), name='cycle-management'),
        ]
        return custom_urls + urls

    def upload_sql(self, request):
        if request.method == "POST":
            form = SQLFileUploadForm(request.POST, request.FILES)
            if form.is_valid():
                sql_file = request.FILES['sql_file']
                try:
                    sql_content = sql_file.read().decode('utf-8')
                    with connection.cursor() as cursor:
                        cursor.execute(sql_content)
                    messages.success(request, "SQL file executed successfully!")
                except Exception as e:
                    messages.error(request, f"Error executing SQL file: {e}")
        else:
            form = SQLFileUploadForm()

        return render(request, 'admin/upload_sql.html', {'form': form})

    def product_mapping_overview(self, request):
        """Overview dashboard for product mapping"""
        # Get mapping statistics
        total_groups = ProductMappingGroup.objects.count()
        active_groups = ProductMappingGroup.objects.filter(is_active=True).count()
        total_mappings = ProductMappingRelation.objects.count()
        
        # Get system-wise mapping counts
        system_stats = ProductMapping.objects.values('system').annotate(
            count=Count('id')
        ).order_by('system')
        
        # Get groups with incomplete mappings (missing systems)
        groups_with_incomplete_mappings = []
        for group in ProductMappingGroup.objects.filter(is_active=True).prefetch_related('mappings__product_mapping'):
            systems_present = set(group.mappings.values_list('product_mapping__system', flat=True))
            all_systems = set(dict(ProductMapping.SYSTEM_CHOICES).keys())
            missing_systems = all_systems - systems_present
            if missing_systems:
                groups_with_incomplete_mappings.append({
                    'group': group,
                    'missing_systems': [dict(ProductMapping.SYSTEM_CHOICES).get(system, system) for system in missing_systems]
                })
        
        # Get unmapped products (products that don't have INDENT_EASY mappings in any group)
        indent_easy_mappings_in_groups = ProductMappingRelation.objects.filter(
            product_mapping__system='INDENT_EASY'
        ).values_list('product_mapping__product_name', flat=True)
        
        unmapped_products = Product.objects.exclude(
            name__in=indent_easy_mappings_in_groups
        )[:50]  # Limit to 50
        
        context = {
            'title': 'Product Mapping Overview',
            'total_groups': total_groups,
            'active_groups': active_groups,
            'total_mappings': total_mappings,
            'system_stats': system_stats,
            'groups_with_incomplete_mappings': groups_with_incomplete_mappings,
            'unmapped_products': unmapped_products,
            'system_choices': ProductMapping.SYSTEM_CHOICES,
        }
        return render(request, 'admin/product_mapping_overview.html', context)

    def quick_mapping_setup(self, request):
        """Quick setup for product mappings"""
        if request.method == 'POST':
            product_ids = request.POST.getlist('products')
            action = request.POST.get('action')
            
            if action == 'create_groups':
                created_count = 0
                for product_id in product_ids:
                    try:
                        product = Product.objects.get(id=product_id)
                        self._create_mapping_group_from_product(product)
                        created_count += 1
                    except Product.DoesNotExist:
                        continue
                
                messages.success(request, f'Successfully created {created_count} mapping groups!')
                return redirect('custom_admin:quick-mapping-setup')
        
        # Get products without mappings
        indent_easy_mappings_in_groups = ProductMappingRelation.objects.filter(
            product_mapping__system='INDENT_EASY'
        ).values_list('product_mapping__product_name', flat=True)
        
        unmapped_products = Product.objects.exclude(
            name__in=indent_easy_mappings_in_groups
        )
        
        context = {
            'title': 'Quick Product Mapping Setup',
            'unmapped_products': unmapped_products,
        }
        return render(request, 'admin/quick_mapping_setup.html', context)

    def cycle_management(self, request):
        """Cycle management dashboard"""
        monthly_cycles = MonthlyCycle.objects.all().order_by('-year', '-month')
        current_date = timezone.now().date()
        
        # Get current month and year for default values
        current_month = current_date.strftime('%B')
        current_year = current_date.year
        
        context = {
            'title': 'Cycle Management',
            'monthly_cycles': monthly_cycles,
            'current_month': current_month,
            'current_year': current_year,
            'months': [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ],
            'years': range(current_year - 1, current_year + 3),
        }
        return render(request, 'admin/cycle_management.html', context)

    def _create_mapping_group_from_product(self, product):
        """Helper method to create mapping group from product"""
        group_name = f"{product.name} - {product.size}" if product.size else product.name
        group, created = ProductMappingGroup.objects.get_or_create(
            name=group_name,
            defaults={
                'description': f"Auto-generated mapping group for {product.name}",
                'is_active': True
            }
        )
        
        if created:
            # Create INDENT_EASY mapping as primary
            product_mapping, _ = ProductMapping.objects.get_or_create(
                system='INDENT_EASY',
                product_name=product.name,
                defaults={
                    'product_code': product.product_code,
                    'uom': product.uom,
                    'size': product.size,
                    'material_type': product.material_type,
                    'is_active': True
                }
            )
            
            ProductMappingRelation.objects.get_or_create(
                group=group,
                product_mapping=product_mapping,
                defaults={'is_primary': True}
            )
        
        return group


# Initialize the custom admin site
custom_admin_site = CustomAdminSite(name='custom_admin')


# ===========================
# USER MANAGEMENT
# ===========================

@admin.register(CustomUser, site=custom_admin_site)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': (
                'plant', 'first_name', 'last_name', 'location', 
                'is_hod', 'is_purchase', 'is_finance', 'is_logistic', 
                'employee_code', 'department', 'address', 'delivery_point_code', 
                'signature', 'mohar'
            )
        }),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'plant', 'email', 'password1', 'password2', 'location', 
                'department', 'employee_code', 'delivery_point_code', 
                'first_name', 'last_name', 'address', 'signature', 'mohar',
                'is_hod', 'is_purchase', 'is_finance', 'is_logistic'
            ),
        }),
    )
    
    list_display = (
        'plant', 'email', 'first_name', 'last_name', 'employee_code', 
        'delivery_point_code', 'location', 'department', 'get_role_badges', 
        'is_active', 'edit_button'
    )
    list_display_links = ('email',)
    list_filter = (
        'is_hod', 'is_purchase', 'is_finance', 'is_logistic', 
        'is_active', 'location', 'department', 'plant'
    )
    search_fields = ('email', 'first_name', 'last_name', 'employee_code', 'delivery_point_code')
    ordering = ('email',)
    list_editable = ('is_active',)
    list_per_page = 25
    readonly_fields = ('date_joined', 'last_login')
    filter_horizontal = ('groups', 'user_permissions')
    
    actions = ['make_hod', 'make_purchase', 'make_logistic', 'make_finance', 'remove_all_roles']

    def get_role_badges(self, obj):
        badges = []
        if obj.is_hod:
            badges.append('<span style="background-color: #4CAF50; color: white; padding: 3px 8px; border-radius: 3px; margin: 2px; display: inline-block;">HOD</span>')
        if obj.is_purchase:
            badges.append('<span style="background-color: #2196F3; color: white; padding: 3px 8px; border-radius: 3px; margin: 2px; display: inline-block;">PURCHASE</span>')
        if obj.is_logistic:
            badges.append('<span style="background-color: #FF9800; color: white; padding: 3px 8px; border-radius: 3px; margin: 2px; display: inline-block;">LOGISTIC</span>')
        if obj.is_finance:
            badges.append('<span style="background-color: #9C27B0; color: white; padding: 3px 8px; border-radius: 3px; margin: 2px; display: inline-block;">FINANCE</span>')
        return format_html(''.join(badges)) if badges else '-'
    get_role_badges.short_description = 'Roles'
    get_role_badges.allow_tags = True

    def edit_button(self, obj):
        return format_html(
            '<a class="button" href="{}/change/">Edit</a>',
            obj.id
        )
    edit_button.short_description = "Actions"
    edit_button.allow_tags = True

    def make_hod(self, request, queryset):
        queryset.update(is_hod=True)
        self.message_user(request, f"{queryset.count()} users marked as HOD.")
    make_hod.short_description = "Mark selected as HOD"

    def make_purchase(self, request, queryset):
        queryset.update(is_purchase=True)
        self.message_user(request, f"{queryset.count()} users marked as Purchase.")
    make_purchase.short_description = "Mark selected as Purchase"

    def make_logistic(self, request, queryset):
        queryset.update(is_logistic=True)
        self.message_user(request, f"{queryset.count()} users marked as Logistic.")
    make_logistic.short_description = "Mark selected as Logistic"

    def make_finance(self, request, queryset):
        queryset.update(is_finance=True)
        self.message_user(request, f"{queryset.count()} users marked as Finance.")
    make_finance.short_description = "Mark selected as Finance"

    def remove_all_roles(self, request, queryset):
        queryset.update(is_hod=False, is_purchase=False, is_logistic=False, is_finance=False)
        self.message_user(request, f"All roles removed from {queryset.count()} users.")
    remove_all_roles.short_description = "Remove all roles from selected"


# ===========================
# EMPLOYEE MANAGEMENT
# ===========================

@admin.register(Employee, site=custom_admin_site)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_code', 'employee_name', 'get_requisition_count']
    search_fields = ['employee_code', 'employee_name']
    ordering = ['employee_name']
    list_per_page = 50
    
    def get_requisition_count(self, obj):
        count = PurchaseRequisition.objects.filter(employee_code=obj.employee_code).count()
        if count:
            url = f'{custom_admin_site.name}:main_app_purchaserequisition_changelist'
            return format_html('<a href="{}?employee_code__exact={}">{}</a>', url, obj.employee_code, count)
        return count
    get_requisition_count.short_description = "Requisitions"
    
    def get_queryset(self, request):
        return super().get_queryset(request)


# ===========================
# PRODUCT & VENDOR MANAGEMENT
# ===========================

class ProductVendorInline(admin.TabularInline):
    model = ProductVendor
    extra = 1
    autocomplete_fields = ['vendor']
    verbose_name = "Vendor"
    verbose_name_plural = "Vendors"


@admin.register(Product, site=custom_admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'product_code', 'clickable_name', 'size', 'category', 'uom', 'material_type', 
        'price', 'is_active', 'hod', 'vendor_count', 'mapping_groups_count'
    ]
    list_display_links = ['clickable_name']
    list_filter = ['is_active', 'uom', 'material_type', 'hod', 'category']
    search_fields = ['product_code', 'name', 'size', 'material_type', 'category']
    list_editable = ['price', 'is_active', 'category']
    list_per_page = 25
    inlines = [ProductVendorInline]
    ordering = ['name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('product_code', 'name', 'category', 'size', 'uom', 'material_type', 'price', 'is_active')
        }),
        ('HOD Assignment', {
            'fields': ('hod',),
            'classes': ('wide',)
        }),
        ('Statistics', {
            'fields': ('vendor_count', 'mapping_groups_count'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['vendor_count', 'mapping_groups_count']
    autocomplete_fields = ['hod']
    
    actions = ['create_mapping_group_from_product']

    def clickable_name(self, obj):
        return format_html('<a href="{}">{}</a>', f'{obj.pk}/change/', obj.name)
    clickable_name.short_description = "Product Name"
    clickable_name.admin_order_field = 'name'

    def vendor_count(self, obj):
        count = obj.product_vendors.count()
        if count:
            url = f'{custom_admin_site.name}:main_app_vendor_changelist'
            return format_html('<a href="{}?products__id__exact={}">{}</a>', url, obj.id, count)
        return count
    vendor_count.short_description = "Vendors"

    def mapping_groups_count(self, obj):
        # Find ProductMapping entries that match this product name
        matching_mappings = ProductMapping.objects.filter(
            product_name=obj.name,
            system='INDENT_EASY'
        )
        
        if matching_mappings.exists():
            # Count how many groups these mappings belong to
            count = ProductMappingRelation.objects.filter(
                product_mapping__in=matching_mappings
            ).values('group').distinct().count()
            
            if count > 0:
                url = f'{custom_admin_site.name}:main_app_productmappinggroup_changelist'
                return format_html(
                    '<a href="{}?mappings__product_mapping__product_name__icontains={}">{}</a>', 
                    url, obj.name, count
                )
        return "0"
    mapping_groups_count.short_description = "Mapping Groups"

    def create_mapping_group_from_product(self, request, queryset):
        created_count = 0
        for product in queryset:
            # Check if product already has mappings in INDENT_EASY system
            existing_mappings = ProductMapping.objects.filter(
                product_name=product.name,
                system='INDENT_EASY'
            )
            
            if existing_mappings.exists():
                # Check if any of these mappings are already in groups
                existing_relations = ProductMappingRelation.objects.filter(
                    product_mapping__in=existing_mappings
                )
                if existing_relations.exists():
                    continue  # Skip if already mapped
                
            group_name = f"{product.name} - {product.size}" if product.size else product.name
            
            # Create mapping group
            group, created = ProductMappingGroup.objects.get_or_create(
                name=group_name,
                defaults={
                    'description': f"Auto-generated mapping group for {product.name}",
                    'is_active': True
                }
            )
            
            if created:
                # Create INDENT_EASY mapping
                product_mapping, _ = ProductMapping.objects.get_or_create(
                    system='INDENT_EASY',
                    product_name=product.name,
                    defaults={
                        'product_code': product.product_code,
                        'uom': product.uom,
                        'size': product.size,
                        'material_type': product.material_type,
                        'description': f"Original product: {product.name}",
                        'is_active': True
                    }
                )
                
                # Create relation as primary
                ProductMappingRelation.objects.create(
                    group=group,
                    product_mapping=product_mapping,
                    is_primary=True
                )
                created_count += 1
        
        if created_count > 0:
            self.message_user(request, f'Created {created_count} mapping groups. Please add SAP and NDDB mappings as needed.')
        else:
            self.message_user(request, 'Selected products already have mapping groups or no products were processed.')
    create_mapping_group_from_product.short_description = "Create mapping groups from products"


@admin.register(Vendor, site=custom_admin_site)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'email_preview', 'address_preview', 'product_count', 'get_po_count']
    search_fields = ['name', 'email', 'address']
    list_per_page = 25
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email', 'address')
        }),
        ('Statistics', {
            'fields': ('product_count', 'get_po_count'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['product_count', 'get_po_count']

    def email_preview(self, obj):
        if obj.email:
            return obj.email[:50] + "..." if len(obj.email) > 50 else obj.email
        return "-"
    email_preview.short_description = "Email"

    def address_preview(self, obj):
        if obj.address:
            return obj.address[:50] + "..." if len(obj.address) > 50 else obj.address
        return "-"
    address_preview.short_description = "Address"

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Products"

    def get_po_count(self, obj):
        # Count purchase departments with this vendor
        count = PurchaseDepartment.objects.filter(party_name__icontains=obj.name).count()
        if count:
            url = f'{custom_admin_site.name}:main_app_purchasedepartment_changelist'
            return format_html('<a href="{}?party_name__icontains={}">{}</a>', url, obj.name, count)
        return count
    get_po_count.short_description = "PO Count"


@admin.register(ProductVendor, site=custom_admin_site)
class ProductVendorAdmin(admin.ModelAdmin):
    list_display = ['product', 'vendor', 'added_at']
    list_filter = ['added_at']
    search_fields = ['product__name', 'vendor__name']
    readonly_fields = ['added_at']
    list_per_page = 50
    autocomplete_fields = ['product', 'vendor']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'vendor')


# ===========================
# PRODUCT MAPPING
# ===========================

class ProductMappingRelationInline(admin.TabularInline):
    model = ProductMappingRelation
    extra = 1
    autocomplete_fields = ['product_mapping']
    fields = ['product_mapping', 'is_primary', 'system_display']
    readonly_fields = ['system_display']
    ordering = ['-is_primary', 'product_mapping__system']
    
    def system_display(self, obj):
        if obj.product_mapping:
            return obj.product_mapping.get_system_display()
        return "-"
    system_display.short_description = "System"


@admin.register(ProductMapping, site=custom_admin_site)
class ProductMappingAdmin(admin.ModelAdmin):
    list_display = [
        'system', 'product_name', 'product_code', 'uom', 'size', 
        'is_active', 'mapping_groups_count', 'created_at'
    ]
    list_filter = ['system', 'is_active', 'uom', 'material_type', 'created_at']
    search_fields = ['product_name', 'product_code', 'description']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at', 'mapping_groups_count']
    list_per_page = 25
    ordering = ['system', 'product_name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('system', 'product_name', 'product_code', 'is_active')
        }),
        ('Product Details', {
            'fields': ('description', 'uom', 'size', 'material_type'),
            'classes': ('collapse',)
        }),
        ('Mapping Information', {
            'fields': ('mapping_groups_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def mapping_groups_count(self, obj):
        count = obj.groups.count()
        if count > 0:
            url = f'{custom_admin_site.name}:main_app_productmappinggroup_changelist'
            return format_html('<a href="{}?mappings__product_mapping__id__exact={}">{}</a>', 
                             url, obj.id, count)
        return count
    mapping_groups_count.short_description = "Mapping Groups"


@admin.register(ProductMappingGroup, site=custom_admin_site)
class ProductMappingGroupAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'is_active', 'mapped_products_count', 'systems_covered', 
        'primary_product', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at', 'systems_covered', 'primary_product']
    list_per_page = 25
    ordering = ['name']
    inlines = [ProductMappingRelationInline]
    
    actions = ['activate_groups', 'deactivate_groups', 'create_missing_mappings']

    def mapped_products_count(self, obj):
        count = obj.mappings.count()
        if count > 0:
            url = f'{custom_admin_site.name}:main_app_productmappingrelation_changelist'
            return format_html('<a href="{}?group__id__exact={}">{}</a>', url, obj.id, count)
        return count
    mapped_products_count.short_description = "Mapped Products"

    def systems_covered(self, obj):
        systems = obj.mappings.values_list('product_mapping__system', flat=True).distinct()
        system_names = [dict(ProductMapping.SYSTEM_CHOICES).get(system, system) for system in systems]
        return ", ".join(system_names) if system_names else "No systems"
    systems_covered.short_description = "Systems Covered"

    def primary_product(self, obj):
        primary = obj.mappings.filter(is_primary=True).first()
        if primary and primary.product_mapping:
            return f"{primary.product_mapping.product_name} ({primary.product_mapping.get_system_display()})"
        return "No primary"
    primary_product.short_description = "Primary Product"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'mappings__product_mapping'
        )

    def activate_groups(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} mapping groups activated.')
    activate_groups.short_description = "Activate selected mapping groups"

    def deactivate_groups(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} mapping groups deactivated.')
    deactivate_groups.short_description = "Deactivate selected mapping groups"

    def create_missing_mappings(self, request, queryset):
        created_count = 0
        for group in queryset:
            # Get existing systems in this group
            existing_systems = set(group.mappings.values_list('product_mapping__system', flat=True))
            all_systems = set(dict(ProductMapping.SYSTEM_CHOICES).keys())
            
            missing_systems = all_systems - existing_systems
            
            for system in missing_systems:
                # Get primary product name to use as base
                primary_mapping = group.mappings.filter(is_primary=True).first()
                base_name = group.name
                if primary_mapping and primary_mapping.product_mapping:
                    base_name = primary_mapping.product_mapping.product_name
                
                # Create system-specific product name
                system_suffix = dict(ProductMapping.SYSTEM_CHOICES)[system]
                product_name = f"{base_name} - {system_suffix}"
                
                # Create placeholder product mapping for missing system
                product_mapping, created = ProductMapping.objects.get_or_create(
                    system=system,
                    product_name=product_name,
                    defaults={
                        'description': f"Auto-generated mapping for {group.name} in {system_suffix}",
                        'is_active': True
                    }
                )
                
                if created:
                    ProductMappingRelation.objects.create(
                        group=group,
                        product_mapping=product_mapping,
                        is_primary=False
                    )
                    created_count += 1
        
        self.message_user(request, f'Created {created_count} missing mappings across {queryset.count()} groups.')
    create_missing_mappings.short_description = "Create missing system mappings"


@admin.register(ProductMappingRelation, site=custom_admin_site)
class ProductMappingRelationAdmin(admin.ModelAdmin):
    list_display = ['group', 'product_mapping', 'system_display', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'group', 'product_mapping__system', 'created_at']
    search_fields = ['group__name', 'product_mapping__product_name']
    list_editable = ['is_primary']
    readonly_fields = ['created_at', 'system_display']
    list_per_page = 50
    ordering = ['group', '-is_primary', 'product_mapping__system']
    autocomplete_fields = ['group', 'product_mapping']

    def system_display(self, obj):
        if obj.product_mapping:
            return obj.product_mapping.get_system_display()
        return "-"
    system_display.short_description = "System"
    system_display.admin_order_field = 'product_mapping__system'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'group', 'product_mapping'
        )


# ===========================
# PURCHASE REQUISITION & APPROVALS
# ===========================

class HODApprovalInline(admin.StackedInline):
    model = HODApproval
    extra = 0
    max_num = 1
    fields = ['status', 'approved_by', 'approval_date']
    readonly_fields = ['approval_date']
    autocomplete_fields = ['approved_by']


@admin.register(PurchaseRequisition, site=custom_admin_site)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = [
        'requisition_number', 'stock_item', 'status_badge', 'employee_name', 
        'quantity', 'location', 'created_at', 'hod_approval_status', 'grn_done',
        'status'  # Added status to list_display for list_editable
    ]
    list_filter = ['status', 'location', 'department', 'created_at', 'grn_done']
    search_fields = ['requisition_number', 'employee_name', 'stock_item', 'employee_code']
    list_editable = ['status', 'quantity']
    readonly_fields = ['requisition_number', 'created_at', 'time_of_request', 'date_of_request']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    inlines = [HODApprovalInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('requisition_number', 'status', 'employee_name', 'employee_code')
        }),
        ('Request Details', {
            'fields': ('department', 'location', 'stock_item', 'quantity', 'uom')
        }),
        ('Dates', {
            'fields': ('date_of_request', 'time_of_request', 'expected_delivery_date', 'created_at')
        }),
        ('Additional Information', {
            'fields': ('remark', 'po_number', 'grn_done', 'send_grn_mail'),
            'classes': ('collapse',)
        }),
        ('GRN Cancellation', {
            'fields': ('grn_cancelled', 'grn_cancelled_at', 'grn_cancelled_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_grn_done', 'send_grn_mail']

    def status_badge(self, obj):
        colors = {
            'INDENT RAISED': '#FFC107',
            'HOD APPROVED': '#17A2B8',
            'PURCHASE ORDER GENERATED': '#007BFF',
            'GOODS RECEIVED': '#28A745',
            'REJECTED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    status_badge.allow_tags = True

    def hod_approval_status(self, obj):
        try:
            # Change this line - use the correct related name
            approval = obj.hodapproval_set.first()  # or obj.hod_approvals.first() if you updated the model
            if approval:
                colors = {
                    'PENDING': '#FFC107',
                    'APPROVED': '#28A745',
                    'REJECTED': '#DC3545',
                    'APPROVED FOR TRANSFER': '#17A2B8'
                }
                color = colors.get(approval.status, '#6C757D')
                return format_html(
                    '<span style="background-color: {}; color: white; padding: 2px 5px; border-radius: 3px;">{}</span>',
                    color, approval.status
                )
            return format_html('<span style="color: #6C757D;">No Approval</span>')
        except:
            return format_html('<span style="color: #6C757D;">No Approval</span>')
    hod_approval_status.short_description = "HOD Approval"

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user

        # Detect if quantity changed on an existing record
        if change and 'quantity' in form.changed_data:
            old_quantity = PurchaseRequisition.objects.get(pk=obj.pk).quantity
            new_quantity = obj.quantity

            super().save_model(request, obj, form, change)

            # Cascade quantity change to LogisticDepartment
            LogisticDepartment.objects.filter(
                requisition=obj
            ).update(quantity=new_quantity)

            # Cascade to DoGRN — update quantity_ordered
            DoGRN.objects.filter(
                requisition_number=obj.requisition_number
            ).update(quantity_ordered=new_quantity)

            messages.warning(
                request,
                f"Quantity updated from {old_quantity} to {new_quantity} on "
                f"{obj.requisition_number}. Linked LogisticDepartment and GRN "
                f"records have been updated automatically."
            )
        else:
            super().save_model(request, obj, form, change)

        # Create HODApproval if not exists and status is INDENT RAISED
        if obj.status == 'INDENT RAISED' and not obj.hodapproval_set.exists():
            HODApproval.objects.get_or_create(requisition=obj)

    def mark_as_grn_done(self, request, queryset):
        updated = queryset.update(grn_done=True)
        self.message_user(request, f'{updated} requisitions marked as GRN done.')
    mark_as_grn_done.short_description = "Mark selected as GRN done"

    def send_grn_mail(self, request, queryset):
        updated = queryset.update(send_grn_mail=True)
        self.message_user(request, f'GRN mail flag set for {updated} requisitions.')
    send_grn_mail.short_description = "Set GRN mail flag"

    def get_queryset(self, request):
        # Change this line - use the correct related name
        return super().get_queryset(request).select_related('created_by').prefetch_related('hodapproval_set')


@admin.register(HODApproval, site=custom_admin_site)
class HODApprovalAdmin(admin.ModelAdmin):
    list_display = (
        'requisition_link',
        'status_badge',
        'approved_by_display',
        'approval_date_display',
        'action_buttons'
    )
    list_filter = ('status', 'approval_date')
    search_fields = (
        'requisition__requisition_number',
        'approved_by__email',
        'approved_by__first_name',
        'approved_by__last_name'
    )
    raw_id_fields = ('requisition', 'approved_by')
    date_hierarchy = 'approval_date'
    ordering = ('-approval_date',)
    list_per_page = 25
    actions = ['approve_selected', 'reject_selected', 'approve_for_transfer_selected']

    def requisition_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/purchaserequisition/{obj.requisition.id}/change/',
            obj.requisition.requisition_number
        )
    requisition_link.short_description = "Requisition"

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'APPROVED': '#28A745',
            'REJECTED': '#DC3545',
            'APPROVED FOR TRANSFER': '#17A2B8'
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'

    def approved_by_display(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}"
        return "-"
    approved_by_display.short_description = "Approved By"

    def approval_date_display(self, obj):
        if obj.approval_date:
            if timezone.is_naive(obj.approval_date):
                approval_date = timezone.make_aware(obj.approval_date)
            else:
                approval_date = obj.approval_date
            
            local_date = timezone.localtime(approval_date)
            return local_date.strftime("%Y-%m-%d %H:%M")
        return "-"
    approval_date_display.short_description = "Approval Date"

    def action_buttons(self, obj):
        if obj.status == "PENDING":
            return format_html(
                '<a class="button" href="{}/change/">Process</a>',
                obj.id
            )
        return format_html(
            '<a class="button" href="../../main_app/purchaserequisition/{}/change/">View Requisition</a>',
            obj.requisition.id
        )
    action_buttons.short_description = "Actions"

    def approve_selected(self, request, queryset):
        updated = queryset.update(
            status="APPROVED", 
            approval_date=timezone.now(), 
            approved_by=request.user
        )
        # Update related requisitions
        for approval in queryset:
            approval.requisition.status = "HOD APPROVED"
            approval.requisition.save()
        self.message_user(request, f'{updated} approvals marked as approved.')
    approve_selected.short_description = "Mark selected as approved"

    def approve_for_transfer_selected(self, request, queryset):
        updated = queryset.update(
            status="APPROVED FOR TRANSFER", 
            approval_date=timezone.now(), 
            approved_by=request.user
        )
        for approval in queryset:
            approval.requisition.status = "HOD APPROVED"
            approval.requisition.save()
        self.message_user(request, f'{updated} approvals marked as approved for transfer.')
    approve_for_transfer_selected.short_description = "Mark selected as approved for transfer"

    def reject_selected(self, request, queryset):
        updated = queryset.update(
            status="REJECTED", 
            approval_date=timezone.now(), 
            approved_by=request.user
        )
        for approval in queryset:
            approval.requisition.status = "REJECTED"
            approval.requisition.save()
        self.message_user(request, f'{updated} approvals marked as rejected.')
    reject_selected.short_description = "Mark selected as rejected"

    def save_model(self, request, obj, form, change):
        if obj.status in ["APPROVED", "REJECTED", "APPROVED FOR TRANSFER"] and not obj.approval_date:
            obj.approval_date = timezone.now()
            if not obj.approved_by:
                obj.approved_by = request.user
            
            # Update requisition status
            if obj.status in ["APPROVED", "APPROVED FOR TRANSFER"]:
                obj.requisition.status = "HOD APPROVED"
            elif obj.status == "REJECTED":
                obj.requisition.status = "REJECTED"
            obj.requisition.save()
            
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requisition', 'approved_by')


@admin.register(PurchaseDepartment, site=custom_admin_site)
class PurchaseDepartmentAdmin(admin.ModelAdmin):
    list_display = [
        'requisition_link', 'po_number', 'po_generated_by', 
        'po_generation_date', 'party_name', 'email', 'mail_sent_badge'
    ]
    list_filter = ['po_generation_date', 'mail_sent']
    search_fields = ['requisition__requisition_number', 'po_number', 'party_name', 'email']
    readonly_fields = ['po_generation_date']
    date_hierarchy = 'po_generation_date'
    list_per_page = 25
    ordering = ['-po_generation_date']
    autocomplete_fields = ['requisition', 'po_generated_by']
    
    fieldsets = (
        ('Requisition Information', {
            'fields': ('requisition',)
        }),
        ('PO Details', {
            'fields': ('po_number', 'party_name', 'email', 'mail_sent')
        }),
        ('Generation Information', {
            'fields': ('po_generated_by', 'po_generation_date', 'remarks_of')
        }),
    )

    def requisition_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/purchaserequisition/{obj.requisition.id}/change/',
            obj.requisition.requisition_number
        )
    requisition_link.short_description = "Requisition"

    def mail_sent_badge(self, obj):
        if obj.mail_sent:
            return format_html('<span style="color: #28A745;">✓ Sent</span>')
        return format_html('<span style="color: #DC3545;">✗ Not Sent</span>')
    mail_sent_badge.short_description = "Mail Status"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requisition', 'po_generated_by')


# ===========================
# GRN MANAGEMENT
# ===========================

@admin.register(DoGRN, site=custom_admin_site)
class DoGRNAdmin(admin.ModelAdmin):
    list_display = [
        'grn_number', 'po_number', 'requisition_number', 'stock_item', 
        'quantity_display', 'chaalan_number', 'chalan_file_link', 'invoice_file_link',
        'created_at'
    ]
    list_filter = ['location', 'date_of_receipt', 'created_at']
    search_fields = ['grn_number', 'po_number', 'requisition_number', 'stock_item', 'employee_name', 'chaalan_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('grn_number', 'po_number', 'requisition_number', 'date_of_receipt', 'time_of_receipt')
        }),
        ('Location & Employee', {
            'fields': ('location', 'employee_name', 'employee_code')
        }),
        ('Item Details', {
            'fields': ('stock_item', 'uom', 'quantity_ordered', 'quantity_received', 'quantity_rejected')
        }),
        ('Documents', {
            'fields': ('chaalan_number', 'chaalan_file', 'invoice_file', 'approval_file')
        }),
        ('Additional', {
            'fields': ('remarks', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def quantity_display(self, obj):
        return f"{obj.quantity_received}/{obj.quantity_ordered} (Rej: {obj.quantity_rejected})"
    quantity_display.short_description = "Qty (Rec/Ord/Rej)"

    def chalan_file_link(self, obj):
        if obj.chaalan_file:
            return format_html('<a href="{}" target="_blank">📄 View</a>', obj.chaalan_file.url)
        return "-"
    chalan_file_link.short_description = 'Chalan File'

    def invoice_file_link(self, obj):
        if obj.invoice_file:
            return format_html('<a href="{}" target="_blank">📄 View</a>', obj.invoice_file.url)
        return "-"
    invoice_file_link.short_description = 'Invoice File'


@admin.register(DoGRNAgainstSTN, site=custom_admin_site)
class DoGRNAgainstSTNAdmin(admin.ModelAdmin):
    list_display = [
        'stn_number', 'grn_number', 'stock_item', 'quantity_display', 
        'location', 'stn_file_link', 'eway_bill_link', 'created_at'
    ]
    list_filter = ['location', 'department', 'stn_date', 'created_at']
    search_fields = ['stn_number', 'grn_number', 'stock_item', 'employee_name', 'employee_code']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    
    fieldsets = (
        ('STN Information', {
            'fields': ('stn_number', 'grn_number', 'stn_date')
        }),
        ('Employee Details', {
            'fields': ('employee_name', 'employee_code', 'location', 'department')
        }),
        ('Item Details', {
            'fields': ('stock_item', 'quantity_ordered', 'quantity_received', 'quantity_rejected')
        }),
        ('Documents', {
            'fields': ('stn_file', 'eway_bill_file', 'rejected_file')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def quantity_display(self, obj):
        return f"{obj.quantity_received}/{obj.quantity_ordered} (Rej: {obj.quantity_rejected})"
    quantity_display.short_description = "Qty (Rec/Ord/Rej)"

    def stn_file_link(self, obj):
        if obj.stn_file:
            return format_html('<a href="{}" target="_blank">📄 STN</a>', obj.stn_file.url)
        return "-"
    stn_file_link.short_description = 'STN File'

    def eway_bill_link(self, obj):
        if obj.eway_bill_file:
            return format_html('<a href="{}" target="_blank">📄 E-Way</a>', obj.eway_bill_file.url)
        return "-"
    eway_bill_link.short_description = 'E-Way Bill'


# ===========================
# LOGISTICS MANAGEMENT
# ===========================

@admin.register(LogisticDepartment, site=custom_admin_site)
class LogisticDepartmentAdmin(admin.ModelAdmin):
    list_display = [
        'stn_number', 'requisition_link', 'to_location', 'from_location', 
        'stock_item', 'quantity', 'created_at', 'mail_sent_badge'
    ]
    list_filter = ['to_location', 'from_location', 'created_at', 'mail_sent']
    search_fields = ['stn_number', 'stock_item', 'requested_by__email', 'to_location', 'from_location']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    autocomplete_fields = ['requested_by', 'requisition']

    def requisition_link(self, obj):
        if obj.requisition:
            return format_html(
                '<a href="{}">{}</a>',
                f'../../main_app/purchaserequisition/{obj.requisition.id}/change/',
                obj.requisition.requisition_number
            )
        return "-"
    requisition_link.short_description = "Requisition"

    def mail_sent_badge(self, obj):
        if obj.mail_sent:
            return format_html('<span style="color: #28A745;">✓ Sent</span>')
        return format_html('<span style="color: #DC3545;">✗ Not Sent</span>')
    mail_sent_badge.short_description = "Mail Status"


@admin.register(DispatchNotification, site=custom_admin_site)
class DispatchNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'logistic_department', 'from_user', 'to_user', 
        'is_dispatched_badge', 'created_at'
    ]
    list_filter = ['is_dispatched', 'created_at']
    search_fields = ['logistic_department__stn_number', 'from_user__email', 'to_user__email']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    autocomplete_fields = ['logistic_department', 'from_user', 'to_user']

    def is_dispatched_badge(self, obj):
        if obj.is_dispatched:
            return format_html('<span style="color: #28A745;">✓ Dispatched</span>')
        return format_html('<span style="color: #FFC107;">⏳ Pending</span>')
    is_dispatched_badge.short_description = "Status"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'logistic_department', 'from_user', 'to_user'
        )


@admin.register(DispatchLog, site=custom_admin_site)
class DispatchLogAdmin(admin.ModelAdmin):
    list_display = ['logistic_department', 'dispatched_by', 'quantity', 'dispatched_at']
    list_filter = ['dispatched_at']
    search_fields = ['logistic_department__stn_number', 'dispatched_by__email']
    readonly_fields = ['dispatched_at']
    date_hierarchy = 'dispatched_at'
    list_per_page = 25
    ordering = ['-dispatched_at']
    autocomplete_fields = ['logistic_department', 'dispatched_by']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'logistic_department', 'dispatched_by'
        )


# ===========================
# INVENTORY MANAGEMENT
# ===========================

@admin.register(Inventory, site=custom_admin_site)
class InventoryAdmin(admin.ModelAdmin):
    list_display = [
        'mcc_bmc_user_link', 'product_link', 'quantity', 
        'location_display', 'last_updated'
    ]
    list_filter = ['mcc_bmc_user__location', 'product']
    search_fields = ['mcc_bmc_user__user__email', 'mcc_bmc_user__location', 'product__name']
    list_editable = ['quantity']
    list_per_page = 25
    ordering = ['mcc_bmc_user__location', 'product__name']
    autocomplete_fields = ['mcc_bmc_user', 'product']
    readonly_fields = ['last_history']

    def mcc_bmc_user_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/mccbmcuser/{obj.mcc_bmc_user.id}/change/',
            obj.mcc_bmc_user.location
        )
    mcc_bmc_user_link.short_description = "Location User"

    def product_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/product/{obj.product.id}/change/',
            obj.product.name
        )
    product_link.short_description = "Product"

    def location_display(self, obj):
        return obj.mcc_bmc_user.location
    location_display.short_description = "Location"
    location_display.admin_order_field = 'mcc_bmc_user__location'

    def last_updated(self, obj):
        last_history = obj.history.order_by('-created_at').first()
        if last_history:
            return last_history.created_at
        return "-"
    last_updated.short_description = "Last Updated"

    def last_history(self, obj):
        histories = obj.history.order_by('-created_at')[:5]
        if histories:
            html = '<ul>'
            for h in histories:
                html += f'<li>{h.created_at.strftime("%Y-%m-%d %H:%M")}: {h.action} ({h.quantity_change:+d})</li>'
            html += '</ul>'
            return format_html(html)
        return "No history"
    last_history.short_description = "Recent History"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'mcc_bmc_user', 
            'product'
        ).prefetch_related('history')


@admin.register(InventoryHistory, site=custom_admin_site)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'inventory_link', 'action', 'quantity_change', 
        'previous_quantity', 'new_quantity', 'reference_number', 
        'performed_by', 'created_at'
    ]
    list_filter = ['action', 'created_at', 'performed_by']
    search_fields = ['reference_number', 'notes', 'inventory__product__name']
    readonly_fields = ['created_at', 'previous_quantity', 'new_quantity', 'quantity_change']
    date_hierarchy = 'created_at'
    list_per_page = 50
    ordering = ['-created_at']
    autocomplete_fields = ['inventory', 'performed_by']

    def inventory_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/inventory/{obj.inventory.id}/change/',
            obj.inventory.product.name
        )
    inventory_link.short_description = "Inventory"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'inventory', 'performed_by', 'inventory__product'
        )


# ===========================
# ADVANCE SALE MANAGEMENT
# ===========================

@admin.register(AdvanceSale, site=custom_admin_site)
class AdvanceSaleAdmin(admin.ModelAdmin):
    list_display = [
        'unique_code', 'bmc_or_mcc', 'mpp_with_code', 'stock_item', 
        'quantity', 'cycle_info', 'pod_status_badge', 'dispatched_at', 'pdf_link'
    ]
    list_filter = ['bmc_or_mcc', 'pod_uploaded', 'dispatched_at', 'cycle']
    search_fields = ['unique_code', 'bmc_or_mcc', 'mpp_with_code', 'stock_item']
    readonly_fields = ['dispatched_at', 'dispatched_by', 'pod_uploaded_at', 'pdf_generated']
    date_hierarchy = 'dispatched_at'
    list_per_page = 25
    ordering = ['-dispatched_at']
    autocomplete_fields = ['dispatched_by', 'cycle', 'template_entry']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('unique_code', 'bmc_or_mcc', 'mpp_with_code', 'cycle')
        }),
        ('Sale Details', {
            'fields': ('stock_item', 'quantity', 'uom', 'sale_date')
        }),
        ('Dispatch Information', {
            'fields': ('dispatched_by', 'dispatched_at')
        }),
        ('POD Information', {
            'fields': ('pod_uploaded', 'pod_uploaded_at', 'pod_file')
        }),
        ('Document Generation', {
            'fields': ('pdf_generated', 'pdf_file'),
            'classes': ('collapse',)
        }),
        ('Template Reference', {
            'fields': ('template_entry',),
            'classes': ('collapse',)
        }),
    )

    def cycle_info(self, obj):
        if obj.cycle:
            return f"{obj.cycle.monthly_cycle.month} - {obj.cycle.name}"
        return "-"
    cycle_info.short_description = "Cycle"

    def pod_status_badge(self, obj):
        if obj.pod_uploaded:
            return format_html(
                '<span style="color: #28A745;">✓ Uploaded</span><br><small>{}</small>',
                obj.pod_uploaded_at.strftime("%d-%m-%Y") if obj.pod_uploaded_at else ''
            )
        return format_html('<span style="color: #FFC107;">⏳ Pending</span>')
    pod_status_badge.short_description = "POD Status"

    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">📄 View PDF</a>', obj.pdf_file.url)
        return "-"
    pdf_link.short_description = "PDF"

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only on creation
            obj.dispatched_by = request.user
        super().save_model(request, obj, form, change)


# ===========================
# MCC/BMC & MPP MANAGEMENT
# ===========================

@admin.register(BMCOrMCC, site=custom_admin_site)
class BMCOrMCCAdmin(admin.ModelAdmin):
    list_display = ['name', 'plant', 'mpp_count', 'get_active_mpps']
    search_fields = ['name', 'plant']
    ordering = ['plant']
    list_per_page = 25

    def mpp_count(self, obj):
        count = obj.mpps.count()
        if count:
            url = f'{custom_admin_site.name}:main_app_mppwithcode_changelist'
            return format_html('<a href="{}?bmc_or_mcc__id__exact={}">{}</a>', url, obj.id, count)
        return count
    mpp_count.short_description = "Total MPPs"

    def get_active_mpps(self, obj):
        active_count = obj.mpps.filter(status='ACTIVE').count()
        return f"{active_count} active"
    get_active_mpps.short_description = "Active MPPs"


@admin.register(MPPWithCode, site=custom_admin_site)
class MPPWithCodeAdmin(admin.ModelAdmin):
    list_display = [
        'name_with_code', 'mpp_transaction_code', 'bmc_or_mcc', 
        'sahayak_mobile_number', 'cycle', 'location', 'status_badge'
    ]
    list_filter = ['bmc_or_mcc', 'cycle', 'location', 'status']
    search_fields = ['name_with_code', 'mpp_transaction_code', 'sahayak_mobile_number', 'location']
    list_per_page = 25
    ordering = ['name_with_code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_with_code', 'mpp_transaction_code', 'bmc_or_mcc', 'status')
        }),
        ('Contact Details', {
            'fields': ('sahayak_mobile_number', 'location')
        }),
        ('Cycle Information', {
            'fields': ('cycle',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        if obj.status == 'ACTIVE':
            return format_html('<span style="color: #28A745;">● ACTIVE</span>')
        return format_html('<span style="color: #DC3545;">● INACTIVE</span>')
    status_badge.short_description = "Status"

    actions = ['activate_mpps', 'deactivate_mpps']

    def activate_mpps(self, request, queryset):
        updated = queryset.update(status='ACTIVE')
        self.message_user(request, f'{updated} MPPs activated.')
    activate_mpps.short_description = "Activate selected MPPs"

    def deactivate_mpps(self, request, queryset):
        updated = queryset.update(status='DEACTIVE')
        self.message_user(request, f'{updated} MPPs deactivated.')
    deactivate_mpps.short_description = "Deactivate selected MPPs"


@admin.register(MCCBMCUser, site=custom_admin_site)
class MCCBMCUserAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'location', 'inventory_count', 'transfer_count']
    list_filter = ['location']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'location']
    list_per_page = 25
    autocomplete_fields = ['user']

    def user_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/customuser/{obj.user.id}/change/',
            obj.user.email
        )
    user_link.short_description = "User"

    def inventory_count(self, obj):
        count = obj.inventories.count()
        if count:
            url = f'{custom_admin_site.name}:main_app_inventory_changelist'
            return format_html('<a href="{}?mcc_bmc_user__id__exact={}">{}</a>', url, obj.id, count)
        return count
    inventory_count.short_description = "Inventory Items"

    def transfer_count(self, obj):
        sent = obj.transfers_out.count()
        received = obj.transfers_in.count()
        return f"Sent: {sent} | Received: {received}"
    transfer_count.short_description = "Transfers"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related(
            'inventories', 'transfers_out', 'transfers_in'
        )


@admin.register(Transfer, site=custom_admin_site)
class TransferAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'from_user', 'to_user', 'product', 'quantity', 
        'status_badge', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['from_user__location', 'to_user__location', 'product__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    autocomplete_fields = ['from_user', 'to_user', 'product']
    
    actions = ['approve_transfers', 'reject_transfers']

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'APPROVED': '#28A745',
            'REJECTED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def approve_transfers(self, request, queryset):
        for transfer in queryset:
            if transfer.status == 'PENDING':
                # Update inventory
                try:
                    from_inventory = Inventory.objects.get(
                        mcc_bmc_user=transfer.from_user,
                        product=transfer.product
                    )
                    to_inventory, _ = Inventory.objects.get_or_create(
                        mcc_bmc_user=transfer.to_user,
                        product=transfer.product,
                        defaults={'quantity': 0}
                    )
                    
                    # Deduct from source
                    from_inventory.deduct_quantity(
                        transfer.quantity,
                        'TRANSFER_OUT',
                        reference_number=f"TRANSFER-{transfer.id}",
                        notes=f"Transfer to {transfer.to_user.location}",
                        user=request.user
                    )
                    
                    # Add to destination
                    to_inventory.add_quantity(
                        transfer.quantity,
                        'TRANSFER_IN',
                        reference_number=f"TRANSFER-{transfer.id}",
                        notes=f"Transfer from {transfer.from_user.location}",
                        user=request.user
                    )
                    
                    transfer.status = 'APPROVED'
                    transfer.save()
                except Inventory.DoesNotExist:
                    self.message_user(request, f"Transfer {transfer.id} failed: Source inventory not found", level='ERROR')
        
        self.message_user(request, f'Transfers processed.')
    approve_transfers.short_description = "Approve selected transfers"

    def reject_transfers(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='REJECTED')
        self.message_user(request, f'{updated} transfers rejected.')
    reject_transfers.short_description = "Reject selected transfers"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'from_user', 'to_user', 'product', 'from_user__user', 'to_user__user'
        )


# ===========================
# CYCLE MANAGEMENT
# ===========================

class CycleInline(admin.TabularInline):
    model = Cycle
    extra = 1
    fields = ['name', 'cycle_number', 'sap_number', 'start_date', 'end_date', 'duration_days', 'is_active']
    readonly_fields = ['duration_days']
    ordering = ['cycle_number']


@admin.register(MonthlyCycle, site=custom_admin_site)
class MonthlyCycleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'month', 'year', 'cycle_count', 'total_days', 
        'is_active_badge', 'created_by', 'created_at', 'is_active'  # Added is_active for list_editable
    ]
    list_filter = ['month', 'year', 'is_active', 'created_at']
    search_fields = ['name', 'month', 'description']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at', 'cycle_count', 'total_days']
    list_per_page = 25
    ordering = ['-year', '-month']
    inlines = [CycleInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'month', 'year', 'is_active', 'created_by')
        }),
        ('Description', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('cycle_count', 'total_days'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28A745;">✓ Active</span>')
        return format_html('<span style="color: #DC3545;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def cycle_count(self, obj):
        return obj.cycles.count()
    cycle_count.short_description = "Cycles"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Cycle, site=custom_admin_site)
class CycleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'monthly_cycle_display', 'cycle_number', 'sap_number',
        'start_date', 'end_date', 'duration_days', 'date_range_display',
        'is_active_badge', 'sale_templates_count', 'is_active'  # Added is_active for list_editable
    ]
    list_filter = ['monthly_cycle__month', 'monthly_cycle__year', 'is_active']
    search_fields = ['name', 'description', 'monthly_cycle__name', 'sap_number']
    list_editable = ['is_active', 'sap_number']
    readonly_fields = ['duration_days', 'date_range_display']
    list_per_page = 25
    ordering = ['monthly_cycle__year', 'monthly_cycle__month', 'cycle_number']
    autocomplete_fields = ['monthly_cycle']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('monthly_cycle', 'name', 'cycle_number', 'sap_number', 'is_active')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date', 'duration_days', 'date_range_display')
        }),
        ('Description', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('sale_templates_count',),
            'classes': ('collapse',)
        }),
    )

    def monthly_cycle_display(self, obj):
        return f"{obj.monthly_cycle.month} {obj.monthly_cycle.year}"
    monthly_cycle_display.short_description = "Monthly Cycle"
    monthly_cycle_display.admin_order_field = 'monthly_cycle'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28A745;">✓ Active</span>')
        return format_html('<span style="color: #DC3545;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def sale_templates_count(self, obj):
        count = obj.sale_templates.count()
        if count > 0:
            url = f'{custom_admin_site.name}:main_app_saletemplateconfig_changelist'
            return format_html('<a href="{}?cycle__id__exact={}">{}</a>', url, obj.id, count)
        return count
    sale_templates_count.short_description = "Sale Templates"

    actions = ['activate_cycles', 'deactivate_cycles']

    def activate_cycles(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} cycles activated.')
    activate_cycles.short_description = "Activate selected cycles"

    def deactivate_cycles(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} cycles deactivated.')
    deactivate_cycles.short_description = "Deactivate selected cycles"


# ===========================
# SALE TEMPLATE MANAGEMENT
# ===========================

class SaleTemplateEntryInline(admin.TabularInline):
    model = SaleTemplateEntry
    extra = 0
    fields = ['location', 'mpp', 'product_name', 'advance_sale_quantity', 'filled_quantity', 'status_badge']
    readonly_fields = ['status_badge']
    ordering = ['location', 'mpp']
    show_change_link = True

    def status_badge(self, obj):
        colors = {
            'OK': '#28A745',
            'OVER_SOLD': '#DC3545',
            'UNDER_SOLD': '#FFC107',
            'NOT_SOLD': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 5px; border-radius: 3px;">{}</span>',
            color, obj.status.replace('_', ' ')
        )
    status_badge.short_description = "Status"


@admin.register(SaleTemplateConfig, site=custom_admin_site)
class SaleTemplateConfigAdmin(admin.ModelAdmin):
    list_display = [
        'get_month_year', 'get_cycle_name', 'get_date_range', 
        'is_active_badge', 'created_at', 'entry_count', 'upload_history_count',
        'is_active'  # Added is_active for list_editable
    ]
    list_filter = ['is_active', 'cycle__monthly_cycle__month', 'cycle__monthly_cycle__year']
    search_fields = ['cycle__name', 'cycle__monthly_cycle__month']
    list_editable = ['is_active']
    ordering = ['-created_at']
    list_per_page = 25
    autocomplete_fields = ['cycle']
    inlines = [SaleTemplateEntryInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('cycle', 'is_active')
        }),
        ('Statistics', {
            'fields': ('entry_count', 'upload_history_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_month_year(self, obj):
        return f"{obj.cycle.monthly_cycle.month} {obj.cycle.monthly_cycle.year}"
    get_month_year.short_description = 'Month/Year'
    get_month_year.admin_order_field = 'cycle__monthly_cycle'

    def get_cycle_name(self, obj):
        return obj.cycle.name
    get_cycle_name.short_description = 'Cycle'
    get_cycle_name.admin_order_field = 'cycle__name'

    def get_date_range(self, obj):
        return obj.cycle.date_range_display
    get_date_range.short_description = 'Date Range'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28A745;">✓ Active</span>')
        return format_html('<span style="color: #DC3545;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def entry_count(self, obj):
        count = obj.saletemplateentry_set.count()
        if count > 0:
            url = f'{custom_admin_site.name}:main_app_saletemplateentry_changelist'
            return format_html('<a href="{}?config__id__exact={}">{}</a>', url, obj.id, count)
        return count
    entry_count.short_description = "Entries"

    def upload_history_count(self, obj):
        count = obj.saleuploadhistory_set.count()
        if count > 0:
            url = f'{custom_admin_site.name}:main_app_saleuploadhistory_changelist'
            return format_html('<a href="{}?config__id__exact={}">{}</a>', url, obj.id, count)
        return count
    upload_history_count.short_description = "Uploads"


@admin.register(SaleTemplateEntry, site=custom_admin_site)
class SaleTemplateEntryAdmin(admin.ModelAdmin):
    list_display = [
        'config_link', 'location', 'mpp', 'product_name', 
        'advance_sale_quantity', 'filled_quantity', 'difference', 
        'status_badge', 'uploaded_by', 'uploaded_at'
    ]
    list_filter = ['config', 'location', 'status', 'uploaded_at']
    search_fields = ['location', 'mpp', 'product_name', 'uploaded_by__email']
    readonly_fields = ['uploaded_at', 'status', 'difference']
    list_editable = ['filled_quantity']
    date_hierarchy = 'uploaded_at'
    list_per_page = 50
    ordering = ['-uploaded_at']
    autocomplete_fields = ['config', 'uploaded_by']

    def config_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/saletemplateconfig/{obj.config.id}/change/',
            f"{obj.config.cycle.monthly_cycle.month} - {obj.config.cycle.name}"
        )
    config_link.short_description = "Configuration"

    def difference(self, obj):
        diff = obj.filled_quantity - obj.advance_sale_quantity
        if diff > 0:
            return format_html('<span style="color: #DC3545;">+{}</span>', diff)
        elif diff < 0:
            return format_html('<span style="color: #FFC107;">{}</span>', diff)
        return format_html('<span style="color: #28A745;">0</span>')
    difference.short_description = "Diff"

    def status_badge(self, obj):
        colors = {
            'OK': '#28A745',
            'OVER_SOLD': '#DC3545',
            'UNDER_SOLD': '#FFC107',
            'NOT_SOLD': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status.replace('_', ' ')
        )
    status_badge.short_description = "Status"

    actions = ['recalculate_status']

    def recalculate_status(self, request, queryset):
        for entry in queryset:
            entry.save()  # This will recalculate status
        self.message_user(request, f'Status recalculated for {queryset.count()} entries.')
    recalculate_status.short_description = "Recalculate status"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'config', 'uploaded_by', 'config__cycle', 'config__cycle__monthly_cycle'
        )


@admin.register(SaleUploadHistory, site=custom_admin_site)
class SaleUploadHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'config_link', 'file_name', 'uploaded_by', 
        'total_records', 'success_count', 'error_count', 
        'success_rate_display', 'uploaded_at'
    ]
    list_filter = ['config', 'uploaded_at']
    search_fields = ['file_name', 'uploaded_by__email']
    readonly_fields = ['uploaded_at']
    date_hierarchy = 'uploaded_at'
    list_per_page = 25
    ordering = ['-uploaded_at']
    autocomplete_fields = ['config', 'uploaded_by']

    def config_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/saletemplateconfig/{obj.config.id}/change/',
            f"{obj.config.cycle.monthly_cycle.month} - {obj.config.cycle.name}"
        )
    config_link.short_description = "Configuration"

    def success_rate_display(self, obj):
        if obj.total_records > 0:
            rate = (obj.success_count / obj.total_records) * 100
            if rate >= 95:
                return format_html('<span style="color: #28A745;">{:.1f}%</span>', rate)
            elif rate >= 80:
                return format_html('<span style="color: #FFC107;">{:.1f}%</span>', rate)
            else:
                return format_html('<span style="color: #DC3545;">{:.1f}%</span>', rate)
        return "0%"
    
    # Remove the old success_rate method or rename it
    # The old success_rate method was causing the error

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'config', 'uploaded_by', 'config__cycle', 'config__cycle__monthly_cycle'
        )


# ===========================
# RECONCILIATION MANAGEMENT
# ===========================  

class ReconciliationRecordInline(admin.TabularInline):
    model = ReconciliationRecord
    extra = 0
    fields = [
        'location', 'mpp_name', 'product_name', 
        'advance_sale_qty', 'sap_entry_qty', 'quantity_difference',
        'status_badge', 'is_processed', 'is_acknowledged'
    ]
    readonly_fields = ['status_badge', 'quantity_difference']
    ordering = ['location', 'mpp_name']
    show_change_link = True

    def status_badge(self, obj):
        colors = {
            'OVER_RECORDED': '#DC3545',
            'UNDER_RECORDED': '#FFC107',
            'PERFECT_MATCH': '#28A745',
            'NOT_RECORDED': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 5px; border-radius: 3px;">{}</span>',
            color, obj.status.replace('_', ' ')
        )
    status_badge.short_description = "Status"


@admin.register(ReconciliationSheet, site=custom_admin_site)
class ReconciliationSheetAdmin(admin.ModelAdmin):
    list_display = [
        'file_name', 'monthly_cycle_display', 'cycle_display', 
        'uploaded_by', 'upload_date', 'status_badge', 
        'records_count', 'summary_stats'
    ]
    list_filter = ['status', 'upload_date', 'monthly_cycle', 'cycle']
    search_fields = ['file_name', 'uploaded_by__email']
    readonly_fields = ['upload_date', 'records_count', 'over_recorded_count', 'under_recorded_count', 
                      'perfect_match_count', 'not_recorded_count']
    date_hierarchy = 'upload_date'
    list_per_page = 25
    ordering = ['-upload_date']
    autocomplete_fields = ['uploaded_by', 'monthly_cycle', 'cycle']
    inlines = [ReconciliationRecordInline]
    
    fieldsets = (
        ('Upload Information', {
            'fields': ('file_name', 'excel_file', 'uploaded_by', 'upload_date')
        }),
        ('Cycle Information', {
            'fields': ('monthly_cycle', 'cycle')
        }),
        ('Processing Status', {
            'fields': ('status', 'processed_at')
        }),
        ('Statistics', {
            'fields': ('total_records', 'over_recorded_count', 'under_recorded_count', 
                      'perfect_match_count', 'not_recorded_count'),
            'classes': ('collapse',)
        }),
    )

    def monthly_cycle_display(self, obj):
        if obj.monthly_cycle:
            return f"{obj.monthly_cycle.month} {obj.monthly_cycle.year}"
        return "-"
    monthly_cycle_display.short_description = "Month"

    def cycle_display(self, obj):
        if obj.cycle:
            return obj.cycle.name
        return "-"
    cycle_display.short_description = "Cycle"

    def status_badge(self, obj):
        colors = {
            'UPLOADED': '#17A2B8',
            'PROCESSING': '#FFC107',
            'DISTRIBUTED': '#007BFF',
            'PROCESSED': '#28A745',
            'FAILED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def records_count(self, obj):
        return obj.records.count()
    records_count.short_description = "Total Records"

    def summary_stats(self, obj):
        return f"O:{obj.over_recorded_count} U:{obj.under_recorded_count} P:{obj.perfect_match_count} N:{obj.not_recorded_count}"
    summary_stats.short_description = "O/U/P/N"

    actions = ['process_sheet', 'distribute_to_locations']

    def process_sheet(self, request, queryset):
        for sheet in queryset:
            sheet.status = 'PROCESSING'
            sheet.save()
            # Trigger processing logic here
        self.message_user(request, f'Processing started for {queryset.count()} sheets.')
    process_sheet.short_description = "Process selected sheets"

    def distribute_to_locations(self, request, queryset):
        for sheet in queryset:
            sheet.status = 'DISTRIBUTED'
            sheet.save()
            # Trigger distribution logic here
        self.message_user(request, f'Distribution started for {queryset.count()} sheets.')
    distribute_to_locations.short_description = "Distribute to locations"


@admin.register(ReconciliationRecord, site=custom_admin_site)
class ReconciliationRecordAdmin(admin.ModelAdmin):
    list_display = [
        'reconciliation_sheet_link', 'location', 'mpp_name', 'mpp_code',
        'product_name', 'advance_sale_qty', 'sap_entry_qty', 
        'quantity_difference_display', 'status_badge', 
        'to_be_sent_to_mpp', 'to_be_deducted', 'acknowledgment_status'
    ]
    list_filter = ['status', 'is_service', 'is_processed', 'is_acknowledged', 'location']
    search_fields = ['location', 'mpp_name', 'mpp_code', 'product_name']
    readonly_fields = ['created_at', 'updated_at', 'quantity_difference', 'is_service']
    list_per_page = 50
    ordering = ['location', 'mpp_name']
    autocomplete_fields = ['reconciliation_sheet', 'mpp', 'product', 'acknowledged_by']
    
    fieldsets = (
        ('Sheet Information', {
            'fields': ('reconciliation_sheet',)
        }),
        ('Location & MPP', {
            'fields': ('location', 'mpp_code', 'mpp_name', 'mpp')
        }),
        ('Product Details', {
            'fields': ('product_name', 'product', 'is_service')
        }),
        ('Quantity Information', {
            'fields': ('advance_sale_qty', 'sap_entry_qty', 'quantity_difference')
        }),
        ('Reconciliation Results', {
            'fields': ('status', 'match_quality')
        }),
        ('Action Required', {
            'fields': ('to_be_sent_to_mpp', 'to_be_deducted')
        }),
        ('Processing', {
            'fields': ('is_processed', 'processed_at')
        }),
        ('Acknowledgment', {
            'fields': ('is_acknowledged', 'acknowledged_at', 'acknowledged_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def reconciliation_sheet_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'../../main_app/reconciliationsheet/{obj.reconciliation_sheet.id}/change/',
            obj.reconciliation_sheet.file_name
        )
    reconciliation_sheet_link.short_description = "Sheet"

    def quantity_difference_display(self, obj):
        diff = obj.quantity_difference
        if diff > 0:
            return format_html('<span style="color: #DC3545;">+{}</span>', diff)
        elif diff < 0:
            return format_html('<span style="color: #FFC107;">{}</span>', diff)
        return format_html('<span style="color: #28A745;">0</span>')
    quantity_difference_display.short_description = "Diff"

    def status_badge(self, obj):
        colors = {
            'OVER_RECORDED': '#DC3545',
            'UNDER_RECORDED': '#FFC107',
            'PERFECT_MATCH': '#28A745',
            'NOT_RECORDED': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status.replace('_', ' ')
        )
    status_badge.short_description = "Status"

    def acknowledgment_status(self, obj):
        if obj.is_acknowledged:
            return format_html(
                '<span style="color: #28A745;">✓ Acknowledged</span><br><small>{}</small>',
                obj.acknowledged_at.strftime("%d-%m-%Y") if obj.acknowledged_at else ''
            )
        return format_html('<span style="color: #FFC107;">⏳ Pending</span>')
    acknowledgment_status.short_description = "Acknowledgment"

    actions = ['mark_as_processed', 'mark_as_acknowledged']

    def mark_as_processed(self, request, queryset):
        updated = queryset.update(
            is_processed=True, 
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} records marked as processed.')
    mark_as_processed.short_description = "Mark selected as processed"

    def mark_as_acknowledged(self, request, queryset):
        updated = queryset.update(
            is_acknowledged=True,
            acknowledged_at=timezone.now(),
            acknowledged_by=request.user
        )
        self.message_user(request, f'{updated} records marked as acknowledged.')
    mark_as_acknowledged.short_description = "Mark selected as acknowledged"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'reconciliation_sheet', 'mpp', 'product', 'acknowledged_by'
        )


@admin.register(ReconciliationNotification, site=custom_admin_site)
class ReconciliationNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'reconciliation_sheet', 'location_user', 'location', 
        'status_badge', 'sent_at', 'viewed_at', 'acknowledged_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['location_user__email', 'location', 'message']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    autocomplete_fields = ['reconciliation_sheet', 'location_user']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('reconciliation_sheet', 'location_user', 'location')
        }),
        ('Status Tracking', {
            'fields': ('status', 'sent_at', 'viewed_at', 'acknowledged_at')
        }),
        ('Content', {
            'fields': ('message', 'pdf_file')
        }),
        ('Response', {
            'fields': ('user_comments',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'SENT': '#17A2B8',
            'VIEWED': '#007BFF',
            'ACKNOWLEDGED': '#28A745',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    actions = ['send_notifications', 'mark_as_viewed', 'mark_as_acknowledged']

    def send_notifications(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='SENT',
            sent_at=timezone.now()
        )
        self.message_user(request, f'{updated} notifications marked as sent.')
    send_notifications.short_description = "Mark selected as sent"

    def mark_as_viewed(self, request, queryset):
        updated = queryset.filter(status='SENT').update(
            status='VIEWED',
            viewed_at=timezone.now()
        )
        self.message_user(request, f'{updated} notifications marked as viewed.')
    mark_as_viewed.short_description = "Mark selected as viewed"

    def mark_as_acknowledged(self, request, queryset):
        updated = queryset.filter(status='VIEWED').update(
            status='ACKNOWLEDGED',
            acknowledged_at=timezone.now()
        )
        self.message_user(request, f'{updated} notifications marked as acknowledged.')
    mark_as_acknowledged.short_description = "Mark selected as acknowledged"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'reconciliation_sheet', 'location_user'
        )


# ===========================
# LEDGER MANAGEMENT
# ===========================

@admin.register(MPPProductLedger, site=custom_admin_site)
class MPPProductLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'cycle', 'mpp', 'product', 
        'opening_balance', 'current_advance_sale', 'current_sap_entry',
        'current_difference_display', 'closing_balance_display',
        'is_reconciled_badge'
    ]
    list_filter = ['cycle', 'is_reconciled', 'mpp__bmc_or_mcc']
    search_fields = ['mpp__name_with_code', 'product__name']
    readonly_fields = ['created_at', 'updated_at', 'current_difference', 'closing_balance']
    list_per_page = 50
    ordering = ['cycle', 'mpp', 'product']
    autocomplete_fields = ['mpp', 'product', 'cycle', 'reconciliation_record']
    
    fieldsets = (
        ('Cycle & MPP', {
            'fields': ('cycle', 'mpp', 'product')
        }),
        ('Balance Information', {
            'fields': ('opening_balance', 'current_advance_sale', 'current_sap_entry', 
                      'current_difference', 'closing_balance')
        }),
        ('Reconciliation', {
            'fields': ('is_reconciled', 'reconciled_at', 'reconciliation_record')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def current_difference_display(self, obj):
        diff = obj.current_difference
        if diff > 0:
            return format_html('<span style="color: #DC3545;">+{}</span>', diff)
        elif diff < 0:
            return format_html('<span style="color: #FFC107;">{}</span>', diff)
        return format_html('<span style="color: #28A745;">0</span>')
    current_difference_display.short_description = "Diff"

    def closing_balance_display(self, obj):
        balance = obj.closing_balance
        if balance > 0:
            return format_html('<span style="color: #DC3545;">To Send: {}</span>', balance)
        elif balance < 0:
            return format_html('<span style="color: #FFC107;">To Deduct: {}</span>', abs(balance))
        return format_html('<span style="color: #28A745;">Balanced: 0</span>')
    closing_balance_display.short_description = "Closing Balance"

    def is_reconciled_badge(self, obj):
        if obj.is_reconciled:
            return format_html('<span style="color: #28A745;">✓ Reconciled</span>')
        return format_html('<span style="color: #FFC107;">⏳ Pending</span>')
    is_reconciled_badge.short_description = "Status"

    actions = ['reconcile_selected', 'create_next_cycle_ledger']

    def reconcile_selected(self, request, queryset):
        updated = queryset.update(
            is_reconciled=True,
            reconciled_at=timezone.now()
        )
        self.message_user(request, f'{updated} ledgers marked as reconciled.')
    reconcile_selected.short_description = "Mark selected as reconciled"

    def create_next_cycle_ledger(self, request, queryset):
        created_count = 0
        for ledger in queryset:
            if ledger.create_next_cycle_ledger():
                created_count += 1
        self.message_user(request, f'Created next cycle ledgers for {created_count} entries.')
    create_next_cycle_ledger.short_description = "Create next cycle ledgers"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'mpp', 'product', 'cycle', 'reconciliation_record',
            'cycle__monthly_cycle', 'mpp__bmc_or_mcc'
        )


@admin.register(CycleProductSummary, site=custom_admin_site)
class CycleProductSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'cycle', 'product', 
        'total_advance_sale', 'total_sap_entry', 'total_difference_display',
        'total_to_send', 'total_to_deduct', 'mpp_count', 'reconciled_count'
    ]
    list_filter = ['cycle']
    search_fields = ['product__name']
    list_per_page = 50
    ordering = ['cycle', 'product']
    autocomplete_fields = ['cycle', 'product']

    def total_difference_display(self, obj):
        diff = obj.total_difference
        if diff > 0:
            return format_html('<span style="color: #DC3545;">+{}</span>', diff)
        elif diff < 0:
            return format_html('<span style="color: #FFC107;">{}</span>', diff)
        return format_html('<span style="color: #28A745;">0</span>')
    total_difference_display.short_description = "Total Diff"


@admin.register(CycleLedger, site=custom_admin_site)
class CycleLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'cycle', 'product', 
        'opening_balance', 'advance_sale_qty', 'sap_entry_qty',
        'closing_balance_display', 'is_reconciled_badge'
    ]
    list_filter = ['cycle', 'is_reconciled']
    search_fields = ['product__name']
    list_per_page = 50
    ordering = ['cycle', 'product']
    autocomplete_fields = ['cycle', 'product']

    def closing_balance_display(self, obj):
        balance = obj.closing_balance
        if balance > 0:
            return format_html('<span style="color: #DC3545;">To Send: {}</span>', balance)
        elif balance < 0:
            return format_html('<span style="color: #FFC107;">To Deduct: {}</span>', abs(balance))
        return format_html('<span style="color: #28A745;">Balanced: 0</span>')
    closing_balance_display.short_description = "Closing Balance"

    def is_reconciled_badge(self, obj):
        if obj.is_reconciled:
            return format_html('<span style="color: #28A745;">✓ Reconciled</span>')
        return format_html('<span style="color: #FFC107;">⏳ Pending</span>')
    is_reconciled_badge.short_description = "Status"

    actions = ['reconcile_selected']

    def reconcile_selected(self, request, queryset):
        updated = queryset.update(
            is_reconciled=True,
            reconciliation_date=timezone.now()
        )
        self.message_user(request, f'{updated} ledgers marked as reconciled.')
    reconcile_selected.short_description = "Mark selected as reconciled"


# ===========================
# GENERAL SALE MANAGEMENT
# ===========================

@admin.register(GeneralSale, site=custom_admin_site)
class GeneralSaleAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'mpp', 'product', 'quantity', 'cycle',
        'status_badge', 'dispatched_at', 'delivered_at', 
        'whatsapp_status', 'pdf_link'
    ]
    list_filter = ['status', 'cycle', 'whatsapp_sent']
    search_fields = ['mpp__name_with_code', 'product__name', 'location']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']
    autocomplete_fields = ['mpp', 'product', 'cycle', 'reconciliation_record']
    
    fieldsets = (
        ('Source Information', {
            'fields': ('reconciliation_record',)
        }),
        ('Sale Details', {
            'fields': ('location', 'mpp', 'product', 'quantity', 'cycle')
        }),
        ('Status Tracking', {
            'fields': ('status', 'dispatched_at', 'delivered_at')
        }),
        ('Document Generation', {
            'fields': ('pdf_file',)
        }),
        ('Notification', {
            'fields': ('whatsapp_sent', 'whatsapp_sent_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'DISPATCHED': '#17A2B8',
            'DELIVERED': '#28A745',
            'CANCELLED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def whatsapp_status(self, obj):
        if obj.whatsapp_sent:
            return format_html(
                '<span style="color: #28A745;">✓ Sent</span><br><small>{}</small>',
                obj.whatsapp_sent_at.strftime("%d-%m-%Y") if obj.whatsapp_sent_at else ''
            )
        return format_html('<span style="color: #FFC707;">⏳ Pending</span>')
    whatsapp_status.short_description = "WhatsApp"

    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">📄 View PDF</a>', obj.pdf_file.url)
        return "-"
    pdf_link.short_description = "PDF"

    actions = ['mark_as_dispatched', 'mark_as_delivered', 'send_whatsapp']

    def mark_as_dispatched(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='DISPATCHED',
            dispatched_at=timezone.now()
        )
        self.message_user(request, f'{updated} sales marked as dispatched.')
    mark_as_dispatched.short_description = "Mark selected as dispatched"

    def mark_as_delivered(self, request, queryset):
        updated = queryset.filter(status='DISPATCHED').update(
            status='DELIVERED',
            delivered_at=timezone.now()
        )
        self.message_user(request, f'{updated} sales marked as delivered.')
    mark_as_delivered.short_description = "Mark selected as delivered"

    def send_whatsapp(self, request, queryset):
        updated = queryset.filter(whatsapp_sent=False).update(
            whatsapp_sent=True,
            whatsapp_sent_at=timezone.now()
        )
        self.message_user(request, f'WhatsApp notifications queued for {updated} sales.')
    send_whatsapp.short_description = "Send WhatsApp notifications"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'mpp', 'product', 'cycle', 'reconciliation_record'
        )


# ===========================
# SAP PO INTEGRATION
# ===========================

@admin.register(SAPPOExcelUpload, site=custom_admin_site)
class SAPPOExcelUploadAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'uploaded_by', 'upload_date', 
        'total_rows', 'rows_succeeded', 'rows_failed',
        'status_badge', 'progress'
    ]
    list_filter = ['status', 'upload_date']
    search_fields = ['filename', 'uploaded_by__email']
    readonly_fields = ['upload_date']
    date_hierarchy = 'upload_date'
    list_per_page = 25
    ordering = ['-upload_date']
    autocomplete_fields = ['uploaded_by']

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'PROCESSING': '#17A2B8',
            'COMPLETED': '#28A745',
            'FAILED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def progress(self, obj):
        if obj.total_rows > 0:
            processed = obj.rows_succeeded + obj.rows_failed
            percentage = (processed / obj.total_rows) * 100
            return f"{processed}/{obj.total_rows} ({percentage:.1f}%)"
        return "0%"
    progress.short_description = "Progress"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')


@admin.register(SAPMaterialPOMapping, site=custom_admin_site)
class SAPMaterialPOMappingAdmin(admin.ModelAdmin):
    list_display = [
        'po_number', 'sap_material_code', 'sap_material_name', 
        'order_quantity', 'product_group_link', 'plant', 
        'is_used_badge', 'upload', 'document_date'
    ]
    list_filter = ['is_used', 'plant', 'document_date']
    search_fields = ['po_number', 'sap_material_code', 'sap_material_name', 'vendor_info']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'document_date'
    list_per_page = 50
    ordering = ['-document_date']
    autocomplete_fields = ['product_group', 'upload', 'used_in_requisition', 'used_by']
    
    fieldsets = (
        ('PO Information', {
            'fields': ('po_number', 'document_date', 'vendor_info')
        }),
        ('Material Details', {
            'fields': ('sap_material_code', 'sap_material_name', 'order_quantity')
        }),
        ('Location', {
            'fields': ('plant', 'storage_location')
        }),
        ('Product Mapping', {
            'fields': ('product_group',)
        }),
        ('Usage Tracking', {
            'fields': ('is_used', 'used_in_requisition', 'used_by', 'used_at')
        }),
        ('Upload Reference', {
            'fields': ('upload',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def product_group_link(self, obj):
        if obj.product_group:
            return format_html(
                '<a href="{}">{}</a>',
                f'../../main_app/productmappinggroup/{obj.product_group.id}/change/',
                obj.product_group.name
            )
        return "-"
    product_group_link.short_description = "Product Group"

    def is_used_badge(self, obj):
        if obj.is_used:
            return format_html(
                '<span style="color: #28A745;">✓ Used</span><br><small>{}</small>',
                obj.used_at.strftime("%d-%m-%Y") if obj.used_at else ''
            )
        return format_html('<span style="color: #FFC107;">⏳ Available</span>')
    is_used_badge.short_description = "Status"

    actions = ['mark_as_used', 'mark_as_available']

    def mark_as_used(self, request, queryset):
        updated = queryset.filter(is_used=False).update(
            is_used=True,
            used_by=request.user,
            used_at=timezone.now()
        )
        self.message_user(request, f'{updated} PO mappings marked as used.')
    mark_as_used.short_description = "Mark selected as used"

    def mark_as_available(self, request, queryset):
        updated = queryset.filter(is_used=True).update(
            is_used=False,
            used_by=None,
            used_at=None,
            used_in_requisition=None
        )
        self.message_user(request, f'{updated} PO mappings marked as available.')
    mark_as_available.short_description = "Mark selected as available"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'product_group', 'upload', 'used_in_requisition', 'used_by'
        )


# ===========================
# MESSAGE & NOTIFICATION MANAGEMENT
# ===========================

@admin.register(MessageQueue, site=custom_admin_site)
class MessageQueueAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'message_type', 'mobile_number', 'mpp_name', 
        'unique_code', 'status_badge', 'retry_count', 
        'created_at', 'sent_at'
    ]
    list_filter = ['message_type', 'status', 'created_at']
    search_fields = ['mobile_number', 'unique_code', 'mpp_name', 'message']
    readonly_fields = ['created_at', 'queued_at', 'processing_started_at', 'sent_at', 'completed_at']
    list_per_page = 50
    ordering = ['-created_at']
    autocomplete_fields = ['advance_sale']
    
    fieldsets = (
        ('Message Metadata', {
            'fields': ('message_type', 'advance_sale', 'unique_code', 'mpp_name')
        }),
        ('Recipient', {
            'fields': ('mobile_number',)
        }),
        ('Content', {
            'fields': ('message', 'cycle_info')
        }),
        ('Processing Status', {
            'fields': ('status', 'retry_count', 'max_retries', 'error_count', 'last_error')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'queued_at', 'processing_started_at', 'sent_at', 'completed_at')
        }),
        ('Ordering', {
            'fields': ('sequence_number', 'correlation_id'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'PROCESSING': '#17A2B8',
            'SENT': '#28A745',
            'FAILED': '#DC3545',
            'RETRY': '#FFC107',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    actions = ['retry_failed_messages', 'reset_to_pending']

    def retry_failed_messages(self, request, queryset):
        updated = queryset.filter(status='FAILED').update(
            status='RETRY',
            retry_count=0,
            last_error=''
        )
        self.message_user(request, f'{updated} messages queued for retry.')
    retry_failed_messages.short_description = "Retry selected failed messages"

    def reset_to_pending(self, request, queryset):
        updated = queryset.exclude(status='SENT').update(
            status='PENDING',
            retry_count=0,
            last_error=''
        )
        self.message_user(request, f'{updated} messages reset to pending.')
    reset_to_pending.short_description = "Reset selected to pending"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('advance_sale')


@admin.register(EnhancedMessageQueue, site=custom_admin_site)
class EnhancedMessageQueueAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'message_type', 'mobile_number', 'mpp_name', 
        'unique_code', 'status_badge', 'retry_count', 
        'sequence_number', 'whatsapp_window_active',
        'created_at', 'sent_at'
    ]
    list_filter = ['message_type', 'status', 'whatsapp_window_active', 'created_at']
    search_fields = ['mobile_number', 'unique_code', 'mpp_name', 'message']
    readonly_fields = ['created_at', 'queued_at', 'processing_started_at', 'sent_at', 'completed_at']
    list_per_page = 50
    ordering = ['-sequence_number', '-created_at']
    autocomplete_fields = ['advance_sale']
    
    fieldsets = (
        ('Message Metadata', {
            'fields': ('message_type', 'advance_sale', 'unique_code', 'mpp_name')
        }),
        ('Recipient', {
            'fields': ('mobile_number',)
        }),
        ('Content', {
            'fields': ('message', 'cycle_info')
        }),
        ('Processing Status', {
            'fields': ('status', 'retry_count', 'max_retries', 'error_count', 'last_error')
        }),
        ('WhatsApp Session', {
            'fields': ('whatsapp_session_id', 'whatsapp_window_active'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'queued_at', 'processing_started_at', 'sent_at', 'completed_at')
        }),
        ('Ordering', {
            'fields': ('sequence_number', 'correlation_id'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'PROCESSING': '#17A2B8',
            'SENT': '#28A745',
            'FAILED': '#DC3545',
            'RETRY': '#FFC107',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    actions = ['retry_failed_messages', 'reset_to_pending']

    def retry_failed_messages(self, request, queryset):
        updated = queryset.filter(status='FAILED').update(
            status='RETRY',
            retry_count=0,
            last_error=''
        )
        self.message_user(request, f'{updated} messages queued for retry.')
    retry_failed_messages.short_description = "Retry selected failed messages"

    def reset_to_pending(self, request, queryset):
        updated = queryset.exclude(status='SENT').update(
            status='PENDING',
            retry_count=0,
            last_error=''
        )
        self.message_user(request, f'{updated} messages reset to pending.')
    reset_to_pending.short_description = "Reset selected to pending"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('advance_sale')


@admin.register(MessageDeliveryLog, site=custom_admin_site)
class MessageDeliveryLogAdmin(admin.ModelAdmin):
    list_display = [
        'message_queue', 'attempt_number', 'status', 
        'sent_via', 'response_time_ms', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['message_queue__mobile_number', 'notes', 'error_message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 100
    ordering = ['-created_at']
    autocomplete_fields = ['message_queue']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('message_queue')


@admin.register(WhatsAppLog, site=custom_admin_site)
class WhatsAppLogAdmin(admin.ModelAdmin):
    list_display = [
        'mobile_number', 'status_badge', 'sent_via', 
        'template_name', 'template_message_id', 'is_read',
        'sent_at', 'delivered_at', 'read_at', 'time_to_read_display',
        'purpose', 'advance_sale_link', 'created_at'
    ]
    list_filter = ['status', 'is_read', 'sent_via', 'purpose', 'created_at']
    search_fields = ['mobile_number', 'message', 'template_message_id', 'unique_code', 'mpp_name']
    readonly_fields = ['time_to_read_display', 'read_status_summary', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    ordering = ['-created_at']
    autocomplete_fields = ['advance_sale']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('mobile_number', 'message', 'purpose', 'advance_sale', 'unique_code', 'mpp_name')
        }),
        ('Status Tracking', {
            'fields': ('status', 'sent_via', 'is_read', 'read_count', 'not_registered')
        }),
        ('Template Information', {
            'fields': ('template_name', 'template_message_id', 'template_variables', 'api_response')
        }),
        ('Timestamps', {
            'fields': ('sent_at', 'delivered_at', 'read_at', 'last_read_at', 'completed_at', 'created_at', 'updated_at')
        }),
        ('Error Tracking', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Read Analytics', {
            'fields': ('time_to_read_display', 'read_status_summary'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'SENT': '#17A2B8',
            'DELIVERED': '#007BFF',
            'READ': '#28A745',
            'FAILED': '#DC3545',
            'NOT_REGISTERED': '#6C757D',
            'RECEIVED': '#17A2B8',
            'DELETED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def time_to_read_display(self, obj):
        if obj.time_to_read:
            if obj.time_to_read < 60:
                return f"{obj.time_to_read:.1f} seconds"
            elif obj.time_to_read < 3600:
                return f"{obj.time_to_read/60:.1f} minutes"
            else:
                return f"{obj.time_to_read/3600:.1f} hours"
        return "N/A"
    time_to_read_display.short_description = "Time to Read"

    def read_status_summary(self, obj):
        if obj.status == 'READ':
            return f"✅ Read {obj.read_count} times"
        elif obj.status == 'DELIVERED':
            return "📨 Delivered (not read)"
        elif obj.status == 'SENT':
            return "📤 Sent (not delivered)"
        else:
            return f"❌ {obj.status}"
    read_status_summary.short_description = "Read Status"

    def advance_sale_link(self, obj):
        if obj.advance_sale:
            return format_html(
                '<a href="{}">{}</a>',
                f'../../main_app/advancesale/{obj.advance_sale.id}/change/',
                obj.advance_sale.unique_code
            )
        return "-"
    advance_sale_link.short_description = "Advance Sale"

    actions = ['mark_as_read', 'retry_failed', 'sync_status']

    def mark_as_read(self, request, queryset):
        updated = 0
        for log in queryset:
            if log.can_be_marked_read():
                log.mark_as_read()
                updated += 1
        self.message_user(request, f'{updated} messages marked as read.')
    mark_as_read.short_description = "Mark selected as read"

    def retry_failed(self, request, queryset):
        updated = queryset.filter(status='FAILED').update(
            status='PENDING',
            error_message=''
        )
        self.message_user(request, f'{updated} messages queued for retry.')
    retry_failed.short_description = "Retry selected failed messages"

    def sync_status(self, request, queryset):
        self.message_user(request, f'Status sync triggered for {queryset.count()} messages.')
    sync_status.short_description = "Sync status from WhatsApp"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('advance_sale')


@admin.register(SMSQueue, site=custom_admin_site)
class SMSQueueAdmin(admin.ModelAdmin):
    list_display = [
        'mobile_number', 'unique_code', 'mpp_name', 'cycle_info',
        'status_badge', 'attempts', 'created_at', 'processed_at',
        'status'  # Added status for list_editable
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['mobile_number', 'unique_code', 'mpp_name']
    readonly_fields = ['created_at', 'processed_at', 'attempts']
    list_editable = ['status']
    date_hierarchy = 'created_at'
    list_per_page = 50
    ordering = ['-created_at']

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'SENT': '#28A745',
            'FAILED': '#DC3545',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    actions = ['retry_failed_sms']

    def retry_failed_sms(self, request, queryset):
        updated = queryset.filter(status='FAILED').update(
            status='PENDING', 
            attempts=0,
            last_error=''
        )
        self.message_user(request, f'{updated} SMS queued for retry.')
    retry_failed_sms.short_description = "Retry selected failed SMS"


# ===========================
# UPLOAD BATCH & ERROR LOGGING
# ===========================

@admin.register(UploadBatch, site=custom_admin_site)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = [
        'batch_id', 'file_name', 'uploaded_by', 'uploaded_at',
        'status_badge', 'total_rows', 'rows_processed', 
        'rows_succeeded', 'rows_failed', 'progress'
    ]
    list_filter = ['status', 'uploaded_at']
    search_fields = ['batch_id', 'file_name', 'uploaded_by__email']
    readonly_fields = ['uploaded_at', 'processing_started_at', 'processing_completed_at']
    date_hierarchy = 'uploaded_at'
    list_per_page = 25
    ordering = ['-uploaded_at']
    autocomplete_fields = ['uploaded_by']
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('batch_id', 'file_name', 'file_size', 'uploaded_by', 'uploaded_at')
        }),
        ('Processing Status', {
            'fields': ('status', 'processing_started_at', 'processing_completed_at')
        }),
        ('Row Counts', {
            'fields': ('total_rows', 'rows_processed', 'rows_succeeded', 'rows_failed')
        }),
        ('Error Information', {
            'fields': ('error_summary', 'metrics'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'PROCESSING': '#17A2B8',
            'COMPLETED': '#28A745',
            'FAILED': '#DC3545',
            'PARTIAL': '#FFC107',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def progress(self, obj):
        if obj.total_rows > 0:
            processed = obj.rows_processed
            percentage = (processed / obj.total_rows) * 100
            return f"{processed}/{obj.total_rows} ({percentage:.1f}%)"
        return "0%"
    progress.short_description = "Progress"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')


@admin.register(ProcessingErrorLog, site=custom_admin_site)
class ProcessingErrorLogAdmin(admin.ModelAdmin):
    list_display = [
        'batch', 'row_index', 'field', 'rule', 
        'error_message_preview', 'is_critical', 'created_at'
    ]
    list_filter = ['rule', 'is_critical', 'created_at']
    search_fields = ['field', 'value', 'error_message', 'suggestion']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 100
    ordering = ['-created_at']
    autocomplete_fields = ['batch']

    def error_message_preview(self, obj):
        return obj.error_message[:100] + "..." if len(obj.error_message) > 100 else obj.error_message
    error_message_preview.short_description = "Error Message"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('batch')


@admin.register(ProductMappingUpload, site=custom_admin_site)
class ProductMappingUploadAdmin(admin.ModelAdmin):
    list_display = [
        'upload_id', 'filename', 'user_id', 'status_badge',
        'progress', 'started_at', 'completed_at', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['upload_id', 'filename', 'user_id']
    readonly_fields = ['started_at', 'created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']

    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFC107',
            'PROCESSING': '#17A2B8',
            'COMPLETED': '#28A745',
            'PARTIAL_SUCCESS': '#FFC107',
            'FAILED': '#DC3545',
            'CANCELLED': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    def progress(self, obj):
        return f"{obj.progress:.1f}%"
    progress.short_description = "Progress"


@admin.register(ReconciliationAuditLog, site=custom_admin_site)
class ReconciliationAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'upload', 'row_index', 'action_type', 'entity_type',
        'entity_identifier', 'timestamp'
    ]
    list_filter = ['action_type', 'entity_type', 'timestamp']
    search_fields = ['entity_identifier', 'upload__upload_id']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    list_per_page = 100
    ordering = ['-timestamp']
    autocomplete_fields = ['upload']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('upload')


# ===========================
# EMAIL SETTINGS
# ===========================

@admin.register(EmailSettings, site=custom_admin_site)
class EmailSettingsAdmin(admin.ModelAdmin):
    list_display = ['subject', 'from_email', 'cc_emails_preview']
    list_display_links = ['subject']
    list_editable = ['from_email']

    def cc_emails_preview(self, obj):
        if obj.cc_emails:
            return obj.cc_emails[:50] + "..." if len(obj.cc_emails) > 50 else obj.cc_emails
        return "-"
    cc_emails_preview.short_description = "CC Emails"


# ===========================
# MEDIA FILES VIEW
# ===========================

def list_media_files(request):
    media_root = settings.MEDIA_ROOT
    media_url = settings.MEDIA_URL
    path = request.GET.get('path', '').strip('/')
    current_path = os.path.join(media_root, path)
    parent_path = '/'.join(path.split('/')[:-1])
    folders = []
    files = []

    if os.path.exists(current_path):
        for entry in os.listdir(current_path):
            entry_path = os.path.join(current_path, entry)
            if os.path.isdir(entry_path):
                folders.append(entry)
            else:
                relative_path = os.path.relpath(entry_path, media_root)
                file_url = os.path.join(media_url, relative_path).replace("\\", "/")
                files.append((entry, file_url))

    folders.sort()
    files.sort()

    if parent_path:
        parent_path = f"/{parent_path}"

    template = loader.get_template('admin/list_media_files.html')
    context = {
        'folders': folders,
        'files': files,
        'current_path': f"/{path}" if path else '',
        'parent_path': parent_path,
    }
    return HttpResponse(template.render(context, request))


# ===========================
# REGISTER ALL REMAINING MODELS
# ===========================

# Register models with default admin if not already registered
remaining_models = [
    # Add any models not explicitly registered above
]

for model in remaining_models:
    try:
        custom_admin_site.register(model)
    except Exception as e:
        pass  # Model might already be registered or doesn't exist