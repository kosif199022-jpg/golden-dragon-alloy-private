const MSG = {
  'on': ['ok', '✓ متوصل بالتطبيق'],
  'busy': ['wait', '… بينفّذ أمر من التطبيق'],
  'no-token': ['wait', 'محتاج كود الربط'],
  'bad-token': ['bad', '✕ كود الربط غلط'],
  'app-off': ['bad', '✕ التطبيق مقفول (افتح التنين الذهبي)'],
  'off': ['wait', '…'],
};
async function show() {
  const { status = 'off', token = '' } = await chrome.storage.local.get(['status', 'token']);
  const [cls, txt] = MSG[status] || MSG.off;
  const el = document.getElementById('st'); el.className = 'st ' + cls; el.textContent = txt;
  if (!document.getElementById('tok').value) document.getElementById('tok').value = token;
}
document.getElementById('save').onclick = async () => {
  await chrome.storage.local.set({ token: document.getElementById('tok').value.trim() });
  chrome.runtime.sendMessage({ kick: true }).catch(() => {});
  setTimeout(show, 1500);
};
show(); setInterval(show, 1000);
