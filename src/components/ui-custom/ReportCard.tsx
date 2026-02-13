import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { 
  BarChart3, 
  Users, 
  TrendingUp, 
  FileText, 
  Download, 
  FileDown,
  Calendar
} from 'lucide-react';

interface ReportCardProps {
  name: string;
  description: string;
  lastGenerated: string;
  icon: string;
  delay?: number;
}

const iconMap: Record<string, React.ElementType> = {
  BarChart3,
  Users,
  TrendingUp,
  FileText,
};

export function ReportCard({
  name,
  description,
  lastGenerated,
  icon,
  delay = 0,
}: ReportCardProps) {
  const Icon = iconMap[icon] || FileText;

  return (
    <div
      className={cn(
        'relative p-5 rounded-xl bg-card border border-border/50 overflow-hidden group',
        'transition-all duration-500 hover:border-primary/30 hover:shadow-card-hover',
        'hover:-translate-y-1',
        'animate-slide-up'
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Document preview area */}
      <div className="relative h-24 mb-4 rounded-lg bg-gradient-to-br from-primary/5 to-cyan-500/5 border border-border/30 flex items-center justify-center overflow-hidden">
        {/* Decorative chart lines */}
        <svg className="absolute inset-0 w-full h-full opacity-30" viewBox="0 0 200 100">
          <path
            d="M0,80 Q50,60 100,70 T200,40"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="text-primary"
          />
          <path
            d="M0,90 Q50,70 100,80 T200,60"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="text-cyan-500"
          />
        </svg>
        
        {/* Icon */}
        <div className="relative z-10 p-3 rounded-xl bg-card border border-border/50 shadow-lg">
          <Icon className="w-6 h-6 text-primary" />
        </div>

        {/* Page curl effect */}
        <div className="absolute bottom-0 right-0 w-8 h-8 bg-gradient-to-tl from-border/50 to-transparent" 
          style={{ clipPath: 'polygon(100% 0, 100% 100%, 0 100%)' }} 
        />
      </div>

      {/* Content */}
      <div className="space-y-2">
        <h4 className="font-semibold text-white group-hover:text-primary transition-colors">
          {name}
        </h4>
        <p className="text-sm text-muted-foreground line-clamp-2">
          {description}
        </p>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-border/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Calendar className="w-3.5 h-3.5" />
            <span>{lastGenerated}</span>
          </div>
          
          <div className="flex gap-2">
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-8 px-2 text-muted-foreground hover:text-white hover:bg-white/5"
            >
              <Download className="w-4 h-4" />
            </Button>
            <Button 
              size="sm" 
              className="h-8 px-3 bg-primary/10 text-primary hover:bg-primary/20 border border-primary/30"
            >
              <FileDown className="w-4 h-4 mr-1.5" />
              Generate
            </Button>
          </div>
        </div>
      </div>

      {/* Hover glow */}
      <div className="absolute -bottom-6 -right-6 w-20 h-20 bg-primary/10 rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
    </div>
  );
}
