import sys
import PyPDF2

pdf_path = r"D:\Codes\agents\Yash-Raj-Resume.pdf"
text = ""
try:
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text()
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
print(text)
