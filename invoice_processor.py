import pdfplumber
from PIL import Image
import io
import base64
import requests
import json
from collections import defaultdict
from typing import List, Dict, Any

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llava:7b"

# Extraction Prompt Template
EXTRACTION_PROMPT = """You are an expert invoice processor. Analyze this page image/text carefully.

If this page contains a TAX INVOICE, INVOICE, BILL, or SALES RECEIPT:
Extract and return ONLY valid JSON with this exact structure (no other text):
{
  "type": "invoice",
  "invoice_num": "...",
  "invoice_date": "...",
  "vendor_name": "...",
  "vendor_gstin": "...",
  "buyer_name": "...",
  "buyer_gstin": "...",
  "line_items": [
    {"description": "...", "hsn_sac": "...", "quantity": 0, "rate": 0, "unit": "...", "amount": 0}
  ],
  "subtotal": 0,
  "tax_breakdown": {
    "cgst": {"rate": "9%", "amount": 0},
    "sgst": {"rate": "9%", "amount": 0},
    "igst": {"rate": "0%", "amount": 0}
  },
  "total": 0
}

If this page is NOT an invoice (e.g., DELIVERY NOTE, PURCHASE ORDER, E-WAY BILL, VOUCHER, WEIGH BRIDGE, PACKING SLIP, PAYMENT RECEIPT):
Return only: {"type": "non_invoice"}

Important notes:
- Extract numbers as numeric values (no currency symbols or commas)
- For dates, preserve the original format from the document
- For line items, include all visible items
- If a field is missing, use empty string "" or 0 for missing numeric values
- Return ONLY JSON, absolutely no other text or explanations
- Do not include markdown code fences or backticks
"""


def load_and_split_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Stage 1: Load PDF and convert each page to image for vision AI"""
    pages_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"PDF loaded successfully. Total pages: {len(pdf.pages)}")
            for page_num, page in enumerate(pdf.pages):
                try:
                    pil_image = page.to_image(resolution=200).original
                    img_bytes = io.BytesIO()
                    pil_image.save(img_bytes, format='PNG')
                    img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
                    text = page.extract_text() or ""
                    pages_data.append({
                        "page_num": page_num + 1,
                        "image_base64": img_base64,
                        "text": text
                    })
                    print(f"  Page {page_num + 1} processed")
                except Exception as e:
                    print(f"  Warning: Could not process page {page_num + 1}: {str(e)}")
                    continue
        return pages_data
    except Exception as e:
        raise Exception(f"Failed to load PDF: {str(e)}")


def call_ollama(image_base64: str, text: str) -> Dict[str, Any]:
    """Stage 2: Call Ollama vision model to extract invoice data"""
    try:
        payload = {
            "model": MODEL,
            "prompt": EXTRACTION_PROMPT,
            "images": [image_base64],
            "stream": False,
            "temperature": 0.1
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        response_json = response.json()
        full_response = response_json.get('response', '')
        full_response = full_response.strip()
        if full_response.startswith('```'):
            full_response = full_response[full_response.find('{'): full_response.rfind('}') + 1]
        invoice_data = json.loads(full_response)
        return invoice_data
    except requests.exceptions.ConnectionError:
        raise Exception("Could not connect to Ollama. Make sure to run 'ollama serve' in a separate terminal.")
    except json.JSONDecodeError:
        return {"type": "non_invoice"}
    except Exception as e:
        print(f"Warning: Ollama error on page: {str(e)}")
        return {"type": "non_invoice"}


def extract_invoices_from_pages(pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 2: Extract invoice data from each page"""
    extracted_invoices = []
    for page in pages_data:
        print(f"Extracting data from page {page['page_num']}...")
        invoice_data = call_ollama(page["image_base64"], page["text"])
        if invoice_data.get("type") == "invoice":
            invoice_data["source_page"] = page["page_num"]
            extracted_invoices.append(invoice_data)
            print(f"  ✓ Invoice found: {invoice_data.get('invoice_num', 'N/A')}")
        else:
            print(f"  ✗ Non-invoice page (skipped)")
    return extracted_invoices


