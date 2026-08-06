import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './auth/AuthContext';
import { ErrorBoundary } from './shell/ErrorBoundary';
import './design-system/tokens.css';
import './design-system/base.css';
import './index.css';

// The boundary sits OUTSIDE the router and the auth provider, so it still
// renders when the failure is in one of them. Without it, any render-time throw
// unmounts the whole tree and leaves an unexplained blank page.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
