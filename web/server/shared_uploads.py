"""Persistent public CSV catalog. Deletion requires a private owner token."""
import csv,hashlib,hmac,io,json,math,os,re,secrets,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import PlainTextResponse,JSONResponse

MAX_BYTES=4*1024*1024

def create_upload_router(directory):
 router=APIRouter(prefix='/api/shared-uploads')
 def cloud():
  return bool(os.environ.get('BLOB_READ_WRITE_TOKEN'))
 def db():
  if os.environ.get('VERCEL'):
   raise HTTPException(503,'Persistent upload storage is not configured')
  path=Path(os.environ.get('TACTILE_UPLOAD_DIR',str(directory)));path.mkdir(parents=True,exist_ok=True)
  conn=sqlite3.connect(path/'shared.sqlite3');conn.row_factory=sqlite3.Row
  conn.execute('CREATE TABLE IF NOT EXISTS uploads (id TEXT PRIMARY KEY, label TEXT, created TEXT, sensor_count INTEGER, owner_hash TEXT, csv TEXT)')
  return conn
 def blob_path(ident):
  if not re.fullmatch(r'[a-f0-9]{32}',ident):raise HTTPException(404,'Upload not found')
  return 'shared-uploads/'+ident+'.json'
 def find(ident):
  if cloud():
   from vercel.blob import BlobClient
   from vercel.blob.errors import BlobNotFoundError
   try:
    with BlobClient() as client:row=json.loads(client.get(blob_path(ident),access='private',use_cache=False).content)
   except BlobNotFoundError:row=None
  else:
   conn=db()
   try:
    found=conn.execute('SELECT * FROM uploads WHERE id=?',(ident,)).fetchone();row=dict(found) if found else None
   finally:conn.close()
  if not row:raise HTTPException(404,'This upload was deleted or does not exist')
  return row
 def save(row):
  if cloud():
   from vercel.blob import BlobClient
   with BlobClient() as client:client.put(blob_path(row['id']),json.dumps(row).encode(),access='private',content_type='application/json',add_random_suffix=False)
  else:
   conn=db()
   try:
    with conn:conn.execute('INSERT INTO uploads VALUES (?,?,?,?,?,?)',tuple(row[k] for k in ['id','label','created','sensor_count','owner_hash','csv']))
   finally:conn.close()
 def remove(ident):
  if cloud():
   from vercel.blob import BlobClient
   with BlobClient() as client:client.delete(blob_path(ident))
  else:
   conn=db()
   try:
    with conn:conn.execute('DELETE FROM uploads WHERE id=?',(ident,))
   finally:conn.close()
 def metadata(row):
  return dict(id='shared_'+row['id'],label=row['label'],uploadedAt=row['created'],sensorCount=row['sensor_count'],group='Shared uploads',url='/api/shared-uploads/'+row['id']+'/data.csv',shareId=row['id'])
 @lru_cache(maxsize=512)
 def cloud_metadata(ident):
  # Recordings are immutable: cache only safe metadata, never CSV or owner keys.
  return metadata(find(ident))
 @router.get('')
 def list_uploads():
  if cloud():
   from vercel.blob import list_objects
   items=[];cursor=None
   while True:
    page=list_objects(prefix='shared-uploads/',limit=1000,cursor=cursor)
    for blob in page.blobs:
     match=re.fullmatch(r'shared-uploads/([a-f0-9]{32})\.json',blob.pathname)
     if not match:continue
     try:items.append(cloud_metadata(match.group(1)))
     except HTTPException as exc:
      if exc.status_code!=404:raise
      # An owner may delete a recording between listing and reading it.
    if not page.has_more:break
    cursor=page.cursor
  else:
   conn=db()
   try:items=[metadata(dict(row)) for row in conn.execute('SELECT id,label,created,sensor_count FROM uploads')]
   finally:conn.close()
  items.sort(key=lambda item:(item['uploadedAt'],item['id']),reverse=True)
  return JSONResponse(items,headers={'Cache-Control':'no-store'})
 @router.post('')
 async def upload(request:Request):
  body=bytearray()
  async for chunk in request.stream():
   body.extend(chunk)
   if len(body)>MAX_BYTES:raise HTTPException(413,'Upload request exceeds 4 MB')
  try:
   payload=json.loads(body);text=payload['csv'];label=payload['filename']
   if not isinstance(text,str) or not isinstance(label,str) or not 1<=len(label)<=255:raise ValueError('Invalid filename or CSV')
   first=text.lstrip('\ufeff').splitlines()[0];delimiter='\t' if '\t' in first else ';' if ';' in first and ',' not in first else ','
   rows=csv.reader(io.StringIO(text.lstrip('\ufeff')),delimiter=delimiter);headers=[h.strip() for h in next(rows)]
   if len(headers)!=len(set(headers)):raise ValueError('Duplicate CSV columns')
   nodes=[(int(h[1:]),i) for i,h in enumerate(headers) if re.fullmatch(r'N\d+',h,re.I)]
   if nodes:
    nodes.sort();count=len(nodes)
    if count not in (18,96,132) or [n for n,i in nodes]!=list(range(1,count+1)):raise ValueError('Expected 18, 96, or 132 consecutive N columns')
    indices=[i for n,i in nodes]
   else:
    count=96;indices=[headers.index('signal_0_to_1')];headers.index('scan_index');headers.index('raw_voltage_v')
   found=0
   for row in rows:
    if not any(c.strip() for c in row):continue
    if len(row)!=len(headers):raise ValueError('Incorrect CSV column count')
    for i in indices:
     value=float(row[i])
     if not math.isfinite(value) or not 0<=value<=1:raise ValueError('Signal values must be finite and between 0 and 1')
    found+=1
   if not found:raise ValueError('CSV has no samples')
  except (ValueError,KeyError,TypeError,IndexError,StopIteration,csv.Error) as exc:raise HTTPException(400,str(exc))
  ident=secrets.token_hex(16);token=secrets.token_urlsafe(32);created=datetime.now(timezone.utc).isoformat()
  row=dict(id=ident,label=label.removesuffix('.csv'),created=created,sensor_count=count,owner_hash=hashlib.sha256(token.encode()).hexdigest(),csv=text)
  save(row)
  result=metadata(row);result['ownerToken']=token;return result
 @router.get('/{ident}/data.csv',response_class=PlainTextResponse)
 def data(ident:str):
  return PlainTextResponse(find(ident)['csv'],media_type='text/csv',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
 @router.get('/{ident}')
 def get(ident:str):
  return metadata(find(ident))
 @router.delete('/{ident}')
 def delete(ident:str,request:Request):
  token=request.headers.get('Authorization','').removeprefix('Bearer ')
  row=find(ident)
  if not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(),row['owner_hash']):raise HTTPException(403,'Only the uploader can delete this recording')
  remove(ident)
  cloud_metadata.cache_clear()
  return {'deleted':True}
 return router
