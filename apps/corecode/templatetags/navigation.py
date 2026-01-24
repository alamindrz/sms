from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()

@register.inclusion_tag('corecode/navigation/admin_nav.html', takes_context=True)
def admin_navigation(context):
    """Admin/Staff navigation menu - Only includes existing URLs"""
    request = context.get('request')
    user = request.user if request else None
    
    # Define all possible nav items with their URLs
    all_nav_items = [
        {
            'title': 'Dashboard',
            'url': 'corecode:home',
            'icon': 'fas fa-tachometer-alt',
        },
        {
            'title': 'Students',
            'url': '#',
            'icon': 'fas fa-user-graduate',
            'children': [
                {'title': 'All Students', 'url': 'students:student_list'},
                {'title': 'Guardians', 'url': 'students:guardian_list'},
            ],
        },
        {
            'title': 'Admissions',
            'url': '#',
            'icon': 'fas fa-file-alt',
            'children': [
                {'title': 'Dashboard', 'url': 'admissions:dashboard'},
                {'title': 'Applications', 'url': 'admissions:application_list'},
                {'title': 'Student Creation', 'url': 'admissions:student_creation_dashboard'},
            ],
        },
        {
            'title': 'Academic',
            'url': '#',
            'icon': 'fas fa-graduation-cap',
            'children': [
                {'title': 'Classes', 'url': 'corecode:classes'},
                {'title': 'Subjects', 'url': 'corecode:subjects'},
                {'title': 'Sessions', 'url': 'corecode:sessions'},
                {'title': 'Terms', 'url': 'corecode:terms'},
            ],
        },
        {
            'title': 'Staff',
            'url': '#',
            'icon': 'fas fa-chalkboard-teacher',
            'children': [
                {'title': 'All Staff', 'url': 'staffs:staff_list'},
            ],
        },
        {
            'title': 'Finance',
            'url': '#',
            'icon': 'fas fa-money-bill-wave',
            'children': [
                {'title': 'Invoices', 'url': 'finance:invoice_list'},
                {'title': 'Receipts', 'url': 'finance:receipt_list'},
            ],
        },
        {
            'title': 'Settings',
            'url': '#',
            'icon': 'fas fa-cog',
            'children': [
                {'title': 'Site Config', 'url': 'corecode:site_config'},
                {'title': 'Current Session', 'url': 'corecode:current_session'},
            ],
        },
    ]
    
    # Filter out items with non-existent URLs
    filtered_nav = []
    for item in all_nav_items:
        # Check main URL
        main_url_valid = _check_url_exists(item['url'])
        
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
        elif main_url_valid:
            filtered_nav.append(item)
    
    return {'nav_items': filtered_nav, 'request': request}

@register.inclusion_tag('corecode/navigation/parent_nav.html', takes_context=True)
def parent_navigation(context):
    """Parent/Guardian navigation menu - Only includes existing URLs"""
    request = context.get('request')
    
    # Define parent nav items
    parent_nav_items = [
        {
            'title': 'Dashboard',
            'url': 'parent:dashboard',
            'icon': 'fas fa-tachometer-alt',
        },
        {
            'title': 'My Wards',
            'url': 'parent:my_wards',
            'icon': 'fas fa-user-graduate',
        },
        {
            'title': 'Academic Results',
            'url': 'parent:results',
            'icon': 'fas fa-chart-line',
        },
        {
            'title': 'Fee Payments',
            'url': 'parent:payments',
            'icon': 'fas fa-money-check-alt',
        },
        {
            'title': 'Announcements',
            'url': 'parent:announcements',
            'icon': 'fas fa-bullhorn',
        },
        {
            'title': 'Profile',
            'url': 'parent:profile',
            'icon': 'fas fa-user',
        },
    ]
    
    # Filter out non-existent URLs
    filtered_nav = []
    for item in parent_nav_items:
        if _check_url_exists(item['url']):
            filtered_nav.append(item)
    
    return {'nav_items': filtered_nav, 'request': request}

@register.simple_tag(takes_context=True)
def get_user_role(context):
    """Determine user role for navigation"""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return 'public'
    
    user = request.user
    
    # Check if user is a guardian
    if hasattr(user, 'guardian_profile'):
        return 'parent'
    
    # Check if user is staff/admin
    if user.is_staff or user.is_superuser:
        return 'admin'
    
    # Check if user has staff profile
    if hasattr(user, 'staff'):
        return 'admin'
    
    return 'public'

def _check_url_exists(url_name):
    """Check if a URL name exists in URL patterns"""
    try:
        if url_name == '#':
            return True
        reverse(url_name)
        return True
    except NoReverseMatch:
        return False