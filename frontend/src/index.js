import React from 'react';
import ReactDOM from 'react-dom/client';
import './css/index.css';
import './components/App.js';
import App from './components/App.js';

const root = ReactDOM.createRoot(document.getElementById('root'));

export const API_URL = 'http://127.0.0.1:8000/api/v1'

root.render(
    <React.StrictMode>
        <App/>
    </React.StrictMode>
);

