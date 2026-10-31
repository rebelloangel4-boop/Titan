const CACHE='titan-shell-v3';
const SHELL=['/','/app.js','/style.css','/manifest.json','/icon.svg','/icon-192.png','/icon-512.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',event=>{const u=new URL(event.request.url);if(event.request.method!=='GET'||u.origin!==self.location.origin||!SHELL.includes(u.pathname)||u.search)return;event.respondWith(fetch(event.request).catch(()=>caches.match(u.pathname)));});
