const React = require('react');

// Minimal stubs so components depending on router can render in tests
exports.MemoryRouter = ({ children }) => React.createElement(React.Fragment, null, children);
exports.BrowserRouter = ({ children }) => React.createElement(React.Fragment, null, children);
exports.Routes = ({ children }) => React.createElement(React.Fragment, null, children);
exports.Route = () => null;
exports.Navigate = () => null;
exports.Link = ({ children }) => React.createElement('a', { href: '#' }, children);

// Hooks
exports.useLocation = () => ({ pathname: '/test', search: '', hash: '', state: null, key: 'test' });
exports.useNavigate = () => () => { };
