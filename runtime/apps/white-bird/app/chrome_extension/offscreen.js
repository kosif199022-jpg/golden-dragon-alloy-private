// Hidden page whose only job is to wake the service worker every 20 s, so Chrome never puts the bridge to sleep
// in the middle of a long job. It sends no data anywhere except to this extension.
setInterval(() => { chrome.runtime.sendMessage({ wbPing: Date.now() }).catch(() => {}); }, 20000);
