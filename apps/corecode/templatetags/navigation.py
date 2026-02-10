from django import template
from django.urls import reverse, NoReverseMatch
from django.apps import apps

register = template.Library()

@register.inclusion_tag('corecode/navigation/admin_nav.html', takes_context=True)
def admin_navigation(context):
    """Modern admin navigation based on actual URLs"""
    request = context.get('request')
    user = request.user if request else None
    
    # Core URLs (based on your urls.py)
    core_urls = {
        'home': 'corecode:home',
        'configs': 'corecode:configs',
        'current_session': 'corecode:current-session',
        'sessions': 'corecode:sessions',
        'session_create': 'corecode:session-create',
        'terms': 'corecode:terms',
        'term_create': 'corecode:term-create',
        'classes': 'corecode:classes',
        'class_create': 'corecode:class-create',
        'subjects': 'corecode:subjects',
        'subject_create': 'corecode:subject-create',
    }
    
    # Student URLs
    student_urls = {
        'student_list': 'students:student_list',
        'student_create': 'students:student_create',
        'student_upload': 'students:student_upload',
        'download_csv': 'students:download-csv',
        'guardian_list': 'students:guardian_list',
        'guardian_create': 'students:guardian_create',
        'enhanced_create': 'students:enhanced_create',
        'quick_create': 'students:quick_create',
        'inactive_students': 'students:inactive_students',
        'bulk_activate': 'students:bulk_activate_students',
        'promotion_safety': 'students:promotion_safety',
        'promotion_logs': 'students:promotion_logs',
    }
    
    # Admission URLs
    admission_urls = {
        'dashboard': 'admissions:dashboard',
        'application_list': 'admissions:application_list',
        'application_create': 'admissions:application_create',
        'student_creation_dashboard': 'admissions:student_creation_dashboard',
        'manual_student_create': 'admissions:manual_student_create',
        'student_activate': 'admissions:student_activate',
        'inactive_students': 'admissions:inactive_students',
        'enhanced_manual_create': 'admissions:enhanced_manual_create',
        'quick_student_create': 'admissions:quick_student_create',
        'activation_wizard': 'admissions:activation_wizard',
    }
    
    # Staff URLs
    staff_urls = {
        'staff_list': 'staffs:staff-list',
        'staff_create': 'staffs:staff-create',
    }
    
    # Finance URLs
    finance_urls = {
        'invoice_list': 'finance:invoice_list',
        'invoice_create': 'finance:invoice_create',
        'bulk_invoice': 'finance:bulk_invoice',
        'fee_structure_list': 'finance:fee_structure_list',
        'fee_structure_create': 'finance:fee_structure_create',
        'financial_report': 'finance:financial_report',
    }
    
    # Result URLs
    result_urls = {
        'result_list': 'result:result_list',
        'result_create': 'result:result_create',
        'batch_create': 'result:batch_create',
        'batch_list': 'result:batch_list',
        'result_validation': 'result:result_validation',
    }
    
    # Define all possible nav items with their URLs
    all_nav_items = [
        {
            'title': 'Dashboard',
            'url': core_urls['home'],
            'icon': 'fas fa-grid-2',
        },
        {
            'title': 'Students',
            'url': '#',
            'icon': 'fas fa-user-graduate',
            'children': [
                {'title': 'All Students', 'url': student_urls['student_list'], 'icon': 'fas fa-users'},
                {'title': 'Add Student', 'url': student_urls['student_create'], 'icon': 'fas fa-user-plus'},
                {'title': 'Quick Create', 'url': student_urls['quick_create'], 'icon': 'fas fa-bolt'},
                {'title': 'Guardians', 'url': student_urls['guardian_list'], 'icon': 'fas fa-user-friends'},
                {'title': 'Bulk Upload', 'url': student_urls['student_upload'], 'icon': 'fas fa-upload'},
                {'title': 'Inactive Students', 'url': student_urls['inactive_students'], 'icon': 'fas fa-user-slash'},
                {'title': 'Promotion Safety', 'url': student_urls['promotion_safety'], 'icon': 'fas fa-shield-alt'},
            ],
        },
        {
            'title': 'Admissions',
            'url': '#',
            'icon': 'fas fa-file-signature',
            'children': [
                {'title': 'Dashboard', 'url': admission_urls['dashboard'], 'icon': 'fas fa-tachometer-alt'},
                {'title': 'Applications', 'url': admission_urls['application_list'], 'icon': 'fas fa-file-alt'},
                {'title': 'Student Creation', 'url': admission_urls['student_creation_dashboard'], 'icon': 'fas fa-user-plus'},
                {'title': 'Manual Create', 'url': admission_urls['manual_student_create'], 'icon': 'fas fa-user-edit'},
                {'title': 'Activation Wizard', 'url': admission_urls['activation_wizard'], 'icon': 'fas fa-magic'},
            ],
        },
        {
            'title': 'Academic',
            'url': '#',
            'icon': 'fas fa-graduation-cap',
            'children': [
                {'title': 'Classes', 'url': core_urls['classes'], 'icon': 'fas fa-chalkboard'},
                {'title': 'Subjects', 'url': core_urls['subjects'], 'icon': 'fas fa-book-open'},
                {'title': 'Sessions', 'url': core_urls['sessions'], 'icon': 'fas fa-calendar-alt'},
                {'title': 'Terms', 'url': core_urls['terms'], 'icon': 'fas fa-calendar'},
            ],
        },
        {
            'title': 'Staff',
            'url': '#',
            'icon': 'fas fa-chalkboard-teacher',
            'children': [
                {'title': 'All Staff', 'url': staff_urls['staff_list'], 'icon': 'fas fa-users'},
                {'title': 'Add Staff', 'url': staff_urls['staff_create'], 'icon': 'fas fa-user-plus'},
            ],
        },
        {
            'title': 'Finance',
            'url': '#',
            'icon': 'fas fa-wallet',
            'children': [
                {'title': 'Invoices', 'url': finance_urls['invoice_list'], 'icon': 'fas fa-file-invoice'},
                {'title': 'Create Invoice', 'url': finance_urls['invoice_create'], 'icon': 'fas fa-plus-circle'},
                {'title': 'Bulk Invoice', 'url': finance_urls['bulk_invoice'], 'icon': 'fas fa-layer-group'},
                {'title': 'Fee Structure', 'url': finance_urls['fee_structure_list'], 'icon': 'fas fa-money-check'},
                {'title': 'Financial Report', 'url': finance_urls['financial_report'], 'icon': 'fas fa-chart-bar'},
            ],
        },
        {
            'title': 'Results',
            'url': '#',
            'icon': 'fas fa-chart-line',
            'children': [
                {'title': 'All Results', 'url': result_urls['result_list'], 'icon': 'fas fa-list'},
                {'title': 'Create Result', 'url': result_urls['result_create'], 'icon': 'fas fa-plus'},
                {'title': 'Batch Results', 'url': result_urls['batch_create'], 'icon': 'fas fa-layer-group'},
                {'title': 'Result Validation', 'url': result_urls['result_validation'], 'icon': 'fas fa-check-double'},
            ],
        },
    ]
    
    # Superuser-only sections
    if user and user.is_superuser:
        all_nav_items.append({
            'title': 'System',
            'url': '#',
            'icon': 'fas fa-cogs',
            'children': [
                {'title': 'Site Config', 'url': core_urls['configs'], 'icon': 'fas fa-cog'},
                {'title': 'Current Session', 'url': core_urls['current_session'], 'icon': 'fas fa-calendar-check'},
                {'title': 'Promotion Logs', 'url': student_urls['promotion_logs'], 'icon': 'fas fa-history'},
            ],
        })
    
    # Filter out items with non-existent URLs
    filtered_nav = []
    for item in all_nav_items:
        # Check if item should be shown
        if item.get('show') is False:
            continue
            
        # Check children URLs if any
        if item.get('children'):
            valid_children = []
            for child in item['children']:
                if _check_url_exists(child['url']):
                    valid_children.append(child)
            
            # Only include parent if it has valid children
            if valid_children:
                item['children'] = valid_children
                filtered_nav.append(item)
        elif _check_url_exists(item['url']):
            filtered_nav.append(item)
    
    return {'nav_items': filtered_nav, 'request': request}

