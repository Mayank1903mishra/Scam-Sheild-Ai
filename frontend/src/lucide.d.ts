declare module 'lucide-react' {
  import { SVGProps, ForwardRefExoticComponent, RefAttributes } from 'react';
  
  interface LucideProps extends SVGProps<SVGSVGElement> {
    size?: number | string;
    strokeWidth?: number | string;
    absoluteStrokeWidth?: boolean;
    color?: string;
  }
  
  type LucideIcon = ForwardRefExoticComponent<LucideProps & RefAttributes<SVGSVGElement>>;
  
  export const AlertTriangle: LucideIcon;
  export const ArrowLeft: LucideIcon;
  export const ArrowUpRight: LucideIcon;
  export const Ban: LucideIcon;
  export const BarChart3: LucideIcon;
  export const Check: LucideIcon;
  export const CheckCircle2: LucideIcon;
  export const ChevronRight: LucideIcon;
  export const Clock3: LucideIcon;
  export const Copy: LucideIcon;
  export const FileImage: LucideIcon;
  export const FileSearch2: LucideIcon;
  export const Fingerprint: LucideIcon;
  export const Flag: LucideIcon;
  export const History: LucideIcon;
  export const Inbox: LucideIcon;
  export const Info: LucideIcon;
  export const LaptopMinimalCheck: LucideIcon;
  export const Link2: LucideIcon;
  export const LockKeyhole: LucideIcon;
  export const MessageCircleWarning: LucideIcon;
  export const MousePointer2: LucideIcon;
  export const Network: LucideIcon;
  export const RotateCcw: LucideIcon;
  export const ScanLine: LucideIcon;
  export const Search: LucideIcon;
  export const Shield: LucideIcon;
  export const ShieldAlert: LucideIcon;
  export const Sparkles: LucideIcon;
  export const Trash2: LucideIcon;
  export const UploadCloud: LucideIcon;
  export const WandSparkles: LucideIcon;
  export const Zap: LucideIcon;
}