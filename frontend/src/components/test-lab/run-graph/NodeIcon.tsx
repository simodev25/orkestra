import {
  Sun, ClipboardCheck, Bot, ShieldCheck, FileSearch2, Award,
  Fingerprint, MessageSquare, GitFork, Tag,
  type LucideProps,
} from 'lucide-react';
import type React from 'react';

const MAP: Record<string, React.ComponentType<LucideProps>> = {
  Sun, ClipboardCheck, Bot, ShieldCheck, FileSearch2, Award,
  Fingerprint, MessageSquare, GitFork, Tag,
};

interface NodeIconProps extends LucideProps {
  name: string;
}

export function NodeIcon({ name, ...props }: NodeIconProps) {
  const Icon = MAP[name] ?? Bot;
  return <Icon {...props} />;
}
