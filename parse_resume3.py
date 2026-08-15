import sys
import PyPDF2
pdf_path = sys.argv[1]
text = ""
with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    for page in reader.pages:
        text += page.extract_text()
print(text)
