from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

r = client.get('/api/v1/reference-data/domains/')
for item in r.json()['items']:
    if item['name'] == 'TestDomain':
        client.delete(f'/api/v1/reference-data/domains/{item["id"]}')
        print('Deleted existing TestDomain')

print('=== POST ===')
r = client.post('/api/v1/reference-data/domains/', json={
    'name': 'TestDomain',
    'domainType': 'lookup',
    'description': 'Test domain'
})
print('Status:', r.status_code)
print('Content-Type:', r.headers.get('content-type'))
data = r.json()
print('Response:', data)
domain_id = data['id']
print('ID:', domain_id)
print('Name:', data['name'])
print('_links keys:', list(data['_links'].keys()))
print('creationTimeStamp:', data['creationTimeStamp'])

print('\n=== GET single ===')
r = client.get(f'/api/v1/reference-data/domains/{domain_id}')
print('Status:', r.status_code)
data = r.json()
print('Name:', data['name'])
print('domainType:', data['domainType'])
print('version:', data['version'])

print('\n=== GET list ===')
r = client.get('/api/v1/reference-data/domains/?start=0&limit=10')
print('Status:', r.status_code)
data = r.json()
print('count:', data['count'])
print('items len:', len(data['items']))

print('\n=== PUT ===')
r = client.put(f'/api/v1/reference-data/domains/{domain_id}', json={
    'description': 'Updated description'
})
print('Status:', r.status_code)
data = r.json()
print('description:', data['description'])
print('version:', data['version'])

print('\n=== DELETE ===')
r = client.delete(f'/api/v1/reference-data/domains/{domain_id}')
print('Status:', r.status_code)

print('\n=== Verify deleted ===')
r = client.get(f'/api/v1/reference-data/domains/{domain_id}')
print('Status:', r.status_code)

r = client.get('/api/v1/reference-data/domains/')
print('count after delete:', r.json()['count'])

print('\n=== Test name uniqueness ===')
r = client.post('/api/v1/reference-data/domains/', json={
    'name': 'UniqueTest',
    'domainType': 'lookup',
    'description': 'First'
})
print('First POST:', r.status_code)
r = client.post('/api/v1/reference-data/domains/', json={
    'name': 'UniqueTest',
    'domainType': 'valueList',
    'description': 'Second'
})
print('Second POST (duplicate name):', r.status_code)
print('Error:', r.json())

print('\n=== Test domainType validation ===')
r = client.post('/api/v1/reference-data/domains/', json={
    'name': 'InvalidTypeTest',
    'domainType': 'invalid',
    'description': 'Test'
})
print('Invalid domainType:', r.status_code)
