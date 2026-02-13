import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { 
  LayoutDashboard, 
  Building2, 
  Users, 
  BarChart3, 
  FileText, 
  Plus,
  Menu,
  X,
  Bell,
  Search
} from 'lucide-react';

interface NavigationProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
}

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'clubs', label: 'Clubs', icon: Building2 },
  { id: 'investors', label: 'Investors', icon: Users },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'reports', label: 'Reports', icon: FileText },
];

export function Navigation({ activeSection, onSectionChange }: NavigationProps) {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <nav
      className={cn(
        'fixed top-0 left-0 right-0 z-50 transition-all duration-200',
        isScrolled
          ? 'bg-[#0a0c10]/95 backdrop-blur-sm border-b border-slate-800/50'
          : 'bg-[#0a0c10] border-b border-slate-800/30'
      )}
    >
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <div 
            className="flex items-center gap-2.5 cursor-pointer group"
            onClick={() => onSectionChange('dashboard')}
          >
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-700 rounded flex items-center justify-center transition-transform duration-200 group-hover:scale-105">
              <span className="text-white font-bold text-sm font-mono">N</span>
            </div>
            <div className="hidden sm:flex items-baseline">
              <span className="text-white font-bold text-base tracking-tight">NAV</span>
              <span className="text-blue-500 font-bold text-base tracking-tight">FUND</span>
            </div>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeSection === item.id;
              
              return (
                <button
                  key={item.id}
                  onClick={() => onSectionChange(item.id)}
                  className={cn(
                    'relative px-4 py-2 flex items-center gap-2 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  )}
                >
                  {isActive && (
                    <span className="absolute bottom-0 left-4 right-4 h-0.5 bg-blue-500" />
                  )}
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-2">
            <button className="hidden sm:flex p-2 text-slate-400 hover:text-slate-200 transition-colors">
              <Search className="w-4 h-4" />
            </button>
            <button className="hidden sm:flex p-2 text-slate-400 hover:text-slate-200 transition-colors relative">
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-amber-500 rounded-full" />
            </button>
            <div className="hidden sm:block w-px h-6 bg-slate-800 mx-1" />
            <Button 
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white text-xs h-8 gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">New</span>
            </Button>
            
            {/* Mobile Menu Button */}
            <button
              className="md:hidden p-2 text-slate-400 hover:text-slate-200 transition-colors"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden py-3 border-t border-slate-800/50 animate-fade-in">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeSection === item.id;
                
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      onSectionChange(item.id);
                      setIsMobileMenuOpen(false);
                    }}
                    className={cn(
                      'px-3 py-2.5 rounded flex items-center gap-3 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-blue-600/10 text-blue-400'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
