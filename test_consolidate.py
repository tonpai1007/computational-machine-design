import sys
sys.path.insert(0, r"c:/codework/computational-machine-design")
from integrations.learning_tools import LearningToolsBridge
import os

bridge = LearningToolsBridge()
html_file = r"c:/codework/computational-machine-design/Project/shaft/shaft_blueprint.html"

# Test consolidate (knowledge consolidation)
print("=== Testing Knowledge Consolidation ===")
try:
    result = bridge.consolidate(html_file)
    print("Consolidate result:", result)
except Exception as e:
    print("Consolidate error:", type(e).__name__, str(e))

# Test generate summaries
print("\n=== Testing Summary Generation ===")
try:
    summaries = bridge.generate_summaries(html_file)
    print("Summaries generated, count:", len(summaries) if summaries else 0)
    if summaries:
        print("First summary preview:", str(summaries[0])[:100] + "...")
except Exception as e:
    print("Summaries error:", type(e).__name__, str(e))

# Test notebookLM pack
print("\n=== Testing NotebookLM Pack ===")
try:
    nb_result = bridge.generate_notebooklm(html_file)
    print("NotebookLM result:", nb_result)
except Exception as e:
    print("NotebookLM error:", type(e).__name__, str(e))

# Test study guide
print("\n=== Testing Study Guide ===")
try:
    study_result = bridge.study_guide(html_file)
    print("Study guide result:", study_result)
except Exception as e:
    print("Study guide error:", type(e).__name__, str(e))