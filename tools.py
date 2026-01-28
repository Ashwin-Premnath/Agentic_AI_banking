from fpdf import FPDF
import os
from crewai.tools import BaseTool
from datetime import datetime

class PDFGeneratorTool(BaseTool):
    name: str = "PDF Generator Tool"
    description: str = (
        "Generates a PDF file with provided text content. "
        "Requires arguments: 'content' (the text to write), 'filename' (name without .pdf), and 'folder_name' (subfolder inside data directory)."
    )

    def _run(self, content: str, filename: str, folder_name: str) -> str:
        """
        Saves the content to a PDF file in a specific subfolder.
        """
        print(f"\n{'='*60}")
        print(f"PDF GENERATOR TOOL CALLED!")
        print(f"Filename: {filename}")
        print(f"Folder: {folder_name}")
        print(f"Content length: {len(content)} characters")
        print(f"{'='*60}\n")
        
        try:
            # Use absolute path from current working directory
            base_dir = os.path.abspath("data")
            save_dir = os.path.join(base_dir, folder_name)
            os.makedirs(save_dir, exist_ok=True)
            
            print(f"Created/verified directory: {save_dir}")
            
            # Create PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=10)
            safe_content = content.replace('✘', '[X]').replace('✅', '[OK]')
            # Add content
            lines_added = 0
            for line in content.split('\n'):
                # Handle encoding issues on Windows
                try:
                    pdf.multi_cell(0, 5, line)
                    lines_added += 1
                except Exception as e:
                    # Fallback for special characters
                    pdf.multi_cell(0, 5, line.encode('utf-8', 'replace').decode('utf-8'))
                    lines_added += 1
            
            print(f"Added {lines_added} lines to PDF")
                
            # Save file
            file_path = os.path.join(save_dir, f"{filename}.pdf")
            pdf.output(file_path)
            
            # Verify file exists
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                success_msg = f"✅ SUCCESS! PDF saved to: {file_path} (Size: {file_size} bytes)"
                print(f"\n{success_msg}\n")
                return success_msg
            else:
                error_msg = f"❌ ERROR: File was not created at {file_path}"
                print(f"\n{error_msg}\n")
                return error_msg
                
        except Exception as e:
            error_msg = f"❌ ERROR saving PDF: {str(e)}"
            print(f"\n{error_msg}\n")
            import traceback
            traceback.print_exc()
            return error_msg