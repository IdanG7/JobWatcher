// Keep a failed module request visible instead of leaving an empty dashboard.
import('./app.js').then(app => app.ready).catch(error => {
  const root = document.getElementById('view');
  if (!root) return;
  const panel = document.createElement('section');
  panel.className = 'panel panel-body';
  const heading = document.createElement('h1');
  heading.textContent = 'Dashboard could not start';
  const message = document.createElement('p');
  message.textContent = `An application file could not load: ${error.message || error}`;
  const help = document.createElement('p');
  help.textContent = 'Open Foothold again and refresh this page. If this persists, check jobwatch.log in your data folder (%LOCALAPPDATA%\\Jobwatch) and whether your browser blocked an application file.';
  const retry = document.createElement('button');
  retry.className = 'btn primary';
  retry.textContent = 'Retry';
  retry.onclick = () => location.reload();
  panel.append(heading, message, help, retry);
  root.replaceChildren(panel);
});
