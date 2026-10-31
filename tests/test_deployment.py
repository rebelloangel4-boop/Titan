import ast,json,re,unittest
from pathlib import Path
class Deployment(unittest.TestCase):
 def test_compose_security_structure(self):
  try:import yaml
  except ImportError:self.skipTest('PyYAML validation dependency unavailable')
  config=yaml.safe_load(Path('compose.yaml').read_text());services=config['services']
  for name in ('api','worker'):
   s=services[name];self.assertTrue(s['read_only']);self.assertEqual(s['cap_drop'],['ALL']);self.assertIn('no-new-privileges:true',s['security_opt']);self.assertEqual(s['restart'],'unless-stopped')
  self.assertTrue(all(p.startswith('127.0.0.1:') for p in services['api']['ports']));self.assertNotIn('ports',services['worker']);self.assertNotIn('/var/run/docker.sock',Path('compose.yaml').read_text())
 def test_docker_nonroot_and_health(self):
  source=Path('Dockerfile').read_text();self.assertIn('USER 10001:10001',source);self.assertIn('HEALTHCHECK',source);self.assertNotIn('COPY . .',source)
 def test_frontend_referenced_elements_exist(self):
  html=Path('titan/web/index.html').read_text();js=Path('titan/web/app.js').read_text();ids=re.findall(r'id="([^"]+)"',html);self.assertEqual(len(ids),len(set(ids)))
  for name in re.findall(r"\$\('([^']+)'\)",js):self.assertIn(name,ids)
  for view in re.findall(r'data-view="([^"]+)"',html):self.assertIn(view,ids)
 def test_service_worker_does_not_cache_api(self):
  js=Path('titan/web/sw.js').read_text();self.assertIn('!SHELL.includes(u.pathname)',js);self.assertNotIn("'/api/",js)
 def test_manifest_assets_exist(self):
  manifest=json.loads(Path('titan/web/manifest.json').read_text())
  for icon in manifest['icons']:self.assertTrue((Path('titan/web')/icon['src'].lstrip('/')).is_file())
