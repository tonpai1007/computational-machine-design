import sys
sys.path.insert(0, r"c:/codework/computational-machine-design")
from integrations.learning_tools import LearningToolsBridge
b = LearningToolsBridge()
methods = [m for m in dir(b) if not m.startswith("_")]
print("Available methods:", methods)