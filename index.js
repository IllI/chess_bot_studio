import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.js';

const container = document.getElementById('root');
if (!container) {
  throw new Error("Target container 'root' not found.");
}

const root = ReactDOM.createRoot(container);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);