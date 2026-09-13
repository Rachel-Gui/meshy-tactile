import tempfile,unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web.server.shared_uploads import create_upload_router

class SharedUploadTests(unittest.TestCase):
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
