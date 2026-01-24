from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from apps.students.models import Student
from apps.corecode.utils import check_student_activation

class Command(BaseCommand):
    help = 'Check student activation status and generate report'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['console', 'csv'],
            default='console',
            help='Output format'
        )
        parser.add_argument(
            '--class',
            dest='class_id',
            help='Filter by class ID'
        )
    
    def handle(self, *args, **options):
        # Get students
        students = Student.objects.all()
        
        if options['class_id']:
            students = students.filter(current_class_id=options['class_id'])
        
        # Analyze activation
        active_count = 0
        inactive_count = 0
        missing_guardian = 0
        missing_class = 0
        missing_session = 0
        
        report_data = []
        
        for student in students:
            is_active, missing = check_student_activation(student)
            
            if is_active:
                active_count += 1
            else:
                inactive_count += 1
            
            if 'Guardian' in missing:
                missing_guardian += 1
            if 'Class' in missing:
                missing_class += 1
            if 'Academic Session' in missing:
                missing_session += 1
            
            report_data.append({
                'student_number': student.student_number,
                'name': student.full_name,
                'class': str(student.current_class) if student.current_class else 'None',
                'is_active': is_active,
                'missing': ', '.join(missing) if missing else 'None',
            })
        
        # Output based on format
        if options['format'] == 'csv':
            self.output_csv(report_data)
        else:
            self.output_console(report_data, active_count, inactive_count, 
                              missing_guardian, missing_class, missing_session)
    
    def output_console(self, data, active_count, inactive_count, 
                      missing_guardian, missing_class, missing_session):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('STUDENT ACTIVATION REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Total Students: {active_count + inactive_count}")
        self.stdout.write(f"   Active Students: {self.style.SUCCESS(str(active_count))}")
        self.stdout.write(f"   Inactive Students: {self.style.WARNING(str(inactive_count))}")
        
        self.stdout.write(f"\n🔧 Missing Requirements:")
        self.stdout.write(f"   No Guardian: {self.style.ERROR(str(missing_guardian))}")
        self.stdout.write(f"   No Class: {self.style.ERROR(str(missing_class))}")
        self.stdout.write(f"   No Session: {self.style.ERROR(str(missing_session))}")
        
        self.stdout.write(f"\n📋 Detailed List:")
        self.stdout.write(f"{'Student ID':<15} {'Name':<30} {'Class':<15} {'Status':<10} {'Missing':<20}")
        self.stdout.write('-' * 90)
        
        for item in data:
            status = self.style.SUCCESS('ACTIVE') if item['is_active'] else self.style.WARNING('INACTIVE')
            self.stdout.write(f"{item['student_number']:<15} {item['name']:<30} "
                            f"{item['class']:<15} {status:<10} {item['missing']:<20}")
    
    def output_csv(self, data):
        import csv
        import sys
        
        writer = csv.writer(sys.stdout)
        writer.writerow(['Student ID', 'Name', 'Class', 'Status', 'Missing Requirements'])
        
        for item in data:
            status = 'ACTIVE' if item['is_active'] else 'INACTIVE'
            writer.writerow([
                item['student_number'],
                item['name'],
                item['class'],
                status,
                item['missing']
            ])