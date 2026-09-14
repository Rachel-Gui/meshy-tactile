import tempfile,unittest
import os,sys,json
from types import ModuleType,SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web.server.shared_uploads import create_upload_router

class SharedUploadTests(unittest.TestCase):
 def test_public_catalog_across_visitors_and_restarts(self):
  with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{},clear=True):
   def client():
    app=FastAPI();app.include_router(create_upload_router(Path(directory)));return TestClient(app)
   owner=client();visitor=client()
   self.assertEqual(visitor.get('/api/shared-uploads').json(),[])
   saved=[]
   for count in [18,96,132]:
    csv='time,'+','.join(f'N{i:03}' for i in range(1,count+1))+'\n0,'+','.join(['0']*count)
    response=owner.post('/api/shared-uploads',json={'filename':f'public-{count}.csv','csv':csv})
    self.assertEqual(response.status_code,200);saved.append(response.json())
   response=client().get('/api/shared-uploads')
   self.assertEqual(response.headers['cache-control'],'no-store')
   self.assertEqual([d['id'] for d in response.json()],[d['id'] for d in reversed(saved)])
   for item in response.json():
    self.assertEqual(set(item),{'id','label','uploadedAt','sensorCount','group','url','shareId'})
    self.assertEqual(visitor.get(item['url']).status_code,200)
   record=saved[1];url='/api/shared-uploads/'+record['shareId']
   self.assertEqual(visitor.delete(url).status_code,403)
   self.assertEqual(owner.delete(url,headers={'Authorization':'Bearer '+record['ownerToken']}).status_code,200)
   self.assertNotIn(record['id'],[d['id'] for d in visitor.get('/api/shared-uploads').json()])

 def test_cloud_catalog_paginates_and_hides_private_fields(self):
  blob=ModuleType('vercel.blob');errors=ModuleType('vercel.blob.errors')
  class NotFound(Exception):pass
  errors.BlobNotFoundError=NotFound
  first='a'*32;second='b'*32;deleted='c'*32;gets=[];cursors=[]
  rows={i:dict(id=i,label=i,created=date,sensor_count=96,owner_hash='private-hash',csv='private-data') for i,date in [(first,'2026-01-01'),(second,'2026-02-01')]}
  class Client:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def get(self,path,**kwargs):
    ident=path.split('/')[-1].removesuffix('.json');gets.append(ident)
    if ident not in rows:raise NotFound()
    return SimpleNamespace(content=json.dumps(rows[ident]).encode())
  def listing(**kwargs):
   cursors.append(kwargs['cursor'])
   names=[first,deleted] if kwargs['cursor'] is None else [second]
   return SimpleNamespace(blobs=[SimpleNamespace(pathname='shared-uploads/'+i+'.json') for i in names],has_more=kwargs['cursor'] is None,cursor='next' if kwargs['cursor'] is None else None)
  blob.BlobClient=Client;blob.list_objects=listing
  with patch.dict(sys.modules,{'vercel':ModuleType('vercel'),'vercel.blob':blob,'vercel.blob.errors':errors}),patch.dict(os.environ,{'BLOB_READ_WRITE_TOKEN':'test'},clear=True):
   app=FastAPI();app.include_router(create_upload_router('/unused'));visitor=TestClient(app)
   response=visitor.get('/api/shared-uploads');self.assertEqual(response.status_code,200)
   self.assertEqual([d['shareId'] for d in response.json()],[second,first])
   self.assertEqual(cursors,[None,'next'])
   self.assertNotIn('private',response.text)
   visitor.get('/api/shared-uploads')
   self.assertEqual(gets.count(first),1);self.assertEqual(gets.count(second),1)

 def test_persistence_sharing_and_owner_delete(self):
  with tempfile.TemporaryDirectory() as directory:
   def client():
    app=FastAPI();app.include_router(create_upload_router(Path(directory)));return TestClient(app)
   owner=client();visitor=client()
   for count in [18,96,132]:
    csv='timestamp,action_time_s,'+','.join(f'N{i:03}' for i in range(1,count+1))+'\n2026-09-13T12:00:00,0,'+','.join(['0']*count)+'\n2026-09-13T12:00:01,1,'+','.join(['1']*count)
    response=owner.post('/api/shared-uploads',json={'filename':'test.csv','csv':csv});self.assertEqual(response.status_code,200,response.text);saved=response.json();base='/api/shared-uploads/'+saved['shareId']
    self.assertEqual(saved['sensorCount'],count);self.assertNotIn(saved['ownerToken'],saved['url'])
    meta=visitor.get(base);self.assertEqual(meta.status_code,200);self.assertNotIn('ownerToken',meta.json())
    self.assertEqual(visitor.get(saved['url']).text,csv)
    self.assertEqual(visitor.delete(base).status_code,403)
    self.assertEqual(visitor.delete(base,headers={'Authorization':'Bearer wrong'}).status_code,403)
    self.assertEqual(client().get(base).status_code,200)
    self.assertEqual(owner.delete(base,headers={'Authorization':'Bearer '+saved['ownerToken']}).status_code,200)
    self.assertEqual(visitor.get(base).status_code,404);self.assertEqual(visitor.get(saved['url']).status_code,404)
   self.assertEqual(owner.post('/api/shared-uploads',json={'filename':'bad.csv','csv':'N001\n2'}).status_code,400)
if __name__=='__main__':unittest.main()
