from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
import os
import tempfile
from invoice_processor import process_invoice_pdf

app = FastAPI(
    title="Invoice Extraction System",
    description="Extract structured data from invoices in PDF format",
    version="1.0.0"
)

# Mount static files
if os.path.exists('static'):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    """Serve the home page"""
    return FileResponse("static/index.html", media_type="text/html")

@app.post("/api/extract-invoices")
async def extract_invoices(file: UploadFile = File(...)):
    """Extract invoices from uploaded PDF"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name
        
        result = process_invoice_pdf(tmp_file_path)
        
        os.unlink(tmp_file_path)
        
        return JSONResponse({
            "status": "success",
            "invoices": result["invoices"],
            "markdown": result["markdown"],
            "count": len(result["invoices"])
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Invoice Extraction API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
