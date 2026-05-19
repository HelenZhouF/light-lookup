from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

r = client.get('/api/v1/reference-data/domains/')
for item in r.json()['items']:
    if item['name'] in ['LookupTest', 'ValueListTest', 'UniqueTest']:
        client.delete('/api/v1/reference-data/domains/' + item['id'])

print("=== Test lookup domain ===")
r = client.post('/api/v1/reference-data/domains/', json={
    'name': 'LookupTest',
    'domainType': 'lookup',
    'description': 'Lookup domain'
})
print('POST Status:', r.status_code)
print('POST Content-Type:', r.headers.get('content-type'))
data = r.json()
lookup_id = data['id']
print('self link type:', data['_links']['self']['type'])
print('update link type:', data['_links']['update']['type'])
print('delete link type:', data['_links']['delete']['type'])
print('getContents link type:', data['_links']['getContents']['type'])
print('createContent link type:', data['_links']['createContent']['type'])
print('up link type:', data['_links']['up']['type'])

print("\n=== Test valueList domain ===")
r = client.post('/api/v1/reference-data/domains/', json={
    'name': 'ValueListTest',
    'domainType': 'valueList',
    'description': 'ValueList domain'
})
print('POST Status:', r.status_code)
print('POST Content-Type:', r.headers.get('content-type'))
data = r.json()
valuelist_id = data['id']
print('self link type:', data['_links']['self']['type'])
print('update link type:', data['_links']['update']['type'])
print('delete link type:', data['_links']['delete']['type'])
print('getContents link type:', data['_links']['getContents']['type'])
print('createContent link type:', data['_links']['createContent']['type'])
print('up link type:', data['_links']['up']['type'])

print("\n=== Verify GET responses ===")
r = client.get(f'/api/v1/reference-data/domains/{lookup_id}')
print('GET lookup Content-Type:', r.headers.get('content-type'))

r = client.get(f'/api/v1/reference-data/domains/{valuelist_id}')
print('GET valueList Content-Type:', r.headers.get('content-type'))

print("\n=== Verify PUT responses ===")
r = client.put(f'/api/v1/reference-data/domains/{lookup_id}', json={'description': 'Updated'})
print('PUT lookup Content-Type:', r.headers.get('content-type'))

r = client.put(f'/api/v1/reference-data/domains/{valuelist_id}', json={'description': 'Updated'})
print('PUT valueList Content-Type:', r.headers.get('content-type'))

print("\n=== Cleanup ===")
client.delete(f'/api/v1/reference-data/domains/{lookup_id}')
client.delete(f'/api/v1/reference-data/domains/{valuelist_id}')
print("Done")
