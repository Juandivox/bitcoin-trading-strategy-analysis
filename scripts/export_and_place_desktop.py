"""
scripts/export_and_place_desktop.py
Convierte C:\\Users\\jugev\\Desktop\\avances.docx a avances.pdf mediante Word nativo,
asegura copias en C:\\Users\\jugev\\Desktop y C:\\Users\\jugev\\OneDrive\\Desktop,
y abre el explorador con el archivo seleccionado.
"""
import os
import shutil
import win32com.client

docx_path = os.path.abspath(r"C:\Users\jugev\Desktop\avances.docx")
pdf_path = os.path.abspath(r"C:\Users\jugev\Desktop\avances.pdf")
onedrive_desktop = r"C:\Users\jugev\OneDrive\Desktop"

print(f"Abriendo {docx_path} con Word...")
word = win32com.client.Dispatch("Word.Application")
word.Visible = False
try:
    doc = word.Documents.Open(docx_path)
    # wdFormatPDF = 17
    doc.SaveAs2(pdf_path, FileFormat=17)
    doc.Close()
    print(f"Exportado exitosamente a PDF: {pdf_path}")
except Exception as e:
    print(f"Error al exportar PDF con Word: {e}")
finally:
    try:
        word.Quit()
    except Exception:
        pass

if os.path.exists(onedrive_desktop):
    shutil.copy2(docx_path, os.path.join(onedrive_desktop, "avances.docx"))
    if os.path.exists(pdf_path):
        shutil.copy2(pdf_path, os.path.join(onedrive_desktop, "avances.pdf"))
    print(f"Copia de seguridad realizada en {onedrive_desktop}")

# Abrir el explorador seleccionando el archivo en el escritorio
os.system(f'explorer.exe /select,"{docx_path}"')
print("Explorador abierto en el escritorio con el archivo seleccionado.")
