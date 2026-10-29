import zipfile

z = zipfile.ZipFile(r'C:\codework\computational-machine-design\Project\chair\academic_assignment_report_v2.docx')
content = z.read('word/document.xml').decode('utf-8', errors='replace')
import re

# Find all numbers with 2-4 decimal places
numbers = re.findall(r'\d+\.\d{2,4}', content)
print("Numbers with 2-4 decimal places:")
for n in numbers[:30]:
    print(n)
print(f"\nTotal found: {len(numbers)}")
