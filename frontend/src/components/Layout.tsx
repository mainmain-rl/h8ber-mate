import React, { ReactNode, useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { logout, userEmail, userRole, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50">
      <nav className="bg-white/80 backdrop-blur-md shadow-soft border-b border-gray-200/50 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <Link to="/dashboard" className="flex items-center gap-3 group">
                <div className="w-10 h-10 rounded-lg bg-gradient-primary p-2 shadow-md group-hover:shadow-glow transition-all duration-200">
                  <svg className="w-full h-full text-white" viewBox="0 0 200 200" fill="currentColor">
                    <ellipse cx="100" cy="120" rx="45" ry="40"/>
                    <circle cx="100" cy="80" r="30"/>
                    <circle cx="80" cy="65" r="12"/>
                    <circle cx="120" cy="65" r="12"/>
                    <ellipse cx="92" cy="78" rx="6" ry="3" fill="#FFFFFF"/>
                    <ellipse cx="108" cy="78" rx="6" ry="3" fill="#FFFFFF"/>
                    <ellipse cx="100" cy="88" rx="4" ry="3" fill="#FFFFFF"/>
                  </svg>
                </div>
                <div>
                  <h1 className="text-xl font-bold bg-gradient-primary bg-clip-text text-transparent">
                    h8ber-mate
                  </h1>
                  <p className="text-xs text-gray-500">K8S Hibernation</p>
                </div>
              </Link>

              {isAdmin && (
                <Link
                  to="/users"
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-primary-600 hover:bg-gray-50 rounded-lg transition-colors"
                >
                  Users
                </Link>
              )}
            </div>

            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex flex-col items-end">
                  <span className="text-sm font-medium text-gray-700">{userEmail}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    userRole === 'admin'
                      ? 'bg-purple-100 text-purple-800'
                      : 'bg-blue-100 text-blue-800'
                  }`}>
                    {userRole}
                  </span>
                </div>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isDropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-lg shadow-lg bg-white ring-1 ring-black ring-opacity-5 divide-y divide-gray-100">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        navigate('/api-keys');
                        setIsDropdownOpen(false);
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3"
                    >
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                      </svg>
                      API Keys
                    </button>
                    <button
                      onClick={() => {
                        navigate('/change-password');
                        setIsDropdownOpen(false);
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3"
                    >
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      Change Password
                    </button>
                  </div>
                  <div className="py-1">
                    <button
                      onClick={() => {
                        handleLogout();
                        setIsDropdownOpen(false);
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-red-700 hover:bg-red-50 flex items-center gap-3"
                    >
                      <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      Logout
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
};
