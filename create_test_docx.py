"""Create a test DOCX for OCR enrichment testing."""
import docx

doc = docx.Document()
doc.add_paragraph("Design overview and analysis of bearing system")
doc.add_paragraph("Assumptions: material yield strength 250 MPa")
doc.add_heading("Design Overview", level=1)
doc.add_paragraph("The bearing design follows standard engineering practices")
doc.add_heading("Assumptions", level=2)
doc.add_paragraph("Material: bearing steel, hardness 60 HRC")
doc.add_heading("Key Results", level=2)
doc.add_paragraph("Basic load rating: 45 kN")
doc.add_heading("Conclusion", level=1)
doc.add_paragraph("Design meets requirements with factor of safety 2.5")

doc.save("c:/codework/computational-machine-design/test_report.docx")
print("Created test_report.docx")