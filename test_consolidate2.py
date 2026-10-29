import sys

sys.path.insert(0, r"c:/codework/computational-machine-design")
import os

from integrations.learning_tools import LearningToolsBridge

bridge = LearningToolsBridge()
html_file = r"c:/codework/computational-machine-design/Project/shaft/shaft_blueprint.html"

print("Is online:", bridge.is_online(timeout=1.0))
print("Consolidating report...")

try:
    result = bridge.consolidate_report(html_file)
    print("Consolidate report result:", result)
except Exception as e:
    print("Consolidate report error:", type(e).__name__, str(e))

# Also check docx was created
docx_file = html_file.replace(".html", ".docx")
if os.path.exists(docx_file):
    print("DOCX exists, size:", os.path.getsize(docx_file), "bytes")