def merge_multipage_invoices(extracted_invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 3.1: Merge invoices that span multiple pages"""
    grouped = defaultdict(list)
    for inv in extracted_invoices:
        key = (
            inv.get("invoice_num"),
            inv.get("vendor_name"),
            inv.get("invoice_date")
        )
        grouped[key].append(inv)
    merged_invoices = []
    for key, pages in grouped.items():
        if len(pages) > 1:
            print(f"Merging {len(pages)} pages for invoice {key}")
        merged = pages[0].copy()
        merged["line_items"] = []
        merged["tax_breakdown"] = {}
        for page_inv in pages:
            merged["line_items"].extend(page_inv.get("line_items", []))
            if page_inv.get("tax_breakdown"):
                merged["tax_breakdown"].update(page_inv["tax_breakdown"])
            if page_inv.get("subtotal"):
                merged["subtotal"] = page_inv["subtotal"]
            if page_inv.get("total"):
                merged["total"] = page_inv["total"]
        seen_items = set()
        unique_items = []
        for item in merged["line_items"]:
            item_key = (
                item.get("description"),
                item.get("hsn_sac"),
                item.get("quantity"),
                item.get("rate")
            )
            if item_key not in seen_items:
                seen_items.add(item_key)
                unique_items.append(item)
        merged["line_items"] = unique_items
        merged_invoices.append(merged)
    return merged_invoices


def deduplicate_invoices(merged_invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 3.2: Remove duplicate invoices"""
    seen_keys = set()
    deduped_invoices = []
    duplicates_count = 0
    for inv in merged_invoices:
        dedup_key = (
            inv.get("invoice_num"),
            inv.get("vendor_name"),
            inv.get("invoice_date"),
            inv.get("total")
        )
        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            deduped_invoices.append(inv)
        else:
            duplicates_count += 1
            print(f"Duplicate removed: Invoice {inv.get('invoice_num')} from {inv.get('vendor_name')}")
    if duplicates_count > 0:
        print(f"Total duplicates removed: {duplicates_count}")
    return deduped_invoices


def format_as_markdown(deduped_invoices: List[Dict[str, Any]]) -> str:
    """Stage 4: Format extracted invoices as Markdown"""
    markdown_output = ""
    for idx, inv in enumerate(deduped_invoices, 1):
        markdown_output += f"## Invoice #{inv.get('invoice_num', 'N/A')} | {inv.get('vendor_name', 'N/A')} | {inv.get('invoice_date', 'N/A')}\n\n"
        markdown_output += f"**Vendor**: {inv.get('vendor_name', 'N/A')} (GSTIN: {inv.get('vendor_gstin', 'N/A')})\n"
        markdown_output += f"**Buyer**: {inv.get('buyer_name', 'N/A')} (GSTIN: {inv.get('buyer_gstin', 'N/A')})\n\n"
        line_items = inv.get('line_items', [])
        if line_items:
            markdown_output += "| Description | HSN/SAC | Qty | Rate | Unit | Amount |\n"
            markdown_output += "|---|---|---|---|---|---|\n"
            for item in line_items:
                desc = item.get('description', '').replace('|', '/')[:50]
                hsn = item.get('hsn_sac', '')
                qty = item.get('quantity', 0)
                rate = item.get('rate', 0)
                unit = item.get('unit', '')
                amount = item.get('amount', 0)
                try:
                    amount_str = f"{float(amount):,.2f}"
                except:
                    amount_str = str(amount)
                markdown_output += f"| {desc} | {hsn} | {qty} | {rate} | {unit} | {amount_str} |\n"
            markdown_output += "\n"
        subtotal = inv.get('subtotal', 0)
        try:
            subtotal_str = f"₹{float(subtotal):,.2f}"
        except:
            subtotal_str = f"₹{subtotal}"
        markdown_output += f"**Subtotal**: {subtotal_str}\n"
        tax_breakdown = inv.get('tax_breakdown', {})
        for tax_type, tax_info in tax_breakdown.items():
            if isinstance(tax_info, dict):
                rate = tax_info.get('rate', '0%')
                amount = tax_info.get('amount', 0)
                try:
                    amount_str = f"₹{float(amount):,.2f}"
                except:
                    amount_str = f"₹{amount}"
                markdown_output += f"**{tax_type.upper()} ({rate})**: {amount_str}\n"
        total = inv.get('total', 0)
        try:
            total_str = f"₹{float(total):,.2f}"
        except:
            total_str = f"₹{total}"
        markdown_output += f"\n**Total**: {total_str}\n\n"
        markdown_output += "---\n\n"
    return markdown_output


def process_invoice_pdf(pdf_path: str) -> Dict[str, Any]:
    """Main pipeline: Orchestrate all 4 stages"""
    print("\n" + "="*60)
    print("INVOICE EXTRACTION PIPELINE STARTED")
    print("="*60 + "\n")
    try:
        print("[Stage 1/4] Loading PDF and splitting into pages...")
        pages = load_and_split_pdf(pdf_path)
        print(f"✓ Loaded {len(pages)} pages from PDF\n")
        print("[Stage 2/4] Extracting invoices from pages using Ollama...")
        extracted = extract_invoices_from_pages(pages)
        print(f"✓ Extracted {len(extracted)} invoice candidates\n")
        print("[Stage 3/4] Merging multi-page invoices and removing duplicates...")
        merged = merge_multipage_invoices(extracted)
        print(f"✓ Merged to {len(merged)} invoices")
        deduped = deduplicate_invoices(merged)
        print(f"✓ After dedup: {len(deduped)} unique invoices\n")
        print("[Stage 4/4] Formatting output...")
        markdown_output = format_as_markdown(deduped)
        json_output = json.dumps(deduped, indent=2, ensure_ascii=False)
        print(f"✓ Output formatted\n")
        print("="*60)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("="*60 + "\n")
        return {
            "invoices": deduped,
            "markdown": markdown_output,
            "json": json_output
        }
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        raise