@register.inclusion_tag('corecode/navigation/parent_nav.html', takes_context=True)
def parent_navigation(context):
    """Modern parent navigation based on actual URLs"""
    request = context.get('request')
    
    parent_nav_items = [
        {
            'title': 'Dashboard',
            'url': 'parent:dashboard',
            'icon': 'fas fa-grid-2',
        },
        {
            'title': 'My Wards',
            'url': 'parent:my_wards',
            'icon': 'fas fa-user-graduate',
        },
        {
            'title': 'Results',
            'url': 'parent:results',
            'icon': 'fas fa-chart-line',
        },
        {
            'title': 'Attendance',
            'url': 'parent:attendance',
            'icon': 'fas fa-calendar-check',
        },
        {
            'title': 'Payments',
            'url': 'parent:payments',
            'icon': 'fas fa-credit-card',
        },
        {
            'title': 'Announcements',
            'url': 'parent:announcements',
            'icon': 'fas fa-bullhorn',
        },
        {
            'title': 'Contact School',
            'url': 'parent:contact',
            'icon': 'fas fa-envelope',
        },
        {
            'title': 'Profile',
            'url': 'parent:profile',
            'icon': 'fas fa-user-circle',
        },
        {
            'title': 'Settings',
            'url': 'parent:settings',
            'icon': 'fas fa-cog',
        },
    ]
    
    filtered_nav = []
    for item in parent_nav_items:
        if _check_url_exists(item['url']):
            filtered_nav.append(item)
    
    return {'nav_items': filtered_nav, 'request': request}

@register.simple_tag(takes_context=True)
def get_user_role(context):
    """Enhanced user role detection"""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return 'public'
    
    user = request.user
    
    # Superuser is always admin
    if user.is_superuser:
        return 'admin'
    
    # Check if user is a guardian
    if hasattr(user, 'guardian_profile'):
        return 'parent'
    
    # Staff with admin permissions
    if user.is_staff:
        return 'admin'
    
    # Check staff profile
    if hasattr(user, 'staff'):
        return 'admin'
    
    return 'public'

@register.filter
def has_permission(user, permission):
    """Check if user has specific permission"""
    if user.is_superuser:
        return True
    return user.has_perm(permission)

def _check_url_exists(url_name):
    """Check if a URL name exists in URL patterns"""
    try:
        if url_name == '#':
            return True
        reverse(url_name)
        return True
    except NoReverseMatch:
        # Check if it's a URL path (starts with /)
        if url_name.startswith('/'):
            return True
        return False