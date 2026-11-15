import sys
import PyPDF2

def extract_text_from_pdf(pdf_path):
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
    return text

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_resume.py <pdf_path>", file=sys.stderr)
        sys.exit(1)
    pdf_path = sys.argv[1]
    text = extract_text_from_pdf(pdf_path)
    print(text)
