import os
import zipfile

base_dir = r'C:\codework\computational-machine-design\Project\chair'

print("=" * 60)
print("Comparing v1 vs v2 report terms")
print("=" * 60)

for version, filename in [("v1", "academic_assignment_report.docx"), ("v2", "academic_assignment_report_v2.docx")]:
    print(f"\n--- {version} ---")
    filepath = os.path.join(base_dir, filename)
    try:
        z = zipfile.ZipFile(filepath)
        content = z.read('word/document.xml').decode('utf-8', errors='replace')
        search_terms = ['overhang', 'strut_base_moment', 'arm_safety_factor', '1300 N', 'yield', 'buckling', 'fatigue']
        for term in search_terms:
            found = term.lower() in content.lower()
            print(f"  {term}: {'FOUND' if found else 'NOT FOUND'}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 60)
