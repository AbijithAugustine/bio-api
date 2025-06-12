from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import shutil
import os
import sqlite3
from datetime import datetime
from tempfile import NamedTemporaryFile
import subprocess
from typing import Optional

app = FastAPI()

# Initialize SQLite DB
def init_db():
    conn = sqlite3.connect('uploads.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS uploads
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.post('/nearest')
async def find_nearest(
    query_bed: UploadFile = File(...),
    gene_bed: UploadFile = File(...),
    mapping_file: Optional[UploadFile] = File(None)
):
    print('Received request')
    # Check file extensions
    for f in [query_bed, gene_bed]:
        if not (f.filename.endswith('.bed')):
            print('File extension error')
            raise HTTPException(status_code=400, detail='Only BED files are allowed.')
    # Log upload
    conn = sqlite3.connect('uploads.db')
    c = conn.cursor()
    mapping_name = mapping_file.filename if mapping_file else ''
    c.execute('INSERT INTO uploads (filename, timestamp) VALUES (?, ?)', (f"{query_bed.filename},{gene_bed.filename},{mapping_name}", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    print('Files logged to DB')
    # Save files to temp
    with NamedTemporaryFile(delete=False, suffix='.bed') as tmp_query, \
         NamedTemporaryFile(delete=False, suffix='.bed') as tmp_gene:
        shutil.copyfileobj(query_bed.file, tmp_query)
        shutil.copyfileobj(gene_bed.file, tmp_gene)
        tmp_query_path = tmp_query.name
        tmp_gene_path = tmp_gene.name
    print(f'Files saved: {tmp_query_path}, {tmp_gene_path}')
    # Sort both BED files using bedtools sort
    with NamedTemporaryFile(delete=False, suffix='.bed') as tmp_query_sorted, \
         NamedTemporaryFile(delete=False, suffix='.bed') as tmp_gene_sorted, \
         NamedTemporaryFile(delete=False, suffix='.bed') as tmp_out:
        tmp_query_sorted_path = tmp_query_sorted.name
        tmp_gene_sorted_path = tmp_gene_sorted.name
        tmp_out_path = tmp_out.name
        print('Sorting query BED')
        try:
            subprocess.run(['bedtools', 'sort', '-i', tmp_query_path], stdout=open(tmp_query_sorted_path, 'w'), stderr=subprocess.PIPE, check=True)
            print('Sorting gene BED')
            subprocess.run(['bedtools', 'sort', '-i', tmp_gene_path], stdout=open(tmp_gene_sorted_path, 'w'), stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            print(f'bedtools sort error: {error_msg}')
            os.remove(tmp_query_path)
            os.remove(tmp_gene_path)
            os.remove(tmp_query_sorted_path)
            os.remove(tmp_gene_sorted_path)
            os.remove(tmp_out_path)
            raise HTTPException(status_code=500, detail=f'Error running bedtools sort: {error_msg}')
        print('BED files sorted')
        # Save mapping file if provided
        mapping_dict = None
        if mapping_file:
            with NamedTemporaryFile(delete=False, suffix='.tsv') as tmp_map:
                shutil.copyfileobj(mapping_file.file, tmp_map)
                tmp_map_path = tmp_map.name
            # Load mapping into dict, skip header if present
            mapping_dict = {}
            with open(tmp_map_path, 'r') as mf:
                for i, line in enumerate(mf):
                    if i == 0 and line.lower().startswith('name'):
                        continue  # skip header
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        mapping_dict[parts[0]] = parts[1]
            os.remove(tmp_map_path)
            print('Mapping file loaded')
        # Run bedtools closest with error capture
        print('Before bedtools closest call')
        try:
            with open(tmp_out_path, 'w') as out_f:
                result = subprocess.run([
                    'bedtools', 'closest', '-d', '-t', 'first', '-a', tmp_query_sorted_path, '-b', tmp_gene_sorted_path
                ], stdout=out_f, stderr=subprocess.PIPE, check=True)
            print('After bedtools closest call')
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            print(f'bedtools closest error: {error_msg}')
            os.remove(tmp_query_path)
            os.remove(tmp_gene_path)
            os.remove(tmp_query_sorted_path)
            os.remove(tmp_gene_sorted_path)
            os.remove(tmp_out_path)
            raise HTTPException(status_code=500, detail=f'Error running bedtools closest: {error_msg}')
        print('Parsing bedtools output')
        # Parse output, filter by distance, extract gene names, map if needed
        def iterfile():
            seen = set()
            with open(tmp_out_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= 1000:
                        break
                    fields = line.strip().split('\t')
                    print(fields)  # DEBUG: print the parsed fields
                    if len(fields) < 7:
                        continue
                    try:
                        distance = int(fields[-1])
                    except Exception:
                        continue
                    if distance > 10000:
                        continue
                    gene_id = fields[6]  # 7th column: gene name in gene BED12
                    if mapping_dict:
                        gene_id = mapping_dict.get(gene_id, gene_id)
                    if gene_id not in seen:
                        seen.add(gene_id)
                        yield (gene_id + '\n').encode()
            os.remove(tmp_query_path)
            os.remove(tmp_gene_path)
            os.remove(tmp_query_sorted_path)
            os.remove(tmp_gene_sorted_path)
            os.remove(tmp_out_path)
        print('Before returning StreamingResponse')
        return StreamingResponse(iterfile(), media_type='text/plain', headers={'Content-Disposition': f'attachment; filename=nearest_genes.txt'})

@app.get("/")
def read_root():
    return {
        "message": "Bio API is live. Use the /nearest endpoint to upload BED files."
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}
