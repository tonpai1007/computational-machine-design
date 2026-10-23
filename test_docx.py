import sys
sys.path.insert(0, r"c:/codework/computational-machine-design")
from integrations.learning_tools import LearningToolsBridge
import os

bridge = LearningToolsBridge()
print("Is online:", bridge.is_online(timeout=1.0))

# Test with the shaft report
html_file = r"c:/codework/computational-machine-design/Project/shaft/shaft_blueprint.html"
if os.path.exists(html_file):
    print("HTML file exists, size:", os.path.getsize(html_file), "bytes")
    try:
        result = bridge.convert_docx(html_file)
        print("DOCX conversion result:", result)
        # Check if docx was created
        docx_file = html_file.replace(".html", ".docx")
        if os.path.exists(docx_file):
            print("DOCX created, size:", os.path.getsize(docx_file), "bytes")
        else:
            print("DOCX not found at expected location")
    except Exception as e:
        print("DOCX conversion error:", type(e).__name__, str(e))
else:
    print("HTML file not found:", html_file)