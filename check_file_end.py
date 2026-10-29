"""Check the end of document_intelligence.py."""
lines = open("c:/codework/computational-machine-design/convert/document_intelligence.py").readlines()
print(f"Total lines: {len(lines)}")
print(f"Last 3 lines:")
for line in lines[-3:]:
    print(repr(line))