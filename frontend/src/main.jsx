import { createRoot } from 'react-dom/client';
import App from './components/App.jsx';
import './styles/theme.css';
import './styles/dashboard.css';
import './styles/editor.css';
import './styles/chat.css';
import './styles/admin.css';

createRoot(document.getElementById('root')).render(<App />);
